"""The Orchestrator's extract plan: Analyst, then Extractor, then Critic, on a real database."""

import json
from typing import cast

import pytest
from sqlalchemy.orm import Session

from app.agents.analyst import DocumentAnalyst
from app.agents.critic import Critic
from app.agents.extractor import Extractor
from app.agents.orchestrator import EXTRACT_PLAN, UNSUPPORTED_DOCUMENT_MESSAGE, Orchestrator
from app.agents.writer import Writer
from app.db.models import Document
from app.db.repositories import DocumentRepository
from app.ingestion.chunking import TextChunk
from app.ingestion.models import PageText
from app.llm.base import LLMError
from app.retrieval.retriever import Retriever

INVOICE_HEADER = (
    "Helix Data Services Ltd. INVOICE\nInvoice No.: HDS-INV-2026-0042\n"
    "Invoice date: 1 April 2026\nDue date: 1 May 2026\nBill to:\nOrion Freight Co."
)
INVOICE_TOTALS = "Subtotal USD 15,950.00\nTotal due USD 15,950.00"

INVOICE_REPLY = json.dumps(
    {
        "fields": {
            "invoice_number": {"value": "HDS-INV-2026-0042", "page": 1},
            "invoice_date": {"value": "1 April 2026", "page": 1},
            "due_date": {"value": "1 May 2026", "page": 1},
            "total_amount": {"value": 15950.0, "page": 1},
            "currency": {"value": "USD", "page": 1},
            "vendor": {"value": "Helix Data Services Ltd.", "page": 1},
            "customer": {"value": "Orion Freight Co.", "page": 1},
        }
    }
)


class StepClock:
    """A clock that moves forward 10 ms each time it is read."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        self.now += 0.010
        return self.now


def add_document(
    db: Session, filename: str, pages: list[str], chunks: list[tuple[int, str]]
) -> tuple[DocumentRepository, Document]:
    """A ready document with these page texts and these (page, text) chunks."""
    repository = DocumentRepository(db)
    document = repository.create(filename, "application/pdf")
    repository.mark_ready(
        document, [PageText(page_number=n, text=text) for n, text in enumerate(pages, 1)]
    )
    positions: dict[int, int] = {}
    text_chunks = []
    for page, text in chunks:
        text_chunks.append(TextChunk(page_number=page, position=positions.get(page, 0), text=text))
        positions[page] = positions.get(page, 0) + 1
    repository.replace_chunks(document, text_chunks)
    return repository, document


def add_invoice(db: Session) -> tuple[DocumentRepository, Document]:
    return add_document(
        db,
        "invoice.pdf",
        [INVOICE_HEADER + "\n" + INVOICE_TOTALS],
        [(1, INVOICE_HEADER), (1, INVOICE_TOTALS)],
    )


def make_orchestrator(fake_llm) -> Orchestrator:
    # The extract plan never searches: the retriever is not needed here.
    return Orchestrator(
        cast(Retriever, object()),
        Writer(fake_llm),
        Critic(fake_llm, use_model=False),
        DocumentAnalyst(fake_llm),
        Extractor(fake_llm),
        min_score=0.6,
        clock=StepClock(),
    )


def steps(outcome) -> list[tuple[str, str, str]]:
    return [(run.name, run.kind, run.status) for run in outcome.trace]


def test_the_extract_plan_is_an_explicit_list_of_agents(fake_llm) -> None:
    plan = make_orchestrator(fake_llm).plan("extract")

    assert plan is EXTRACT_PLAN
    assert [(step.name, step.kind) for step in plan.steps] == [
        ("analyst", "agent"),
        ("extractor", "agent"),
        ("critic", "agent"),
    ]


def test_an_invoice_goes_through_the_analyst_the_extractor_and_the_critic(
    db_session, fake_llm
) -> None:
    repository, invoice = add_invoice(db_session)
    fake_llm.replies.extend(['{"type": "invoice"}', INVOICE_REPLY])

    outcome = make_orchestrator(fake_llm).extract(repository, invoice)

    assert outcome.status == "extracted"
    assert outcome.document_type == "invoice"
    assert outcome.document_id == invoice.id
    assert steps(outcome) == [
        ("analyst", "agent", "ok"),
        ("extractor", "agent", "ok"),
        ("critic", "agent", "ok"),
    ]
    assert [run.summary for run in outcome.trace] == [
        "type invoice (by model), pages 1",
        "7 of 7 fields found",
        "no issue (code checks)",
    ]
    assert outcome.review is not None
    assert outcome.review.verdict == "ok"
    assert outcome.message == "Extracted 7 of 7 fields from invoice.pdf (invoice)."
    # Analyst, then Extractor: two model calls; the Critic of an extraction uses none.
    assert len(fake_llm.calls) == 2


def test_each_value_gets_the_chunk_of_its_page_as_a_clickable_source(db_session, fake_llm) -> None:
    repository, invoice = add_invoice(db_session)
    fake_llm.replies.extend(['{"type": "invoice"}', INVOICE_REPLY])

    outcome = make_orchestrator(fake_llm).extract(repository, invoice)

    by_name = {value.name: value for value in outcome.fields}
    number = by_name["invoice_number"]
    assert number.source is not None
    assert number.source.display == "[invoice.pdf, p. 1]"
    assert number.source.passage.text == INVOICE_HEADER
    # The amount, sent as the number 15950.0, is found in the totals chunk.
    total = by_name["total_amount"]
    assert total.value == "15950.0"
    assert total.source is not None
    assert total.source.passage.text == INVOICE_TOTALS


def test_the_saved_extraction_has_a_json_shape(db_session, fake_llm) -> None:
    repository, invoice = add_invoice(db_session)
    fake_llm.replies.extend(['{"type": "invoice"}', INVOICE_REPLY])

    outcome = make_orchestrator(fake_llm).extract(repository, invoice)
    saved = json.loads(json.dumps(outcome.extraction_dict()))

    assert saved["document_id"] == invoice.id
    assert saved["filename"] == "invoice.pdf"
    assert saved["document_type"] == "invoice"
    first = saved["fields"][0]
    assert {key: first[key] for key in ("name", "label", "value", "page")} == {
        "name": "invoice_number",
        "label": "Invoice number",
        "value": "HDS-INV-2026-0042",
        "page": 1,
    }
    assert first["source"]["display"] == "[invoice.pdf, p. 1]"
    assert first["source"]["label"] == "invoice_number"


def test_a_value_the_extractor_invented_is_reported_and_has_no_source(db_session, fake_llm) -> None:
    repository, invoice = add_invoice(db_session)
    reply = json.loads(INVOICE_REPLY)
    reply["fields"]["invoice_number"]["value"] = "HDS-INV-2026-0099"
    fake_llm.replies.extend(['{"type": "invoice"}', json.dumps(reply)])

    outcome = make_orchestrator(fake_llm).extract(repository, invoice)

    assert outcome.review is not None
    assert [(issue.code, issue.field) for issue in outcome.review.issues] == [
        ("value_not_found", "invoice_number")
    ]
    assert outcome.fields[0].source is None
    assert outcome.trace[2].summary == "1 issues (code checks)"


def test_only_the_pages_chosen_by_the_analyst_reach_the_extractor(db_session, fake_llm) -> None:
    pages = [
        "MASTER SERVICES AGREEMENT\nAgreement No. HDS-2026-014 made between the Parties.",
        "2. Services\nThe Provider hosts the data platform.",
        "4.3 Termination for convenience: 60 days' written notice. 4.1 Initial term: 24 months.",
    ]
    repository, contract = add_document(
        db_session, "contract.pdf", pages, [(1, pages[0]), (2, pages[1]), (3, pages[2])]
    )
    fake_llm.replies.extend(['{"type": "contract"}', json.dumps({"fields": {}})])

    outcome = make_orchestrator(fake_llm).extract(repository, contract)

    prompt = fake_llm.calls[1].messages[1].content
    assert "[Page 1]" in prompt
    assert "[Page 3]" in prompt
    assert "The Provider hosts the data platform" not in prompt
    # Nothing was found: the four required contract fields are reported.
    assert outcome.review is not None
    assert [issue.code for issue in outcome.review.issues] == ["missing_required_field"] * 4


def test_an_unsupported_document_ends_the_plan_after_the_analyst(db_session, fake_llm) -> None:
    repository, menu = add_document(
        db_session, "menu.pdf", ["Lunch menu: soup, pasta, fruit salad."], [(1, "Lunch menu")]
    )
    fake_llm.replies.append('{"type": "other"}')

    outcome = make_orchestrator(fake_llm).extract(repository, menu)

    assert outcome.status == "refused"
    assert outcome.document_type == "other"
    assert outcome.fields == []
    assert outcome.review is None
    assert outcome.message == UNSUPPORTED_DOCUMENT_MESSAGE
    assert outcome.extraction_dict() is None
    assert steps(outcome) == [
        ("analyst", "agent", "refused"),
        ("extractor", "agent", "skipped"),
        ("critic", "agent", "skipped"),
    ]
    assert outcome.trace[1].summary == "the document is neither an invoice nor a contract"
    assert len(fake_llm.calls) == 1  # the Extractor was never called


def test_an_unusable_extraction_is_an_error(db_session, fake_llm) -> None:
    repository, invoice = add_invoice(db_session)
    fake_llm.replies.extend(['{"type": "invoice"}', "not json"])

    with pytest.raises(LLMError, match="no usable extraction"):
        make_orchestrator(fake_llm).extract(repository, invoice)


def test_a_document_without_pages_is_an_error(db_session, fake_llm) -> None:
    repository = DocumentRepository(db_session)
    document = repository.create("empty.pdf", "application/pdf")

    with pytest.raises(ValueError, match="no extracted page"):
        make_orchestrator(fake_llm).extract(repository, document)
    assert fake_llm.calls == []