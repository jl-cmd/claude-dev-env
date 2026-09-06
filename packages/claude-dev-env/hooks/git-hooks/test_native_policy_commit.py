"""Exercise the native Git commit boundary in disposable repositories."""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path

import pre_commit
import pytest
from test_native_hook_support import run_git


def _git(repository_path: Path, *arguments: str) -> str:
    return run_git(repository_path, *arguments).stdout.strip()


def _stage(repository_path: Path, relative_path: str, content: str) -> Path:
    file_path = repository_path / relative_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    _git(repository_path, "add", "--", relative_path)
    return file_path


@pytest.fixture()
def repository_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repository_path = tmp_path / "repository"
    repository_path.mkdir()
    _git(repository_path, "init")
    _git(repository_path, "config", "user.name", "Fixture")
    _git(repository_path, "config", "user.email", "fixture@example.com")
    _git(repository_path, "commit", "--allow-empty", "-m", "fixture base")
    monkeypatch.chdir(repository_path)
    return repository_path


@pytest.fixture()
def installed_native_hook(
    repository_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """Install a native fixture shim pointing to the actual pre-commit owner."""
    hook_directory = repository_root / ".git" / "fixture-native-hooks"
    hook_directory.mkdir()
    hook_path = hook_directory / "pre-commit"
    command = " ".join(
        shlex.quote(each_argument)
        for each_argument in (sys.executable, str(Path(pre_commit.__file__).resolve()))
    )
    hook_path.write_text(f"#!/bin/sh\nexec {command}\n", encoding="utf-8")
    hook_path.chmod(0o755)
    _git(repository_root, "config", "core.hooksPath", str(hook_directory))
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(repository_root / "missing-legacy-gate.py"))
    return repository_root


def test_valid_commit_passes_the_installed_native_hook(installed_native_hook: Path) -> None:
    before = _git(installed_native_hook, "rev-parse", "HEAD")
    _stage(installed_native_hook, "docs/config.md", "The API uses port 8080.\n")
    _git(installed_native_hook, "commit", "-m", "valid fixture")
    assert _git(installed_native_hook, "rev-parse", "HEAD") != before


def _assert_write_proceeds(repository_root: Path, relative_path: str, content: str) -> None:
    """Exercise the actual dispatcher before attempting the staged commit."""
    hooks_root = Path(pre_commit.__file__).resolve().parent.parent
    payload = {
        "tool_name": "Write",
        "cwd": str(repository_root),
        "tool_input": {
            "file_path": str(repository_root / relative_path),
            "content": content,
        },
    }
    edit_result = subprocess.run(
        [sys.executable, str(hooks_root / "blocking/pre_tool_use_dispatcher.py")],
        cwd=repository_root,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
        timeout=90,
    )
    assert edit_result.returncode == 0, edit_result.stderr
    edit_output = json.loads(edit_result.stdout or "{}")
    assert edit_output.get("hookSpecificOutput", {}).get("permissionDecision") != "deny"


def test_retired_write_check_allows_edit_but_explicit_lint_reports_violation(
    installed_native_hook: Path,
) -> None:
    relative_path = "docs/config.md"
    content = "Previously set via env var.\n"
    _assert_write_proceeds(installed_native_hook, relative_path, content)
    before = _git(installed_native_hook, "rev-parse", "HEAD")
    _stage(installed_native_hook, relative_path, content)
    package_root = Path(pre_commit.__file__).resolve().parents[2]
    lint_result = subprocess.run(
        [sys.executable, str(package_root / "scripts/cde_lint.py"), "--staged", "--format", "json"],
        cwd=installed_native_hook,
        capture_output=True,
        text=True,
        check=False,
        timeout=240,
    )
    assert lint_result.returncode != 0
    assert "state-description" in lint_result.stdout + lint_result.stderr
    commit_result = subprocess.run(
        ["git", "commit", "-m", "invalid fixture"],
        cwd=installed_native_hook,
        capture_output=True,
        text=True,
        check=False,
        timeout=240,
    )
    assert commit_result.returncode == 0
    assert _git(installed_native_hook, "rev-parse", "HEAD") != before
