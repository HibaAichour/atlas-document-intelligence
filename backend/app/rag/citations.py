"""Check the passage identifiers cited by the model and turn them into sources.

The Writer receives passages numbered [S1]...[Sn] and cites those identifiers.
A small model may invent an identifier, so the code (not the prompt) decides
which citations are real: valid ones become "[filename, p. X]", invented ones
are removed from the answer and reported.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from app.retrieval.retriever import RetrievedPassage

# One citation marker: [S1], [S1, S3], [s2], [S1; S2], [S1, 3], [ S4 ].
_MARKER = r"\[\s*S\d+(?:\s*[,;]\s*S?\d+)*\s*\]"
# A run of markers written side by side ("[S1][S2]" or "[S1] [S2]"),
# with the spaces or tabs before it (kept out of the answer when it is removed).
_MARKER_RUN = re.compile(rf"[ \t]*{_MARKER}(?:[ \t]*{_MARKER})*", re.IGNORECASE)
_NUMBER = re.compile(r"\d+")


def passage_label(index: int) -> str:
    """Return the identifier of the passage at this 0-based index: 0 -> "S1"."""
    return f"S{index + 1}"


def number_passages(passages: Sequence[RetrievedPassage]) -> list[tuple[str, RetrievedPassage]]:
    """Pair each passage with its identifier, in the order given to the model."""
    return [(passage_label(index), passage) for index, passage in enumerate(passages)]


def source_label(passage: RetrievedPassage) -> str:
    """Return the citation shown to the user, e.g. "[contract.pdf, p. 3]"."""
    return f"[{passage.filename}, p. {passage.page_number}]"


@dataclass(frozen=True, slots=True)
class Citation:
    """A passage that the answer really cites."""

    label: str  # identifier given to the model, e.g. "S1"
    display: str  # text shown in the answer, e.g. "[contract.pdf, p. 3]"
    passage: RetrievedPassage


@dataclass(frozen=True, slots=True)
class CitationResult:
    """The answer with its citations checked and converted."""

    text: str  # answer where "[S1]" became "[contract.pdf, p. 3]"
    citations: list[Citation]  # cited passages, unique, in order of first citation
    invalid_labels: list[str]  # identifiers cited but not given to the model


def resolve_citations(answer: str, passages: Sequence[RetrievedPassage]) -> CitationResult:
    """Replace the [Sx] identifiers of the answer by their document and page.

    Passages are numbered in the order given (the first one is S1), exactly as
    in the Writer's prompt. Text in brackets that is not a citation, such as
    "[Note]", is left unchanged.
    """
    by_label = dict(number_passages(passages))
    citations: dict[str, Citation] = {}
    invalid: dict[str, None] = {}  # a dict keeps the order and removes duplicates

    def replace(match: re.Match[str]) -> str:
        displays: dict[str, None] = {}
        for number in _NUMBER.findall(match.group(0)):
            label = f"S{int(number)}"  # "s01" and "S1" are the same identifier
            passage = by_label.get(label)
            if passage is None:
                invalid[label] = None
                continue
            citation = citations.setdefault(
                label, Citation(label=label, display=source_label(passage), passage=passage)
            )
            # Two passages from the same page are shown as one citation.
            displays[citation.display] = None
        if not displays:
            return ""  # only invented identifiers: the marker is removed
        return " " + " ".join(displays)

    text = _MARKER_RUN.sub(replace, answer).strip()
    return CitationResult(
        text=text, citations=list(citations.values()), invalid_labels=list(invalid)
    )