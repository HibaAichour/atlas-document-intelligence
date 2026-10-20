"""Objects that FastAPI gives to the routes (database session, indexer, retriever)."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.retrieval.indexing import DocumentIndexer
from app.retrieval.retriever import Retriever


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


def get_retriever(indexer: Annotated[DocumentIndexer, Depends(get_indexer)]) -> Retriever:
    """Return a retriever that shares the indexer's embedder and vector store.

    Built from get_indexer, so search always uses the same embedding model,
    prefixes and index as indexing (and the same fake model in tests).
    """
    return Retriever(indexer.embedder, indexer.vector_store)