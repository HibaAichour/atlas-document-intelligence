"""Tests for the page-bounded chunker (pure functions, no database, no network)."""

import pytest

from app.ingestion.chunking import ChunkOptions, chunk_pages, split_text
from app.ingestion.models import PageText


def make_text(sentence_count: int) -> str:
    """Return English prose made of numbered sentences."""
    return " ".join(
        f"Sentence {number} describes the termination notice period of the contract."
        for number in range(1, sentence_count + 1)
    )


def test_empty_and_blank_pages_produce_no_chunk() -> None:
    pages = [PageText(1, ""), PageText(2, "   \n\t  ")]
    assert chunk_pages(pages) == []


def test_short_page_gives_one_chunk_at_position_zero() -> None:
    chunks = chunk_pages([PageText(3, "  A short page.  ")])
    assert len(chunks) == 1
    assert chunks[0].page_number == 3
    assert chunks[0].position == 0
    assert chunks[0].text == "A short page."


def test_long_page_respects_the_maximum_size() -> None:
    options = ChunkOptions(chunk_size=300, chunk_overlap=50)
    pieces = split_text(make_text(60), options)
    assert len(pieces) > 1
    assert all(len(piece) <= 300 for piece in pieces)


def test_chunks_never_cross_pages_and_positions_restart() -> None:
    pages = [PageText(1, make_text(40)), PageText(2, make_text(40))]
    chunks = chunk_pages(pages, ChunkOptions(chunk_size=400, chunk_overlap=60))

    for page_number in (1, 2):
        page_chunks = [chunk for chunk in chunks if chunk.page_number == page_number]
        assert [chunk.position for chunk in page_chunks] == list(range(len(page_chunks)))
        page_text = pages[page_number - 1].text
        assert all(chunk.text in page_text for chunk in page_chunks)


def test_chunks_prefer_to_end_at_a_sentence() -> None:
    pieces = split_text(make_text(60), ChunkOptions(chunk_size=300, chunk_overlap=50))
    # Every chunk except the last ends on a full sentence.
    assert all(piece.endswith(".") for piece in pieces[:-1])


def test_paragraph_break_is_preferred_over_sentence() -> None:
    first = make_text(3)  # about 230 characters
    second = make_text(5)
    pieces = split_text(f"{first}\n\n{second}", ChunkOptions(chunk_size=300, chunk_overlap=0))
    assert pieces[0] == first


def test_no_chunk_starts_or_ends_in_the_middle_of_a_word() -> None:
    text = make_text(60)
    words = set(text.split())
    pieces = split_text(text, ChunkOptions(chunk_size=250, chunk_overlap=80))
    for piece in pieces:
        piece_words = piece.split()
        assert piece_words[0] in words
        assert piece_words[-1] in words


def test_consecutive_chunks_overlap() -> None:
    pieces = split_text(make_text(60), ChunkOptions(chunk_size=300, chunk_overlap=100))
    for previous, following in zip(pieces, pieces[1:]):
        first_words = " ".join(following.split()[:3])
        assert first_words in previous


def test_without_overlap_every_word_appears_exactly_once() -> None:
    text = make_text(60)
    pieces = split_text(text, ChunkOptions(chunk_size=300, chunk_overlap=0))
    rebuilt = " ".join(" ".join(pieces).split())
    assert rebuilt == " ".join(text.split())


def test_with_overlap_no_text_is_lost() -> None:
    text = make_text(60)
    pieces = split_text(text, ChunkOptions(chunk_size=300, chunk_overlap=100))
    for number in range(1, 61):
        assert any(f"Sentence {number} " in piece for piece in pieces)


def test_a_single_huge_word_is_cut_at_the_maximum_size() -> None:
    text = "x" * 2500
    pieces = split_text(text, ChunkOptions(chunk_size=1000, chunk_overlap=150))
    assert all(len(piece) <= 1000 for piece in pieces)
    assert "".join(pieces) == text  # no overlap is possible inside one word


@pytest.mark.parametrize(
    ("size", "overlap"),
    [(50, 0), (1000, 500), (1000, -1)],
)
def test_invalid_options_are_refused(size: int, overlap: int) -> None:
    with pytest.raises(ValueError):
        ChunkOptions(chunk_size=size, chunk_overlap=overlap)


def test_default_options_match_the_architecture() -> None:
    options = ChunkOptions()
    assert (options.chunk_size, options.chunk_overlap) == (1000, 150)