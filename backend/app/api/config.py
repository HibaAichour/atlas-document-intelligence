"""Route that tells the interface how this deployment is configured."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.schemas import ConfigOut
from app.core.config import Settings, get_settings

router = APIRouter(prefix="/config", tags=["config"])


@router.get("")
def get_config(settings: Annotated[Settings, Depends(get_settings)]) -> ConfigOut:
    """Return the demo mode and the kind of LLM provider (never a URL or a key)."""
    return ConfigOut(demo_mode=settings.demo_mode, llm_provider=settings.llm_provider)