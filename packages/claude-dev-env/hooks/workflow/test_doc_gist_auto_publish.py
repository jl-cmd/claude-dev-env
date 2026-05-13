"""Tests for doc_gist_auto_publish hook.

Validates payload parsing, target-path resolution, sentinel detection,
and the always-exit-0 contract without needing `gh` authentication.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


HOOK_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "doc_gist_auto_publish.py")
SENTINEL = "<!-- @publish-as-gist -->"


STUB_PREVIEW_URL = "https://htmlpreview.github.io/?stub"


class _RunHook:
    def __call__(self, tool_name: str, tool_input: dict) -> subprocess.CompletedProcess:
        payload = json.dumps({"tool_name": tool_name, "tool_input": tool_input})
        with tempfile.TemporaryDirectory() as isolation_root:
            stub_dir = Path(isolation_root) / "skills" / "doc-gist" / "scripts"
            stub_dir.mkdir(parents=True)
            (stub_dir / "gist_upload.py").write_text(
                f"import sys; print({STUB_PREVIEW_URL!r}); "
                f"print('Gist: stub', file=sys.stderr); "
                f"print('Preview: stub', file=sys.stderr)",
                encoding="utf-8",
            )
            return subprocess.run(
                [sys.executable, HOOK_SCRIPT_PATH, isolation_root],
                input=payload,
                capture_output=True,
                text=True,
                check=False,
            )


_run_hook = _RunHook()


def test_exits_zero_on_invalid_json():
    result = subprocess.run(
        [sys.executable, HOOK_SCRIPT_PATH],
        input="not json",
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "invalid json" in result.stderr.lower()


def test_exits_zero_on_non_dict_payload():
    result = subprocess.run(
        [sys.executable, HOOK_SCRIPT_PATH],
        input="[]",
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stderr == ""


def test_skips_non_html_files():
    with tempfile.TemporaryDirectory() as tmp:
        txt_path = os.path.join(tmp, "notes.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("plain text")

        result = _run_hook("Write", {"file_path": txt_path, "content": "plain text"})
    assert result.returncode == 0
    assert result.stderr == ""


def test_skips_html_without_sentinel():
    with tempfile.TemporaryDirectory() as tmp:
        html_path = os.path.join(tmp, "page.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write("<html><body>No marker</body></html>")

        result = _run_hook("Write", {"file_path": html_path, "content": "<html>"})
    assert result.returncode == 0
    assert result.stderr == ""


def test_exits_zero_when_html_has_sentinel():
    with tempfile.TemporaryDirectory() as tmp:
        html_path = os.path.join(tmp, "report.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(f"<html>{SENTINEL}<body>Report</body></html>")

        result = _run_hook("Write", {"file_path": html_path, "content": "<html>"})
    assert result.returncode == 0
    assert STUB_PREVIEW_URL in result.stdout


def test_skips_non_write_tool():
    with tempfile.TemporaryDirectory() as tmp:
        html_path = os.path.join(tmp, "page.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(f"<html>{SENTINEL}</html>")

        result = _run_hook("Read", {"file_path": html_path})
    assert result.returncode == 0
    assert result.stderr == ""


def test_exits_zero_when_file_missing():
    result = _run_hook("Write", {"file_path": "/nonexistent/path/page.html"})
    assert result.returncode == 0
    assert result.stderr == ""
