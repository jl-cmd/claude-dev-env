"""Tests for post-bugbot-run PowerShell helpers.

Covers Resolve-InvocationMode / Build-GhArgumentList for URL, owner/repo#N, and
-Repository/-Number forms (Windows Bugbot re-trigger argv construction).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def _run_powershell(*, expression: str) -> str:
    helpers = Path(__file__).resolve().parent / "post-bugbot-run.helpers.ps1"
    command = (
        f". '{helpers}'; "
        + expression
        + " | ConvertTo-Json -Compress -Depth 5"
    )
    completed = subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"pwsh failed ({completed.returncode}): stderr={completed.stderr!r} stdout={completed.stdout!r}"
        )
    return completed.stdout.strip()


def _argv_for(*, pull: str, repository: str, number: int, body: str) -> list[str]:
    pull_esc = pull.replace("'", "''")
    repository_esc = repository.replace("'", "''")
    body_esc = body.replace("'", "''")
    expression = (
        f"$i = Resolve-InvocationMode -PullRequestInput '{pull_esc}' "
        f"-RepositoryInput '{repository_esc}' -NumberInput {int(number)}; "
        f"@(Build-GhArgumentList -Invocation $i -BodyFilePath '{body_esc}')"
    )
    raw = _run_powershell(expression=expression)
    return json.loads(raw)


def test_should_build_arguments_for_https_pull_url() -> None:
    argv = _argv_for(
        pull="https://github.com/acme/widget/pull/42",
        repository="",
        number=0,
        body=r"C:\\temp\\body.md",
    )
    assert argv == [
        "pr",
        "comment",
        "https://github.com/acme/widget/pull/42",
        "--body-file",
        r"C:\\temp\\body.md",
    ]


def test_should_build_arguments_for_owner_repo_hash_form() -> None:
    argv = _argv_for(
        pull="acme/widget#7",
        repository="",
        number=0,
        body=r"D:\\x\\f.md",
    )
    assert argv == ["pr", "comment", "7", "-R", "acme/widget", "--body-file", r"D:\\x\\f.md"]


def test_should_build_arguments_for_repository_and_number_parameters() -> None:
    argv = _argv_for(
        pull="",
        repository="jl-cmd/claude-code-config",
        number=331,
        body=r"E:\\y\\z.md",
    )
    assert argv == [
        "pr",
        "comment",
        "331",
        "-R",
        "jl-cmd/claude-code-config",
        "--body-file",
        r"E:\\y\\z.md",
    ]


def test_should_fail_when_number_without_repository() -> None:
    helpers = Path(__file__).resolve().parent / "post-bugbot-run.helpers.ps1"
    command = (
        f". '{helpers}'; "
        "try { Resolve-InvocationMode -PullRequestInput '' -RepositoryInput '' -NumberInput 3 } "
        "catch { $_.Exception.Message }"
    )
    completed = subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert completed.returncode == 0
    message = completed.stdout.strip()
    assert "Repository" in message


def test_should_reject_pull_url_with_trailing_junk() -> None:
    helpers = Path(__file__).resolve().parent / "post-bugbot-run.helpers.ps1"
    pull = "https://github.com/acme/widget/pull/42extra"
    command = (
        f". '{helpers}'; "
        f"$i = Resolve-InvocationMode -PullRequestInput '{pull}' -RepositoryInput '' -NumberInput 0; "
        r"try { Build-GhArgumentList -Invocation $i -BodyFilePath 'C:\\t\\b.md' } "
        "catch { $_.Exception.Message }"
    )
    completed = subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert completed.returncode == 0
    assert "Unrecognized PullRequest" in completed.stdout


def test_should_fail_for_unrecognized_pull_string() -> None:
    helpers = Path(__file__).resolve().parent / "post-bugbot-run.helpers.ps1"
    pull = "not-a-valid-pr-reference"
    command = (
        f". '{helpers}'; "
        f"$i = Resolve-InvocationMode -PullRequestInput '{pull}' -RepositoryInput '' -NumberInput 0; "
        r"try { Build-GhArgumentList -Invocation $i -BodyFilePath 'C:\\t\\b.md' } "
        "catch { $_.Exception.Message }"
    )
    completed = subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert completed.returncode == 0
    assert "Unrecognized PullRequest" in completed.stdout


def test_full_script_removes_temp_files_when_gh_stub_succeeds(tmp_path: Path) -> None:
    scripts_dir = Path(__file__).resolve().parent
    script_path = scripts_dir / "post-bugbot-run.ps1"
    stub_bin_dir = tmp_path / "gh_stub_bin"
    stub_bin_dir.mkdir()
    gh_cmd = stub_bin_dir / "gh.cmd"
    gh_cmd.write_text("@echo off\r\nexit /b 0\r\n", encoding="utf-8")
    env = dict(os.environ)
    env["PATH"] = str(stub_bin_dir) + os.pathsep + env.get("PATH", "")
    completed = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(script_path),
            "acme/widget#9",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )
    assert completed.returncode == 0, (completed.stdout, completed.stderr)

def test_post_bugbot_run_script_finally_removes_temp_paths() -> None:
    script_text = (Path(__file__).resolve().parent / "post-bugbot-run.ps1").read_text(
        encoding="utf-8"
    )
    assert "finally" in script_text
    assert "Remove-Item" in script_text
    assert "body_file_path" in script_text
    assert "scratch_temp_path" in script_text
