"""The evaluation runner, against a fake server: documents, questions, extractions, results."""

import json
from pathlib import Path

import httpx2
import pytest

from scripts.eval_scoring import AskCase, EvalSet, ExtractCase, PageRef, load_eval_set
from scripts.run_eval import (
    EvalRunError,
    ask_line,
    context,
    demo_document_ids,
    extract_line,
    run,
    write_results,
)

NOTICE = AskCase(
    "notice-en",
    "en",
    "What is the termination notice period?",
    ("60 days",),
    ("30 days",),
    (PageRef("contract.pdf", (4,)),),
)
SALARY = AskCase("salary-fr", "fr", "Quel est le salaire du PDG ?", None, (), ())
INVOICE = ExtractCase(
    "invoice", "invoice.pdf", {"invoice_number": ("INV-42",), "due_date": ("1 May",)}
)
EVAL_SET = EvalSet(("contract.pdf", "invoice.pdf"), (NOTICE, SALARY), (INVOICE,))

DOCUMENTS = [
    {"id": "c1", "filename": "contract.pdf", "status": "ready"},
    {"id": "c2", "filename": "contract.pdf", "status": "ready"},  # uploaded twice
    {"id": "i1", "filename": "invoice.pdf", "status": "ready"},
    {"id": "t1", "filename": "test_document.docx", "status": "ready"},
    {"id": "f1", "filename": "invoice.pdf", "status": "failed"},
]
ANSWER = {
    "status": "answered",
    "refusal_reason": None,
    "answer": "The notice period is 60 days [contract.pdf, p. 4].",
    "citations": [{"filename": "contract.pdf", "page_number": 4}],
    "review": {"verdict": "ok", "issues": []},
}
REFUSAL = {"status": "refused", "refusal_reason": "no_relevant_passages", "answer": "x"}
EXTRACTION = {
    "answer": {
        "extraction": {
            "fields": [
                {"name": "invoice_number", "value": "INV-42"},
                {"name": "due_date", "value": "1 June 2026"},
            ]
        },
        "review": {"issues": [{"code": "value_not_found", "origin": "code", "field": "due_date"}]},
    }
}


class FakeServer:
    """Answers the routes the runner calls, and records every request."""

    def __init__(self, documents=DOCUMENTS) -> None:
        self.documents = documents
        self.requests: list[tuple[str, str, dict | None]] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content) if request.content else None
        self.requests.append((request.method, request.url.path, body))
        path = request.url.path
        if path == "/api/documents":
            return httpx2.Response(200, json=self.documents)
        if path == "/api/ask" and body is not None:
            return httpx2.Response(200, json=REFUSAL if "PDG" in body["question"] else ANSWER)
        if path == "/api/sessions":
            return httpx2.Response(201, json={"id": "s1"})
        if path == "/api/sessions/s1/extract":
            return httpx2.Response(200, json=EXTRACTION)
        return httpx2.Response(404, json={"detail": "not found"})


def client_for(server: FakeServer) -> httpx2.Client:
    return httpx2.Client(base_url="http://test", transport=httpx2.MockTransport(server))


class Clock:
    """Each call moves time forward by 2 seconds."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        self.now += 2.0
        return self.now


def test_demo_document_ids_keeps_ready_copies_of_demo_files_only() -> None:
    with client_for(FakeServer()) as client:
        ids = demo_document_ids(client, ["contract.pdf", "invoice.pdf"])
    assert ids == {"contract.pdf": ["c1", "c2"], "invoice.pdf": ["i1"]}


def test_a_missing_demo_document_stops_the_evaluation() -> None:
    with (
        client_for(FakeServer(DOCUMENTS[:2])) as client,
        pytest.raises(EvalRunError, match="invoice.pdf"),
    ):
        demo_document_ids(client, ["contract.pdf", "invoice.pdf"])


def test_run_asks_on_the_demo_documents_and_extracts_in_one_session() -> None:
    server = FakeServer()
    logged: list[str] = []
    with client_for(server) as client:
        asks, extracts = run(client, EVAL_SET, clock=Clock(), log=logged.append)

    ask_bodies = [body for method, path, body in server.requests if path == "/api/ask"]
    assert ask_bodies[0] == {"question": NOTICE.question, "document_ids": ["c1", "c2", "i1"]}
    assert [score.right for score in asks] == [True, True]
    assert asks[0].citation_right is True
    assert asks[0].outcome.seconds == pytest.approx(2.0)

    assert ("POST", "/api/sessions", None) in server.requests
    assert ("POST", "/api/sessions/s1/extract", {"document_id": "i1"}) in server.requests
    (invoice,) = extracts
    assert invoice.right == 1
    assert invoice.issues == ("value_not_found (due_date)",)
    assert any("1 of 2 fields right" in line for line in logged)


def test_run_without_extractions_creates_no_session() -> None:
    server = FakeServer()
    with client_for(server) as client:
        _, extracts = run(client, EVAL_SET, extractions=False, log=lambda line: None)
    assert extracts == []
    assert all(path != "/api/sessions" for _, path, _ in server.requests)


def test_a_server_error_is_raised() -> None:
    transport = httpx2.MockTransport(lambda request: httpx2.Response(503, json={"detail": "x"}))
    with (
        httpx2.Client(base_url="http://test", transport=transport) as client,
        pytest.raises(httpx2.HTTPStatusError),
    ):
        run(client, EVAL_SET, log=lambda line: None)


def test_log_lines() -> None:
    with client_for(FakeServer()) as client:
        asks, extracts = run(client, EVAL_SET, clock=Clock(), log=lambda line: None)
    assert ask_line(asks[0]).split()[:4] == ["ok", "notice-en", "2.0", "s"]
    assert "refused (no_relevant_passages)" in ask_line(asks[1])
    assert "wrong: due_date='1 June 2026'" in extract_line(extracts[0])


def test_context_and_results_file(tmp_path: Path) -> None:
    run_context = context("http://localhost:8080", "docker", extractions=True)
    assert run_context["label"] == "docker"
    assert run_context["local_settings"]["retrieval_max_gap"] == pytest.approx(0.05)
    path = tmp_path / "results.json"
    write_results(path, {"summary": {"questions": "1 of 2 (50%)"}, "note": "préavis"})
    assert json.loads(path.read_text(encoding="utf-8"))["note"] == "préavis"
    assert "préavis" in path.read_text(encoding="utf-8")  # accents kept, readable on GitHub


def test_the_real_evaluation_set_uses_only_files_the_runner_looks_up() -> None:
    eval_set = load_eval_set()
    files = set(eval_set.documents)
    assert {extraction.file for extraction in eval_set.extractions} <= files