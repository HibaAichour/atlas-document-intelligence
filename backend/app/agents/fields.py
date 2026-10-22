"""The fields extracted from each type of document.

One fixed list per type: the Extractor asks for exactly these fields, and the
Critic knows which ones are required and how to read each value (a date, an
amount). Free-form extraction ("extract what I ask") is out of scope in V1:
a small model invents fields, and nothing could be checked.
"""

from dataclasses import dataclass
from typing import Literal

ExtractableType = Literal["invoice", "contract"]
# How the Critic checks a value: text must appear in the page; a date must be
# readable as a date; an amount must contain a number.
FieldKind = Literal["text", "date", "amount"]


@dataclass(frozen=True, slots=True)
class FieldSpec:
    """One field to extract."""

    name: str  # key in the JSON, e.g. "invoice_number"
    label: str  # shown to the user, e.g. "Invoice number"
    kind: FieldKind
    required: bool  # a missing required field is reported by the Critic
    description: str  # what the model should look for


INVOICE_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec("invoice_number", "Invoice number", "text", True, "the invoice number"),
    FieldSpec("invoice_date", "Invoice date", "date", True, "the date the invoice was issued"),
    FieldSpec("due_date", "Due date", "date", True, "the date by which it must be paid"),
    FieldSpec("total_amount", "Total due", "amount", True, "the total amount due, with taxes"),
    FieldSpec("currency", "Currency", "text", False, "the currency of the amounts, e.g. USD"),
    FieldSpec("vendor", "Vendor", "text", False, "the company that issued the invoice"),
    FieldSpec("customer", "Customer", "text", False, "the company the invoice is billed to"),
)

CONTRACT_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec("agreement_number", "Agreement number", "text", True, "the number of the agreement"),
    FieldSpec("provider", "Provider", "text", True, "the company that provides the services"),
    FieldSpec("client", "Client", "text", True, "the company that receives the services"),
    FieldSpec("effective_date", "Effective date", "date", True, "the date the services start"),
    FieldSpec("initial_term", "Initial term", "text", False, "the length of the initial term"),
    FieldSpec(
        "convenience_notice",
        "Notice to terminate for convenience",
        "text",
        False,
        "the notice period to terminate the agreement for convenience",
    ),
    FieldSpec(
        "non_renewal_notice",
        "Notice of non-renewal",
        "text",
        False,
        "the notice period to stop the automatic renewal",
    ),
    FieldSpec("governing_law", "Governing law", "text", False, "the law that governs it"),
)

FIELDS: dict[ExtractableType, tuple[FieldSpec, ...]] = {
    "invoice": INVOICE_FIELDS,
    "contract": CONTRACT_FIELDS,
}