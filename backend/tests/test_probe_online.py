"""The Groq usage measurement script: usage and headers, pauses, totals, recording."""

import httpx2
import pytest

from app.agents.critic import Critic
from app.agents.writer import Writer
from app.llm.base import ChatMessage, LLMError
from app.llm.openai_compatible import OpenAICompatibleProvider
from app.retrieval.retriever import RetrievedPassage
from scripts.probe_margin import WRITER_CASES
from scripts.probe_online import (
    CallRecord,
    RateInfo,
    Usage,
    UsageRecorder,
    ask,
    capacity_lines,
    parse_duration,
    parse_retry_after,
    pause_seconds,
    rate_from_headers,
    record_line,
    task_totals,
    usage_from_json,
)
from tests.conftest import FakeLLMProvider

BASE_URL = "http://llm.test/v1"
NO_RATE = RateInfo(None, None, None, None)


def completion(content: str, usage: dict | None = None) -> dict:
    body: dict = {"choices": [{"message": {"content": content}}]}
    if usage is not None:
        body["usage"] = usage
    return body


@pytest.mark.parametrize(
    ("text", "seconds"),
    [
        ("7.66s", 7.66),
        ("2m59.56s", 179.56),
        ("120ms", 0.12),
        ("1h2m", 3720.0),
        ("", None),
        (None, None),
        ("soon", None),
        ("7.66s later", None),
    ],
)
def test_parse_duration(text: str | None, seconds: float | None) -> None:
    result = parse_duration(text)
    if seconds is None:
        assert result is None
    else:
        assert result == pytest.approx(seconds)


def test_parse_retry_after_accepts_seconds_and_durations() -> None:
    assert parse_retry_after("12") == 12.0
    assert parse_retry_after("1m2s") == pytest.approx(62.0)
    assert parse_retry_after(None) is None


def test_usage_with_reasoning_tokens() -> None:
    data = completion(
        "ok",
        {
            "prompt_tokens": 900,
            "completion_tokens": 300,
            "total_tokens": 1200,
            "completion_tokens_details": {"reasoning_tokens": 220},
        },
    )
    assert usage_from_json(data) == Usage(900, 300, 220, 1200)


def test_usage_without_details_or_total() -> None:
    data = completion("ok", {"prompt_tokens": 900, "completion_tokens": 300})
    assert usage_from_json(data) == Usage(900, 300, None, 1200)


@pytest.mark.parametrize(
    "data",
    [
        None,
        [],
        completion("ok"),
        completion("ok", {"prompt_tokens": 900}),
        completion("ok", {"prompt_tokens": "many", "completion_tokens": 3}),
    ],
)
def test_missing_usage_is_none(data: object) -> None:
    assert usage_from_json(data) is None


def test_rate_from_groq_headers() -> None:
    rate = rate_from_headers(
        {
            "x-ratelimit-remaining-tokens": "4200",
            "x-ratelimit-reset-tokens": "28.5s",
            "x-ratelimit-remaining-requests": "998",
            "retry-after": "3",
        }
    )
    assert rate == RateInfo(4200, 28.5, 998, 3.0)


def test_rate_without_headers() -> None:
    assert rate_from_headers({}) == NO_RATE


def test_pause_only_when_tokens_run_low() -> None:
    assert pause_seconds(RateInfo(6000, 20.0, None, None)) == 0.0
    assert pause_seconds(RateInfo(4999, 20.0, None, None)) == 20.0
    # No reset time: a full minute, the length of the window.
    assert pause_seconds(RateInfo(100, None, None, None)) == 60.0
    # Unknown remaining tokens: no pause.
    assert pause_seconds(NO_RATE) == 0.0


def record(task: str, agent: str, total: int | None, reasoning: int | None = None) -> CallRecord:
    usage = None if total is None else Usage(total - 100, 100, reasoning, total)
    return CallRecord(task, agent, 200 if usage else 500, usage, NO_RATE, 1.5)


def test_task_totals_sum_each_task_in_order() -> None:
    records = [
        record("question en", "writer", 1500, 400),
        record("question en", "critic", 1000, 200),
        record("extraction invoice", "analyst", 800),
        record("extraction invoice", "extractor", None),
    ]
    totals = task_totals(records, {"question en": "question", "extraction invoice": "extraction"})

    assert [total.task for total in totals] == ["question en", "extraction invoice"]
    question, extraction = totals
    assert (question.kind, question.tokens, question.reasoning, question.calls) == (
        "question",
        2500,
        600,
        2,
    )
    assert question.agents == ["writer", "critic"]
    assert question.seconds == pytest.approx(3.0)
    assert (extraction.tokens, extraction.unreported) == (800, 1)


def test_capacity_lines_use_the_free_tier_limits() -> None:
    totals = task_totals(
        [record("q1", "writer", 2000), record("q2", "writer", 2000)],
        {"q1": "question", "q2": "question"},
    )
    lines = capacity_lines(totals)

    assert lines[0].startswith("question: 2,000 tokens on average")
    assert "4.0 per minute" in lines[0]
    assert "100 per day" in lines[0]
    assert lines[1] == "extraction: no measurement"


def test_record_line_shows_unknown_values() -> None:
    line = record_line(record("q", "writer", 1200))
    assert "reasoning    ?" in line
    assert "left this minute: ?" in line
    assert "no usage reported" in record_line(record("q", "writer", None))


def recorded_provider(
    recorder: UsageRecorder, responses: list[httpx2.Response]
) -> OpenAICompatibleProvider:
    """The real provider, answered by a mock, with the recorder's response hook."""
    replies = iter(responses)

    def handler(request: httpx2.Request) -> httpx2.Response:
        return next(replies)

    client = httpx2.Client(
        base_url=BASE_URL,
        transport=httpx2.MockTransport(handler),
        event_hooks=recorder.hooks,
    )
    return OpenAICompatibleProvider(BASE_URL, "model", api_key="key", client=client)


def test_recorder_reads_usage_and_waits_when_tokens_run_low() -> None:
    waits: list[float] = []
    ticks = iter([10.0, 12.5, 20.0, 21.0])
    recorder = UsageRecorder(sleep=waits.append, clock=lambda: next(ticks))
    recorder.task, recorder.agent = "question en", "writer"
    usage = {"prompt_tokens": 900, "completion_tokens": 300, "total_tokens": 1200}
    provider = recorded_provider(
        recorder,
        [
            httpx2.Response(
                200,
                json=completion("first", usage),
                headers={
                    "x-ratelimit-remaining-tokens": "6800",
                    "x-ratelimit-reset-tokens": "9s",
                },
            ),
            httpx2.Response(
                200,
                json=completion("second", usage),
                headers={
                    "x-ratelimit-remaining-tokens": "1200",
                    "x-ratelimit-reset-tokens": "41.2s",
                },
            ),
        ],
    )
    messages = [ChatMessage(role="user", content="Hello")]

    assert provider.generate(messages) == "first"
    assert provider.generate(messages) == "second"
    assert [r.usage for r in recorder.records] == [Usage(900, 300, None, 1200)] * 2
    assert [r.rate.remaining_tokens for r in recorder.records] == [6800, 1200]
    assert [r.seconds for r in recorder.records] == [2.5, 1.0]
    assert waits == [pytest.approx(41.2)]
    assert not recorder.rate_limited


def test_recorder_notes_a_429_without_waiting() -> None:
    waits: list[float] = []
    recorder = UsageRecorder(sleep=waits.append)
    provider = recorded_provider(
        recorder,
        [httpx2.Response(429, json={"error": "rate limit"}, headers={"retry-after": "17"})],
    )

    with pytest.raises(LLMError, match="429"):
        provider.generate([ChatMessage(role="user", content="Hello")])
    assert recorder.rate_limited
    assert recorder.records[0].usage is None
    assert recorder.records[0].rate.retry_after_seconds == 17.0
    assert waits == []


def passages() -> list[RetrievedPassage]:
    return [
        RetrievedPassage(
            chunk_id="c1",
            document_id="d1",
            filename="service_agreement.pdf",
            page_number=4,
            position=0,
            text="Either Party may terminate for convenience with 60 days' written notice.",
            score=0.6,
        )
    ]


class LabellingLLM(FakeLLMProvider):
    """A fake model that notes which agent the recorder names at each call."""

    def __init__(self, recorder: UsageRecorder, replies: list[str]) -> None:
        super().__init__()
        self.replies = replies
        self.labels: list[str] = []
        self._recorder = recorder

    def generate(
        self, messages: list[ChatMessage], *, temperature: float = 0.0, json_mode: bool = False
    ) -> str:
        self.labels.append(self._recorder.agent)
        return super().generate(messages, temperature=temperature, json_mode=json_mode)


def test_ask_labels_the_writer_then_the_critic() -> None:
    recorder = UsageRecorder()
    llm = LabellingLLM(recorder, ["The notice period is 60 days [S1].", '{"unsupported": []}'])
    outcome = ask(recorder, Writer(llm), Critic(llm), WRITER_CASES[0], passages())

    assert llm.labels == ["writer", "critic"]
    assert outcome.refused is None
    assert "60 days" in outcome.answer
    assert outcome.issues == []


def test_ask_skips_the_critic_when_the_writer_refuses() -> None:
    recorder = UsageRecorder()
    llm = LabellingLLM(recorder, ["NOT_FOUND"])
    outcome = ask(recorder, Writer(llm), Critic(llm), WRITER_CASES[0], passages())

    assert outcome.refused == "model"
    assert llm.labels == ["writer"]