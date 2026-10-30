"""Readable messages for HTTP errors raised by provider calls."""

import httpx2

MAX_DETAIL_LENGTH = 300


def describe_http_error(exc: httpx2.HTTPError) -> str:
    """Describe an HTTP error, with the reason given by the server when available."""
    if isinstance(exc, httpx2.HTTPStatusError):
        detail = exc.response.text.strip()
        if len(detail) > MAX_DETAIL_LENGTH:
            detail = detail[:MAX_DETAIL_LENGTH] + "..."
        return f"HTTP {exc.response.status_code} from {exc.request.url}: {detail or 'no details'}"
    return str(exc)


def is_too_many_requests(exc: httpx2.HTTPError) -> bool:
    """True when the server answered 429 Too Many Requests (a usage limit was reached)."""
    return (
        isinstance(exc, httpx2.HTTPStatusError)
        and exc.response.status_code == httpx2.codes.TOO_MANY_REQUESTS
    )
