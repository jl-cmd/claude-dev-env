"""Tests for gist_upload.py pure functions — URL composition and filename resolution."""

from pathlib import Path
import sys

_script_directory = str(Path(__file__).resolve().parent)
if _script_directory not in sys.path:
    sys.path.insert(0, _script_directory)

from gist_upload import _compose_preview_url, _resolve_filename


class TestResolveFilename:
    def test_uses_override_when_provided(self):
        assert (
            _resolve_filename("report.html", "custom-name.html") == "custom-name.html"
        )

    def test_strips_directory_from_override(self):
        assert (
            _resolve_filename("report.html", "/some/path/override.html")
            == "override.html"
        )

    def test_uses_input_filename_when_no_override(self):
        assert _resolve_filename("report.html", None) == "report.html"

    def test_uses_default_for_stdin_without_override(self):
        assert _resolve_filename("-", None) == "doc.html"

    def test_override_takes_precedence_over_stdin(self):
        assert _resolve_filename("-", "writeup.html") == "writeup.html"


class TestComposePreviewUrl:
    def test_standard_gist_url(self):
        result = _compose_preview_url(
            "https://gist.github.com/user123/abc123def456",
            "report.html",
        )
        assert result == (
            "https://htmlpreview.github.io/"
            "?https://gist.githubusercontent.com/user123/abc123def456/raw/report.html"
        )

    def test_filename_with_spaces_is_encoded(self):
        result = _compose_preview_url(
            "https://gist.github.com/user123/abc123def456",
            "my report.html",
        )
        assert "my%20report.html" in result
