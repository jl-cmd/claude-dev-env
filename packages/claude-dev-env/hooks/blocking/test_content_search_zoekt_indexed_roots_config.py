"""Tests for Zoekt indexed root resolution (env, file, empty built-in fallback, WSL variants)."""

import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

HOOK_DIRECTORY = pathlib.Path(__file__).resolve().parent
if str(HOOK_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(HOOK_DIRECTORY))

from content_search_zoekt_indexed_paths import is_in_indexed_repo
from content_search_zoekt_indexed_roots_config import (
    clear_indexed_root_prefixes_cache,
    indexed_root_prefixes,
)


class IndexedRootsConfigTests(unittest.TestCase):
    def tearDown(self) -> None:
        clear_indexed_root_prefixes_cache()

    def test_environment_json_array_defines_prefixes(self) -> None:
        roots_json = json.dumps(["Y:/OnlyOne/Indexed/"])
        with patch.dict(os.environ, {"ZOEKT_REDIRECT_INDEXED_ROOTS": roots_json}, clear=False):
            clear_indexed_root_prefixes_cache()
            prefixes = indexed_root_prefixes()
        self.assertIn("y:/onlyone/indexed/", prefixes)
        self.assertIn("/mnt/y/onlyone/indexed/", prefixes)

    def test_empty_environment_array_yields_no_prefixes(self) -> None:
        with patch.dict(os.environ, {"ZOEKT_REDIRECT_INDEXED_ROOTS": "[]"}, clear=False):
            clear_indexed_root_prefixes_cache()
            prefixes = indexed_root_prefixes()
        self.assertEqual(prefixes, ())

    def test_json_file_used_when_env_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            home = pathlib.Path(tmp_str)
            config_dir = home / ".claude"
            config_dir.mkdir(parents=True)
            roots_payload = {"roots": ["Y:/FromFile/Project/"]}
            (config_dir / "zoekt-indexed-roots.json").write_text(
                json.dumps(roots_payload),
                encoding="utf-8",
            )
            with patch("pathlib.Path.home", return_value=home):
                saved = os.environ.pop("ZOEKT_REDIRECT_INDEXED_ROOTS", None)
                try:
                    clear_indexed_root_prefixes_cache()
                    prefixes = indexed_root_prefixes()
                finally:
                    if saved is not None:
                        os.environ["ZOEKT_REDIRECT_INDEXED_ROOTS"] = saved
        self.assertIn("y:/fromfile/project/", prefixes)

    def test_environment_overrides_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_str:
            home = pathlib.Path(tmp_str)
            config_dir = home / ".claude"
            config_dir.mkdir(parents=True)
            (config_dir / "zoekt-indexed-roots.json").write_text(
                json.dumps({"roots": ["Y:/FromFile/"]}),
                encoding="utf-8",
            )
            with patch("pathlib.Path.home", return_value=home):
                with patch.dict(
                    os.environ,
                    {"ZOEKT_REDIRECT_INDEXED_ROOTS": json.dumps(["Y:/FromEnv/"])},
                    clear=False,
                ):
                    clear_indexed_root_prefixes_cache()
                    prefixes = indexed_root_prefixes()
        self.assertIn("y:/fromenv/", prefixes)
        self.assertNotIn("y:/fromfile/", prefixes)

    def test_longer_prefix_matches_before_shorter_parent(self) -> None:
        roots_json = json.dumps(["Y:/parent/", "Y:/parent/child/"])
        with patch.dict(os.environ, {"ZOEKT_REDIRECT_INDEXED_ROOTS": roots_json}, clear=False):
            clear_indexed_root_prefixes_cache()
            self.assertTrue(is_in_indexed_repo("Y:/parent/child/file.py"))

    def test_invalid_environment_json_falls_through_to_empty_builtin(self) -> None:
        with patch(
            "content_search_zoekt_indexed_roots_config._roots_from_json_file",
            return_value=None,
        ):
            with patch.dict(
                os.environ,
                {"ZOEKT_REDIRECT_INDEXED_ROOTS": "not-json"},
                clear=False,
            ):
                clear_indexed_root_prefixes_cache()
                prefixes = indexed_root_prefixes()
        self.assertEqual(prefixes, ())


if __name__ == "__main__":
    unittest.main()
