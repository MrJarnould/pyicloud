import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from pyicloud.services.notes.rendering.attachments import (
    AttachmentContext,
    render_attachment,
)
from pyicloud.services.notes.rendering.ck_datasource import CloudKitNoteDataSource
from pyicloud.services.notes.rendering.exporter import (
    NoteExporter,
    download_image_assets,
)
from pyicloud.services.notes.rendering.options import ExportConfig
from pyicloud.services.notes.rendering.renderer import NoteRenderer

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "note_fixture.json")
with open(FIXTURE_PATH, "r", encoding="utf-8") as fixture_file:
    NOTE_FIXTURE = json.load(fixture_file)


class _Field:
    def __init__(self, value):
        self.value = value


class _Fields:
    def __init__(self, values):
        self.values = values

    def get_value(self, key):
        return self.values.get(key)

    def get_field(self, key):
        if key not in self.values:
            return None
        return _Field(self.values[key])


class _Record:
    def __init__(self, record_name, fields):
        self.recordName = record_name
        self.recordType = "Attachment"
        self.fields = _Fields(fields)


class TestNoteRendering(unittest.TestCase):
    def setUp(self):
        self.fixture = NOTE_FIXTURE

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

    def test_public_url_attachment_keeps_useful_title_and_href(self):
        ds = CloudKitNoteDataSource()
        ds.add_attachment_record(
            _Record(
                "url-1",
                {
                    "UTI": "public.url",
                    "SummaryEncrypted": b"Discord Notes Link",
                    "URLStringEncrypted": b"https://discord.example.com/channel/1",
                },
            )
        )

        html = render_attachment(
            AttachmentContext(
                id="url-1",
                uti=ds.get_attachment_uti("url-1") or "",
                title=ds.get_title("url-1"),
                primary_url=ds.get_primary_asset_url("url-1"),
                thumb_url=ds.get_thumbnail_url("url-1"),
                mergeable_gz=ds.get_mergeable_gz("url-1"),
            ),
            lambda _: "",
        )

        self.assertIn("Discord Notes Link", html)
        self.assertIn('href="https://discord.example.com/channel/1"', html)

    def test_image_attachment_does_not_use_signed_url_as_alt_text(self):
        signed_url = "https://cvws.icloud-content.com/B/example-signed-asset"
        ds = CloudKitNoteDataSource()
        ds.add_attachment_record(
            _Record(
                "img-1",
                {
                    "UTI": "com.apple.paper",
                    "PreviewImages": [SimpleNamespace(downloadURL=signed_url)],
                },
            )
        )

        self.assertIsNone(ds.get_title("img-1"))

        html = render_attachment(
            AttachmentContext(
                id="img-1",
                uti=ds.get_attachment_uti("img-1") or "",
                title=ds.get_title("img-1"),
                primary_url=ds.get_primary_asset_url("img-1"),
                thumb_url=ds.get_thumbnail_url("img-1"),
                mergeable_gz=ds.get_mergeable_gz("img-1"),
            ),
            lambda _: "",
        )

        self.assertIn(f'src="{signed_url}"', html)
        self.assertNotIn(f'alt="{signed_url}"', html)


class TestNoteExporter(unittest.TestCase):
    def _note_record(self, record_name="note-1", title=b"Example Title"):
        return _Record(record_name, {"TitleEncrypted": title})

    def _output_dir(self, name):
        path = os.path.join("/tmp/python-test-results", "notes-rendering", name)
        os.makedirs(path, exist_ok=True)
        return path

    def test_export_archival_mode_downloads_assets_into_custom_assets_dir(self):
        client = MagicMock()
        datasource = MagicMock(name="datasource")
        note_record = self._note_record()
        config = ExportConfig(
            export_mode="archival",
            assets_dir=os.path.join(
                "/tmp/python-test-results", "notes-rendering", "shared-assets"
            ),
        )
        exporter = NoteExporter(client, config=config)

        tmpdir = self._output_dir("archival-mode")
        with (
            patch(
                "pyicloud.services.notes.rendering.exporter.decode_and_parse_note",
                return_value=MagicMock(name="note"),
            ),
            patch(
                "pyicloud.services.notes.rendering.exporter.build_datasource",
                return_value=(datasource, ["att-1"]),
            ),
            patch.object(exporter.renderer, "render", return_value="<p>rendered</p>"),
            patch(
                "pyicloud.services.notes.rendering.exporter.download_pdf_assets"
            ) as mock_pdf,
            patch(
                "pyicloud.services.notes.rendering.exporter.download_image_assets"
            ) as mock_img,
            patch(
                "pyicloud.services.notes.rendering.exporter.download_av_assets"
            ) as mock_av,
            patch(
                "pyicloud.services.notes.rendering.exporter.download_vcard_assets"
            ) as mock_vcard,
        ):
            path = exporter.export(note_record, output_dir=tmpdir, filename="note.html")

        expected_assets_dir = os.path.join(config.assets_dir, "note-1")
        expected = {
            "assets_dir": expected_assets_dir,
            "out_dir": tmpdir,
            "config": config,
        }

        mock_pdf.assert_called_once_with(client, datasource, ["att-1"], **expected)
        mock_img.assert_called_once_with(client, datasource, ["att-1"], **expected)
        mock_av.assert_called_once_with(client, datasource, ["att-1"], **expected)
        mock_vcard.assert_called_once_with(client, datasource, ["att-1"], **expected)

        with open(path, "r", encoding="utf-8") as handle:
            html = handle.read()

        self.assertIn("<!doctype html>", html)
        self.assertIn("<title>Example Title</title>", html)

    def test_export_lightweight_mode_skips_downloads_and_writes_fragment(self):
        client = MagicMock()
        datasource = MagicMock(name="datasource")
        note_record = self._note_record(title=b"Fragment Title")
        config = ExportConfig(export_mode="lightweight", full_page=False)
        exporter = NoteExporter(client, config=config)

        tmpdir = self._output_dir("lightweight-mode")
        with (
            patch(
                "pyicloud.services.notes.rendering.exporter.decode_and_parse_note",
                return_value=MagicMock(name="note"),
            ),
            patch(
                "pyicloud.services.notes.rendering.exporter.build_datasource",
                return_value=(datasource, ["att-1"]),
            ),
            patch.object(exporter.renderer, "render", return_value="<p>rendered</p>"),
            patch(
                "pyicloud.services.notes.rendering.exporter.download_pdf_assets"
            ) as mock_pdf,
            patch(
                "pyicloud.services.notes.rendering.exporter.download_image_assets"
            ) as mock_img,
            patch(
                "pyicloud.services.notes.rendering.exporter.download_av_assets"
            ) as mock_av,
            patch(
                "pyicloud.services.notes.rendering.exporter.download_vcard_assets"
            ) as mock_vcard,
        ):
            path = exporter.export(note_record, output_dir=tmpdir, filename="note.html")

        with open(path, "r", encoding="utf-8") as handle:
            html = handle.read()

        mock_pdf.assert_not_called()
        mock_img.assert_not_called()
        mock_av.assert_not_called()
        mock_vcard.assert_not_called()
        self.assertEqual(html, "<p>rendered</p>")

    def test_download_image_assets_uses_caller_config(self):
        ck_client = MagicMock()
        ds = MagicMock()
        ds.get_attachment_uti.return_value = "com.apple.paper"
        ds.get_primary_asset_url.return_value = (
            "https://cvws.icloud-content.com/B/image"
        )
        ds.get_thumbnail_url.return_value = None

        config = ExportConfig(image_uti_exacts=())

        tmpdir = self._output_dir("download-image-config")
        updated = download_image_assets(
            ck_client,
            ds,
            ["img-1"],
            assets_dir=os.path.join(tmpdir, "assets"),
            out_dir=tmpdir,
            config=config,
        )

        ck_client.download_asset_to.assert_not_called()
        self.assertEqual(updated, {})


if __name__ == "__main__":
    unittest.main()
