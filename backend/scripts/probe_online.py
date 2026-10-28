"""Measure how many Groq tokens a demo question and a demo extraction cost.

The online demo calls Groq's free tier, limited in tokens per minute and per
day (8,000 and 200,000 for openai/gpt-oss-20b, checked on 2026-10-28). This
script runs the real agents on demo documents and records, for every model
call, the tokens Groq reports and its rate-limit headers:
- demo scenario 1 in English and in French: Writer, then Critic, on the
  chunks of page 4 of the contract (no search, so no embeddings are needed);
- two extractions, the invoice then the contract: Analyst, then Extractor
  (JSON mode).

The calls go through the application's OpenAICompatibleProvider; the script
only gives it its own HTTP client, whose response hook reads the "usage" field
and the headers. When few tokens remain for the minute, the hook waits for
Groq's reset time. A 429 stops the script. Nothing is saved.

Usage, from backend/ with the Groq settings in the environment (the key in
LLM_API_KEY, as for check_providers):
    LLM_PROVIDER=openai_compatible LLM_BASE_URL=https://api.groq.com/openai/v1 \
    LLM_MODEL=openai/gpt-oss-20b python -m scripts.probe_online
The invoice is a scan, read with Tesseract as an upload would.
"""

import re
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx2

from app.agents.analyst import DocumentAnalyst
from app.agents.critic import Critic
from app.agents.extractor import Extractor
from app.agents.fields import FIELDS
from app.agents.writer import Writer
from app.core.config import Settings
from app.ingestion.chunking import ChunkOptions, chunk_pages
from app.ingestion.file_types import detect_file_type
from app.ingestion.models import PageText, ParseOptions
from app.ingestion.parsing import parse_document
from app.llm.base import LLMError
from app.llm.openai_compatible import OpenAICompatibleProvider
from app.retrieval.retriever import RetrievedPassage
from scripts.probe_margin import WRITER_CASES, Outcome, WriterCase, judge

DEMO_DIR = Path(__file__).resolve().parents[2] / "demo_documents"
CONTRACT = "service_agreement.pdf"
INVOICE = "invoice_HDS-INV-2026-0042.pdf"
SCENARIO_PAGE = 4
# Scenario 1, in English and in French.
CASES = WRITER_CASES[:2]

# Groq free tier for openai/gpt-oss-20b (console.groq.com/docs/rate-limits).
TOKENS_PER_MINUTE = 8_000
TOKENS_PER_DAY = 200_000
# Below this many tokens left for the minute, wait before the next call.
MIN_REMAINING_TOKENS = 5_000

_DURATION_PART = re.compile(r"(\d+(?:\.\d+)?)(ms|h|m|s)")
_UNIT_SECONDS = {"h": 3600.0, "m": 60.0, "s": 1.0, "ms": 0.001}


@dataclass(frozen=True, slots=True)
class Usage:
    """Tokens of one call, as reported in the response's "usage" field."""

    prompt: int
    completion: int
    reasoning: int | None  # part of the completion; None when not reported
    total: int


@dataclass(frozen=True, slots=True)
class RateInfo:
    """What Groq's rate-limit headers say after a call (None when absent)."""

    remaining_tokens: int | None
    reset_tokens_seconds: float | None
    remaining_requests: int | None
    retry_after_seconds: float | None


@dataclass(frozen=True, slots=True)
class CallRecord:
    """One model call: the task it belongs to, the agent, and what it cost."""

    task: str
    agent: str
    status: int
    usage: Usage | None
    rate: RateInfo
    seconds: float


def parse_duration(text: str | None) -> float | None:
    """Seconds in a Groq duration such as "7.66s", "2m59.56s" or "120ms"."""
    if not text:
        return None
    value = text.strip()
    parts = _DURATION_PART.findall(value)
    if not parts or "".join(number + unit for number, unit in parts) != value:
        return None
    return sum(float(number) * _UNIT_SECONDS[unit] for number, unit in parts)


def _as_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def usage_from_json(data: object) -> Usage | None:
    """The token counts of a chat completion, or None if they are missing."""
    if not isinstance(data, dict):
        return None
    usage = data.get("usage")
    if not isinstance(usage, dict):
        return None
    prompt = _as_int(usage.get("prompt_tokens"))
    completion = _as_int(usage.get("completion_tokens"))
    if prompt is None or completion is None:
        return None
    total = _as_int(usage.get("total_tokens"))
    details = usage.get("completion_tokens_details")
    reasoning = _as_int(details.get("reasoning_tokens")) if isinstance(details, dict) else None
    return Usage(prompt, completion, reasoning, total if total is not None else prompt + completion)


def parse_retry_after(text: str | None) -> float | None:
    """Seconds in a Retry-After header: a plain number ("12") or a duration ("1m2s")."""
    if not text:
        return None
    seconds = _as_int(text)
    return float(seconds) if seconds is not None else parse_duration(text)


def rate_from_headers(headers: Mapping[str, str]) -> RateInfo:
    """Read Groq's rate-limit headers (each one may be absent)."""
    return RateInfo(
        remaining_tokens=_as_int(headers.get("x-ratelimit-remaining-tokens")),
        reset_tokens_seconds=parse_duration(headers.get("x-ratelimit-reset-tokens")),
        remaining_requests=_as_int(headers.get("x-ratelimit-remaining-requests")),
        retry_after_seconds=parse_retry_after(headers.get("retry-after")),
    )


def pause_seconds(rate: RateInfo, min_remaining: int = MIN_REMAINING_TOKENS) -> float:
    """How long to wait before the next call: 0 while enough tokens remain."""
    if rate.remaining_tokens is None or rate.remaining_tokens >= min_remaining:
        return 0.0
    # Without a reset time, wait a full minute: the window is one minute long.
    return rate.reset_tokens_seconds if rate.reset_tokens_seconds is not None else 60.0


class UsageRecorder:
    """HTTP hooks that record every model call and wait when tokens run low."""

    def __init__(
        self,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self.records: list[CallRecord] = []
        self.task = ""
        self.agent = ""
        self._sleep = sleep
        self._clock = clock
        self._started = 0.0

    @property
    def hooks(self) -> dict[str, list[Callable[[Any], None]]]:
        """The event hooks to give an httpx2 client."""
        return {"request": [self.on_request], "response": [self.on_response]}

    @property
    def rate_limited(self) -> bool:
        """True once Groq has answered 429 (Too Many Requests)."""
        return any(record.status == 429 for record in self.records)

    def on_request(self, request: httpx2.Request) -> None:
        self._started = self._clock()

    def on_response(self, response: httpx2.Response) -> None:
        response.read()
        data: Any = None
        try:
            data = response.json()
        except ValueError:
            data = None
        rate = rate_from_headers(response.headers)
        self.records.append(
            CallRecord(
                task=self.task,
                agent=self.agent,
                status=response.status_code,
                usage=usage_from_json(data) if response.is_success else None,
                rate=rate,
                seconds=self._clock() - self._started,
            )
        )
        wait = pause_seconds(rate) if response.is_success else 0.0
        if wait > 0:
            print(
                f"    (only {rate.remaining_tokens} tokens left this minute: waiting {wait:.0f}s)"
            )
            self._sleep(wait)


@dataclass(slots=True)
class TaskTotal:
    """All the calls of one task (a question or an extraction)."""

    task: str
    kind: str  # "question" or "extraction"
    tokens: int = 0
    reasoning: int = 0
    calls: int = 0
    unreported: int = 0  # calls without a usage field
    seconds: float = 0.0
    agents: list[str] = field(default_factory=list)


def task_totals(records: Sequence[CallRecord], kinds: Mapping[str, str]) -> list[TaskTotal]:
    """Sum the calls of each task, in the order the tasks were run."""
    totals: dict[str, TaskTotal] = {}
    for record in records:
        total = totals.setdefault(record.task, TaskTotal(record.task, kinds.get(record.task, "")))
        total.calls += 1
        total.seconds += record.seconds
        total.agents.append(record.agent)
        if record.usage is None:
            total.unreported += 1
            continue
        total.tokens += record.usage.total
        total.reasoning += record.usage.reasoning or 0
    return list(totals.values())


def capacity_lines(totals: Sequence[TaskTotal]) -> list[str]:
    """Average tokens per question and per extraction, and what the free tier allows."""
    lines = []
    for kind in ("question", "extraction"):
        measured = [total for total in totals if total.kind == kind and total.tokens > 0]
        if not measured:
            lines.append(f"{kind}: no measurement")
            continue
        average = sum(total.tokens for total in measured) / len(measured)
        reasoning = sum(total.reasoning for total in measured) / len(measured)
        lines.append(
            f"{kind}: {average:,.0f} tokens on average ({reasoning:,.0f} of reasoning), "
            f"{len(measured)} measured -> {TOKENS_PER_MINUTE / average:.1f} per minute, "
            f"{TOKENS_PER_DAY / average:.0f} per day"
        )
    return lines


def record_line(record: CallRecord) -> str:
    """One printed line per model call."""
    if record.usage is None:
        cost = f"HTTP {record.status}, no usage reported"
    else:
        usage = record.usage
        reasoning = "?" if usage.reasoning is None else f"{usage.reasoning}"
        cost = (
            f"in {usage.prompt:>5}  out {usage.completion:>5} "
            f"(reasoning {reasoning:>4})  total {usage.total:>5}"
        )
    left = record.rate.remaining_tokens
    left_text = "?" if left is None else f"{left}"
    return f"    {record.agent:<9} {cost}  | {record.seconds:4.1f}s | left this minute: {left_text}"


def load_pages(filename: str) -> list[PageText]:
    """The pages of a demo document, exactly as an upload reads them (OCR included)."""
    path = DEMO_DIR / filename
    detected = detect_file_type(path, filename)
    return parse_document(path, detected.file_type, ParseOptions())


def scenario_passages(pages: Sequence[PageText]) -> list[RetrievedPassage]:
    """The chunks of page 4 of the contract, as passages for the Writer."""
    chunks = [
        chunk for chunk in chunk_pages(pages, ChunkOptions()) if chunk.page_number == SCENARIO_PAGE
    ]
    return [
        RetrievedPassage(
            chunk_id=f"probe-{chunk.position}",
            document_id="probe",
            filename=CONTRACT,
            page_number=chunk.page_number,
            position=chunk.position,
            text=chunk.text,
            score=0.6,  # not a search: the score is not used by the Writer or the Critic
        )
        for chunk in chunks
    ]


def build_provider(settings: Settings, recorder: UsageRecorder) -> OpenAICompatibleProvider:
    """The application's provider, with an HTTP client that reports to the recorder."""
    client = httpx2.Client(
        base_url=settings.llm_base_url.rstrip("/"),
        timeout=settings.llm_timeout_seconds,
        event_hooks=recorder.hooks,
    )
    key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else ""
    return OpenAICompatibleProvider(
        settings.llm_base_url,
        settings.llm_model,
        api_key=key or None,
        timeout_seconds=settings.llm_timeout_seconds,
        client=client,
    )


def ask(
    recorder: UsageRecorder,
    writer: Writer,
    critic: Critic,
    case: WriterCase,
    passages: Sequence[RetrievedPassage],
) -> Outcome:
    """The Writer then the Critic, as in the ask plan, with each call labelled."""
    outcome = Outcome(passages=len(passages))
    try:
        recorder.agent = "writer"
        written = writer.write(case.question, passages)
        if written.refused or written.answer is None:
            outcome.refused = "model"
            return outcome
        recorder.agent = "critic"
        review = critic.review_answer(written.answer, passages)
    except LLMError as error:
        outcome.refused = f"error: {error}"
        return outcome
    outcome.answer = " ".join(written.answer.text.split())
    outcome.issues = [f"{issue.code} ({issue.origin})" for issue in review.issues]
    return outcome


def run_questions(
    recorder: UsageRecorder, writer: Writer, critic: Critic, contract: Sequence[PageText]
) -> None:
    passages = scenario_passages(contract)
    for case in CASES:
        if recorder.rate_limited:
            return
        recorder.task = f"question {case.language}"
        print(f"[{case.language}] {case.question}  ({len(passages)} passages)")
        start = len(recorder.records)
        outcome = ask(recorder, writer, critic, case, passages)
        for record in recorder.records[start:]:
            print(record_line(record))
        mark = "right" if judge(case, outcome) else "WRONG"
        text = f"REFUSED ({outcome.refused})" if outcome.refused else outcome.answer
        print(f"    answer ({mark}): {text}")
        print(f"    critic: {', '.join(outcome.issues) or 'no issue'}")


def run_extraction(
    recorder: UsageRecorder,
    analyst: DocumentAnalyst,
    extractor: Extractor,
    filename: str,
    pages: Sequence[PageText],
) -> None:
    recorder.task = f"extraction {filename}"
    print(f"[extract] {filename}")
    start = len(recorder.records)
    try:
        recorder.agent = "analyst"
        profile = analyst.analyze(pages)
        if profile.document_type not in FIELDS:
            print(f"    analyst: type {profile.document_type}, nothing to extract")
            return
        chosen = [page for page in pages if page.page_number in profile.pages]
        recorder.agent = "extractor"
        result = extractor.extract(profile.document_type, chosen)
    except LLMError as error:
        print(f"    error: {error}")
        return
    finally:
        for record in recorder.records[start:]:
            print(record_line(record))
    found = sum(1 for value in result.fields if value.value is not None)
    print(f"    {profile.summary()}; {found} of {len(result.fields)} fields found (JSON mode ok)")


def main() -> int:
    settings = Settings()
    if settings.llm_provider != "openai_compatible":
        print(
            "This script measures the online provider: set LLM_PROVIDER=openai_compatible "
            "and the Groq settings (see the usage at the top of the file).",
            file=sys.stderr,
        )
        return 1
    print(f"LLM: {settings.llm_model} | {settings.llm_base_url}\n")

    contract = load_pages(CONTRACT)
    invoice = load_pages(INVOICE)

    recorder = UsageRecorder()
    llm = build_provider(settings, recorder)
    writer = Writer(llm)
    critic = Critic(llm, use_model=settings.critic_use_llm)

    run_questions(recorder, writer, critic, contract)
    for filename, pages in ((INVOICE, invoice), (CONTRACT, contract)):
        if recorder.rate_limited:
            break
        print()
        run_extraction(recorder, DocumentAnalyst(llm), Extractor(llm), filename, pages)

    print()
    if recorder.rate_limited:
        last = next(record for record in reversed(recorder.records) if record.status == 429)
        wait = last.rate.retry_after_seconds
        print(
            "Stopped: Groq answered 429 (rate limit)"
            + (f", retry after {wait:.0f}s." if wait is not None else ".")
        )
    kinds = {f"question {case.language}": "question" for case in CASES}
    kinds.update({f"extraction {name}": "extraction" for name in (INVOICE, CONTRACT)})
    totals = task_totals(recorder.records, kinds)
    print("Per task:")
    for total in totals:
        missing = f", {total.unreported} without usage" if total.unreported else ""
        print(
            f"    {total.task:<42} {total.tokens:>6} tokens in {total.calls} calls "
            f"({' -> '.join(total.agents)}), {total.seconds:.1f}s{missing}"
        )
    print(
        f"Free tier: {TOKENS_PER_MINUTE:,} tokens per minute, {TOKENS_PER_DAY:,} per day; "
        f"{sum(t.tokens for t in totals):,} tokens used by this run."
    )
    for line in capacity_lines(totals):
        print(line)
    return 1 if recorder.rate_limited else 0


if __name__ == "__main__":
    sys.exit(main())