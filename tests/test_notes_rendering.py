import json
import os
import unittest
from unittest.mock import Mock

from pyicloud.services.notes.rendering.ck_datasource import CloudKitNoteDataSource
from pyicloud.services.notes.rendering.renderer import NoteRenderer


class TestNoteRendering(unittest.TestCase):
    def setUp(self):
        # Load the fixture
        path = os.path.join(os.path.dirname(__file__), "fixtures", "note_fixture.json")
        with open(path, "r") as f:
            self.fixture = json.load(f)

    def _reconstruct_record(self, data):
        # Helper to rebuild a pseudo-CKRecord from the JSON dict
        # We need to minimally satisfy what build_datasource expects (fields.get_value)
        class MockFields:
            def __init__(self, fields_dict):
                self.d = fields_dict

            def get_value(self, key):
                val = self.d.get(key)
                if isinstance(val, dict) and "__bytes__" in val:
                    import base64

                    return base64.b64decode(val["__bytes__"])
                return val

            def get_field(self, key):
                # Needed for some checks like Attachments
                # For references, we might need more complex reconstruction if the code checks types
                # But let's start simple.
                return None

        rec = Mock()
        rec.recordName = data["recordName"]
        rec.recordType = data["recordType"]
        rec.fields = MockFields(data["fields"])
        return rec

    def test_render_fixture_output(self):
        """Ensure the captured test note renders to HTML without crashing."""
        note_data = self.fixture["note"]
        note_rec = self._reconstruct_record(note_data)

        # Patch CKRecord in exporter so isinstance(mock, CKRecord) passes
        with unittest.mock.patch(
            "pyicloud.services.notes.rendering.exporter.CKRecord", autospec=True
        ) as MockCKRecord:
            # We need note_rec to be an instance of this patched class
            MockCKRecord.return_value = note_rec
            # Actually, isinstance(byte_obj, MockClass) works if we set __class__ maybe?
            # Easier: just bypass decode_and_parse_note manually since we are testing rendering, not decoding validation.
            pass

        # Manual decode to skip isinstance check causing issues with simple mocks
        from pyicloud.services.notes.decoding import BodyDecoder
        from pyicloud.services.notes.protobuf import notes_pb2

        raw_cypher = note_rec.fields.get_value("TextDataEncrypted")
        nb = BodyDecoder().decode(raw_cypher)
        self.assertIsNotNone(nb, "Failed to BodyDecoder.decode fixture data")

        msg = notes_pb2.NoteStoreProto()
        msg.ParseFromString(nb.bytes)
        note = getattr(getattr(msg, "document", None), "note", None)

        # Mock datasource hydration
        # We manually populate the datasource with the attachment records from the fixture
        ds = CloudKitNoteDataSource()
        att_data_list = self.fixture["attachments"]
        for att_data in att_data_list:
            att_rec = self._reconstruct_record(att_data)
            ds.add_attachment_record(att_rec)

        renderer = NoteRenderer()
        html = renderer.render(note, datasource=ds)

        # Verify basic structure
        self.assertIn(
            "checklist",
            html.lower(),
            "Should contain checkbox logic if note has checklist",
        )
        # The test note had "pyicloud notes service test" in title, likely not in body.
        # But we expect SOME content.
        self.assertTrue(len(html) > 0)

        print("\n--- Rendered HTML Preview (First 500 chars) ---")
        print(html[:500])
        print("-----------------------------------------------")


if __name__ == "__main__":
    unittest.main()
