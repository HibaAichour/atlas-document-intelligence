"""Small helpers to clean extracted text."""

import re

_SPACES_BEFORE_NEWLINE = re.compile(r"[ \t]+\n")
_MANY_BLANK_LINES = re.compile(r"\n{3,}")


def clean_text(text: str) -> str:
    """Normalise line endings and blank space, without changing the words.

    Keeping the words untouched matters: citations must match the source.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Remove characters that are invisible but break storage or display.
    text = text.replace("\x00", "").replace("\x0c", "\n")
    text = _SPACES_BEFORE_NEWLINE.sub("\n", text)
    text = _MANY_BLANK_LINES.sub("\n\n", text)
    return text.strip()


def visible_char_count(text: str) -> int:
    """Count the characters that are not blank space."""
    return sum(1 for char in text if not char.isspace())