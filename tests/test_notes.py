"""Tests for the Notes service."""

import os
import unittest
from unittest.mock import MagicMock, patch

from pydantic import ValidationError

from pyicloud.common.cloudkit import CKLookupResponse
from pyicloud.common.cloudkit.base import resolve_cloudkit_validation_extra
from pyicloud.common.cloudkit.models import (
    CKParticipant,
    CKParticipantProtectionInfo,
    CKPCSInfo,
    CKRecord,
    CKUserIdentity,
)
from pyicloud.services.notes import AttachmentId, Note, NotesService, NoteSummary
from pyicloud.services.notes.client import CloudKitNotesClient, NotesApiError


class NotesServiceTest(unittest.TestCase):
    """Tests for the Notes service."""

    def setUp(self):
        """Set up the test case."""
        self.service = NotesService(
            service_root="https://example.com",
            session=MagicMock(),
            params={},
        )

    def test_get_note(self):
        """Test getting a note."""
        # This test will be implemented once sample data is available.
        pass

    def test_notes_domain_models_are_pydantic(self):
        """Notes public models expose Pydantic serialization."""
        summary = NoteSummary(
            id="note-1",
            title="Hello",
            snippet="World",
            modified_at=None,
            folder_id="folder-1",
            folder_name="Inbox",
            is_deleted=False,
            is_locked=False,
        )
        attachment_id = AttachmentId(identifier="att-1", type_uti="public.jpeg")

        self.assertEqual(summary.model_dump()["id"], "note-1")
        self.assertEqual(attachment_id.model_dump()["type_uti"], "public.jpeg")

    def test_note_has_attachments_is_in_model_dump(self):
        note = Note(
            id="note-1",
            title="Hello",
            snippet="World",
            modified_at=None,
            folder_id="folder-1",
            folder_name="Inbox",
            is_deleted=False,
            is_locked=False,
            text="Body",
            attachments=[],
        )

        self.assertFalse(note.model_dump()["has_attachments"])

    def test_notes_domain_models_forbid_unknown_fields(self):
        with self.assertRaises(ValidationError):
            NoteSummary(
                id="note-1",
                title="Hello",
                snippet="World",
                modified_at=None,
                folder_id="folder-1",
                folder_name="Inbox",
                is_deleted=False,
                is_locked=False,
                unexpected=True,
            )

    def test_notes_domain_models_are_frozen(self):
        summary = NoteSummary(
            id="note-1",
            title="Hello",
            snippet="World",
            modified_at=None,
            folder_id="folder-1",
            folder_name="Inbox",
            is_deleted=False,
            is_locked=False,
        )

        with self.assertRaises(ValidationError):
            summary.title = "Updated"

    def test_resolve_cloudkit_validation_extra_defaults_to_allow(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(resolve_cloudkit_validation_extra(), "allow")

    def test_resolve_cloudkit_validation_extra_uses_env(self):
        with patch.dict(os.environ, {"PYICLOUD_CK_EXTRA": "forbid"}, clear=True):
            self.assertEqual(resolve_cloudkit_validation_extra(), "forbid")

    def test_notes_client_allows_unexpected_fields_by_default(self):
        session = MagicMock()
        session.post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"records": [], "unexpectedTopLevel": {"present": True}},
        )
        client = CloudKitNotesClient(
            "https://example.com",
            session,
            {},
        )

        response = client.lookup(["Note/1"], desired_keys=None)

        self.assertIsInstance(response, CKLookupResponse)
        self.assertEqual(response.model_extra["unexpectedTopLevel"], {"present": True})

    def test_notes_client_strict_mode_wraps_validation_error(self):
        session = MagicMock()
        payload = {"records": [], "unexpectedTopLevel": {"present": True}}
        session.post.return_value = MagicMock(status_code=200, json=lambda: payload)
        client = CloudKitNotesClient(
            "https://example.com",
            session,
            {},
            validation_extra="forbid",
        )

        with self.assertRaisesRegex(
            NotesApiError, "Lookup response validation failed"
        ) as ctx:
            client.lookup(["Note/1"], desired_keys=None)

        self.assertEqual(ctx.exception.payload, payload)
        self.assertIsInstance(ctx.exception.__cause__, ValidationError)

    def test_notes_client_explicit_override_wins_over_env(self):
        session = MagicMock()
        session.post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"records": [], "unexpectedTopLevel": {"present": True}},
        )
        with patch.dict(os.environ, {"PYICLOUD_CK_EXTRA": "forbid"}, clear=True):
            client = CloudKitNotesClient(
                "https://example.com",
                session,
                {},
                validation_extra="allow",
            )

            response = client.lookup(["Note/1"], desired_keys=None)

        self.assertEqual(response.model_extra["unexpectedTopLevel"], {"present": True})

    def test_notes_service_passes_through_validation_override(self):
        service = NotesService(
            service_root="https://example.com",
            session=MagicMock(),
            params={},
            cloudkit_validation_extra="ignore",
        )

        self.assertEqual(service.raw._validation_extra, "ignore")

    def test_shared_cloudkit_share_allows_encrypted_string_fields(self):
        """Shared cloudkit.share records may expose STRING + isEncrypted fields."""
        record = CKRecord.model_validate(
            {
                "recordName": "Share-123",
                "recordType": "cloudkit.share",
                "fields": {
                    "SnippetEncrypted": {
                        "value": "Shared snippet",
                        "type": "STRING",
                        "isEncrypted": True,
                    }
                },
            }
        )

        self.assertEqual(record.fields.get_value("SnippetEncrypted"), "Shared snippet")
        self.assertEqual(
            NotesService._decode_encrypted(record.fields.get_value("SnippetEncrypted")),
            "Shared snippet",
        )

    def test_shared_cloudkit_share_participant_surfaces_are_typed(self):
        """Shared-record participant and PCS surfaces parse into structured models."""
        record = CKRecord.model_validate(
            {
                "recordName": "Share-123",
                "recordType": "cloudkit.share",
                "publicPermission": "NONE",
                "participants": [
                    {
                        "participantId": "owner-1",
                        "userIdentity": {
                            "userRecordName": "_owner",
                            "nameComponents": {
                                "givenName": "Jacob",
                                "familyName": "Arnould",
                            },
                            "lookupInfo": {
                                "emailAddress": "jacob@example.com",
                            },
                        },
                        "type": "OWNER",
                        "acceptanceStatus": "ACCEPTED",
                        "permission": "READ_WRITE",
                        "customRole": "",
                        "isApprovedRequester": False,
                        "orgUser": False,
                        "publicKeyVersion": 1,
                        "outOfNetworkPrivateKey": "",
                        "outOfNetworkKeyType": 0,
                        "protectionInfo": {
                            "bytes": "aGVsbG8=",
                            "pcsChangeTag": "owner-tag",
                        },
                    }
                ],
                "requesters": [],
                "blocked": [],
                "owner": {
                    "participantId": "owner-1",
                    "userIdentity": {
                        "userRecordName": "_owner",
                    },
                    "type": "OWNER",
                    "permission": "READ_WRITE",
                    "protectionInfo": {
                        "bytes": "aGVsbG8=",
                        "pcsChangeTag": "owner-tag",
                    },
                },
                "currentUserParticipant": {
                    "participantId": "user-1",
                    "userIdentity": {
                        "userRecordName": "_user",
                        "lookupInfo": {
                            "phoneNumber": "352621583784",
                        },
                    },
                    "type": "ADMINISTRATOR",
                    "acceptanceStatus": "ACCEPTED",
                    "permission": "READ_WRITE",
                    "protectionInfo": {
                        "bytes": "d29ybGQ=",
                        "pcsChangeTag": "user-tag",
                    },
                },
                "invitedPCS": {
                    "bytes": "aW52aXRlZA==",
                    "pcsChangeTag": "invited-tag",
                },
                "selfAddedPCS": {
                    "bytes": "c2VsZg==",
                    "pcsChangeTag": "self-tag",
                },
                "fields": {
                    "SnippetEncrypted": {
                        "value": "Shared snippet",
                        "type": "STRING",
                        "isEncrypted": True,
                    }
                },
            }
        )

        self.assertIsInstance(record.participants, list)
        self.assertIsInstance(record.participants[0], CKParticipant)
        self.assertIsInstance(record.participants[0].userIdentity, CKUserIdentity)
        self.assertEqual(
            record.participants[0].userIdentity.nameComponents.givenName, "Jacob"
        )
        self.assertIsInstance(
            record.participants[0].protectionInfo, CKParticipantProtectionInfo
        )
        self.assertIsInstance(record.owner, CKParticipant)
        self.assertIsInstance(record.currentUserParticipant, CKParticipant)
        self.assertEqual(
            record.currentUserParticipant.userIdentity.lookupInfo.phoneNumber,
            "352621583784",
        )
        self.assertIsInstance(record.invitedPCS, CKPCSInfo)
        self.assertEqual(record.invitedPCS.pcsChangeTag, "invited-tag")
        self.assertIsInstance(record.selfAddedPCS, CKPCSInfo)
        self.assertEqual(record.selfAddedPCS.pcsChangeTag, "self-tag")

    def test_encrypted_string_fields_without_flag_are_rejected(self):
        """STRING wrappers on *Encrypted fields must carry isEncrypted=true."""
        with self.assertRaises(ValidationError):
            CKRecord.model_validate(
                {
                    "recordName": "Share-123",
                    "recordType": "cloudkit.share",
                    "fields": {
                        "SnippetEncrypted": {
                            "value": "Shared snippet",
                            "type": "STRING",
                        }
                    },
                }
            )

    def test_decode_encrypted_bytes_and_strings(self):
        """Notes encrypted decoder handles both bytes and string field values."""
        self.assertEqual(NotesService._decode_encrypted(b"hello"), "hello")
        self.assertEqual(NotesService._decode_encrypted("bonjour"), "bonjour")


if __name__ == "__main__":
    unittest.main()
