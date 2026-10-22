"""Critic agent: checks an answer, or an extraction, against its sources.

The Critic reports problems; it never changes the result (correcting it would
be replanning, planned for V2). Most checks are done by the code, which is
reliable. For an answer, the model adds one simple judgement: which sentences
no passage supports. If the model's reply cannot be used, the review rests on
the code checks alone, and the answer is still returned. An extraction is
checked by the code only: each value must appear on the page given for it.
"""

import json
import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ValidationError

from app.agents.extractor import ExtractionResult
from app.agents.fields import FIELDS
from app.ingestion.models import PageText
from app.llm.base import ChatMessage, LLMError, LLMProvider
from app.rag.citations import CitationResult, number_passages
from app.retrieval.retriever import RetrievedPassage

Verdict = Literal["ok", "issues"]
IssueOrigin = Literal["code", "model"]
IssueCode = Literal[
    "invented_citations",  # the Writer cited an identifier it was not given
    "no_citation",  # the answer cites no source at all
    "uncited_sentence",  # one sentence carries no citation
    "unsupported_number",  # a number of the answer appears in no cited passage
    "unsupported_claim",  # the model found no passage supporting a sentence
    "missing_required_field",  # an extraction lacks a required field
    "value_not_found",  # an extracted value appears on none of the pages given
    "wrong_page",  # the value is not on the page the model gave for it
    "unreadable_date",  # a date field holds no readable date
    "unreadable_amount",  # an amount field holds no number
]

SYSTEM_PROMPT = """You check an answer against numbered passages.

For each numbered sentence of the answer, decide whether at least one passage
states it. Reply with JSON only, in this exact form:
{"unsupported": [numbers of the sentences that no passage supports]}
Reply {"unsupported": []} when every sentence is supported."""

# A sentence ends with . ! or ? followed by spaces.
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
# A number, with optional thousands or decimal separators: 30, 1,200, 4.5
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
# Date formats accepted for a date field ("1 April 2026", "April 1, 2026", ...).
_DATE_FORMATS = ("%d %B %Y", "%d %b %Y", "%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%d/%m/%Y")
# A citation is replaced by this marker before splitting: "p. 4." would
# otherwise end a sentence, and the page number would count as a number.
_CITATION_MARK = "\u0000"
_MIN_WORDS_FOR_CITATION = 3  # "Yes." alone does not need a citation


@dataclass(frozen=True, slots=True)
class Issue:
    """One problem found in an answer or in an extraction."""

    code: IssueCode
    origin: IssueOrigin  # "code": found by a rule; "model": found by the LLM
    message: str  # short technical explanation (the interface writes its own text)
    sentence: str | None = None  # the sentence concerned, without its citations
    field: str | None = None  # for an extraction: the field concerned


@dataclass(frozen=True, slots=True)
class Review:
    """The Critic's verdict on one answer or one extraction."""

    verdict: Verdict
    issues: list[Issue]
    model_checked: bool  # False when the model check was off or unusable

    def to_dict(self) -> dict[str, Any]:
        """The JSON shape saved in messages.review."""
        return asdict(self)

    def summary(self) -> str:
        """A short note for the execution trace."""
        by_code = sum(1 for issue in self.issues if issue.origin == "code")
        by_model = len(self.issues) - by_code
        found = "no issue" if not self.issues else f"{len(self.issues)} issues"
        model = "model checked" if self.model_checked else "model check unavailable"
        return f"{found} ({by_code} by code, {by_model} by model), {model}"


@dataclass(frozen=True, slots=True)
class Sentence:
    text: str  # without its citations
    cited: bool


def split_sentences(answer: CitationResult) -> list[Sentence]:
    """Split the answer into sentences and note which ones carry a citation."""
    text = answer.text
    # Longest first, so a citation is never replaced inside a longer one.
    displays = sorted({citation.display for citation in answer.citations}, key=len, reverse=True)
    for display in displays:
        text = text.replace(display, _CITATION_MARK)
    sentences = []
    for part in _SENTENCE_END.split(text.strip()):
        cited = _CITATION_MARK in part
        clean = re.sub(r"\s+([.!?,;:])", r"\1", part.replace(_CITATION_MARK, ""))
        clean = " ".join(clean.split())
        if clean:
            sentences.append(Sentence(text=clean, cited=cited))
    return sentences


def numbers_in(text: str) -> set[str]:
    """The numbers written in a text, compared the same way: "1,200" is "1200",
    "07" is "7", and "15,950.00" is "15950" (like 15950.0 sent by the model)."""
    found = set()
    for number in _NUMBER.findall(text):
        digits = number.replace(",", "")
        integer, _, decimals = digits.partition(".")
        integer = integer.lstrip("0") or "0"
        decimals = decimals.rstrip("0")
        found.add(f"{integer}.{decimals}" if decimals else integer)
    return found


def comparable(text: str) -> str:
    """Text compared without case, line breaks or curly quotes."""
    flat = " ".join(text.split()).lower()
    return flat.replace("\u2019", "'").replace("\u2018", "'")


def is_readable_date(value: str) -> bool:
    """True if the value is a date in one of the usual formats."""
    for date_format in _DATE_FORMATS:
        try:
            datetime.strptime(value.strip(), date_format)
        except ValueError:
            continue
        return True
    return False


def appears_in(value: str, text: str, *, amount: bool) -> bool:
    """True if the value is written in the text: the same words, or for an
    amount, the same numbers ("USD 15,950.00" is found in "Total 15950.00")."""
    if amount:
        numbers = numbers_in(value)
        return bool(numbers) and numbers <= numbers_in(text)
    return comparable(value) in comparable(text)


class _ModelVerdict(BaseModel):
    """The only JSON shape accepted from the model."""

    unsupported: list[int]


class Critic:
    """Checks a cited answer: rules in the code, then one question to the model."""

    name = "critic"

    def __init__(self, llm: LLMProvider, *, use_model: bool = True) -> None:
        self._llm = llm
        self._use_model = use_model

    def review_answer(self, answer: CitationResult, passages: Sequence[RetrievedPassage]) -> Review:
        """Review an answer written from these passages. Never raises for a model
        problem: the review then rests on the code checks."""
        sentences = split_sentences(answer)
        issues = self._code_checks(answer, sentences, passages)
        model_checked = False
        if self._use_model and sentences:
            model_issues = self._model_check(sentences, passages)
            if model_issues is not None:
                issues.extend(model_issues)
                model_checked = True
        return Review(
            verdict="issues" if issues else "ok", issues=issues, model_checked=model_checked
        )

    def build_messages(
        self, sentences: Sequence[Sentence], passages: Sequence[RetrievedPassage]
    ) -> list[ChatMessage]:
        """Return the prompt: the rules, the numbered passages, the numbered sentences."""
        blocks = [
            f"[{label}]\n{passage.text.strip()}" for label, passage in number_passages(passages)
        ]
        numbered = [f"{index}. {sentence.text}" for index, sentence in enumerate(sentences, 1)]
        user_content = (
            "Passages:\n\n" + "\n\n".join(blocks) + "\n\nAnswer sentences:\n" + "\n".join(numbered)
        )
        return [
            ChatMessage(role="system", content=SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_content),
        ]

    def _code_checks(
        self,
        answer: CitationResult,
        sentences: Sequence[Sentence],
        passages: Sequence[RetrievedPassage],
    ) -> list[Issue]:
        issues: list[Issue] = []
        if answer.invalid_labels:
            issues.append(
                Issue(
                    "invented_citations",
                    "code",
                    f"invented identifiers removed: {', '.join(answer.invalid_labels)}",
                )
            )
        if not answer.citations:
            issues.append(Issue("no_citation", "code", "the answer cites no passage"))
        else:
            for sentence in sentences:
                if not sentence.cited and len(sentence.text.split()) >= _MIN_WORDS_FOR_CITATION:
                    issues.append(Issue("uncited_sentence", "code", "no citation", sentence.text))

        # Numbers are checked against the cited passages (all passages if none is cited).
        sources = [c.passage for c in answer.citations] or list(passages)
        known = numbers_in(" ".join(passage.text for passage in sources))
        for sentence in sentences:
            missing = sorted(numbers_in(sentence.text) - known)
            if missing:
                issues.append(
                    Issue(
                        "unsupported_number",
                        "code",
                        f"not found in the cited passages: {', '.join(missing)}",
                        sentence.text,
                    )
                )
        return issues

    def _model_check(
        self, sentences: Sequence[Sentence], passages: Sequence[RetrievedPassage]
    ) -> list[Issue] | None:
        """Ask the model which sentences no passage supports; None if unusable."""
        try:
            reply = self._llm.generate(
                self.build_messages(sentences, passages), temperature=0.0, json_mode=True
            )
            verdict = _ModelVerdict.model_validate(json.loads(reply))
        except (LLMError, json.JSONDecodeError, ValidationError):
            return None
        # Numbers outside the list are ignored; each sentence is reported once.
        flagged = sorted(
            {number for number in verdict.unsupported if 1 <= number <= len(sentences)}
        )
        return [
            Issue(
                "unsupported_claim",
                "model",
                "the model found no passage supporting this sentence",
                sentences[number - 1].text,
            )
            for number in flagged
        ]


def review_extraction(result: ExtractionResult, pages: Sequence[PageText]) -> Review:
    """Check an extraction against the pages given to the Extractor (code only).

    Each value must appear on the page given for it; required fields must be
    present; dates and amounts must be readable. A value found on another of
    the pages is reported as a wrong page, not as an invented value.
    """
    specs = {spec.name: spec for spec in FIELDS[result.document_type]}
    texts = {page.page_number: page.text for page in pages}
    issues: list[Issue] = []
    for field in result.fields:
        spec = specs[field.name]
        if field.value is None:
            if spec.required:
                issues.append(
                    Issue(
                        "missing_required_field",
                        "code",
                        "required field not found",
                        None,
                        field.name,
                    )
                )
            continue
        if spec.kind == "date" and not is_readable_date(field.value):
            issues.append(
                Issue("unreadable_date", "code", f"not a date: {field.value}", None, field.name)
            )
        if spec.kind == "amount" and not numbers_in(field.value):
            issues.append(
                Issue("unreadable_amount", "code", f"no number in: {field.value}", None, field.name)
            )
            continue  # without a number, there is nothing to look for in the pages
        amount = spec.kind == "amount"
        page_text = None if field.page is None else texts.get(field.page)
        if page_text is not None and appears_in(field.value, page_text, amount=amount):
            continue
        elsewhere = [n for n, text in texts.items() if appears_in(field.value, text, amount=amount)]
        if elsewhere:
            issues.append(
                Issue(
                    "wrong_page",
                    "code",
                    f"found on page {elsewhere[0]}, "
                    + ("no page given" if field.page is None else f"not on page {field.page}"),
                    None,
                    field.name,
                )
            )
        else:
            issues.append(
                Issue(
                    "value_not_found",
                    "code",
                    f"not found in the document: {field.value}",
                    None,
                    field.name,
                )
            )
    return Review(verdict="issues" if issues else "ok", issues=issues, model_checked=False)