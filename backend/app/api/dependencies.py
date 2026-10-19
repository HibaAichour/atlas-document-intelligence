"""Objects that FastAPI gives to the routes (database session, settings)."""

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session


def get_db(request: Request) -> Iterator[Session]:
    """Open one database session per request, closed when the request ends."""
    with request.app.state.session_factory() as session:
        yield session