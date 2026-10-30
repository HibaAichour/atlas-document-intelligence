"""Provider-agnostic interface for text generation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class ChatMessage:
    """One message of a conversation sent to a language model."""

    role: Role
    content: str


class LLMError(Exception):
    """Raised when a provider cannot return a completion.

    rate_limited is True when an online provider refused the call because a
    usage limit was reached (HTTP 429): the API then answers 429, not 503.
    """

    def __init__(self, message: str, *, rate_limited: bool = False) -> None:
        super().__init__(message)
        self.rate_limited = rate_limited


class LLMProvider(ABC):
    """Common interface implemented by every text generation provider."""

    name: str

    @abstractmethod
    def generate(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.0,
        json_mode: bool = False,
    ) -> str:
        """Return the model's reply to the conversation.

        Args:
            messages: The conversation, oldest message first.
            temperature: Sampling temperature; 0 gives the most stable answers.
            json_mode: Ask the provider to return a valid JSON object.

        Raises:
            LLMError: If the provider is unreachable or answers unexpectedly.
        """