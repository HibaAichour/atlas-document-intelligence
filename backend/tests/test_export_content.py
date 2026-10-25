"""Content of an exported file: built from a saved message, without LLM or database."""

from datetime import UTC, datetime
from typing import Any, get_args

import pytest

from app.agents.critic import IssueCode
from app.agents.fields import FIELDS
from app.api.schemas import MessageOut
from app.export.content import (
    ENGLISH,
    EXPORT_TEXTS,
    FRENCH,
    NotExportableError,
    build_export,
    download_name,
    readable_text,
)

NOW = datetime(2026, 10, 23, 19, 20, tzinfo=UTC)
REVIEW_FILE = "quarterly_review_HDS_Q2_2026.pptx"


def citation(chunk_id: str, page: int, text: str, filename: str = REVIEW_FILE) -> dict[str, Any]:
    return {
        "label": "S1",
        "display": f"[{filename}, p. {page}]",
        "chunk_id": chunk_id,
        "document_id": "doc-1",
        "filename": filename,
        "page_number": page,
        "position": 0,
        "text": text,
        "score": 0.8,
    }


def message(**fields: Any) -> MessageOut:
    """A saved message; the answer fields are filled for an answered message."""
    values: dict[str, Any] = {
        "id": "m-2",
        "position": 1,
        "role": "assistant",
        "mode": "ask",
        "content": "",
        "status": "answered",
        "refusal_reason": None,
        "citations": [],
        "invalid_citations": [],
        "warnings": [],
        "best_score": 0.8,
        "review": None,
        "agent_trace": [],
        "extraction": None,
        "created_at": NOW,
    }
    values.update(fields)
    return MessageOut.model_validate(values)


def question(text: str) -> MessageOut:
    return message(id="m-1", position=0, role="user", content=text, status=None, best_score=None)


def review(*issues: dict[str, Any], model_checked: bool = True) -> dict[str, Any]:
    return {
        "verdict": "issues" if issues else "ok",
        "issues": list(issues),
        "model_checked": model_checked,
    }


def issue(code: str, origin: str = "code", **fields: Any) -> dict[str, Any]:
    return {"code": code, "origin": origin, "message": "technical note", "sentence": None} | fields


ANSWER_TEXT = (
    f"The total invoiced in Q2 2026 was USD 45,370.00 [{REVIEW_FILE}, p. 5] [{REVIEW_FILE}, p. 2]."
)


def answered(**fields: Any) -> MessageOut:
    values: dict[str, Any] = {
        "content": ANSWER_TEXT,
        "citations": [
            citation("c5", 5, "Total invoiced in the\nquarter: USD 45,370.00."),
            citation("c2", 2, "Total invoiced in Q2 2026: USD 45,370.00."),
        ],
        "review": review(),
    }
    values.update(fields)
    return message(**values)


def test_an_answer_keeps_its_question_text_citations_and_verdict() -> None:
    content = build_export(
        answered(), question("How much was invoiced in Q2 2026?"), "How much was…", NOW
    )

    assert content.kind == "answer"
    assert content.title == "Answer from your documents"
    assert content.session_title == "How much was…"
    assert content.request == "How much was invoiced in Q2 2026?"
    assert content.answer == ANSWER_TEXT
    assert content.rows == []
    assert content.review is not None
    assert content.review.summary == "Checked by the Critic: no problem found."
    assert content.generated_at == NOW
    assert content.texts is ENGLISH


def test_answer_sources_have_file_page_and_readable_text() -> None:
    content = build_export(answered(), question("Q?"), None, NOW)

    assert [(s.display, s.filename, s.page) for s in content.sources] == [
        (f"[{REVIEW_FILE}, p. 5]", REVIEW_FILE, 5),
        (f"[{REVIEW_FILE}, p. 2]", REVIEW_FILE, 2),
    ]
    # The line break of the slide layout is joined for reading.
    assert content.sources[0].text == "Total invoiced in the quarter: USD 45,370.00."
    assert content.sources[1].used_for == []


def test_two_passages_of_the_same_page_make_one_source() -> None:
    content = build_export(
        answered(citations=[citation("a", 4, "First part"), citation("b", 4, "Second part")]),
        question("Q?"),
        None,
        NOW,
    )

    assert len(content.sources) == 1
    assert content.sources[0].text == "First part\n\nSecond part"


def test_issues_are_written_in_words_and_split_by_origin() -> None:
    saved = answered(
        review=review(
            issue("uncited_sentence", sentence="It is fair."),
            issue("unsupported_claim", origin="model", sentence="Renewal is automatic."),
        )
    )

    content = build_export(saved, question("Q?"), None, NOW)

    assert content.review is not None
    assert content.review.summary == "The Critic found 2 problems."
    assert content.review.certain == ["A sentence cites no source. “It is fair.”"]
    assert content.review.to_check == [
        "No passage seems to state this sentence. “Renewal is automatic.”"
    ]
    assert content.review.note is None


def test_review_summaries() -> None:
    one = build_export(answered(review=review(issue("no_citation"))), None, None, NOW)
    rules = build_export(answered(review=review(model_checked=False)), None, None, NOW)
    none = build_export(answered(review=None), None, None, NOW)

    assert one.review is not None and one.review.summary == "The Critic found 1 problem."
    assert one.review.certain == ["The answer cites no source."]
    assert rules.review is not None
    assert rules.review.summary == "Checked by the Critic (rules only): no problem found."
    # An answer saved before step 9 has no verdict.
    assert none.review is None
    # Without the question message, the request is empty rather than invented.
    assert none.request == ""


INVOICE_FILE = "invoice_HDS-INV-2026-0042.pdf"
INVOICE_PAGE = "Invoice No.: HDS-INV-2026-0042\nInvoice date: 1 April 2026\nTotal due USD 15,950.00"


def extracted(**fields: Any) -> MessageOut:
    source = citation("inv-1", 1, INVOICE_PAGE, filename=INVOICE_FILE)
    values: dict[str, Any] = {
        "mode": "extract",
        "content": "Extracted 3 of 4 fields.",
        "extraction": {
            "document_id": "doc-2",
            "filename": INVOICE_FILE,
            "document_type": "invoice",
            "fields": [
                {
                    "name": "invoice_number",
                    "label": "Invoice number",
                    "value": "HDS-INV-2026-0042",
                    "page": 1,
                    "source": source,
                },
                {
                    "name": "invoice_date",
                    "label": "Invoice date",
                    "value": "1 April 2026",
                    "page": 1,
                    "source": source,
                },
                {
                    "name": "total",
                    "label": "Total",
                    "value": "USD 15,950.00",
                    "page": 1,
                    "source": source,
                },
                {
                    "name": "due_date",
                    "label": "Due date",
                    "value": None,
                    "page": None,
                    "source": None,
                },
            ],
        },
        "review": review(issue("missing_required_field", field="due_date"), model_checked=False),
    }
    values.update(fields)
    return message(**values)


def test_an_extraction_gives_one_row_per_field() -> None:
    request = question(f"Extract the key fields of {INVOICE_FILE}")

    content = build_export(extracted(), request, None, NOW)

    assert content.kind == "extraction"
    assert content.title == f"Key fields of {INVOICE_FILE} (invoice)"
    assert content.request == f"Extract the key fields of {INVOICE_FILE}"
    assert content.answer is None
    assert [(row.label, row.value, row.page) for row in content.rows] == [
        ("Invoice number", "HDS-INV-2026-0042", "p. 1"),
        ("Invoice date", "1 April 2026", "p. 1"),
        ("Total", "USD 15,950.00", "p. 1"),
        ("Due date", "Not found", "–"),
    ]


def test_extraction_issues_go_next_to_their_field() -> None:
    content = build_export(extracted(), None, None, NOW)

    assert content.rows[3].issues == ["Required field not found."]
    assert content.rows[0].issues == []
    assert content.review is not None
    assert content.review.summary == "The Critic found 1 problem."
    assert content.review.certain == []
    assert content.review.note == "Problems about a field are shown next to its value."


def test_fields_read_from_the_same_passage_share_one_source() -> None:
    content = build_export(extracted(), None, None, NOW)

    assert len(content.sources) == 1
    source = content.sources[0]
    assert source.display == f"[{INVOICE_FILE}, p. 1]"
    assert source.used_for == ["Invoice number", "Invoice date", "Total"]
    assert "Total due USD 15,950.00" in source.text


def test_an_extraction_without_problem_has_the_rules_only_summary() -> None:
    content = build_export(extracted(review=review(model_checked=False)), None, None, NOW)

    assert content.review is not None
    assert content.review.summary == "Checked by the Critic (rules only): no problem found."
    assert content.review.note is None


@pytest.mark.parametrize(
    "saved",
    [
        question("What is the termination notice period?"),
        answered(status="refused", refusal_reason="no_relevant_passages", citations=[]),
        extracted(status="refused", refusal_reason="unsupported_document", extraction=None),
        extracted(extraction=None),
    ],
    ids=["question", "refused answer", "refused extraction", "extraction without fields"],
)
def test_questions_and_refusals_cannot_be_exported(saved: MessageOut) -> None:
    with pytest.raises(NotExportableError):
        build_export(saved, None, None, NOW)


def test_dates_use_the_month_names_of_the_texts() -> None:
    assert ENGLISH.format_date(NOW) == "23 October 2026, 19:20 UTC"
    assert ENGLISH.footer.format(date=ENGLISH.format_date(NOW)) == (
        "Generated by ATLAS on 23 October 2026, 19:20 UTC from the saved session."
    )


def test_french_texts_cover_every_code_type_field_and_month() -> None:
    assert set(FRENCH.issue_texts) == set(get_args(IssueCode)) == set(ENGLISH.issue_texts)
    assert set(FRENCH.document_types) == set(ENGLISH.document_types)
    names = {spec.name for specs in FIELDS.values() for spec in specs}
    assert set(FRENCH.field_labels) == names
    assert len(FRENCH.months) == 12
    assert EXPORT_TEXTS == {"en": ENGLISH, "fr": FRENCH}


def test_french_dates() -> None:
    assert FRENCH.format_date(NOW) == "23 octobre 2026, 19:20 UTC"
    assert FRENCH.format_date(datetime(2026, 8, 1, 9, 5, tzinfo=UTC)) == "1er août 2026, 09:05 UTC"
    assert ENGLISH.format_date(datetime(2026, 8, 1, 9, 5, tzinfo=UTC)) == "1 August 2026, 09:05 UTC"


def test_a_french_answer_export_keeps_the_question_and_answer_as_written() -> None:
    content = build_export(
        answered(review=review(issue("unsupported_number", sentence="Le total est faux."))),
        question("Combien a été facturé au T2 2026 ?"),
        "Combien a été facturé au T2 2026 ?",
        NOW,
        FRENCH,
    )

    assert content.title == "Réponse tirée de vos documents"
    assert content.request == "Combien a été facturé au T2 2026 ?"
    assert content.answer == ANSWER_TEXT
    assert content.review is not None
    assert content.review.summary == "Le Critic a trouvé 1 problème."
    assert content.review.certain == [
        "Un nombre n’apparaît dans aucun des passages cités. “Le total est faux.”"
    ]
    assert content.texts is FRENCH


def test_a_french_extraction_export_translates_labels_and_request() -> None:
    # The saved request is in English; the export writes its own.
    content = build_export(
        extracted(), question(f"Extract the key fields of {INVOICE_FILE}"), None, NOW, FRENCH
    )

    assert content.title == f"Champs clés de {INVOICE_FILE} (facture)"
    assert content.request == f"Extraire les champs clés de {INVOICE_FILE}"
    assert [(row.label, row.value, row.page) for row in content.rows] == [
        ("Numéro de facture", "HDS-INV-2026-0042", "p. 1"),
        ("Date de facture", "1 April 2026", "p. 1"),  # values stay as in the document
        ("Total", "USD 15,950.00", "p. 1"),  # an unknown field name keeps its saved label
        ("Date d’échéance", "Non trouvé", "–"),
    ]
    assert content.rows[3].issues == ["Champ obligatoire non trouvé."]
    assert content.sources[0].used_for == ["Numéro de facture", "Date de facture", "Total"]
    assert content.review is not None
    assert content.review.note == "Les problèmes liés à un champ sont indiqués à côté de sa valeur."


def test_an_extraction_request_is_written_even_without_the_saved_question() -> None:
    content = build_export(extracted(), None, None, NOW)

    assert content.request == f"Extract the key fields of {INVOICE_FILE}"


def test_download_name() -> None:
    assert download_name("answer", NOW, "docx") == "ATLAS_answer_2026-10-23.docx"
    assert download_name("extraction", NOW, "pptx") == "ATLAS_extraction_2026-10-23.pptx"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "Either Party may terminate\nthis Agreement.",
            "Either Party may terminate this Agreement.",
        ),
        (
            "The term is 24 months.\n4.2 Renewal. The Agreement renews.",
            "The term is 24 months.\n4.2 Renewal. The Agreement renews.",
        ),
        ("Fees:\nUSD 12,500 per month", "Fees:\nUSD 12,500 per month"),
        ("First paragraph\n\nSecond paragraph", "First paragraph\n\nSecond paragraph"),
        (
            "  shall pay all fees  \r\ndue up to the date.  ",
            "shall pay all fees due up to the date.",
        ),
    ],
)
def test_readable_text_matches_the_interface(raw: str, expected: str) -> None:
    """Same cases as frontend/src/lib/text.test.ts."""
    assert readable_text(raw) == expected