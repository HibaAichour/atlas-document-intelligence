"""The Critic's checks on an extraction: each value on its page, required fields, formats."""

from app.agents.critic import appears_in, is_readable_date, review_extraction
from app.agents.extractor import ExtractedField, ExtractionResult
from app.agents.fields import FIELDS
from app.ingestion.models import PageText

INVOICE_PAGE = PageText(
    page_number=1,
    text=(
        "Helix Data Services Ltd. INVOICE\nInvoice No.: HDS-INV-2026-0042\n"
        "Invoice date: 1 April 2026\nDue date: 1 May 2026\n"
        "Bill to:\nOrion Freight Co. - Accounts Payable\nTotal due USD 15,950.00"
    ),
    ocr_used=True,
)
CONTRACT_PAGES = [
    PageText(page_number=1, text="Agreement No. HDS-2026-014 between Helix Data Services Ltd."),
    PageText(
        page_number=4, text="the Client may terminate by giving 60 days\u2019 written notice."
    ),
]

GOOD_INVOICE = {
    "invoice_number": ("HDS-INV-2026-0042", 1),
    "invoice_date": ("1 April 2026", 1),
    "due_date": ("1 May 2026", 1),
    "total_amount": ("USD 15,950.00", 1),
    "currency": ("USD", 1),
    "vendor": ("Helix Data Services Ltd.", 1),
    "customer": ("Orion Freight Co.", 1),
}


def extraction(document_type, values, pages) -> ExtractionResult:
    """An Extractor result with these (value, page) pairs; other fields not found."""
    fields = [
        ExtractedField(spec.name, spec.label, *values.get(spec.name, (None, None)))
        for spec in FIELDS[document_type]
    ]
    return ExtractionResult(document_type, [page.page_number for page in pages], fields)


def issues(review) -> list[tuple[str, str | None]]:
    return [(issue.code, issue.field) for issue in review.issues]


def test_values_copied_from_their_page_are_ok() -> None:
    review = review_extraction(extraction("invoice", GOOD_INVOICE, [INVOICE_PAGE]), [INVOICE_PAGE])

    assert review.verdict == "ok"
    assert review.issues == []
    assert review.model_checked is False  # an extraction is checked by the code only


def test_a_value_absent_from_the_document_is_reported() -> None:
    values = {**GOOD_INVOICE, "invoice_number": ("HDS-INV-2026-0043", 1)}

    review = review_extraction(extraction("invoice", values, [INVOICE_PAGE]), [INVOICE_PAGE])

    assert issues(review) == [("value_not_found", "invoice_number")]
    assert review.issues[0].origin == "code"
    assert review.issues[0].message == "not found in the document: HDS-INV-2026-0043"


def test_an_amount_is_compared_by_its_numbers() -> None:
    """15950.0, as the model may send it, is the amount "USD 15,950.00" of the page."""
    for value in ["15950.0", "15,950", "USD 15950.00"]:
        values = {**GOOD_INVOICE, "total_amount": (value, 1)}

        review = review_extraction(extraction("invoice", values, [INVOICE_PAGE]), [INVOICE_PAGE])

        assert review.verdict == "ok", value


def test_a_changed_amount_is_reported() -> None:
    values = {**GOOD_INVOICE, "total_amount": ("USD 15,590.00", 1)}

    review = review_extraction(extraction("invoice", values, [INVOICE_PAGE]), [INVOICE_PAGE])

    assert issues(review) == [("value_not_found", "total_amount")]


def test_an_amount_without_a_number_is_unreadable_and_reported_once() -> None:
    values = {**GOOD_INVOICE, "total_amount": ("fifteen thousand", 1)}

    review = review_extraction(extraction("invoice", values, [INVOICE_PAGE]), [INVOICE_PAGE])

    assert issues(review) == [("unreadable_amount", "total_amount")]


def test_a_date_rewritten_in_another_format_is_reported() -> None:
    """The model must copy the date as written: "2026-05-01" is not on the page."""
    values = {**GOOD_INVOICE, "due_date": ("2026-05-01", 1)}

    review = review_extraction(extraction("invoice", values, [INVOICE_PAGE]), [INVOICE_PAGE])

    assert issues(review) == [("value_not_found", "due_date")]


def test_a_date_field_without_a_date_is_reported() -> None:
    values = {**GOOD_INVOICE, "invoice_date": ("Invoice", 1)}

    review = review_extraction(extraction("invoice", values, [INVOICE_PAGE]), [INVOICE_PAGE])

    # "Invoice" is on the page, but it is not a date.
    assert issues(review) == [("unreadable_date", "invoice_date")]


def test_missing_required_fields_are_reported_but_not_missing_optional_ones() -> None:
    values = {
        name: value for name, value in GOOD_INVOICE.items() if name not in {"due_date", "vendor"}
    }

    review = review_extraction(extraction("invoice", values, [INVOICE_PAGE]), [INVOICE_PAGE])

    assert issues(review) == [("missing_required_field", "due_date")]


def test_a_value_on_another_page_is_a_wrong_page_not_an_invention() -> None:
    values = {
        "agreement_number": ("HDS-2026-014", 4),  # it is on page 1
        "provider": ("Helix Data Services Ltd.", 1),
        "client": ("Orion Freight Co.", None),  # not in these pages at all
        "effective_date": ("1 March 2026", 9),  # page 9 was not given
        "convenience_notice": ("60 days' written notice", 4),
    }

    review = review_extraction(extraction("contract", values, CONTRACT_PAGES), CONTRACT_PAGES)

    assert issues(review) == [
        ("wrong_page", "agreement_number"),
        ("value_not_found", "client"),
        ("value_not_found", "effective_date"),
    ]
    assert review.issues[0].message == "found on page 1, not on page 4"


def test_a_page_given_as_none_is_reported_with_the_page_where_the_value_is() -> None:
    values = {"agreement_number": ("HDS-2026-014", None)}

    review = review_extraction(extraction("contract", values, CONTRACT_PAGES), CONTRACT_PAGES)

    assert review.issues[0].code == "wrong_page"
    assert review.issues[0].message == "found on page 1, no page given"


def test_text_is_compared_without_case_line_breaks_or_curly_quotes() -> None:
    assert appears_in("orion freight co.", "Bill to:\nOrion  Freight Co.", amount=False)
    assert appears_in("60 days' written notice", CONTRACT_PAGES[1].text, amount=False)
    assert not appears_in("Orion Freight Inc.", "Orion Freight Co.", amount=False)


def test_usual_date_formats_are_readable() -> None:
    for value in ["1 April 2026", "1 Apr 2026", "April 1, 2026", "2026-04-01", "01/04/2026"]:
        assert is_readable_date(value), value
    assert not is_readable_date("next Monday")