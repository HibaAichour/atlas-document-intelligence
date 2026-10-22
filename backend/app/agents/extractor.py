"""Extractor agent: fills the fixed list of fields of a document, with their page.

The model receives the pages chosen by the Analyst, labelled with their page
number, and the list of fields. It must copy each value exactly as written,
with its page, or give null. The code accepts only the expected JSON shape;
the Critic then checks that each value really appears on its page.
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

from app.agents.fields import FIELDS, ExtractableType, FieldSpec
from app.ingestion.models import PageText
from app.llm.base import ChatMessage, LLMError, LLMProvider

SYSTEM_PROMPT = """You extract fields from a business document.

Rules:
1. Copy each value exactly as it is written in the document. Do not change its format.
2. Give the number of the page where you found it.
3. Use null for a field that is not in the document. Never guess.
Reply with JSON only, in this exact form:
{"fields": {"<field name>": {"value": "<text copied from the document>", "page": <page number>}}}"""


@dataclass(frozen=True, slots=True)
class ExtractedField:
    """One field and what the model found for it."""

    name: str
    label: str
    value: str | None  # None when the model found nothing
    page: int | None


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    """The fields of one document, in the order of its schema."""

    document_type: ExtractableType
    pages: list[int]  # the pages given to the model
    fields: list[ExtractedField]

    def summary(self) -> str:
        """A short note for the execution trace."""
        found = sum(1 for field in self.fields if field.value is not None)
        return f"{found} of {len(self.fields)} fields found"


class _ModelValue(BaseModel):
    # A number such as 15950.0 is accepted and turned into text below.
    value: str | int | float | None = None
    page: int | None = None


class _ModelReply(BaseModel):
    """The only JSON shape accepted from the model."""

    fields: dict[str, _ModelValue | None]


class Extractor:
    """Asks the model for the fields of a document and keeps only the expected ones."""

    name = "extractor"

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    def build_messages(
        self, specs: Sequence[FieldSpec], pages: Sequence[PageText]
    ) -> list[ChatMessage]:
        """Return the prompt: the rules, the fields, then the pages with their number."""
        wanted = "\n".join(f"- {spec.name}: {spec.description}" for spec in specs)
        document = "\n\n".join(f"[Page {page.page_number}]\n{page.text.strip()}" for page in pages)
        return [
            ChatMessage(role="system", content=SYSTEM_PROMPT),
            ChatMessage(
                role="user", content=f"Fields to extract:\n{wanted}\n\nDocument:\n\n{document}"
            ),
        ]

    def extract(
        self, document_type: ExtractableType, pages: Sequence[PageText]
    ) -> ExtractionResult:
        """Extract the fields of this type of document from these pages.

        Raises:
            ValueError: If no page is given.
            LLMError: If the model fails or its reply is not the expected JSON.
        """
        if not pages:
            raise ValueError("The Extractor needs at least one page")
        specs = FIELDS[document_type]
        reply = self._llm.generate(
            self.build_messages(specs, pages), temperature=0.0, json_mode=True
        )
        try:
            parsed = _ModelReply.model_validate(json.loads(reply))
        except (json.JSONDecodeError, ValidationError) as error:
            raise LLMError("The language model returned no usable extraction") from error

        fields = []
        for spec in specs:  # fields the model added on its own are ignored
            found = parsed.fields.get(spec.name)
            value = None if found is None or found.value is None else str(found.value).strip()
            fields.append(
                ExtractedField(
                    name=spec.name,
                    label=spec.label,
                    value=value or None,  # an empty text means "not found"
                    page=None if found is None or not value else found.page,
                )
            )
        return ExtractionResult(document_type, [page.page_number for page in pages], fields)