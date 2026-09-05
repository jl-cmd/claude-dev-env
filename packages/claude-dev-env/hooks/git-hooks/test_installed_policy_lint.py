"""Prove retirement and local enforcement through an actual disposable install."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from test_pre_commit import ALL_RULE_FIXTURES, _git, _stage
from test_pre_commit import repository_root as repository_root

ALL_RETIRED_HOOK_PATHS = (
    "blocking/code_rules_enforcer.py",
    "blocking/tdd_enforcer.py",
    "blocking/windows_rmtree_blocker.py",
    "blocking/state_description_blocker.py",
    "blocking/subprocess_budget_completeness.py",
    "blocking/hook_prose_detector_consistency.py",
    "blocking/workflow_substitution_slot_blocker.py",
)
PACKAGE_ROOT = Path(__file__).resolve().parents[2]


def _legacy_settings_bytes(managed_root: Path, foreign_command: str) -> bytes:
    original_settings = {
        "permissions": {"allow": ["Read"]},
        "hooks": {"PreToolUse": [{
            "matcher": "Write|Edit|MultiEdit|apply_patch",
            "hooks": [
                {"type": "command", "command": foreign_command, "timeout": 17},
                *({
                    "type": "command",
                    "command": f"python {managed_root.as_posix()}/hooks/{each_path}",
                    "timeout": 10,
                } for each_path in ALL_RETIRED_HOOK_PATHS),
            ],
        }]},
    }
    return json.dumps(original_settings, indent=2).encode("utf-8")


def _install_environment(home: Path) -> dict[str, str]:
    environment = {
        each_name: each_value for each_name, each_value in os.environ.items()
        if not each_name.startswith("GIT_")
    }
    environment.update({
        "HOME": str(home),
        "USERPROFILE": str(home),
        "CLAUDE_CONFIG_DIR": str(home / ".claude"),
        "CODEX_HOME": str(home / ".codex"),
        "GIT_CONFIG_GLOBAL": str(home / "gitconfig"),
        "GIT_CONFIG_NOSYSTEM": "1",
    })
    return environment


def _install_twice(home: Path, settings_path: Path) -> bytes:
    all_settings_bytes: list[bytes] = []
    for each_run in range(2):
        completed = subprocess.run(
            ["node", str(PACKAGE_ROOT / "bin/install.mjs"), "--only", "core"],
            cwd=PACKAGE_ROOT, env=_install_environment(home),
            capture_output=True, text=True, check=False, timeout=180,
        )
        (home / f"install-{each_run}.log").write_text(
            completed.stdout + completed.stderr, encoding="utf-8"
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        all_settings_bytes.append(settings_path.read_bytes())
    assert all_settings_bytes[0] == all_settings_bytes[1]
    return all_settings_bytes[-1]


def _assert_retired_registrations(managed_root: Path, settings_bytes: bytes, foreign_command: str) -> None:
    settings = json.loads(settings_bytes)
    all_commands = [
        each_hook["command"]
        for each_groups in settings["hooks"].values()
        for each_group in each_groups
        for each_hook in each_group["hooks"]
    ]
    assert all_commands.count(foreign_command) == 1
    assert "Read" in settings["permissions"]["allow"]
    for each_relative_path in ALL_RETIRED_HOOK_PATHS:
        assert not any(each_relative_path in each_command for each_command in all_commands)
        source = PACKAGE_ROOT / "hooks" / each_relative_path
        installed = managed_root / "hooks" / each_relative_path
        assert hashlib.sha256(installed.read_bytes()).digest() == hashlib.sha256(source.read_bytes()).digest()


@pytest.fixture(scope="module")
def managed_installation(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Install twice into a private home while retaining exact prior settings."""
    home = tmp_path_factory.mktemp("installed-policy")
    managed_root = home / ".claude"
    managed_root.mkdir()
    foreign_command = "python /unmanaged/fixture_notice.py"
    original_bytes = _legacy_settings_bytes(managed_root, foreign_command)
    settings_path = managed_root / "settings.json"
    settings_path.write_bytes(original_bytes)
    backup_directory = home / "before-cutover"
    backup_directory.mkdir()
    (backup_directory / "settings.json").write_bytes(original_bytes)
    installed_settings = _install_twice(home, settings_path)
    _assert_retired_registrations(managed_root, installed_settings, foreign_command)
    assert (backup_directory / "settings.json").read_bytes() == original_bytes
    hook_path = _git(home, "config", "--file", str(home / "gitconfig"), "--get", "core.hooksPath")
    assert Path(hook_path).resolve() == (managed_root / "hooks/git-hooks").resolve()
    return managed_root


@pytest.mark.parametrize(("rule_id", "relative_path", "content"), ALL_RULE_FIXTURES)
def test_installed_native_commit_catches_each_retired_file_rule(
    managed_installation: Path,
    repository_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    rule_id: str,
    relative_path: str,
    content: str,
) -> None:
    _git(repository_root, "config", "core.hooksPath", str(managed_installation / "hooks/git-hooks"))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(repository_root / "missing-old-gate.py"))
    before = _git(repository_root, "rev-parse", "HEAD")
    _stage(repository_root, relative_path, content)
    completed = subprocess.run(
        ["git", "commit", "-m", "invalid fixture"],
        cwd=repository_root, capture_output=True, text=True, check=False, timeout=240,
    )
    assert completed.returncode != 0
    assert rule_id in completed.stdout + completed.stderr
    assert _git(repository_root, "rev-parse", "HEAD") == before


def test_installed_linter_and_native_commit_allow_valid_changes(
    managed_installation: Path,
    repository_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _git(repository_root, "config", "core.hooksPath", str(managed_installation / "hooks/git-hooks"))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(repository_root / "missing-old-gate.py"))
    _stage(repository_root, "docs/guide.md", "# Guide\n\nThe API uses port 8080.\n")
    completed = subprocess.run(
        [sys.executable, str(managed_installation / "scripts/cde_lint.py"), "--staged", "--format", "json"],
        cwd=repository_root, capture_output=True, text=True, check=False, timeout=240,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    report = json.loads(completed.stdout)
    assert report["failed_rules"] == []
    assert "terminology-sweep" in report["executed_rules"]
    before = _git(repository_root, "rev-parse", "HEAD")
    _git(repository_root, "commit", "-m", "valid installed fixture")
    assert _git(repository_root, "rev-parse", "HEAD") != before
