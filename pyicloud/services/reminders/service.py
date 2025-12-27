"""
Reminders service (CloudKit-based).
"""

from __future__ import annotations

import base64
import gzip
import logging
from typing import Any, Dict, Iterable, Optional

from pyicloud.common.cloudkit import (
    CKRecord,
    CKZoneIDReq,
)
from pyicloud.services.base import BaseService

from .client import CloudKitRemindersClient
from .models import Reminder, RemindersList
from .protobuf import reminders_pb2

LOGGER = logging.getLogger(__name__)


class RemindersService(BaseService):
    """
    Reminders API via CloudKit.
    """

    _CONTAINER = "com.apple.reminders"
    _ENV = "production"
    _SCOPE = "private"

    def __init__(self, service_root: str, session: object, params: Dict[str, Any]):
        super().__init__(
            str(service_root).replace(
                "reminders.icloud.com", "ckdatabasews.icloud.com"
            ),
            session,
            params,
        )
        endpoint = f"{self.service_root}/database/1/{self._CONTAINER}/{self._ENV}/{self._SCOPE}"
        base_params = {
            "remapEnums": True,
            "getCurrentSyncToken": True,
            **(params or {}),
        }
        self._raw = CloudKitRemindersClient(endpoint, session, base_params)
        self._lists: Dict[str, RemindersList] = {}
        self._reminders: Dict[str, Reminder] = {}
        self._populated = False

    def populate(self):
        """Fetch all lists and reminders."""
        if self._populated:
            return

        zone_id = CKZoneIDReq(zoneName="Reminders", zoneType="REGULAR_CUSTOM_ZONE")
        try:
            response = self._raw.changes(zone_id=zone_id)
        except Exception:
            # Retry or handle error?
            raise

        if not response.zones:
            return

        # Assuming first zone is our target
        zone_data = response.zones[0]

        for rec in zone_data.records:
            # Skip tombstone/error for now
            if not isinstance(rec, CKRecord):
                continue

            if rec.recordType == "List":
                # Decode List
                title = rec.fields.get_value("Title")
                color = None
                self._lists[rec.recordName] = RemindersList(
                    id=rec.recordName,
                    title=str(title) if title else "Untitled",
                    color=str(color) if color else None,
                )
            elif rec.recordType == "Reminder":
                # Decode Reminder
                self._reminders[rec.recordName] = self._record_to_reminder(rec)

        self._populated = True

    def lists(self) -> Iterable[RemindersList]:
        """Fetch reminders lists."""
        self.populate()
        return self._lists.values()

    def reminders(self, list_id: Optional[str] = None) -> Iterable[Reminder]:
        """Fetch reminders, optionally filtered by list."""
        self.populate()
        if list_id:
            return [r for r in self._reminders.values() if r.list_id == list_id]
        return self._reminders.values()

    def _record_to_reminder(self, rec: CKRecord) -> Reminder:
        fields = rec.fields

        # Title decoding
        title_doc = fields.get_value("TitleDocument")
        title = "Untitled"
        if title_doc:
            try:
                title = self._decode_title_document(title_doc)
            except Exception as e:
                LOGGER.warning(
                    "Failed to decode TitleDocument for %s: %s", rec.recordName, e
                )
                title = "Error Decoding Title"

        # List ID
        list_ref = fields.get_field("List")
        list_id = ""
        if list_ref and list_ref.value and hasattr(list_ref.value, "recordName"):
            list_id = list_ref.value.recordName

        # Due Date
        due = fields.get_value("DueDate")

        return Reminder(
            id=rec.recordName,
            title=title,
            desc=None,  # Description might be in another field
            due=due,
            completed=bool(fields.get_value("Completed") or 0),
            priority=int(fields.get_value("Priority") or 0),
            list_id=list_id,
        )

    def _decode_title_document(self, encrypted_value: str) -> str:
        data = base64.b64decode(encrypted_value)
        try:
            data = gzip.decompress(data)
        except gzip.BadGzipFile:
            pass  # Maybe not gzipped? But verification showed it was.

        doc = reminders_pb2.TitleDocument()
        doc.ParseFromString(data)

        # Navigate: TitleDocument -> Title (2) -> TitleContent (3) -> text (2)
        if doc.title and doc.title.content and doc.title.content.text:
            return doc.title.content.text

        return ""
