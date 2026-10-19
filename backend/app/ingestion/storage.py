"""Save uploaded files on disk without ever loading them fully in memory."""

import shutil
import uuid
from pathlib import Path
from typing import BinaryIO

CHUNK_SIZE = 1024 * 1024  # 1 MB
UPLOADS_FOLDER = "uploads"


class FileTooLargeError(Exception):
    """The upload exceeds the size limit. Safe to show to the user."""


def uploads_dir(data_dir: Path) -> Path:
    """Return the folder where uploaded files are kept, creating it if needed."""
    folder = data_dir / UPLOADS_FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def save_to_temporary_file(source: BinaryIO, folder: Path, max_bytes: int) -> Path:
    """Copy source into a new file in folder, chunk by chunk, enforcing max_bytes.

    The partial file is deleted if the limit is exceeded.
    """
    destination = folder / f"incoming-{uuid.uuid4()}.part"
    written = 0
    try:
        with destination.open("wb") as target:
            while chunk := source.read(CHUNK_SIZE):
                written += len(chunk)
                if written > max_bytes:
                    raise FileTooLargeError(
                        f"The file is larger than the {max_bytes // (1024 * 1024)} MB limit."
                    )
                target.write(chunk)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return destination


def move_into_place(temporary: Path, folder: Path, document_id: str, extension: str) -> Path:
    """Give the stored file its final name: <document id><extension>."""
    final_path = folder / f"{document_id}{extension}"
    shutil.move(temporary, final_path)
    return final_path


def safe_display_name(filename: str | None) -> str:
    """Keep only the file name the user sees, never a path (e.g. "C:\\fakepath\\a.pdf")."""
    name = (filename or "").replace("\\", "/").split("/")[-1].strip()
    return name[:255] or "unnamed"