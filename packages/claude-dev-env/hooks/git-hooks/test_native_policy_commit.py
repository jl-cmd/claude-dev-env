"""Exercise the native Git commit boundary in disposable repositories."""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path

import pre_commit
import pytest
from test_pre_commit import _git, _stage
from test_pre_commit import repository_root as repository_root


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


def test_retired_write_check_allows_edit_but_local_commit_catches_violation(
    installed_native_hook: Path,
) -> None:
    relative_path = "docs/config.md"
    content = "Previously set via env var.\n"
    hooks_root = Path(pre_commit.__file__).resolve().parent.parent
    payload = {
        "tool_name": "Write",
        "cwd": str(installed_native_hook),
        "tool_input": {
            "file_path": str(installed_native_hook / relative_path),
            "content": content,
        },
    }
    edit_result = subprocess.run(
        [sys.executable, str(hooks_root / "blocking/pre_tool_use_dispatcher.py")],
        cwd=installed_native_hook,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
        timeout=90,
    )
    assert edit_result.returncode == 0, edit_result.stderr
    edit_output = json.loads(edit_result.stdout or "{}")
    assert edit_output.get("hookSpecificOutput", {}).get("permissionDecision") != "deny"
    before = _git(installed_native_hook, "rev-parse", "HEAD")
    _stage(installed_native_hook, relative_path, content)
    commit_result = subprocess.run(
        ["git", "commit", "-m", "invalid fixture"],
        cwd=installed_native_hook,
        capture_output=True,
        text=True,
        check=False,
        timeout=240,
    )
    assert commit_result.returncode != 0
    assert "state-description" in commit_result.stdout + commit_result.stderr
    assert _git(installed_native_hook, "rev-parse", "HEAD") == before
