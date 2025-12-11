"""High-level Notes data transfer objects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Iterator, List, Optional

if TYPE_CHECKING:  # pragma: no cover - import for type checking only
    from ..service import NotesService


@dataclass(frozen=True)
class NoteSummary:
    """Lightweight metadata returned by list/search APIs."""

    id: str
    title: Optional[str]
    snippet: Optional[str]
    modified_at: Optional[datetime]
    folder_id: Optional[str]
    folder_name: Optional[str]
    is_deleted: bool
    is_locked: bool


@dataclass(frozen=True)
class Attachment:
    """Metadata for a note attachment."""

    id: str
    filename: Optional[str]
    uti: Optional[str]
    size: Optional[int]
    download_url: Optional[str]
    preview_url: Optional[str]
    thumbnail_url: Optional[str]

    def save_to(self, directory: str, *, service: "NotesService") -> str:
        """Download the attachment to ``directory`` using the provided service."""

        return service._download_attachment_to(self, directory)

    def stream(
        self, *, service: "NotesService", chunk_size: int = 65_536
    ) -> Iterator[bytes]:
        """Yield the attachment bytes in chunks using the provided service."""

        yield from service._stream_attachment(self, chunk_size=chunk_size)


@dataclass(frozen=True)
class Note(NoteSummary):
    """Full note payload returned by ``NotesService.get``."""

    text: Optional[str]
    html: Optional[str]
    attachments: Optional[List[Attachment]]

    @property
    def has_attachments(self) -> Optional[bool]:
        """Return ``True``/``False`` when attachments were loaded, otherwise ``None``."""
        if self.attachments is None:
            return None
        return bool(self.attachments)


@dataclass(frozen=True)
class NoteFolder:
    id: str
    name: Optional[str]
    has_subfolders: Optional[bool]
    count: Optional[int]  # not always available


@dataclass(frozen=True)
class ChangeEvent:
    type: str  # "updated" | "deleted"
    note: NoteSummary
