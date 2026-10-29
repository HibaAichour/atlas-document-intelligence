"""Record the demo documents in the database, ready but not yet indexed.

Run when the production image is built (see the Dockerfile at the root of
the repository), from the backend folder:

    python -m scripts.seed_demo ../demo_documents

Each file of the folder is read exactly as an upload would read it (OCR for
the scanned invoice) and recorded with the status "ready" and its pages.
No embedding is computed: building the image needs neither the network nor
an API key. When the container starts, "python -m scripts.reindex" computes
the vectors from these pages with the online embedding provider.

The original files are not copied into the uploads folder: nothing reads
them after their text is extracted. A file already recorded under the same
name is left as it is, so running the script twice adds nothing. A file
that cannot be read stops nothing else, but the script then exits with an
error code, so that a broken demo document fails the image build.
"""

import argparse
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.repositories import DocumentRepository
from app.db.session import create_db_engine, create_session_factory, init_db, sqlite_url
from app.ingestion.file_types import UnsupportedFileError, detect_file_type
from app.ingestion.models import ParseError, ParseOptions
from app.ingestion.ocr import OCRError
from app.ingestion.parsing import parse_document
from app.ingestion.service import parse_options_from_settings


@dataclass
class SeedReport:
    """What happened to each file of the demo folder."""

    added: list[tuple[str, int, bool]] = field(default_factory=list)  # (filename, pages, OCR)
    existing: list[str] = field(default_factory=list)  # already in the database
    skipped: list[tuple[str, str]] = field(default_factory=list)  # not a supported document
    failed: list[tuple[str, str]] = field(default_factory=list)  # (filename, reason)


def seed_documents(
    session: Session,
    source_dir: Path,
    options: ParseOptions,
    log: Callable[[str], None] = print,
) -> SeedReport:
    """Record every supported file of source_dir as a ready document, in name order."""
    repository = DocumentRepository(session)
    known = {document.filename for document in repository.list_all()}
    report = SeedReport()
    for path in sorted(item for item in source_dir.iterdir() if item.is_file()):
        if path.name in known:
            report.existing.append(path.name)
            log(f"[KEEP] {path.name} (already recorded)")
            continue
        try:
            detected = detect_file_type(path, path.name)
        except UnsupportedFileError as error:
            report.skipped.append((path.name, str(error)))
            log(f"[SKIP] {path.name}: {error}")
            continue
        try:
            pages = parse_document(path, detected.file_type, options)
        except (ParseError, OCRError) as error:
            # Read before anything is stored: a broken file leaves no record.
            report.failed.append((path.name, str(error)))
            log(f"[FAIL] {path.name}: {error}")
            continue
        document = repository.create(path.name, detected.mime_type)
        repository.mark_ready(document, pages)
        ocr_used = any(page.ocr_used for page in pages)
        report.added.append((path.name, len(pages), ocr_used))
        log(f"[OK]   {path.name}: {len(pages)} pages{' (OCR)' if ocr_used else ''}")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    """Seed the database of DATA_DIR and return a process exit code (0 means success)."""
    parser = argparse.ArgumentParser(description="Record the demo documents, ready to index.")
    parser.add_argument("source", type=Path, help="folder of the demo documents")
    args = parser.parse_args(argv)
    source: Path = args.source
    if not source.is_dir():
        print(f"[FAIL] Not a folder: {source}")
        return 1

    settings = Settings()
    print(f"Source: {source.resolve()}")
    print(f"Data:   {settings.data_dir.resolve()}\n")
    engine = create_db_engine(sqlite_url(settings.data_dir))
    init_db(engine)
    try:
        with create_session_factory(engine)() as session:
            report = seed_documents(session, source, parse_options_from_settings(settings))
    finally:
        engine.dispose()

    print(
        f"\nAdded: {len(report.added)} | Already there: {len(report.existing)} "
        f"| Skipped: {len(report.skipped)} | Failed: {len(report.failed)}"
    )
    if report.failed:
        return 1
    if not report.added and not report.existing:
        print("[FAIL] No demo document found.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())