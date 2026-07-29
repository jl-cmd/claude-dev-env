"""Behavioral tests for shared gh body-file comment helpers."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from gh_body_comment import run_gh_pr_comment, write_markdown_body_file  # noqa: E402
from split_pr_scripts_constants.config.execute_constants import (  # noqa: E402
    GH_BODY_FILE,
    GH_COMMAND,
    GH_COMMENT,
    GH_PR,
)

ERROR_TEMPLATE = "comment failed for #%s: %s"


def test_write_markdown_body_file_writes_content(tmp_path: Path) -> None:
    del tmp_path
    body_path = write_markdown_body_file("hello body")
    written = Path(body_path)
    assert written.is_file()
    assert written.read_text(encoding="utf-8") == "hello body"


def test_run_gh_pr_comment_uses_body_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    all_calls: list[list[str]] = []

    def fake_run(
        all_command: list[str],
        cwd: str | None = None,
        capture_output: bool = False,
        text: bool = False,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        del cwd, capture_output, text, check
        all_calls.append(list(all_command))
        return subprocess.CompletedProcess(
            args=all_command,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    body_path = str(tmp_path / "body.md")
    Path(body_path).write_text("x", encoding="utf-8")
    run_gh_pr_comment(
        pr_number=42,
        body_path=body_path,
        repo="example/repo",
        working_directory=str(tmp_path),
        error_template=ERROR_TEMPLATE,
    )
    assert len(all_calls) == 1
    assert all_calls[0][:3] == [GH_COMMAND, GH_PR, GH_COMMENT]
    assert GH_BODY_FILE in all_calls[0]
    assert "42" in all_calls[0]
