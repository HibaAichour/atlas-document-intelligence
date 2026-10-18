"""ATLAS backend entry point."""

from fastapi import APIRouter, FastAPI

APP_VERSION = "0.1.0"

app = FastAPI(
    title="ATLAS API",
    description="Autonomous Multi-Agent Document Intelligence Platform",
    version=APP_VERSION,
)

# All API routes live under /api, so the frontend can call relative URLs
# like /api/health in every environment (Vite proxy, Nginx, single container).
api_router = APIRouter(prefix="/api")


@api_router.get("/health")
def health() -> dict[str, str]:
    """Return a minimal liveness status used by the frontend and Docker."""
    return {"status": "ok", "version": APP_VERSION}


# Routes must be declared on the router before it is included in the app.
app.include_router(api_router)