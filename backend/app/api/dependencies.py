"""Objects that FastAPI gives to the routes (database, indexer, retriever, LLM, agents)."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.agents.orchestrator import Orchestrator
from app.agents.writer import Writer
from app.core.config import Settings, get_settings
from app.llm.base import LLMProvider
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


def get_llm_provider(request: Request) -> LLMProvider:
    """Return the text generation provider created when the server started.

    Tests replace it with a fake model that returns scripted replies.
    """
    llm: LLMProvider = request.app.state.llm
    return llm


def get_orchestrator(
    retriever: Annotated[Retriever, Depends(get_retriever)],
    llm: Annotated[LLMProvider, Depends(get_llm_provider)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Orchestrator:
    """Return the Orchestrator with its agents, the retriever and the threshold.

    Built for each request from objects created at startup, so it is cheap,
    and tests get the fake embedding model and the fake LLM automatically.
    """
    return Orchestrator(retriever, Writer(llm), min_score=settings.retrieval_min_score)