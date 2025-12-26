"""Proof-of-concept showing NotesService.iter_changes mislabels CKErrorItem entries."""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

# Provide a lightweight BodyDecoder stub so importing NotesService does not pull in
# google.protobuf (not available in this minimal environment).
_fake_decoding = types.ModuleType("pyicloud.services.notes.decoding")


class _BodyDecoderStub:
    def decode(self, *_args, **_kwargs):
        return None


def _install_stub() -> None:
    _fake_decoding.BodyDecoder = _BodyDecoderStub
    sys.modules.setdefault("pyicloud.services.notes.decoding", _fake_decoding)


_install_stub()

from pyicloud.services.notes.models.cloudkit import (  # noqa: E402  (after stub install)
    CKErrorItem,
    CKZoneChangesZone,
    CKZoneID,
)
from pyicloud.services.notes.service import NotesApiError  # noqa: E402
from pyicloud.services.notes.service import NotesService  # noqa: E402


class FakeChangesClient:
    """Minimal stub that returns a zone containing a CKErrorItem."""

    def __init__(self, zone: CKZoneChangesZone) -> None:
        self.zone = zone

    def changes(self, *, zone_req):  # type: ignore[no-untyped-def]
        # Mimic the generator returned by CloudKitNotesClient.changes
        yield self.zone


def build_error_zone() -> CKZoneChangesZone:
    """Create a /changes/zone page whose records list contains a CKErrorItem."""

    return CKZoneChangesZone(
        records=[
            CKErrorItem(
                serverErrorCode="AUTHENTICATION_REQUIRED",
                reason="Session expired",
                recordName="A1111111-2222-3333-4444-555555555555",
            )
        ],
        moreComing=False,
        syncToken="fake-sync-token",
        zoneID=CKZoneID(zoneName="Notes"),
    )


def main() -> None:
    # Instantiate NotesService with a dummy session; we will replace the raw client.
    svc = NotesService(
        service_root="https://example.com",
        session=MagicMock(),
        params={},
    )

    zone = build_error_zone()
    svc._raw = FakeChangesClient(zone)  # type: ignore[attr-defined]

    print("=== Input from CloudKit ===")
    print("Record entry class:", type(zone.records[0]).__name__)
    print("Server error code:", zone.records[0].serverErrorCode)
    print()

    try:
        events = list(svc.iter_changes())
    except NotesApiError as exc:
        print(
            "NotesService.iter_changes raised NotesApiError, preventing the mislabeling bug."
        )
        print("Payload:", getattr(exc, "payload", {}))
        return

    print("=== NotesService output ===")
    for idx, event in enumerate(events, start=1):
        print(
            f"Event {idx}: type={event.type!r}, note.id={event.note.id!r}, is_deleted={event.note.is_deleted}"
        )


if __name__ == "__main__":
    main()
