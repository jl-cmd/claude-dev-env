"""Test file with inline imports inside functions - this is a violation."""
from unittest.mock import patch

from django.test import TestCase, Client


class ImportEvolutionsViewTest(TestCase):
    def setUp(self) -> None:
        self.luna_l1 = "Luna L1"
        self.luna_l2 = "Lunara L2"
        self.luna_l3 = "Lunabella L3"

    @patch('example_app.views.settings')
    def test_dry_run_shows_preview_without_saving(self, mock_settings: patch) -> None:
        from pathlib import Path
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as temp_dir:
            metadata_path = Path(temp_dir) / 'data' / 'metadata.json'
            print(metadata_path)

    @patch('example_app.views.settings')
    def test_apply_mode_sets_evolves_from(self, mock_settings: patch) -> None:
        from pathlib import Path
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as temp_dir:
            metadata_path = Path(temp_dir) / 'data' / 'metadata.json'
            print(metadata_path)

    @patch('example_app.views.settings')
    def test_skips_already_linked_evolutions(self, mock_settings: patch) -> None:
        self.luna_l2 = self.luna_l1

        from pathlib import Path
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as temp_dir:
            metadata_path = Path(temp_dir) / 'data' / 'metadata.json'
            print(metadata_path)
