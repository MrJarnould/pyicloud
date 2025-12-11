"""Tests for the Notes service."""

import unittest
from unittest.mock import MagicMock

from pyicloud.services.notes import NotesService


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


if __name__ == "__main__":
    unittest.main()
