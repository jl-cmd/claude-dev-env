"""Tests for the env-var-table code-drift blocker.

Each test builds a real on-disk directory holding a code file and a markdown
doc, then drives the blocker's detection function against that tree. The drift
the blocker catches: a markdown env-var summary table row attributes an
environment variable to a code file whose source never references that variable.
"""

from __future__ import annotations

import sys
from pathlib import Path

_blocking_dir = str(Path(__file__).resolve().parent)
if _blocking_dir not in sys.path:
    sys.path.insert(0, _blocking_dir)

from env_var_table_code_drift_blocker import (  # noqa: E402
    find_drift_rows,
    is_markdown_file,
)


def _write(file_path: Path, content: str) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")


def _anchor_repo_root(repo_root: Path) -> None:
    (repo_root / ".git").mkdir(parents=True, exist_ok=True)


def test_is_markdown_file_accepts_md_and_rejects_python() -> None:
    assert is_markdown_file("docs/configuration.md") is True
    assert is_markdown_file("auth/google_auth.py") is False


def test_flags_variable_absent_from_named_code_file(tmp_path: Path) -> None:
    _anchor_repo_root(tmp_path)
    _write(tmp_path / "auth" / "google_auth.py", "def load():\n    return read_bws_secret()\n")
    doc_path = tmp_path / "docs" / "configuration.md"
    content = (
        "## Summary: Environment Variables\n\n"
        "| Variable | Used By | Purpose |\n"
        "|----------|---------|---------|\n"
        "| `GOOGLE_APPLICATION_CREDENTIALS` | `auth/google_auth.py` | Path to JSON |\n"
    )
    drift_rows = find_drift_rows(content, doc_path.parent)
    assert drift_rows == ["GOOGLE_APPLICATION_CREDENTIALS -> auth/google_auth.py"]


def test_passes_when_variable_present_in_code_file(tmp_path: Path) -> None:
    _anchor_repo_root(tmp_path)
    _write(
        tmp_path / "automation_logging" / "__init__.py",
        'topic = os.environ["NTFY_TOPIC"]\n',
    )
    doc_path = tmp_path / "docs" / "configuration.md"
    content = (
        "| Variable | Used By | Purpose |\n"
        "|----------|---------|---------|\n"
        "| `NTFY_TOPIC` | `automation_logging/__init__.py` | ntfy topic |\n"
    )
    assert find_drift_rows(content, doc_path.parent) == []


def test_skips_row_whose_code_file_is_absent(tmp_path: Path) -> None:
    _anchor_repo_root(tmp_path)
    doc_path = tmp_path / "docs" / "configuration.md"
    content = (
        "| Variable | Used By | Purpose |\n"
        "|----------|---------|---------|\n"
        "| `MISSING_VAR` | `nowhere/ghost.py` | unresolved |\n"
    )
    assert find_drift_rows(content, doc_path.parent) == []


def test_ignores_rows_inside_a_fenced_code_block(tmp_path: Path) -> None:
    _anchor_repo_root(tmp_path)
    _write(tmp_path / "auth" / "google_auth.py", "no variable here\n")
    doc_path = tmp_path / "docs" / "configuration.md"
    content = "```\n| `GOOGLE_APPLICATION_CREDENTIALS` | `auth/google_auth.py` | sample |\n```\n"
    assert find_drift_rows(content, doc_path.parent) == []


def test_ignores_row_whose_second_cell_is_not_a_code_file(tmp_path: Path) -> None:
    _anchor_repo_root(tmp_path)
    doc_path = tmp_path / "docs" / "configuration.md"
    content = (
        "| Variable | Purpose | Default |\n"
        "|----------|---------|---------|\n"
        "| `SOME_FLAG` | `enables the thing` | off |\n"
    )
    assert find_drift_rows(content, doc_path.parent) == []
