"""Critic agent: checks an answer against the passages it relies on.

The Critic reports problems; it never changes the answer (correcting it would
be replanning, planned for V2). Most checks are done by the code, which is
reliable; the model adds one simple judgement: which sentences no passage
supports. If the model's reply cannot be used, the review rests on the code
checks alone, and the answer is still returned.
"""

import json
import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any, Literal

from pydantic import BaseModel, ValidationError

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
# A citation is replaced by this marker before splitting: "p. 4." would
# otherwise end a sentence, and the page number would count as a number.
_CITATION_MARK = "\u0000"
_MIN_WORDS_FOR_CITATION = 3  # "Yes." alone does not need a citation


@dataclass(frozen=True, slots=True)
class Issue:
    """One problem found in the answer."""

    code: IssueCode
    origin: IssueOrigin  # "code": found by a rule; "model": found by the LLM
    message: str  # short technical explanation (the interface writes its own text)
    sentence: str | None = None  # the sentence concerned, without its citations


@dataclass(frozen=True, slots=True)
class Review:
    """The Critic's verdict on one answer."""

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
    "07" is "7"."""
    found = set()
    for number in _NUMBER.findall(text):
        digits = number.replace(",", "")
        integer, _, decimals = digits.partition(".")
        integer = integer.lstrip("0") or "0"
        found.add(f"{integer}.{decimals}" if decimals else integer)
    return found


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