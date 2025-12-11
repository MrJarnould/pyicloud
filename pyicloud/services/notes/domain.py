# pyicloud/services/notes_domain.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class AttachmentId:
    identifier: str
    type_uti: Optional[str] = None


@dataclass(frozen=True)
class NoteBody:
    bytes: bytes
    text: Optional[str]
    attachment_ids: List[AttachmentId]
