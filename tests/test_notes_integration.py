import os
import shutil
import unittest

from pyicloud import PyiCloudService
from pyicloud.utils import get_password

# The ID of the "Clean Reference Note" we found earlier
NOTE_ID = "C42C3055-8825-4CCE-8839-ED48C1D913B0"
OUTPUT_DIR = "tests/integration_output"

try:
    from pyicloud import PyiCloudService

    # Try to initialize service to check for credentials/keychain
    # This is a bit hacky but effective for skipping in CI
    try:
        PyiCloudService("test", "test")
    except Exception:
        pass
    HAS_CREDENTIALS = True
except ImportError:
    HAS_CREDENTIALS = False

# Ideally we check if we can actually authenticate, but for now we assume
# if the dev runs this file directly, they want to try.
# In CI, we might want an env var logic.
SKIP_INTEGRATION = os.environ.get("CI") or not os.path.exists(
    "tests/fixtures/note_fixture.json"
)


class TestNotesIntegration(unittest.TestCase):
    @unittest.skipIf(
        SKIP_INTEGRATION or not HAS_CREDENTIALS,
        "Skipping integration test due to missing credentials or CI environment",
    )
    @classmethod
    def setUpClass(cls):
        # Clean up previous run
        if os.path.exists(OUTPUT_DIR):
            shutil.rmtree(OUTPUT_DIR)
        os.makedirs(OUTPUT_DIR)

        # Authenticate once
        username = "jacob@jacob-arnould.com"
        password = get_password(username)
        cls.api = PyiCloudService(apple_id=username, password=password)

    def test_export_note_end_to_end(self):
        """Test the full export pipeline against real CloudKit."""
        print(f"\nExporting note {NOTE_ID} to {OUTPUT_DIR}...")
        try:
            path = self.api.notes.export_note(NOTE_ID, output_dir=OUTPUT_DIR)
        except Exception as e:
            self.fail(f"Export failed with exception: {e}")

        print(f"Exported to: {path}")
        self.assertIsNotNone(path)
        self.assertTrue(os.path.exists(path), "HTML file was not created")

        # Check that assets were downloaded
        assets_dir = os.path.join(OUTPUT_DIR, "assets", NOTE_ID)
        # We expect at least some assets folder if there were attachments
        # The test note has 15 attachments, so we expect this dir to exist and have files
        self.assertTrue(os.path.exists(assets_dir), "Assets directory not created")
        files = os.listdir(assets_dir)
        print(f"Downloaded {len(files)} asset files.")
        self.assertTrue(len(files) > 0, "No assets downloaded")


if __name__ == "__main__":
    unittest.main()
