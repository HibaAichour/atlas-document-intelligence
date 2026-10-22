"""The Extractor: fixed fields per type, values copied with their page, strict JSON."""

import json

import pytest

from app.agents.extractor import SYSTEM_PROMPT, Extractor
from app.agents.fields import CONTRACT_FIELDS, FIELDS, INVOICE_FIELDS
from app.ingestion.models import PageText
from app.llm.base import LLMError

INVOICE_PAGE = PageText(
    page_number=1,
    text=(
        "Helix Data Services Ltd. INVOICE\nInvoice No.: HDS-INV-2026-0042\n"
        "Invoice date: 1 April 2026\nDue date: 1 May 2026\nTotal due USD 15,950.00"
    ),
    ocr_used=True,
)


def reply(**fields) -> str:
    """The model's JSON reply with these fields."""
    return json.dumps({"fields": fields})


def test_each_type_has_its_required_fields() -> None:
    required = {name: [s.name for s in specs if s.required] for name, specs in FIELDS.items()}

    assert required == {
        "invoice": ["invoice_number", "invoice_date", "due_date", "total_amount"],
        "contract": ["agreement_number", "provider", "client", "effective_date"],
    }
    assert len({spec.name for spec in INVOICE_FIELDS}) == len(INVOICE_FIELDS)
    assert len({spec.name for spec in CONTRACT_FIELDS}) == len(CONTRACT_FIELDS)


def test_the_prompt_lists_the_fields_and_numbers_the_pages(fake_llm) -> None:
    fake_llm.replies.append(reply())
    page_4 = PageText(page_number=4, text="4.3 Termination for convenience: 60 days.")

    Extractor(fake_llm).extract("contract", [PageText(page_number=1, text="Agreement"), page_4])

    call = fake_llm.calls[0]
    assert call.json_mode is True
    assert call.temperature == 0.0
    assert call.messages[0].content == SYSTEM_PROMPT
    user = call.messages[1].content
    assert "- agreement_number: the number of the agreement" in user
    assert "- governing_law: the law that governs it" in user
    assert "[Page 1]\nAgreement" in user
    assert "[Page 4]\n4.3 Termination for convenience" in user


def test_values_and_pages_are_kept_in_the_order_of_the_schema(fake_llm) -> None:
    fake_llm.replies.append(
        reply(
            total_amount={"value": "USD 15,950.00", "page": 1},
            invoice_number={"value": " HDS-INV-2026-0042 ", "page": 1},
            due_date={"value": "1 May 2026", "page": 1},
            invoice_date={"value": "1 April 2026", "page": 1},
        )
    )

    result = Extractor(fake_llm).extract("invoice", [INVOICE_PAGE])

    assert result.document_type == "invoice"
    assert result.pages == [1]
    assert [field.name for field in result.fields] == [spec.name for spec in INVOICE_FIELDS]
    values = {field.name: (field.value, field.page) for field in result.fields}
    assert values["invoice_number"] == ("HDS-INV-2026-0042", 1)  # spaces removed
    assert values["total_amount"] == ("USD 15,950.00", 1)
    assert values["vendor"] == (None, None)  # not given by the model
    assert result.fields[0].label == "Invoice number"
    assert result.summary() == "4 of 7 fields found"


def test_null_and_empty_values_mean_not_found(fake_llm) -> None:
    fake_llm.replies.append(
        reply(
            invoice_number={"value": None, "page": 1},
            invoice_date={"value": "   ", "page": 1},
            due_date=None,
        )
    )

    result = Extractor(fake_llm).extract("invoice", [INVOICE_PAGE])

    for field in result.fields[:3]:
        assert (field.value, field.page) == (None, None)


def test_a_number_given_as_a_number_is_kept_as_text(fake_llm) -> None:
    fake_llm.replies.append(reply(total_amount={"value": 15950.0, "page": 1}))

    result = Extractor(fake_llm).extract("invoice", [INVOICE_PAGE])

    assert result.fields[3].value == "15950.0"


def test_fields_the_model_adds_on_its_own_are_ignored(fake_llm) -> None:
    fake_llm.replies.append(
        reply(invoice_number={"value": "HDS-INV-2026-0042", "page": 1}, ceo={"value": "Dana"})
    )

    result = Extractor(fake_llm).extract("invoice", [INVOICE_PAGE])

    assert "ceo" not in {field.name for field in result.fields}


@pytest.mark.parametrize(
    "bad_reply",
    [
        "not json",
        '{"invoice_number": "HDS-INV-2026-0042"}',  # no "fields" object
        '{"fields": ["HDS-INV-2026-0042"]}',  # a list instead of an object
        '{"fields": {"invoice_number": {"value": "x", "page": "first"}}}',
    ],
)
def test_a_reply_that_is_not_the_expected_json_is_an_error(fake_llm, bad_reply) -> None:
    fake_llm.replies.append(bad_reply)

    with pytest.raises(LLMError, match="no usable extraction"):
        Extractor(fake_llm).extract("invoice", [INVOICE_PAGE])


def test_a_model_that_is_down_raises_llm_error(fake_llm) -> None:
    fake_llm.unavailable = True

    with pytest.raises(LLMError, match="connection refused"):
        Extractor(fake_llm).extract("invoice", [INVOICE_PAGE])


def test_without_pages_the_model_is_not_called(fake_llm) -> None:
    with pytest.raises(ValueError):
        Extractor(fake_llm).extract("invoice", [])
    assert fake_llm.calls == []