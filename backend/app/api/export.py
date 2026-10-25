"""Route that exports one saved answer or extraction as a Word or PowerPoint file."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.schemas import MessageOut
from app.api.sessions import DbSession, get_session_or_404
from app.db.repositories import SessionRepository
from app.export.content import (
    EXPORT_TEXTS,
    ExportFormat,
    ExportLanguage,
    NotExportableError,
    build_export,
    download_name,
)
from app.export.docx_export import render_docx
from app.export.pptx_export import render_pptx

router = APIRouter(prefix="/sessions", tags=["export"])

MESSAGE_NOT_FOUND = "Message not found."
NOT_EXPORTABLE = "Only an answer or an extraction can be exported."

MEDIA_TYPES: dict[str, str] = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def get_export_time() -> datetime:
    """The time written in the file and its name; replaced by a fixed time in tests."""
    return datetime.now(UTC)


ExportTime = Annotated[datetime, Depends(get_export_time)]


# Plain "def": building the file is CPU work, so it runs in a thread pool.
@router.get("/{session_id}/messages/{message_id}/export")
def export_message(
    session_id: str,
    message_id: str,
    db: DbSession,
    now: ExportTime,
    file_format: Annotated[ExportFormat, Query(alias="format")],
    language: Annotated[ExportLanguage, Query(alias="lang")] = "en",
) -> Response:
    """Return the answer or extraction as a .docx or .pptx file, sources included.

    lang (en or fr) sets the fixed texts of the file: headings, verdict, field
    labels, date. The question, the answer and the sources stay as written.

    The file is built from the saved message, in memory: no LLM call and
    nothing written on disk. A question or a refusal cannot be exported (409).
    """
    repository = SessionRepository(db)
    chat_session = get_session_or_404(repository, session_id)
    messages = repository.list_messages(chat_session.id)
    index = next((i for i, m in enumerate(messages) if m.id == message_id), None)
    if index is None:
        # Also when the message exists but belongs to another session.
        raise HTTPException(status.HTTP_404_NOT_FOUND, MESSAGE_NOT_FOUND)

    message = MessageOut.from_message(messages[index])
    # The request is the user message just before the answer.
    previous = messages[index - 1] if index > 0 else None
    question = (
        MessageOut.from_message(previous)
        if previous is not None and previous.role == "user"
        else None
    )
    try:
        content = build_export(message, question, chat_session.title, now, EXPORT_TEXTS[language])
    except NotExportableError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, NOT_EXPORTABLE) from error

    data = render_docx(content) if file_format == "docx" else render_pptx(content)
    filename = download_name(content.kind, now, file_format)
    return Response(
        content=data,
        media_type=MEDIA_TYPES[file_format],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )