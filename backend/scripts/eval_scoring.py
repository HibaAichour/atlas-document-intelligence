"""Load the evaluation set (eval/questions.json) and score answers and extractions.

Pure functions only (no network): run_eval.py calls the API and uses them.
Scoring is done by code, without an LLM judge (a 3B model is not a reliable
judge of its own answers):
- a question with expected texts is right when the answer is not a refusal,
  contains one of the expected texts and none of the forbidden ones;
- a question without expected texts (expected: null) is right when refused;
- a right answer has a right citation when one of its sources is on an
  expected page; "right and cited" counts these answers and the right refusals;
- the language of every answer is guessed from common words and compared
  with the language of the question (a separate line: a French answer to an
  English question can still be right);
- the Critic is scored on the answers it reviewed: wrong answers it flagged
  (caught), right and well-cited answers it flagged (false alarms), and right
  answers with a wrong or missing citation it flagged (justified alerts);
- an extracted field is right when its value contains one of the expected texts.

Texts are compared in lower case, with one plain space between words (French
numbers use narrow no-break spaces: "17 100,00").
"""

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

EVAL_FILE = Path(__file__).resolve().parents[2] / "eval" / "questions.json"
LANGUAGES = ("en", "fr")


class EvalSetError(ValueError):
    """The evaluation file is malformed (the message says where)."""


@dataclass(frozen=True, slots=True)
class PageRef:
    file: str
    pages: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class AskCase:
    id: str
    language: str
    question: str
    expected: tuple[str, ...] | None  # None: the documents do not hold the answer
    forbidden: tuple[str, ...]
    pages: tuple[PageRef, ...]
    note: str = ""


@dataclass(frozen=True, slots=True)
class ExtractCase:
    id: str
    file: str
    fields: dict[str, tuple[str, ...]]  # field name -> accepted texts (any of)
    note: str = ""


@dataclass(frozen=True, slots=True)
class EvalSet:
    documents: tuple[str, ...]
    questions: tuple[AskCase, ...]
    extractions: tuple[ExtractCase, ...]


def _texts(value: Any, where: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise EvalSetError(f"{where}: expected a list of non-empty texts")
    return tuple(value)


def parse_eval_set(data: Mapping[str, Any]) -> EvalSet:
    """Check and convert the JSON content of the evaluation file.

    Raises:
        EvalSetError: If a field is missing, has the wrong type, or an id repeats.
    """
    try:
        documents = _texts(data["documents"], "documents")
        questions: list[AskCase] = []
        for number, item in enumerate(data["questions"], 1):
            where = f"question {number} ({item.get('id', '?')})"
            if item["language"] not in LANGUAGES:
                raise EvalSetError(f"{where}: language must be one of {LANGUAGES}")
            expected = None if item["expected"] is None else _texts(item["expected"], where)
            if expected == ():
                raise EvalSetError(f"{where}: expected is empty (use null for a refusal)")
            pages = tuple(
                PageRef(ref["file"], tuple(int(page) for page in ref["pages"]))
                for ref in item["pages"]
            )
            if expected is None and pages:
                raise EvalSetError(f"{where}: a refusal has no expected pages")
            if expected is not None and not pages:
                raise EvalSetError(f"{where}: an answer needs expected pages")
            unknown = [ref.file for ref in pages if ref.file not in documents]
            if unknown:
                raise EvalSetError(f"{where}: pages of unknown documents {unknown}")
            questions.append(
                AskCase(
                    id=item["id"],
                    language=item["language"],
                    question=item["question"],
                    expected=expected,
                    forbidden=tuple(item.get("forbidden", [])),
                    pages=pages,
                    note=item.get("note", ""),
                )
            )
        extractions = []
        for item in data["extractions"]:
            where = f"extraction {item.get('id', '?')}"
            if item["file"] not in documents:
                raise EvalSetError(f"{where}: unknown document {item['file']!r}")
            fields = {
                name: _texts(texts, f"{where}, {name}") for name, texts in item["fields"].items()
            }
            extractions.append(ExtractCase(item["id"], item["file"], fields, item.get("note", "")))
    except (KeyError, TypeError) as error:
        raise EvalSetError(f"missing or malformed entry: {error}") from error

    ids = [case.id for case in questions] + [case.id for case in extractions]
    repeated = sorted({case_id for case_id in ids if ids.count(case_id) > 1})
    if repeated:
        raise EvalSetError(f"repeated ids: {repeated}")
    return EvalSet(documents, tuple(questions), tuple(extractions))


def load_eval_set(path: Path = EVAL_FILE) -> EvalSet:
    return parse_eval_set(json.loads(path.read_text(encoding="utf-8")))


def normalize(text: str) -> str:
    """Lower case, one plain space between words (narrow and no-break spaces too)."""
    return " ".join(text.replace("\u202f", " ").replace("\xa0", " ").split()).lower()


def contains_any(text: str, candidates: Sequence[str]) -> bool:
    normalized = normalize(text)
    return any(normalize(candidate) in normalized for candidate in candidates)


# Language of an answer.

_FRENCH_WORDS = {"le", "la", "les", "est", "de", "des", "du", "une", "un", "et", "au", "sont"}
_ENGLISH_WORDS = {"the", "is", "of", "and", "a", "an", "are", "to", "was", "for", "in"}
_CITATION = re.compile(r"\[[^\]]*\]")
_WORD = re.compile(r"[a-zàâçéèêëîïôûùüÿœ']+")


def guess_language(text: str) -> str | None:
    """'fr' or 'en' from a few common words (enough for short answers), None if unclear.

    Citations are removed first: "[service_agreement.pdf, p. 4]" says nothing
    about the language of the answer.
    """
    words = _WORD.findall(_CITATION.sub(" ", text.lower()))
    french = sum(word in _FRENCH_WORDS for word in words)
    english = sum(word in _ENGLISH_WORDS for word in words)
    if french == english:
        return None
    return "fr" if french > english else "en"


# Questions.


@dataclass(frozen=True, slots=True)
class AskOutcome:
    """What the API returned for one question (the part the score needs)."""

    refused: bool
    refusal_reason: str | None = None
    answer: str = ""
    sources: tuple[tuple[str, int], ...] = ()  # (file name, page) of each citation
    issues: tuple[str, ...] = ()  # Critic issues, as "code (origin)"
    seconds: float = 0.0


def outcome_from_api(data: Mapping[str, Any], seconds: float = 0.0) -> AskOutcome:
    """Read the JSON of POST /api/ask."""
    review = data.get("review") or {"issues": []}
    return AskOutcome(
        refused=data["status"] == "refused",
        refusal_reason=data.get("refusal_reason"),
        answer=data.get("answer") or "",
        sources=tuple(
            (citation["filename"], int(citation["page_number"]))
            for citation in data.get("citations", [])
        ),
        issues=tuple(f"{issue['code']} ({issue['origin']})" for issue in review["issues"]),
        seconds=seconds,
    )


@dataclass(frozen=True, slots=True)
class AskScore:
    case: AskCase
    outcome: AskOutcome
    right: bool
    citation_right: bool | None  # None unless the answer is right and expected one
    flagged: bool  # the Critic reported at least one issue on an answer
    language: str | None = None  # guessed language of the answer (None: refused or unclear)

    @property
    def language_right(self) -> bool | None:
        """None when there is no answer or its language is unclear."""
        return None if self.language is None else self.language == self.case.language

    @property
    def right_and_cited(self) -> bool:
        """A right refusal, or a right answer citing an expected page."""
        return self.right and self.citation_right is not False


def score_ask(case: AskCase, outcome: AskOutcome) -> AskScore:
    if case.expected is None:
        right = outcome.refused
    else:
        right = (
            not outcome.refused
            and contains_any(outcome.answer, case.expected)
            and not contains_any(outcome.answer, case.forbidden)
        )
    citation_right = None
    if right and case.expected is not None:
        citation_right = any(
            file == ref.file and page in ref.pages
            for file, page in outcome.sources
            for ref in case.pages
        )
    flagged = not outcome.refused and bool(outcome.issues)
    language = None if outcome.refused else guess_language(outcome.answer)
    return AskScore(case, outcome, right, citation_right, flagged, language)


# Extractions.


@dataclass(frozen=True, slots=True)
class FieldScore:
    name: str
    value: str | None
    right: bool


@dataclass(frozen=True, slots=True)
class ExtractScore:
    case: ExtractCase
    refused: bool
    fields: tuple[FieldScore, ...]
    issues: tuple[str, ...] = ()  # Critic issues, as "code (field)"
    seconds: float = 0.0

    @property
    def right(self) -> int:
        return sum(field_score.right for field_score in self.fields)


def extracted_values(data: Mapping[str, Any]) -> dict[str, str | None] | None:
    """Field name -> value, from the assistant message of an extraction (None if refused)."""
    extraction = data.get("extraction")
    if not extraction:
        return None
    return {item["name"]: item.get("value") for item in extraction["fields"]}


def score_extraction(
    case: ExtractCase,
    values: Mapping[str, str | None] | None,
    issues: Sequence[str] = (),
    seconds: float = 0.0,
) -> ExtractScore:
    """Every expected field is scored; a refused extraction gets all fields wrong."""
    found = values or {}
    fields = tuple(
        FieldScore(
            name,
            found.get(name),
            found.get(name) is not None and contains_any(str(found.get(name)), texts),
        )
        for name, texts in case.fields.items()
    )
    return ExtractScore(case, values is None, fields, tuple(issues), seconds)


# Summary.


@dataclass(slots=True)
class Tally:
    right: int = 0
    total: int = 0

    def add(self, ok: bool) -> None:
        self.right += ok
        self.total += 1

    def __str__(self) -> str:
        if not self.total:
            return "-"
        return f"{self.right} of {self.total} ({100 * self.right / self.total:.0f}%)"


@dataclass(slots=True)
class Summary:
    answers: dict[str, Tally] = field(default_factory=dict)  # language or "all"
    refusals: dict[str, Tally] = field(default_factory=dict)
    questions: dict[str, Tally] = field(default_factory=dict)
    cited: dict[str, Tally] = field(default_factory=dict)  # right and cited
    citations: Tally = field(default_factory=Tally)  # among right answers
    languages: Tally = field(default_factory=Tally)  # answers in the question's language
    caught: Tally = field(default_factory=Tally)  # wrong answers flagged by the Critic
    false_alarms: Tally = field(default_factory=Tally)  # right, well-cited answers flagged
    justified: Tally = field(default_factory=Tally)  # right, badly cited answers flagged
    fields: Tally = field(default_factory=Tally)


def summarize(asks: Sequence[AskScore], extracts: Sequence[ExtractScore]) -> Summary:
    summary = Summary()
    for group in (*LANGUAGES, "all"):
        summary.answers[group] = Tally()
        summary.refusals[group] = Tally()
        summary.questions[group] = Tally()
        summary.cited[group] = Tally()
    for score in asks:
        kind = summary.refusals if score.case.expected is None else summary.answers
        for group in (score.case.language, "all"):
            kind[group].add(score.right)
            summary.questions[group].add(score.right)
            summary.cited[group].add(score.right_and_cited)
        if score.citation_right is not None:
            summary.citations.add(score.citation_right)
        if score.language_right is not None:
            summary.languages.add(score.language_right)
        if not score.outcome.refused:  # the Critic only reviews answers
            if not score.right:
                summary.caught.add(score.flagged)
            elif score.citation_right:
                summary.false_alarms.add(score.flagged)
            else:
                summary.justified.add(score.flagged)
    for extract in extracts:
        for field_score in extract.fields:
            summary.fields.add(field_score.right)
    return summary


def summary_lines(summary: Summary) -> list[str]:
    lines = [f"{'':<32}{'English':>16}{'French':>16}{'All':>16}"]
    for label, tallies in (
        ("Questions right", summary.questions),
        ("  answers right", summary.answers),
        ("  refusals right", summary.refusals),
        ("Right, with a right citation", summary.cited),
    ):
        cells = "".join(f"{tallies[group]!s:>16}" for group in (*LANGUAGES, "all"))
        lines.append(f"{label:<32}{cells}")
    lines += [
        f"{'Right answers with a right page':<32}{summary.citations!s:>48}",
        f"{'Answers in the right language':<32}{summary.languages!s:>48}",
        f"{'Critic, on wrong answers':<32}{'flagged ' + str(summary.caught):>48}",
        f"{'Critic, right and well cited':<32}{'flagged ' + str(summary.false_alarms):>48}",
        f"{'Critic, right but badly cited':<32}{'flagged ' + str(summary.justified):>48}",
        f"{'Extracted fields right':<32}{summary.fields!s:>48}",
    ]
    return lines


def results_json(
    asks: Sequence[AskScore], extracts: Sequence[ExtractScore], context: Mapping[str, Any]
) -> dict[str, Any]:
    """The detail saved next to the evaluation set, so the score can be checked."""
    summary = summarize(asks, extracts)
    return {
        "context": dict(context),
        "summary": {
            "questions": {group: str(tally) for group, tally in summary.questions.items()},
            "answers": {group: str(tally) for group, tally in summary.answers.items()},
            "refusals": {group: str(tally) for group, tally in summary.refusals.items()},
            "right_and_cited": {group: str(tally) for group, tally in summary.cited.items()},
            "right_answers_with_right_page": str(summary.citations),
            "answers_in_right_language": str(summary.languages),
            "critic_wrong_answers_flagged": str(summary.caught),
            "critic_false_alarms_on_right_well_cited_answers": str(summary.false_alarms),
            "critic_justified_alerts_on_right_badly_cited_answers": str(summary.justified),
            "extracted_fields_right": str(summary.fields),
        },
        "questions": [
            {
                "id": score.case.id,
                "language": score.case.language,
                "question": score.case.question,
                "right": score.right,
                "citation_right": score.citation_right,
                "answer_language": score.language,
                "refused": score.outcome.refused,
                "refusal_reason": score.outcome.refusal_reason,
                "answer": score.outcome.answer,
                "sources": [f"{file} p. {page}" for file, page in score.outcome.sources],
                "critic": list(score.outcome.issues),
                "seconds": round(score.outcome.seconds, 1),
            }
            for score in asks
        ],
        "extractions": [
            {
                "id": extract.case.id,
                "file": extract.case.file,
                "refused": extract.refused,
                "fields_right": f"{extract.right} of {len(extract.fields)}",
                "fields": [
                    {"name": f.name, "value": f.value, "right": f.right} for f in extract.fields
                ],
                "critic": list(extract.issues),
                "seconds": round(extract.seconds, 1),
            }
            for extract in extracts
        ],
    }