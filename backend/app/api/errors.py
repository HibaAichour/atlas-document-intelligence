"""HTTP errors for a failed call to the language model or the embedding service."""

from fastapi import HTTPException, status

RATE_LIMIT_DETAIL = "The usage limit of the online provider was reached. Try again in a minute."


def is_rate_limited(error: BaseException) -> bool:
    """True when the error, or an error it wraps, comes from a usage limit (HTTP 429).

    The flag can sit deeper than the error the route catches: a RetrievalError
    wraps the EmbeddingError raised by the provider ("raise ... from error").
    So the chain of causes is followed until an error carries the flag.
    """
    current: BaseException | None = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        if getattr(current, "rate_limited", False):
            return True
        seen.add(id(current))
        current = current.__cause__
    return False


def service_error(error: BaseException, detail: str) -> HTTPException:
    """The HTTP error for a service that did not answer: 429 if rate limited, else 503.

    Args:
        error: The error raised by the orchestrator or the retriever.
        detail: The message of the 503. A 429 gets a fixed message instead, so
            the provider's own text (account identifiers, limits) is never shown.
    """
    if is_rate_limited(error):
        return HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, RATE_LIMIT_DETAIL)
    return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail)