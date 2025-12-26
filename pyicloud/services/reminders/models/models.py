"""Reminders service data models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class RemindersList:
    """Represents a Reminders list (collection)."""

    id: str
    title: str
    color: Optional[str] = None


@dataclass
class Reminder:
    """Represents a single Reminder."""

    id: str
    title: str
    desc: Optional[str]
    due: Optional[datetime]
    completed: bool
    priority: int
    list_id: str
