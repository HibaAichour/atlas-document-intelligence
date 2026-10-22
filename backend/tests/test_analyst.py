"""The Document Analyst: type from the model (keywords as fallback), pages by keywords."""

import pytest

from app.agents.analyst import (
    MAX_EXTRACTION_CHARS,
    SYSTEM_PROMPT,
    DocumentAnalyst,
    classify_by_keywords,
    select_pages,
)
from app.ingestion.models import PageText

INVOICE = [
    PageText(
        page_number=1,
        text=(
            "Helix Data Services Ltd. INVOICE\nInvoice No.: HDS-INV-2026-0042\n"
            "Invoice date: 1 April 2026\nDue date: 1 May 2026\nBill to: Orion Freight Co.\n"
            "Subtotal USD 15,950.00\nTotal due USD 15,950.00\nAgreement No.: HDS-2026-014"
        ),
        ocr_used=True,
    )
]

CONTRACT = [
    PageText(
        page_number=1,
        text="MASTER SERVICES AGREEMENT\nAgreement No. HDS-2026-014\nmade between the Parties.",
    ),
    PageText(page_number=2, text="2. Services\nThe Provider hosts the data platform."),
    PageText(page_number=3, text="3. Fees and Payment\nMonthly Fee USD 12,500."),
    PageText(
        page_number=4,
        text="4.1 Initial term of 24 months.\n4.2 Renewal for 12 months.\n"
        "4.3 Termination for convenience: 60 days' written notice.",
    ),
    PageText(page_number=6, text="7.5 Governing law. This Agreement is governed by English law."),
]

MENU = [PageText(page_number=1, text="Lunch menu: soup of the day, pasta, fruit salad.")]


def test_keywords_recognise_an_invoice_even_if_it_mentions_an_agreement() -> None:
    assert classify_by_keywords(INVOICE[0].text) == ("invoice", 5)


def test_keywords_recognise_a_contract() -> None:
    document_type, score = classify_by_keywords(" ".join(page.text for page in CONTRACT))

    assert document_type == "contract"
    assert score >= 2


def test_keywords_give_other_when_nothing_matches_or_on_a_tie() -> None:
    assert classify_by_keywords(MENU[0].text) == ("other", 0)
    assert classify_by_keywords("invoice agreement") == ("other", 0)


def test_the_model_names_the_type_from_the_start_of_the_document(fake_llm) -> None:
    fake_llm.replies.append('{"type": "invoice"}')

    profile = DocumentAnalyst(fake_llm).analyze(INVOICE)

    assert profile.document_type == "invoice"
    assert profile.type_source == "model"
    assert profile.pages == [1]
    call = fake_llm.calls[0]
    assert call.json_mode is True
    assert call.temperature == 0.0
    assert call.messages[0].content == SYSTEM_PROMPT
    assert "HDS-INV-2026-0042" in call.messages[1].content


def test_the_model_reads_only_the_start_of_a_long_document(fake_llm) -> None:
    fake_llm.replies.append('{"type": "contract"}')
    long_page = PageText(page_number=1, text="Agreement between the Parties. " + "x" * 5000)

    DocumentAnalyst(fake_llm).analyze([long_page])

    assert len(fake_llm.calls[0].messages[1].content) < 1600


def test_an_unusable_model_reply_leaves_the_keywords_to_decide(fake_llm) -> None:
    for reply in ["not json", '{"type": "receipt"}', '{"kind": "invoice"}']:
        fake_llm.replies.append(reply)

        profile = DocumentAnalyst(fake_llm).analyze(INVOICE)

        assert profile.document_type == "invoice"
        assert profile.type_source == "keywords"


def test_a_model_that_is_down_leaves_the_keywords_to_decide(fake_llm) -> None:
    fake_llm.unavailable = True

    profile = DocumentAnalyst(fake_llm).analyze(CONTRACT)

    assert profile.document_type == "contract"
    assert profile.type_source == "keywords"


def test_the_model_may_not_turn_away_a_document_the_keywords_recognise(fake_llm) -> None:
    fake_llm.replies.append('{"type": "other"}')

    profile = DocumentAnalyst(fake_llm).analyze(INVOICE)

    assert profile.document_type == "invoice"
    assert profile.type_source == "keywords"


def test_an_unknown_document_is_other_with_no_page(fake_llm) -> None:
    fake_llm.replies.append('{"type": "other"}')

    profile = DocumentAnalyst(fake_llm).analyze(MENU)

    assert profile.document_type == "other"
    assert profile.type_source == "model"
    assert profile.pages == []
    assert profile.summary() == "type other (by model), pages none"


def test_contract_pages_are_chosen_by_field_keywords_in_page_order() -> None:
    # Page 2 (services) and page 3 (fees) hold none of the contract fields.
    assert select_pages(CONTRACT, "contract") == [1, 4, 6]


def test_pages_stay_within_the_character_budget() -> None:
    big = "governing law " + "x" * (MAX_EXTRACTION_CHARS - 1000)
    pages = [
        PageText(page_number=1, text="Agreement No. 1, effective date, " + big),
        PageText(page_number=2, text="initial term and renewal, " + big),
        PageText(page_number=3, text="termination for convenience."),
    ]

    chosen = select_pages(pages, "contract")

    # The best page is kept, the second is too long, the short third one still fits.
    assert chosen == [1, 3]
    assert sum(len(pages[number - 1].text) for number in chosen) <= MAX_EXTRACTION_CHARS


def test_a_document_without_field_keywords_gives_its_first_page() -> None:
    pages = [PageText(page_number=1, text="Hello."), PageText(page_number=2, text="World.")]

    assert select_pages(pages, "invoice") == [1]


def test_the_summary_names_the_type_its_source_and_the_pages(fake_llm) -> None:
    fake_llm.replies.append('{"type": "contract"}')

    profile = DocumentAnalyst(fake_llm).analyze(CONTRACT)

    assert profile.summary() == "type contract (by model), pages 1, 4, 6"


def test_a_document_without_pages_is_an_error(fake_llm) -> None:
    with pytest.raises(ValueError):
        DocumentAnalyst(fake_llm).analyze([])
    assert fake_llm.calls == []