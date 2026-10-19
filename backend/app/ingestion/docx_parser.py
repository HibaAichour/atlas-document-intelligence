"""Read DOCX files as heading-based sections.

The DOCX format stores no reliable page numbers (pages are computed by Word
when it displays the file), so each section that starts with a heading is
numbered like a page. This limitation is documented in the README.
"""

from pathlib import Path

import docx
from docx.document import Document as DocxDocument
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.ingestion.models import PageText, ParseError, ParseOptions
from app.ingestion.text import clean_text


def parse_docx(path: Path, options: ParseOptions) -> list[PageText]:
    """Return one PageText per section, in reading order (tables included)."""
    try:
        document = docx.Document(str(path))
    except Exception as error:  # A damaged file can fail in many different ways.
        raise ParseError(f"Cannot open the DOCX file ({error}).") from error

    sections = _split_into_sections(document)
    if len(sections) > options.max_pages:
        raise ParseError(
            f"The DOCX has {len(sections)} sections; the limit is {options.max_pages}."
        )
    return [
        PageText(page_number=number, text=clean_text("\n".join(lines)))
        for number, lines in enumerate(sections, start=1)
    ]


def _split_into_sections(document: DocxDocument) -> list[list[str]]:
    sections: list[list[str]] = []
    current: list[str] = []
    for block in document.iter_inner_content():
        if isinstance(block, Paragraph):
            text = block.text.strip()
            if not text:
                continue
            # A heading starts a new section, unless the current one is still empty.
            if _is_heading(block) and current:
                sections.append(current)
                current = []
            current.append(text)
        elif isinstance(block, Table):
            current.extend(_table_lines(block))
    if current:
        sections.append(current)
    return sections


def _is_heading(paragraph: Paragraph) -> bool:
    style_name = (paragraph.style.name if paragraph.style is not None else "") or ""
    return style_name.lower().startswith(("heading", "title"))


def _table_lines(table: Table) -> list[str]:
    """One line per row, cells separated by " | "."""
    lines = []
    for row in table.rows:
        cells = [cell.text.strip() for cell in row.cells]
        if any(cells):
            lines.append(" | ".join(cells))
    return lines