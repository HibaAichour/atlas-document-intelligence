"""Document Analyst agent: what kind of document this is, and which pages matter.

The type is chosen from a closed list (invoice, contract, other). The model
reads the start of the document and names the type; if its reply cannot be
used, or if it says "other" while the keywords clearly recognise the document,
the keywords decide. The pages given to the Extractor are chosen by the code,
from the keywords of the fields to extract, within a character budget that
fits the model's context.
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ValidationError

from app.ingestion.models import PageText
from app.llm.base import ChatMessage, LLMError, LLMProvider

DocumentType = Literal["invoice", "contract", "other"]
TypeSource = Literal["model", "keywords"]

# Characters of text read by the model to recognise the type.
CLASSIFY_CHARS = 1500
# Characters of page text given to the Extractor: about 2,000 tokens, which
# leaves room for the prompt and the reply in a 4,096-token context.
MAX_EXTRACTION_CHARS = 8000
# The keywords must be this clear to overrule a model that answered "other".
MIN_KEYWORD_SCORE = 2

# Words that recognise each type of document.
TYPE_KEYWORDS: dict[DocumentType, tuple[str, ...]] = {
    "invoice": ("invoice", "due date", "total due", "amount due", "bill to", "subtotal"),
    "contract": ("agreement", "parties", "termination", "governing law", "effective date"),
}
# Words near the fields the Extractor looks for, used to choose the pages.
FIELD_KEYWORDS: dict[DocumentType, tuple[str, ...]] = {
    "invoice": ("invoice", "date", "due", "total", "amount", "bill to"),
    "contract": (
        "agreement no",
        "between",
        "effective date",
        "initial term",
        "renewal",
        "termination for convenience",
        "governing law",
    ),
}

SYSTEM_PROMPT = """You classify business documents.

Read the start of the document and reply with JSON only, in this exact form:
{"type": "invoice"} or {"type": "contract"} or {"type": "other"}"""


@dataclass(frozen=True, slots=True)
class DocumentProfile:
    """What the Analyst found: the type, and the pages to give the Extractor."""

    document_type: DocumentType
    pages: list[int]  # page numbers, in page order (empty for "other")
    type_source: TypeSource  # who decided the type

    def summary(self) -> str:
        """A short note for the execution trace."""
        pages = ", ".join(str(page) for page in self.pages) or "none"
        return f"type {self.document_type} (by {self.type_source}), pages {pages}"


class _ModelType(BaseModel):
    """The only JSON shape accepted from the model."""

    type: DocumentType


def keyword_score(text: str, keywords: Sequence[str]) -> int:
    """How many of the keywords appear in the text (case and line breaks ignored)."""
    flat = " ".join(text.lower().split())
    return sum(1 for keyword in keywords if keyword in flat)


def classify_by_keywords(text: str) -> tuple[DocumentType, int]:
    """The type with the most keywords, and its score; "other" if none or a tie."""
    scores = {name: keyword_score(text, words) for name, words in TYPE_KEYWORDS.items()}
    best = max(scores.values())
    leaders = [name for name, score in scores.items() if score == best]
    if best == 0 or len(leaders) > 1:
        return "other", 0
    return leaders[0], best


def select_pages(pages: Sequence[PageText], document_type: DocumentType) -> list[int]:
    """The pages most likely to hold the fields, within the character budget.

    Pages are ranked by how many field keywords they contain; the best page is
    always kept, then the next ones while the budget allows. A document whose
    pages contain no keyword gives its first page.
    """
    if document_type == "other" or not pages:
        return []
    keywords = FIELD_KEYWORDS[document_type]
    ranked = sorted(pages, key=lambda page: (-keyword_score(page.text, keywords), page.page_number))
    useful = [page for page in ranked if keyword_score(page.text, keywords) > 0] or ranked[:1]
    chosen: list[int] = []
    used = 0
    for page in useful:
        if chosen and used + len(page.text) > MAX_EXTRACTION_CHARS:
            continue  # too long for what is left; a shorter page may still fit
        chosen.append(page.page_number)
        used += len(page.text)
    return sorted(chosen)


class DocumentAnalyst:
    """Recognises the type of a document and chooses the pages to extract from."""

    name = "analyst"

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    def build_messages(self, pages: Sequence[PageText]) -> list[ChatMessage]:
        """Return the prompt: the rules, then the start of the document."""
        start = "\n\n".join(page.text.strip() for page in pages)[:CLASSIFY_CHARS]
        return [
            ChatMessage(role="system", content=SYSTEM_PROMPT),
            ChatMessage(role="user", content=f"Document start:\n\n{start}"),
        ]

    def analyze(self, pages: Sequence[PageText]) -> DocumentProfile:
        """Profile the document. Never raises for a model problem: the keywords
        then decide the type.

        Raises:
            ValueError: If the document has no page.
        """
        if not pages:
            raise ValueError("The Analyst needs at least one page")

        keyword_type, keyword_strength = classify_by_keywords(
            " ".join(page.text for page in pages)[: CLASSIFY_CHARS * 2]
        )
        model_type = self._ask_model(pages)

        document_type: DocumentType
        source: TypeSource
        if model_type is None:
            document_type, source = keyword_type, "keywords"
        elif model_type == "other" and keyword_strength >= MIN_KEYWORD_SCORE:
            # The model may not turn away a document the keywords clearly recognise.
            document_type, source = keyword_type, "keywords"
        else:
            document_type, source = model_type, "model"
        return DocumentProfile(document_type, select_pages(pages, document_type), source)

    def _ask_model(self, pages: Sequence[PageText]) -> DocumentType | None:
        """The type named by the model, or None if its reply cannot be used."""
        try:
            reply = self._llm.generate(self.build_messages(pages), temperature=0.0, json_mode=True)
            return _ModelType.model_validate(json.loads(reply)).type
        except (LLMError, json.JSONDecodeError, ValidationError):
            return None