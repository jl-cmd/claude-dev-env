"""Prove retirement and local enforcement through an actual disposable install."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from test_native_hook_support import run_git

ALL_RETIRED_HOOK_PATHS = (
    "blocking/code_rules_enforcer.py",
    "blocking/tdd_enforcer.py",
    "blocking/windows_rmtree_blocker.py",
    "blocking/state_description_blocker.py",
    "blocking/subprocess_budget_completeness.py",
    "blocking/hook_prose_detector_consistency.py",
    "blocking/workflow_substitution_slot_blocker.py",
    "validation/hook_format_validator.py",
    "blocking/open_questions_in_plans_blocker.py",
    "blocking/docstring_rule_gate_count_blocker.py",
    "blocking/plain_language_blocker.py",
    "lifecycle/config_change_guard.py",
)
PACKAGE_ROOT = Path(__file__).resolve().parents[2]
ALL_RULE_FIXTURES = (
    ("code-rules", "src/worker.py", "from typing import Any\n\ndef worker() -> Any:\n    return None\n"),
    ("test-pairing", "src/feature.py", "def work() -> None:\n    pass\n"),
    ("state-description", "docs/config.md", "# Config\n\nPreviously set via env var.\n"),
    ("subprocess-budget", "src/timing.py", "import subprocess\nPYTHON_FORMAT_TIMEOUT_SECONDS = 12\nGIT_CHECK_TIMEOUT_SECONDS = 5\ndef worst_case_python_format_seconds() -> int:\n    fix_phase_seconds = PYTHON_FORMAT_TIMEOUT_SECONDS\n    format_phase_seconds = PYTHON_FORMAT_TIMEOUT_SECONDS\n    return fix_phase_seconds + format_phase_seconds\ndef is_untracked_in_git(file_path: str) -> bool:\n    git_check = subprocess.run(['git', 'ls-files', file_path], timeout=GIT_CHECK_TIMEOUT_SECONDS)\n    return git_check.returncode != 0\ndef run_format(file_path: str) -> None:\n    subprocess.run(['ruff', 'format', file_path], timeout=PYTHON_FORMAT_TIMEOUT_SECONDS)\ndef main(file_path: str) -> None:\n    if is_untracked_in_git(file_path):\n        return\n    run_format(file_path)\n"),
    ("hook-prose-consistency", "hooks/hooks_constants/probe_constants.py", 'CORRECTIVE_MESSAGE = "appears as a path or output-key segment"\n'),
    ("workflow-substitution", "scripts/sample.workflow.js", "For EACH candidate i, build a bible dir cand_i per the contract.\n   & ${PY} compose.py --out ${args.work_dir}\\\\cand_i\\\\sample.png --glow <candidate glow_hex>\nReturn: {key: \"cand_i\", name, sample_png}\n"),
)


def _git(repository_path: Path, *arguments: str) -> str:
    return run_git(repository_path, *arguments).stdout.strip()


def _stage(repository_path: Path, relative_path: str, content: str) -> Path:
    file_path = repository_path / relative_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    _git(repository_path, "add", "--", relative_path)
    return file_path


@pytest.fixture()
def repository_root(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> Path:
    temporary_root = tmp_path_factory.mktemp("policy-fixture")
    home_directory = temporary_root / "home"
    home_directory.mkdir()
    monkeypatch.setenv("HOME", str(home_directory))
    monkeypatch.setenv("USERPROFILE", str(home_directory))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    repository_path = temporary_root / "repository"
    repository_path.mkdir()
    _git(repository_path, "init")
    _git(repository_path, "config", "core.hooksPath", str(temporary_root / "disabled-fixture-hooks"))
    _git(repository_path, "config", "user.name", "Fixture")
    _git(repository_path, "config", "user.email", "fixture@example.com")
    _git(repository_path, "commit", "--allow-empty", "-m", "fixture base")
    monkeypatch.chdir(repository_path)
    return repository_path


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
def test_installed_linter_reports_each_retired_file_rule_before_soft_commit(
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
    lint_completed = subprocess.run(
        [sys.executable, str(managed_installation / "scripts/cde_lint.py"), "--staged", "--format", "json"],
        cwd=repository_root, capture_output=True, text=True, check=False, timeout=240,
    )
    assert lint_completed.returncode != 0
    assert rule_id in lint_completed.stdout + lint_completed.stderr
    completed = subprocess.run(
        ["git", "commit", "-m", "invalid fixture"],
        cwd=repository_root, capture_output=True, text=True, check=False, timeout=240,
    )
    assert completed.returncode == 0
    assert _git(repository_root, "rev-parse", "HEAD") != before


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
