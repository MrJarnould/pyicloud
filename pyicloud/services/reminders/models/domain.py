from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Reminder:
    id: str
    list_id: str
    title: str
    desc: str = ""
    completed: bool = False
    completed_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    priority: int = 0
    created: Optional[datetime] = None
    modified: Optional[datetime] = None


@dataclass
class RemindersList:
    id: str
    title: str
    color: Optional[str] = None
    guid: Optional[str] = None
