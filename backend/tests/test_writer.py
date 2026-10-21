"""The Writer builds a numbered prompt, detects refusals and checks citations."""

import pytest

from app.agents.writer import NOT_FOUND, SYSTEM_PROMPT, Writer
from app.llm.base import LLMError
from app.retrieval.retriever import RetrievedPassage

QUESTION = "What is the termination notice period?"


def make_passage(chunk_id: str, page_number: int, text: str) -> RetrievedPassage:
    return RetrievedPassage(
        chunk_id=chunk_id,
        document_id="doc-1",
        filename="contract.pdf",
        page_number=page_number,
        position=0,
        text=text,
        score=0.8,
    )


PASSAGES = [
    make_passage("c1", 4, "Either party may terminate with 30 days written notice."),
    make_passage("c2", 2, "The agreement starts on 1 March 2026."),
]


def test_prompt_numbers_the_passages_and_hides_file_names(fake_llm) -> None:
    messages = Writer(fake_llm).build_messages(f"  {QUESTION} ", PASSAGES)

    assert [m.role for m in messages] == ["system", "user"]
    assert messages[0].content == SYSTEM_PROMPT
    assert NOT_FOUND in SYSTEM_PROMPT
    user = messages[1].content
    assert "[S1]\nEither party may terminate with 30 days written notice." in user
    assert "[S2]\nThe agreement starts on 1 March 2026." in user
    assert user.index("[S1]") < user.index("[S2]")
    assert user.endswith(f"Question: {QUESTION}")
    # The model never sees sources it could copy wrongly or invent.
    assert "contract.pdf" not in user
    assert "page" not in user.lower()


def test_a_cited_answer_is_checked_and_converted(fake_llm) -> None:
    fake_llm.replies.append("The notice period is 30 days [S1].")

    result = Writer(fake_llm).write(QUESTION, PASSAGES)

    assert result.refused is False
    assert result.raw_answer == "The notice period is 30 days [S1]."
    assert result.answer is not None
    assert result.answer.text == "The notice period is 30 days [contract.pdf, p. 4]."
    assert [c.passage.chunk_id for c in result.answer.citations] == ["c1"]
    assert len(fake_llm.calls) == 1
    assert fake_llm.calls[0].temperature == 0.0
    assert fake_llm.calls[0].json_mode is False


@pytest.mark.parametrize(
    "reply",
    [
        "NOT_FOUND",
        "not_found",
        "  NOT_FOUND.\n",
        "**NOT_FOUND**",
        "`NOT_FOUND`",
        "Not found.",
        "NOT_FOUND\nThe passages do not mention the salary.",
        "I am sorry, NOT_FOUND.",
    ],
)
def test_refusals_are_detected(fake_llm, reply: str) -> None:
    fake_llm.replies.append(reply)

    result = Writer(fake_llm).write("What is the CEO's salary?", PASSAGES)

    assert result.refused is True
    assert result.answer is None
    assert result.raw_answer == reply


def test_the_words_not_found_inside_an_answer_are_not_a_refusal(fake_llm) -> None:
    fake_llm.replies.append("Defects not found at delivery are covered for 90 days.")

    result = Writer(fake_llm).write("What about hidden defects?", PASSAGES)

    assert result.refused is False
    assert result.answer is not None
    assert result.answer.citations == []


def test_a_cited_answer_mentioning_the_keyword_is_not_a_refusal(fake_llm) -> None:
    fake_llm.replies.append("The notice is 30 days [S1]. The penalty: NOT_FOUND.")

    result = Writer(fake_llm).write(QUESTION, PASSAGES)

    assert result.refused is False


def test_invented_citations_are_reported(fake_llm) -> None:
    fake_llm.replies.append("The notice period is 30 days [S7].")

    result = Writer(fake_llm).write(QUESTION, PASSAGES)

    assert result.answer is not None
    assert result.answer.text == "The notice period is 30 days."
    assert result.answer.invalid_labels == ["S7"]


def test_without_passages_the_model_is_not_called(fake_llm) -> None:
    with pytest.raises(ValueError):
        Writer(fake_llm).write(QUESTION, [])
    assert fake_llm.calls == []


def test_an_empty_reply_is_an_error(fake_llm) -> None:
    fake_llm.replies.append("   \n")

    with pytest.raises(LLMError, match="empty answer"):
        Writer(fake_llm).write(QUESTION, PASSAGES)


def test_a_model_that_is_down_raises_llm_error(fake_llm) -> None:
    fake_llm.unavailable = True

    with pytest.raises(LLMError, match="connection refused"):
        Writer(fake_llm).write(QUESTION, PASSAGES)