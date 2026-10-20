"""Split page texts into overlapping chunks that never cross a page boundary.

Each chunk keeps its page number and its position within the page, so every
search result (and later every citation) points to one exact page.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from app.ingestion.models import PageText

# Places where a chunk may end, from the most natural to the least natural.
# The chunker uses the first group that appears in the allowed window.
_BREAK_GROUPS: tuple[tuple[str, ...], ...] = (
    ("\n\n",),  # paragraph
    ("\n",),  # line
    (". ", "! ", "? ", "; "),  # sentence
    (" ", "\t"),  # word
)


@dataclass(frozen=True, slots=True)
class ChunkOptions:
    """Settings that control chunking (sizes are counted in characters)."""

    chunk_size: int = 1000
    chunk_overlap: int = 150

    def __post_init__(self) -> None:
        if self.chunk_size < 100:
            raise ValueError("chunk_size must be at least 100 characters.")
        if not 0 <= self.chunk_overlap < self.chunk_size // 2:
            raise ValueError("chunk_overlap must be between 0 and half of chunk_size.")


@dataclass(frozen=True, slots=True)
class TextChunk:
    """A piece of one page, ready to be stored and embedded."""

    page_number: int  # 1-based, same numbering as PageText
    position: int  # 0-based order of the chunk within its page
    text: str


def chunk_pages(pages: Iterable[PageText], options: ChunkOptions | None = None) -> list[TextChunk]:
    """Return the chunks of every page, in page order then position order.

    Pages with no visible text produce no chunk.
    """
    options = options or ChunkOptions()
    chunks: list[TextChunk] = []
    for page in pages:
        for position, text in enumerate(split_text(page.text, options)):
            chunks.append(TextChunk(page_number=page.page_number, position=position, text=text))
    return chunks


def split_text(text: str, options: ChunkOptions | None = None) -> list[str]:
    """Split one page of text into chunks of at most chunk_size characters.

    A chunk ends at the most natural break found in its second half
    (paragraph, line, sentence, then word). Only a single word longer than
    half a chunk forces a cut in the middle of a word. The next chunk starts
    about chunk_overlap characters earlier, at the beginning of a word.
    """
    options = options or ChunkOptions()
    text = text.strip()
    if not text:
        return []

    pieces: list[str] = []
    start = 0
    while start < len(text):
        hard_end = start + options.chunk_size
        if hard_end >= len(text):
            pieces.append(text[start:].strip())
            break

        end = _find_break(text, start + options.chunk_size // 2, hard_end)
        pieces.append(text[start:end].strip())
        start = _next_start(text, start, end, options.chunk_overlap)

    return [piece for piece in pieces if piece]


def _find_break(text: str, window_start: int, window_end: int) -> int:
    """Return the index right after the best break in text[window_start:window_end]."""
    window = text[window_start:window_end]
    for group in _BREAK_GROUPS:
        best = -1
        for separator in group:
            index = window.rfind(separator)
            if index != -1:
                best = max(best, index + len(separator))
        if best != -1:
            return window_start + best
    # No break at all (one very long word): cut at the maximum size.
    return window_end


def _next_start(text: str, start: int, end: int, overlap: int) -> int:
    """Return where the next chunk starts: overlap characters back, on a word start."""
    candidate = end - overlap
    if candidate <= start:
        return end
    # Move forward to the start of the next word, so no chunk begins mid-word.
    while candidate < end and not text[candidate - 1].isspace():
        candidate += 1
    # Skip the spaces themselves.
    while candidate < end and text[candidate].isspace():
        candidate += 1
    return candidate