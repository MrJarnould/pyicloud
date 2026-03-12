"""Reminders service (CloudKit-based)."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Union

from pyicloud.common.cloudkit import CKRecord
from pyicloud.common.cloudkit.base import CloudKitExtraMode
from pyicloud.services.base import BaseService

from ._mappers import RemindersRecordMapper
from ._protocol import (
    _decode_crdt_document,
    _encode_crdt_document,
    _generate_resolution_token_map,
)
from ._reads import RemindersReadAPI
from ._writes import RemindersWriteAPI
from .client import CloudKitRemindersClient
from .models import (
    Alarm,
    AlarmWithTrigger,
    Hashtag,
    ImageAttachment,
    ListRemindersResult,
    LocationTrigger,
    Proximity,
    RecurrenceFrequency,
    RecurrenceRule,
    Reminder,
    ReminderChangeEvent,
    RemindersList,
    URLAttachment,
)

LOGGER = logging.getLogger(__name__)

Attachment = Union[URLAttachment, ImageAttachment]


class RemindersService(BaseService):
    """Reminders API via CloudKit."""

    _CONTAINER = "com.apple.reminders"
    _ENV = "production"
    _SCOPE = "private"

    def __init__(
        self,
        service_root: str,
        session: Any,
        params: Dict[str, Any],
        *,
        cloudkit_validation_extra: CloudKitExtraMode | None = None,
    ):
        super().__init__(service_root, session, params)
        endpoint = (
            f"{self.service_root}/database/1/"
            f"{self._CONTAINER}/{self._ENV}/{self._SCOPE}"
        )
        base_params = {
            "remapEnums": True,
            **(params or {}),
        }
        self._raw = CloudKitRemindersClient(
            endpoint,
            session,
            base_params,
            validation_extra=cloudkit_validation_extra,
        )

        def get_raw() -> CloudKitRemindersClient:
            return self._raw

        self._mapper = RemindersRecordMapper(get_raw, LOGGER)
        self._reads = RemindersReadAPI(get_raw, self._mapper, LOGGER)
        self._writes = RemindersWriteAPI(get_raw, self._mapper, LOGGER)

    def lists(self) -> Iterable[RemindersList]:
        return self._reads.lists()

    def reminders(
        self,
        list_id: Optional[str] = None,
    ) -> Iterable[Reminder]:
        reminder_map: Dict[str, Reminder] = {}

        list_ids: List[str]
        if list_id:
            list_ids = [list_id]
        else:
            list_ids = [lst.id for lst in self.lists()]

        for lid in list_ids:
            batch = self.list_reminders(
                list_id=lid,
                include_completed=True,
                results_limit=200,
            )
            for reminder in batch.reminders:
                reminder_map[reminder.id] = reminder

        for reminder in reminder_map.values():
            yield reminder

    def sync_cursor(self) -> str:
        return self._reads.sync_cursor()

    def iter_changes(
        self,
        *,
        since: Optional[str] = None,
    ) -> Iterable[ReminderChangeEvent]:
        return self._reads.iter_changes(since=since)

    def get(self, reminder_id: str) -> Reminder:
        return self._reads.get(reminder_id)

    def create(
        self,
        list_id: str,
        title: str,
        desc: str = "",
        completed: bool = False,
        due_date: Optional[datetime] = None,
        priority: int = 0,
        flagged: bool = False,
        all_day: bool = False,
        time_zone: Optional[str] = None,
    ) -> Reminder:
        return self._writes.create(
            list_id=list_id,
            title=title,
            desc=desc,
            completed=completed,
            due_date=due_date,
            priority=priority,
            flagged=flagged,
            all_day=all_day,
            time_zone=time_zone,
        )

    def update(self, reminder: Reminder) -> None:
        self._writes.update(reminder)

    def delete(self, reminder: Reminder) -> None:
        self._writes.delete(reminder)

    def add_location_trigger(
        self,
        reminder: Reminder,
        title: str = "",
        address: str = "",
        latitude: float = 0.0,
        longitude: float = 0.0,
        radius: float = 100.0,
        proximity: Proximity = Proximity.ARRIVING,
    ) -> tuple[Alarm, LocationTrigger]:
        return self._writes.add_location_trigger(
            reminder=reminder,
            title=title,
            address=address,
            latitude=latitude,
            longitude=longitude,
            radius=radius,
            proximity=proximity,
        )

    def create_hashtag(self, reminder: Reminder, name: str) -> Hashtag:
        return self._writes.create_hashtag(reminder, name)

    def update_hashtag(self, hashtag: Hashtag, name: str) -> None:
        self._writes.update_hashtag(hashtag, name)

    def delete_hashtag(self, reminder: Reminder, hashtag: Hashtag) -> None:
        self._writes.delete_hashtag(reminder, hashtag)

    def create_url_attachment(
        self,
        reminder: Reminder,
        url: str,
        uti: str = "public.url",
    ) -> URLAttachment:
        return self._writes.create_url_attachment(reminder, url, uti)

    def update_attachment(
        self,
        attachment: Attachment,
        *,
        url: Optional[str] = None,
        uti: Optional[str] = None,
        filename: Optional[str] = None,
        file_size: Optional[int] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> None:
        self._writes.update_attachment(
            attachment,
            url=url,
            uti=uti,
            filename=filename,
            file_size=file_size,
            width=width,
            height=height,
        )

    def delete_attachment(self, reminder: Reminder, attachment: Attachment) -> None:
        self._writes.delete_attachment(reminder, attachment)

    def create_recurrence_rule(
        self,
        reminder: Reminder,
        *,
        frequency: RecurrenceFrequency = RecurrenceFrequency.DAILY,
        interval: int = 1,
        occurrence_count: int = 0,
        first_day_of_week: int = 0,
    ) -> RecurrenceRule:
        return self._writes.create_recurrence_rule(
            reminder,
            frequency=frequency,
            interval=interval,
            occurrence_count=occurrence_count,
            first_day_of_week=first_day_of_week,
        )

    def update_recurrence_rule(
        self,
        recurrence_rule: RecurrenceRule,
        *,
        frequency: Optional[RecurrenceFrequency] = None,
        interval: Optional[int] = None,
        occurrence_count: Optional[int] = None,
        first_day_of_week: Optional[int] = None,
    ) -> None:
        self._writes.update_recurrence_rule(
            recurrence_rule,
            frequency=frequency,
            interval=interval,
            occurrence_count=occurrence_count,
            first_day_of_week=first_day_of_week,
        )

    def delete_recurrence_rule(
        self,
        reminder: Reminder,
        recurrence_rule: RecurrenceRule,
    ) -> None:
        self._writes.delete_recurrence_rule(reminder, recurrence_rule)

    def list_reminders(
        self,
        list_id: str,
        include_completed: bool = False,
        results_limit: int = 200,
    ) -> ListRemindersResult:
        return self._reads.list_reminders(
            list_id=list_id,
            include_completed=include_completed,
            results_limit=results_limit,
        )

    def alarms_for(self, reminder: Reminder) -> List[AlarmWithTrigger]:
        return self._reads.alarms_for(reminder)

    def tags_for(self, reminder: Reminder) -> List[Hashtag]:
        return self._reads.tags_for(reminder)

    def attachments_for(self, reminder: Reminder) -> List[Attachment]:
        return self._reads.attachments_for(reminder)

    def recurrence_rules_for(self, reminder: Reminder) -> List[RecurrenceRule]:
        return self._reads.recurrence_rules_for(reminder)

    # Compatibility wrappers for the service's tested helper surface.
    def _decode_crdt_document(self, encrypted_value: str | bytes) -> str:
        return _decode_crdt_document(encrypted_value)

    def _encode_crdt_document(self, text: str) -> str:
        return _encode_crdt_document(text)

    def _generate_resolution_token_map(self, fields_modified: list[str]) -> str:
        return _generate_resolution_token_map(fields_modified)

    def _record_to_list(self, rec: CKRecord) -> RemindersList:
        return self._mapper.record_to_list(rec)

    def _record_to_reminder(self, rec: CKRecord) -> Reminder:
        return self._mapper.record_to_reminder(rec)

    def _record_to_alarm(self, rec: CKRecord) -> Alarm:
        return self._mapper.record_to_alarm(rec)

    def _record_to_alarm_trigger(self, rec: CKRecord) -> Optional[LocationTrigger]:
        return self._mapper.record_to_alarm_trigger(rec)

    def _record_to_attachment(self, rec: CKRecord) -> Optional[Attachment]:
        return self._mapper.record_to_attachment(rec)

    def _record_to_hashtag(self, rec: CKRecord) -> Hashtag:
        return self._mapper.record_to_hashtag(rec)

    def _record_to_recurrence_rule(self, rec: CKRecord) -> RecurrenceRule:
        return self._mapper.record_to_recurrence_rule(rec)
