"""Objects that FastAPI gives to the routes (database session, indexer)."""

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from app.retrieval.indexing import DocumentIndexer


def get_db(request: Request) -> Iterator[Session]:
    """Open one database session per request, closed when the request ends."""
    with request.app.state.session_factory() as session:
        yield session


def get_indexer(request: Request) -> DocumentIndexer:
    """Return the indexer created when the server started.

    Tests replace it with an indexer that uses a fake embedding model.
    """
    indexer: DocumentIndexer = request.app.state.indexer
    return indexer