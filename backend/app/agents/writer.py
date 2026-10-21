"""Writer agent: answers a question from numbered passages, citing them.

The model only sees the passage identifiers [S1]...[Sn], never the file names
or page numbers, so it cannot invent a source: the code converts the cited
identifiers afterwards (app.rag.citations). When the passages do not contain
the answer, the model must reply with the NOT_FOUND keyword, which the code
detects; the message shown to the user is written by the code, not the model.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from app.llm.base import ChatMessage, LLMError, LLMProvider
from app.rag.citations import CitationResult, number_passages, resolve_citations
from app.retrieval.retriever import RetrievedPassage

NOT_FOUND = "NOT_FOUND"

SYSTEM_PROMPT = f"""You answer questions using only the numbered passages you are given.

Rules:
1. Use only facts written in the passages. Never use outside knowledge.
2. After each sentence, cite the passages it comes from, like [S1] or [S2, S3].
3. If the passages do not contain the answer, reply with exactly: {NOT_FOUND}
4. Be concise: a few sentences, in the language of the question."""

# The answer starts with the keyword, even decorated: "**NOT_FOUND**", "`not found`.".
_STARTS_WITH_REFUSAL = re.compile(r"^[\s\"'`*_>:.-]*NOT[\s_]FOUND\b", re.IGNORECASE)
# The exact keyword anywhere ("Sorry, NOT_FOUND."). Plain words such as
# "not found" inside a sentence are not treated as a refusal.
_REFUSAL_KEYWORD = re.compile(rf"\b{NOT_FOUND}\b")


@dataclass(frozen=True, slots=True)
class WriterResult:
    """What the Writer produced for one question."""

    raw_answer: str  # the model's reply, unchanged (kept for the trace)
    refused: bool  # True when the model said the passages lack the answer
    answer: CitationResult | None  # checked citations; None when refused


class Writer:
    """Turns retrieved passages into a short, cited answer."""

    name = "writer"

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    def build_messages(
        self, question: str, passages: Sequence[RetrievedPassage]
    ) -> list[ChatMessage]:
        """Return the prompt: the rules, then the numbered passages and the question."""
        blocks = [
            f"[{label}]\n{passage.text.strip()}" for label, passage in number_passages(passages)
        ]
        user_content = (
            "Passages:\n\n" + "\n\n".join(blocks) + f"\n\nQuestion: {question.strip()}"
        )
        return [
            ChatMessage(role="system", content=SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_content),
        ]

    def write(self, question: str, passages: Sequence[RetrievedPassage]) -> WriterResult:
        """Ask the model for a cited answer and check its citations.

        Raises:
            ValueError: If no passage is given (the caller refuses before).
            LLMError: If the model fails or returns an empty reply.
        """
        if not passages:
            raise ValueError("The Writer needs at least one passage")

        messages = self.build_messages(question, passages)
        raw_answer = self._llm.generate(messages, temperature=0.0)
        if not raw_answer.strip():
            raise LLMError("The language model returned an empty answer")

        answer = resolve_citations(raw_answer, passages)
        has_citation = bool(answer.citations or answer.invalid_labels)
        refused = bool(_STARTS_WITH_REFUSAL.match(raw_answer)) or (
            not has_citation and bool(_REFUSAL_KEYWORD.search(raw_answer))
        )
        return WriterResult(
            raw_answer=raw_answer, refused=refused, answer=None if refused else answer
        )