"""Tests for the text cleaning helpers."""

from app.ingestion.text import clean_text, visible_char_count


def test_clean_text_normalises_line_endings_and_blank_lines() -> None:
    """Windows line endings, trailing spaces and long gaps are tidied up."""
    raw = "  Title  \r\nLine one   \r\n\r\n\r\n\r\nLine two\x00\x0c"

    assert clean_text(raw) == "Title\nLine one\n\nLine two"


def test_clean_text_keeps_words_unchanged() -> None:
    """Words, numbers and punctuation are never modified."""
    raw = "Total: USD 1,200.50 (due 2026-11-30)"

    assert clean_text(raw) == raw


def test_visible_char_count_ignores_blank_space() -> None:
    """Spaces, tabs and line breaks are not counted."""
    assert visible_char_count(" a b\n\tc ") == 3