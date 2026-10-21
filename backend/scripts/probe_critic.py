"""Measure how reliably the model judges whether a sentence is supported.

The Critic's model check flagged correct sentences of the demo contract as
unsupported. This script compares four ways of asking, on sentences whose
answer is known, taken from page 4 of service_agreement.pdf:

1. current:      the Critic's prompt, a list of unsupported sentence numbers,
                 with 5 passages (page 4 plus other pages, as a real search returns).
2. per_sentence: one true/false verdict per sentence, same 5 passages.
3. cited_only:   one verdict per sentence, only the page 4 passages.
4. with_context: like cited_only, with the question and the full answer shown
                 first, so a sentence such as "it is 60 days" can be understood.

Run it with Ollama started (the backend can keep running: it only reads SQLite):
    python -m scripts.probe_critic
"""

import json
import time
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

from app.agents.critic import Critic, Sentence
from app.core.config import get_settings
from app.core.providers import build_llm_provider
from app.db.models import Chunk, DocumentStatus
from app.db.repositories import DocumentRepository
from app.db.session import create_db_engine, create_session_factory, sqlite_url
from app.llm.base import ChatMessage, LLMError, LLMProvider
from app.rag.citations import number_passages
from app.retrieval.retriever import RetrievedPassage

CONTRACT = "service_agreement.pdf"
PAGE = 4
# Words that must appear on page 4 for the expected answers below to be right.
GROUND_TRUTH_WORDS = ["insolvent", "Client Data", "60 days", "two Monthly Fees"]

# Three answers of three sentences, mixing supported (True) and unsupported
# (False) sentences, as the Writer would write them, with their question.
# The third one is the real answer qwen2.5:3b gave for demo scenario 1: "30 days"
# is the time to remedy a breach (4.4), not a notice period.
ANSWERS: list[tuple[str, list[tuple[str, bool]]]] = [
    (
        "When can the Agreement end, and what happens to the Client Data?",
        [
            (
                "Either Party may terminate the Agreement with immediate effect if the other "
                "Party becomes insolvent.",
                True,
            ),
            (
                "The Provider must return all Client Data within 90 days of the termination date.",
                False,
            ),
            (
                "The Provider must return all Client Data within 30 days of the termination date.",
                True,
            ),
        ],
    ),
    (
        "What are the conditions of termination?",
        [
            (
                "Either Party may terminate the Agreement with immediate effect if the other "
                "Party is late with one payment.",
                False,
            ),
            (
                "The Provider shall provide reasonable transition assistance for up to 60 days "
                "after termination.",
                True,
            ),
            (
                "The Client must pay an early termination fee equal to three Monthly Fees.",
                False,
            ),
        ],
    ),
    (
        "What is the termination notice period?",
        [
            ("The termination notice period for a material breach is 30 days.", False),
            ("For convenience termination, it is 60 days.", True),
            ("For cause termination, it is also 30 days.", False),
        ],
    ),
]

PER_SENTENCE_PROMPT = """You check an answer against numbered passages.

For each numbered sentence of the answer, decide whether a passage clearly states it.
A sentence whose number, name or condition differs from the passages is not supported.
Reply with JSON only, with one entry for every sentence, in this exact form:
{"sentences": [{"n": <sentence number>, "supported": <true or false>}]}"""


CONTEXT_PROMPT = """You check an answer against numbered passages.

Read the question and the full answer first. Then, for each numbered sentence,
decide whether a passage clearly states it, understanding the sentence in the
context of the question and of the sentences before it.
A sentence whose number, name or condition differs from the passages is not supported.
Reply with JSON only, with one entry for every sentence, in this exact form:
{"sentences": [{"n": <sentence number>, "supported": <true or false>}]}"""


class _PerSentence(BaseModel):
    class Entry(BaseModel):
        n: int
        supported: bool

    sentences: list[Entry]


@dataclass
class Score:
    """How one way of asking did on every sentence."""

    correct: int = 0
    false_alarms: int = 0  # a supported sentence flagged as unsupported
    misses: int = 0  # an unsupported sentence accepted
    unusable: int = 0  # no usable verdict for the sentence
    seconds: float = 0.0


def to_passage(chunk: Chunk) -> RetrievedPassage:
    return RetrievedPassage(
        chunk_id=chunk.id,
        document_id=chunk.document_id,
        filename=CONTRACT,
        page_number=chunk.page_number,
        position=chunk.position,
        text=chunk.text,
        score=1.0,
    )


def load_passages() -> tuple[list[RetrievedPassage], list[RetrievedPassage]]:
    """The page 4 passages, and 5 passages: page 4 completed with other pages."""
    settings = get_settings()
    engine = create_db_engine(sqlite_url(settings.data_dir))
    with create_session_factory(engine)() as db:
        repository = DocumentRepository(db)
        contract = next(
            (
                document
                for document in repository.list_all()
                if document.filename == CONTRACT and document.status == DocumentStatus.READY
            ),
            None,
        )
        if contract is None:
            raise SystemExit(f"{CONTRACT} is not in the database: upload it first.")
        chunks = repository.list_chunks(contract.id)
    engine.dispose()
    cited = [to_passage(chunk) for chunk in chunks if chunk.page_number == PAGE]
    if not cited:
        raise SystemExit(f"{CONTRACT} has no text on page {PAGE}.")
    # Like a real search: the page that answers, plus passages from other pages.
    others = [to_passage(chunk) for chunk in chunks if chunk.page_number != PAGE]
    return cited, cited + others[: max(0, 5 - len(cited))]


def ask_current(llm: LLMProvider, question, sentences, passages) -> dict[int, bool]:
    """The Critic's current prompt: the numbers of the unsupported sentences."""
    messages = Critic(llm).build_messages(sentences, passages)
    reply = llm.generate(messages, temperature=0.0, json_mode=True)
    flagged = set(json.loads(reply)["unsupported"])
    return {n: n not in flagged for n in range(1, len(sentences) + 1)}


def _per_sentence(llm: LLMProvider, prompt: str, context: str, sentences, passages):
    blocks = [f"[{label}]\n{p.text.strip()}" for label, p in number_passages(passages)]
    numbered = [f"{n}. {s.text}" for n, s in enumerate(sentences, 1)]
    messages = [
        ChatMessage(role="system", content=prompt),
        ChatMessage(
            role="user",
            content="Passages:\n\n"
            + "\n\n".join(blocks)
            + context
            + "\n\nAnswer sentences:\n"
            + "\n".join(numbered),
        ),
    ]
    reply = llm.generate(messages, temperature=0.0, json_mode=True)
    parsed = _PerSentence.model_validate(json.loads(reply))
    return {entry.n: entry.supported for entry in parsed.sentences}


def ask_per_sentence(llm: LLMProvider, question, sentences, passages) -> dict[int, bool]:
    """One true/false verdict per sentence."""
    return _per_sentence(llm, PER_SENTENCE_PROMPT, "", sentences, passages)


def ask_with_context(llm: LLMProvider, question, sentences, passages) -> dict[int, bool]:
    """One verdict per sentence, after the question and the full answer."""
    full_answer = " ".join(sentence.text for sentence in sentences)
    context = f"\n\nQuestion: {question}\nFull answer: {full_answer}"
    return _per_sentence(llm, CONTEXT_PROMPT, context, sentences, passages)


def run(name, ask, llm, passages) -> Score:
    score = Score()
    print(f"\n=== {name} ({len(passages)} passages) ===")
    for question, answer in ANSWERS:
        sentences = [Sentence(text=text, cited=True) for text, _ in answer]
        start = time.perf_counter()
        try:
            verdicts = ask(llm, question, sentences, passages)
        except (LLMError, json.JSONDecodeError, ValidationError, KeyError, TypeError) as error:
            print(f"  unusable reply: {type(error).__name__}")
            verdicts = {}
        score.seconds += time.perf_counter() - start
        for n, (text, expected) in enumerate(answer, 1):
            got = verdicts.get(n)
            if got is None:
                score.unusable += 1
                mark = "?"
            elif got == expected:
                score.correct += 1
                mark = "ok"
            elif expected:
                score.false_alarms += 1
                mark = "FALSE ALARM"
            else:
                score.misses += 1
                mark = "MISSED"
            label = "supported" if expected else "unsupported"
            print(f"  [{mark:>11}] expected {label:<11} | {text[:70]}")
    return score


def main() -> None:
    cited, with_others = load_passages()
    # Shown so the expected answers can be checked against the real text.
    for passage in cited:
        print(f"--- page {PAGE}, passage {passage.position} ---\n{passage.text.strip()}\n")
    page_text = " ".join(" ".join(p.text for p in cited).split())  # line breaks ignored
    missing = [word for word in GROUND_TRUTH_WORDS if word not in page_text]
    if missing:
        print(f"Warning: page {PAGE} does not contain {missing}; check the expected answers.")
    llm = build_llm_provider(get_settings())
    total = sum(len(answer) for _, answer in ANSWERS)
    results = {
        "current": run("current", ask_current, llm, with_others),
        "per_sentence": run("per_sentence", ask_per_sentence, llm, with_others),
        "cited_only": run("cited_only", ask_per_sentence, llm, cited),
        "with_context": run("with_context", ask_with_context, llm, cited),
    }
    header = f"{'variant':<14}{'correct':>9}{'false alarms':>14}{'misses':>8}"
    print(f"\n{header}{'unusable':>10}{'time':>8}")
    for name, s in results.items():
        print(
            f"{name:<14}{s.correct:>6}/{total}{s.false_alarms:>14}{s.misses:>8}"
            f"{s.unusable:>10}{s.seconds:>7.1f}s"
        )


if __name__ == "__main__":
    main()