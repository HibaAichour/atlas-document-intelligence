"""ATLAS backend entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from app.api.ask import router as ask_router
from app.api.documents import router as documents_router
from app.api.search import router as search_router
from app.core.config import get_settings
from app.core.providers import build_document_indexer, build_llm_provider
from app.db.session import create_db_engine, create_session_factory, init_db, sqlite_url

APP_VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open the database, the vector store and the LLM client when the server starts."""
    settings = get_settings()
    engine = create_db_engine(sqlite_url(settings.data_dir))
    init_db(engine)
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    # No call to the embedding service or the LLM here: the server starts even
    # if Ollama is not running (requests will then fail with a clear reason).
    app.state.indexer = build_document_indexer(settings)
    app.state.llm = build_llm_provider(settings)
    yield
    engine.dispose()


app = FastAPI(
    title="ATLAS API",
    description="Autonomous Multi-Agent Document Intelligence Platform",
    version=APP_VERSION,
    lifespan=lifespan,
)

# All API routes live under /api, so the frontend can call relative URLs
# like /api/health in every environment (Vite proxy, Nginx, single container).
api_router = APIRouter(prefix="/api")


@api_router.get("/health")
def health() -> dict[str, str]:
    """Return a minimal liveness status used by the frontend and Docker."""
    return {"status": "ok", "version": APP_VERSION}


api_router.include_router(documents_router)
api_router.include_router(search_router)
api_router.include_router(ask_router)

# Routes must be declared on the router before it is included in the app.
app.include_router(api_router)