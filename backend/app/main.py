"""ATLAS backend entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from app.api.documents import router as documents_router
from app.core.config import get_settings
from app.db.session import create_db_engine, create_session_factory, init_db, sqlite_url

APP_VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open the database when the server starts and close it when it stops."""
    settings = get_settings()
    engine = create_db_engine(sqlite_url(settings.data_dir))
    init_db(engine)
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
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

# Routes must be declared on the router before it is included in the app.
app.include_router(api_router)