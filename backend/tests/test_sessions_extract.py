"""Tests for POST /api/sessions/{id}/extract (fake embeddings, fake LLM, real Chroma)."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.agents.orchestrator import UNSUPPORTED_DOCUMENT_MESSAGE
from app.core.config import get_settings
from app.db.models import DocumentStatus
from app.db.repositories import AssistantReply, DocumentRepository, SessionRepository
from app.main import app
from tests.builders import make_pdf

INVOICE_TEXT = (
    "Helix Data Services Ltd.\n"
    "INVOICE\n"
    "Invoice No.: HDS-INV-2026-0042\n"
    "Invoice date: 1 April 2026\n"
    "Due date: 1 May 2026\n"
    "Bill to: Orion Freight Co.\n"
    "Total due: USD 15,950.00"
)
NOTES_TEXT = "Team lunch on Friday. Bring a dessert and a good mood."

INVOICE_TYPE = json.dumps({"type": "invoice"})
OTHER_TYPE = json.dumps({"type": "other"})
INVOICE_FIELDS = json.dumps(
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


def upload_pdf(client: TestClient, tmp_path: Path, filename: str, text: str) -> str:
    """Upload a one-page text PDF and return the id of the ready document."""
    path = make_pdf(tmp_path / filename, [text])
    response = client.post(
        "/api/documents", files={"file": (filename, path.read_bytes(), "application/pdf")}
    )
    assert response.json()["status"] == "ready"
    return str(response.json()["id"])


def new_session(client: TestClient) -> str:
    response = client.post("/api/sessions")
    assert response.status_code == 201
    return str(response.json()["id"])


def extract(client: TestClient, session_id: str, document_id: str):
    return client.post(f"/api/sessions/{session_id}/extract", json={"document_id": document_id})


def test_unknown_session_gives_404_without_calling_the_model(
    client: TestClient, fake_llm, tmp_path: Path
) -> None:
    document_id = upload_pdf(client, tmp_path, "invoice.pdf", INVOICE_TEXT)

    response = extract(client, "does-not-exist", document_id)

    assert response.status_code == 404
    assert response.json()["detail"] == "Session not found."
    assert fake_llm.calls == []


def test_unknown_document_gives_404_without_calling_the_model(
    client: TestClient, fake_llm
) -> None:
    session_id = new_session(client)

    response = extract(client, session_id, "does-not-exist")

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found."
    assert fake_llm.calls == []
    assert client.get(f"/api/sessions/{session_id}").json()["messages"] == []


def test_a_document_that_is_not_ready_gives_409(client: TestClient, fake_llm) -> None:
    session_id = new_session(client)
    with app.state.session_factory() as db:
        repository = DocumentRepository(db)
        document = repository.create("broken.pdf", "application/pdf")
        repository.mark_failed(document, "Unreadable file")
        document_id = document.id

    response = extract(client, session_id, document_id)

    assert response.status_code == 409
    assert response.json()["detail"] == "Document is not ready for extraction (status: failed)."
    assert fake_llm.calls == []


def test_a_ready_document_without_text_gives_409(client: TestClient, fake_llm) -> None:
    session_id = new_session(client)
    with app.state.session_factory() as db:
        repository = DocumentRepository(db)
        document = repository.create("empty.pdf", "application/pdf")
        repository.mark_ready(document, [])
        assert document.status == DocumentStatus.READY
        document_id = document.id

    response = extract(client, session_id, document_id)

    assert response.status_code == 409
    assert response.json()["detail"] == "Document has no extracted text to read."
    assert fake_llm.calls == []


def test_a_blank_document_id_is_refused(client: TestClient) -> None:
    session_id = new_session(client)

    response = client.post(f"/api/sessions/{session_id}/extract", json={"document_id": "  "})

    assert response.status_code == 422


def test_an_invoice_extraction_is_saved_with_its_values_sources_review_and_trace(
    client: TestClient, fake_llm, tmp_path: Path
) -> None:
    document_id = upload_pdf(client, tmp_path, "invoice.pdf", INVOICE_TEXT)
    session_id = new_session(client)
    fake_llm.replies.extend([INVOICE_TYPE, INVOICE_FIELDS])

    response = extract(client, session_id, document_id)

    assert response.status_code == 200
    body = response.json()
    assert body["session"]["title"] == "Extract the key fields of invoice.pdf"
    assert body["session"]["message_count"] == 2
    question = body["question"]
    assert (question["role"], question["mode"]) == ("user", "extract")
    assert question["content"] == "Extract the key fields of invoice.pdf"
    assert question["extraction"] is None

    answer = body["answer"]
    assert (answer["role"], answer["mode"], answer["status"]) == (
        "assistant",
        "extract",
        "answered",
    )
    assert answer["refusal_reason"] is None
    assert answer["content"] == "Extracted 7 of 7 fields from invoice.pdf (invoice)."
    assert answer["citations"] == []
    assert answer["best_score"] is None

    extraction = answer["extraction"]
    assert extraction["document_id"] == document_id
    assert extraction["filename"] == "invoice.pdf"
    assert extraction["document_type"] == "invoice"
    values = {field["name"]: (field["value"], field["page"]) for field in extraction["fields"]}
    assert values["invoice_number"] == ("HDS-INV-2026-0042", 1)
    assert values["total_amount"] == ("15950.0", 1)  # a number from the model becomes text
    total = next(field for field in extraction["fields"] if field["name"] == "total_amount")
    assert total["label"] == "Total due"
    assert total["source"]["display"] == "[invoice.pdf, p. 1]"
    assert total["source"]["document_id"] == document_id
    assert "15,950.00" in total["source"]["text"]

    assert answer["review"] == {"verdict": "ok", "issues": [], "model_checked": False}
    assert [(run["name"], run["status"]) for run in answer["agent_trace"]] == [
        ("analyst", "ok"),
        ("extractor", "ok"),
        ("critic", "ok"),
    ]
    assert len(fake_llm.calls) == 2  # the Analyst, then the Extractor; the Critic uses code only


def test_a_saved_extraction_reads_back_exactly_like_the_live_one(
    client: TestClient, fake_llm, tmp_path: Path
) -> None:
    document_id = upload_pdf(client, tmp_path, "invoice.pdf", INVOICE_TEXT)
    session_id = new_session(client)
    fake_llm.replies.extend([INVOICE_TYPE, INVOICE_FIELDS])
    live = extract(client, session_id, document_id).json()

    restored = client.get(f"/api/sessions/{session_id}").json()

    assert restored["messages"] == [live["question"], live["answer"]]


def test_issues_found_by_the_critic_name_their_field(
    client: TestClient, fake_llm, tmp_path: Path
) -> None:
    document_id = upload_pdf(client, tmp_path, "invoice.pdf", INVOICE_TEXT)
    session_id = new_session(client)
    reply = json.loads(INVOICE_FIELDS)
    reply["fields"]["due_date"] = {"value": "15 June 2026", "page": 1}  # not in the invoice
    reply["fields"]["invoice_number"] = {"value": None, "page": None}  # a required field
    fake_llm.replies.extend([INVOICE_TYPE, json.dumps(reply)])

    extract(client, session_id, document_id)

    review = client.get(f"/api/sessions/{session_id}").json()["messages"][1]["review"]
    assert review["verdict"] == "issues"
    assert sorted((issue["code"], issue["field"]) for issue in review["issues"]) == [
        ("missing_required_field", "invoice_number"),
        ("value_not_found", "due_date"),
    ]
    assert all(issue["origin"] == "code" for issue in review["issues"])


def test_a_document_that_is_neither_invoice_nor_contract_is_a_saved_refusal(
    client: TestClient, fake_llm, tmp_path: Path
) -> None:
    document_id = upload_pdf(client, tmp_path, "notes.pdf", NOTES_TEXT)
    session_id = new_session(client)
    fake_llm.replies.append(OTHER_TYPE)

    response = extract(client, session_id, document_id)

    assert response.status_code == 200
    answer = client.get(f"/api/sessions/{session_id}").json()["messages"][1]
    assert answer == response.json()["answer"]
    assert answer["status"] == "refused"
    assert answer["refusal_reason"] == "unsupported_document"
    assert answer["content"] == UNSUPPORTED_DOCUMENT_MESSAGE
    assert answer["extraction"] is None
    assert answer["review"] is None
    assert [(run["name"], run["status"]) for run in answer["agent_trace"]] == [
        ("analyst", "refused"),
        ("extractor", "skipped"),
        ("critic", "skipped"),
    ]
    assert len(fake_llm.calls) == 1  # only the Analyst


def test_nothing_is_saved_when_the_model_is_down(
    client: TestClient, fake_llm, tmp_path: Path
) -> None:
    """The Analyst falls back on keywords; the Extractor cannot, so the request fails."""
    document_id = upload_pdf(client, tmp_path, "invoice.pdf", INVOICE_TEXT)
    session_id = new_session(client)
    fake_llm.unavailable = True

    response = extract(client, session_id, document_id)

    assert response.status_code == 503
    assert response.json()["detail"].startswith("Extraction failed")
    body = client.get(f"/api/sessions/{session_id}").json()
    assert body["messages"] == []
    assert body["title"] is None


def test_an_extraction_keeps_the_documents_selected_for_questions(
    client: TestClient, fake_llm, tmp_path: Path
) -> None:
    contract_id = upload_pdf(client, tmp_path, "contract.pdf", "Service agreement, 30 days notice.")
    invoice_id = upload_pdf(client, tmp_path, "invoice.pdf", INVOICE_TEXT)
    session_id = new_session(client)
    # A threshold no passage reaches: the question is refused without any LLM call.
    settings = get_settings().model_copy(update={"retrieval_min_score": 0.999})
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        client.post(
            f"/api/sessions/{session_id}/ask",
            json={"question": "Notice period?", "document_ids": [contract_id]},
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)
    fake_llm.replies.extend([INVOICE_TYPE, INVOICE_FIELDS])

    extract(client, session_id, invoice_id)

    body = client.get(f"/api/sessions/{session_id}").json()
    assert body["document_ids"] == [contract_id]
    assert [message["mode"] for message in body["messages"]] == ["ask", "ask", "extract", "extract"]
    assert body["title"] == "Notice period?"


def test_a_first_extraction_leaves_a_new_session_without_selected_documents(
    client: TestClient, fake_llm, tmp_path: Path
) -> None:
    """No saved selection: the interface then opens the session with every document."""
    document_id = upload_pdf(client, tmp_path, "invoice.pdf", INVOICE_TEXT)
    session_id = new_session(client)
    fake_llm.replies.extend([INVOICE_TYPE, INVOICE_FIELDS])

    extract(client, session_id, document_id)

    assert client.get(f"/api/sessions/{session_id}").json()["document_ids"] == []


def test_an_old_review_without_the_field_key_is_still_read_back(client: TestClient) -> None:
    """Reviews saved before step 9.4 have no "field" in their issues."""
    session_id = new_session(client)
    with app.state.session_factory() as db:
        repository = SessionRepository(db)
        chat_session = repository.get(session_id)
        assert chat_session is not None
        old_review = {
            "verdict": "issues",
            "issues": [
                {"code": "uncited_sentence", "origin": "code", "message": "x", "sentence": "S."}
            ],
            "model_checked": False,
        }
        repository.add_exchange(
            chat_session,
            question="Q?",
            document_ids=[],
            reply=AssistantReply(content="A.", status="answered", review=old_review),
        )

    answer = client.get(f"/api/sessions/{session_id}").json()["messages"][1]

    assert answer["review"]["issues"][0]["field"] is None
    assert answer["extraction"] is None