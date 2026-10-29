"""Tests for the demo seeding script (real parsers, fake embeddings for the re-index)."""

from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import DocumentStatus
from app.db.repositories import DocumentRepository
from app.db.session import create_db_engine, create_session_factory, sqlite_url
from app.ingestion.models import ParseOptions
from app.ingestion.ocr import is_tesseract_available
from app.retrieval.indexing import DocumentIndexer
from scripts.reindex import reindex_documents
from scripts.seed_demo import main, seed_documents
from tests.builders import CONTRACT_TEXT, make_pdf, make_pptx

DEMO_DIR = Path(__file__).resolve().parents[2] / "demo_documents"


def demo_folder(tmp_path: Path) -> Path:
    """A small demo folder: a text PDF, a PPTX and a file that is not a document."""
    folder = tmp_path / "demo"
    folder.mkdir()
    make_pdf(folder / "contract.pdf", [CONTRACT_TEXT, "Payment is due within 15 days."])
    make_pptx(folder / "review.pptx")
    (folder / ".DS_Store").write_bytes(b"\x00\x01binary")
    return folder


def test_documents_are_ready_with_pages_and_no_chunks(db_session: Session, tmp_path: Path) -> None:
    messages: list[str] = []

    report = seed_documents(db_session, demo_folder(tmp_path), ParseOptions(), messages.append)

    assert [name for name, _, _ in report.added] == ["contract.pdf", "review.pptx"]
    assert [name for name, _ in report.skipped] == [".DS_Store"]
    assert report.failed == [] and report.existing == []
    repository = DocumentRepository(db_session)
    documents = {document.filename: document for document in repository.list_all()}
    contract = documents["contract.pdf"]
    assert contract.status == DocumentStatus.READY
    assert contract.page_count == 2
    assert [page.page_number for page in repository.list_pages(contract.id)] == [1, 2]
    # Not indexed yet: the container start computes the vectors.
    assert repository.list_chunks(contract.id) == []
    assert len(messages) == 3


def test_running_twice_adds_nothing(db_session: Session, tmp_path: Path) -> None:
    folder = demo_folder(tmp_path)
    seed_documents(db_session, folder, ParseOptions(), lambda _: None)

    report = seed_documents(db_session, folder, ParseOptions(), lambda _: None)

    assert report.added == []
    assert report.existing == ["contract.pdf", "review.pptx"]
    assert len(DocumentRepository(db_session).list_all()) == 2


def test_an_unreadable_file_is_reported_and_not_recorded(
    db_session: Session, tmp_path: Path
) -> None:
    folder = demo_folder(tmp_path)
    # Starts like a PDF, so it is accepted as one, but cannot be parsed.
    (folder / "broken.pdf").write_bytes(b"%PDF-1.7\nnot a real pdf")

    report = seed_documents(db_session, folder, ParseOptions(), lambda _: None)

    assert [name for name, _ in report.failed] == ["broken.pdf"]
    assert [name for name, _, _ in report.added] == ["contract.pdf", "review.pptx"]
    filenames = [document.filename for document in DocumentRepository(db_session).list_all()]
    assert "broken.pdf" not in filenames


def test_reindex_then_makes_the_seeded_documents_searchable(
    db_session: Session, tmp_path: Path, indexer: DocumentIndexer
) -> None:
    """The container start: the existing re-index script indexes the seeded pages."""
    seed_documents(db_session, demo_folder(tmp_path), ParseOptions(), lambda _: None)

    report = reindex_documents(db_session, indexer, log=lambda _: None)

    assert sorted(name for name, _ in report.indexed) == ["contract.pdf", "review.pptx"]
    assert report.failed == []
    assert indexer.vector_store.count() > 0


def test_main_seeds_the_data_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    data = tmp_path / "data"
    monkeypatch.setenv("DATA_DIR", str(data))
    get_settings.cache_clear()

    assert main([str(demo_folder(tmp_path))]) == 0
    assert "Added: 2" in capsys.readouterr().out
    engine = create_db_engine(sqlite_url(data))
    with create_session_factory(engine)() as session:
        assert len(DocumentRepository(session).list_all()) == 2
    engine.dispose()


def test_main_fails_on_a_broken_document(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    folder = demo_folder(tmp_path)
    (folder / "broken.pdf").write_bytes(b"%PDF-1.7\nnot a real pdf")

    assert main([str(folder)]) == 1


def test_main_fails_without_documents(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    empty = tmp_path / "empty"
    empty.mkdir()

    assert main([str(empty)]) == 1
    assert main([str(tmp_path / "missing")]) == 1


@pytest.mark.skipif(not is_tesseract_available(), reason="Tesseract is not installed")
def test_the_real_demo_documents_are_all_readable(db_session: Session) -> None:
    """What the image build does: the four demo documents, the invoice through OCR."""
    report = seed_documents(db_session, DEMO_DIR, ParseOptions(), lambda _: None)

    assert report.failed == []
    added = {name: (pages, ocr) for name, pages, ocr in report.added}
    assert set(added) == {
        "compte_rendu_copil_HDS_2026-07.pdf",
        "invoice_HDS-INV-2026-0042.pdf",
        "quarterly_review_HDS_Q2_2026.pptx",
        "service_agreement.pdf",
    }
    assert added["invoice_HDS-INV-2026-0042.pdf"] == (1, True)
    assert added["service_agreement.pdf"] == (6, False)