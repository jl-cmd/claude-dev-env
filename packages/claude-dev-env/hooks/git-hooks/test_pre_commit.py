from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pre_commit
import pytest

from git_hooks_constants.staged_policy_lint import POLICY_LINT_TIMEOUT_SECONDS


def make_gate_script_returning(exit_code: int, target_path: Path) -> Path:
    target_path.write_text(
        f"import sys\nsys.exit({exit_code})\n",
        encoding="utf-8",
    )
    return target_path


@pytest.fixture()
def fake_gate_script_blocking(tmp_path: Path) -> Path:
    return make_gate_script_returning(1, tmp_path / "fake_gate_blocking.py")


@pytest.fixture()
def fake_gate_script_passing(tmp_path: Path) -> Path:
    return make_gate_script_returning(0, tmp_path / "fake_gate_passing.py")


def test_main_exits_zero_when_gate_script_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "CODE_RULES_GATE_PATH",
        str(tmp_path / "does_not_exist.py"),
    )

    exit_code = pre_commit.main()

    assert exit_code == 0


def test_main_propagates_blocking_exit_code_from_gate(
    fake_gate_script_blocking: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(fake_gate_script_blocking))

    exit_code = pre_commit.main()

    assert exit_code == 1


def test_main_propagates_passing_exit_code_from_gate(
    fake_gate_script_passing: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(fake_gate_script_passing))

    exit_code = pre_commit.main()

    assert exit_code == 0


def test_main_invokes_gate_with_immediate_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded_arguments_path = tmp_path / "recorded_arguments.txt"
    recording_gate_script_path = tmp_path / "recording_gate.py"
    recording_gate_script_path.write_text(
        "import sys, pathlib\n"
        f'pathlib.Path(r"{recorded_arguments_path}").write_text('
        "'\\n'.join(sys.argv[1:]), encoding='utf-8')\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(recording_gate_script_path))

    exit_code = pre_commit.main()

    assert exit_code == 0
    assert recorded_arguments_path.exists(), (
        f"recording gate did not write to {recorded_arguments_path}"
    )
    recorded_arguments = recorded_arguments_path.read_text(
        encoding="utf-8"
    ).splitlines()
    assert recorded_arguments == ["--immediate"]


def test_main_exits_two_when_invoke_gate_raises_oserror(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing_gate_path = tmp_path / "gate.py"
    existing_gate_path.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(existing_gate_path))

    original_run = __import__("subprocess").run

    def raising_run(*args: object, **kwargs: object) -> object:
        raise OSError("no such file")

    monkeypatch.setattr(__import__("subprocess"), "run", raising_run)

    exit_code = pre_commit.main()

    assert exit_code == 2


def test_main_emits_stderr_warning_when_gate_script_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv(
        "CODE_RULES_GATE_PATH",
        str(tmp_path / "does_not_exist.py"),
    )

    exit_code = pre_commit.main()

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "gate script not found" in captured.err


def test_invoke_gate_returns_infrastructure_failure_when_strict_resolve_raises(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing_gate_path = tmp_path / "missing_gate.py"
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(missing_gate_path))
    missing_gate_path.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")

    original_resolve = Path.resolve

    def raising_resolve(self: Path, strict: bool = False) -> Path:
        if strict and self == missing_gate_path.resolve():
            raise FileNotFoundError("not found")
        return original_resolve(self, strict=strict)

    monkeypatch.setattr(Path, "resolve", raising_resolve)

    exit_code = pre_commit.invoke_gate(missing_gate_path)

    assert exit_code == 2


def test_invoke_gate_uses_resolved_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_gate_dir = tmp_path / "real"
    real_gate_dir.mkdir()
    real_gate_path = real_gate_dir / "gate.py"
    recorded_path_file = tmp_path / "recorded_path.txt"
    real_gate_path.write_text(
        "import sys, pathlib\n"
        f'pathlib.Path(r"{recorded_path_file}").write_text(sys.argv[0], encoding="utf-8")\n'
        "sys.exit(0)\n",
        encoding="utf-8",
    )
    symlink_gate_path = tmp_path / "link_gate.py"
    symlink_gate_path.symlink_to(real_gate_path)
    resolved_path = symlink_gate_path.resolve()
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(symlink_gate_path))

    exit_code = pre_commit.main()

    assert exit_code == 0
    executed_path = recorded_path_file.read_text(encoding="utf-8")
    assert executed_path == str(resolved_path)


RMTREE_FIXTURE_KEYWORD = "ignore_errors"
ALL_RULE_FIXTURES = (
    (
        "code-rules",
        "src/worker.py",
        "from typing import Any\n\ndef worker() -> Any:\n    return None\n",
    ),
    (
        "test-pairing",
        "src/feature.py",
        "def work() -> None:\n    pass\n",
    ),
    (
        "rmtree-safety",
        "src/cleanup.py",
        f"import shutil\nshutil.rmtree('fixture', {RMTREE_FIXTURE_KEYWORD}=True)\n",
    ),
    (
        "state-description",
        "docs/config.md",
        "# Config\n\nPreviously set via env var.\n",
    ),
    (
        "subprocess-budget",
        "src/timing.py",
        "import subprocess\n"
        "PYTHON_FORMAT_TIMEOUT_SECONDS = 12\n"
        "GIT_CHECK_TIMEOUT_SECONDS = 5\n"
        "def worst_case_python_format_seconds() -> int:\n"
        "    fix_phase_seconds = PYTHON_FORMAT_TIMEOUT_SECONDS\n"
        "    format_phase_seconds = PYTHON_FORMAT_TIMEOUT_SECONDS\n"
        "    return fix_phase_seconds + format_phase_seconds\n"
        "def is_untracked_in_git(file_path: str) -> bool:\n"
        "    git_check = subprocess.run(['git', 'ls-files', file_path], "
        "timeout=GIT_CHECK_TIMEOUT_SECONDS)\n"
        "    return git_check.returncode != 0\n"
        "def run_format(file_path: str) -> None:\n"
        "    subprocess.run(['ruff', 'format', file_path], "
        "timeout=PYTHON_FORMAT_TIMEOUT_SECONDS)\n"
        "def main(file_path: str) -> None:\n"
        "    if is_untracked_in_git(file_path):\n"
        "        return\n"
        "    run_format(file_path)\n",
    ),
    (
        "hook-prose-consistency",
        "hooks/hooks_constants/probe_constants.py",
        'CORRECTIVE_MESSAGE = "appears as a path or output-key segment"\n',
    ),
    (
        "workflow-substitution",
        "scripts/sample.workflow.js",
        "For EACH candidate i, build a bible dir cand_i per the contract.\n"
        "   & ${PY} compose.py --out ${args.work_dir}\\\\cand_i\\\\sample.png "
        "--glow <candidate glow_hex>\n"
        'Return: {key: "cand_i", name, sample_png}\n',
    ),
)


def _git(repository_root: Path, *all_arguments: str) -> str:
    completed = subprocess.run(
        ["git", *all_arguments],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return completed.stdout.strip()


@pytest.fixture()
def repository_root(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """Create a repository with private Git configuration and no inherited hooks."""
    tmp_path = tmp_path_factory.mktemp("policy-fixture")
    home_directory = tmp_path / "home"
    home_directory.mkdir()
    monkeypatch.setenv("HOME", str(home_directory))
    monkeypatch.setenv("USERPROFILE", str(home_directory))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.delenv("GIT_INDEX_FILE", raising=False)
    monkeypatch.delenv("GIT_DIR", raising=False)
    monkeypatch.delenv("GIT_WORK_TREE", raising=False)
    root = tmp_path / "repository"
    root.mkdir()
    _git(root, "init")
    _git(root, "config", "core.hooksPath", str(tmp_path / "disabled-fixture-hooks"))
    _git(root, "config", "user.name", "Fixture")
    _git(root, "config", "user.email", "fixture@example.com")
    _git(root, "commit", "--allow-empty", "-m", "fixture base")
    monkeypatch.chdir(root)
    return root


def _stage(repository_root: Path, relative_path: str, content: str) -> Path:
    file_path = repository_root / relative_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    _git(repository_root, "add", "--", relative_path)
    return file_path


def _lint_report(repository_root: Path) -> tuple[int, dict[str, object]]:
    completed = subprocess.run(
        [
            sys.executable,
            str(pre_commit.resolve_policy_lint_script_path()),
            "--staged",
            "--format",
            "json",
        ],
        cwd=repository_root,
        check=False,
        capture_output=True,
        text=True,
        timeout=POLICY_LINT_TIMEOUT_SECONDS,
    )
    assert completed.stderr == "", completed.stderr
    return completed.returncode, json.loads(completed.stdout)


@pytest.mark.parametrize(("rule_id", "relative_path", "content"), ALL_RULE_FIXTURES)
def test_real_staged_linter_catches_each_replaced_rule(
    repository_root: Path,
    rule_id: str,
    relative_path: str,
    content: str,
) -> None:
    _stage(repository_root, relative_path, content)
    exit_code, report = _lint_report(repository_root)
    assert exit_code == 1, report
    assert report["failed_rules"] == [], report
    all_diagnostics = report["diagnostics"]
    assert isinstance(all_diagnostics, list)
    assert rule_id in {each["rule_id"] for each in all_diagnostics}, report


def _stage_valid_pair(repository_root: Path, relative_path: str) -> None:
    source_path = Path(relative_path)
    clean_content = {
        ".py": (
            "def is_ready() -> bool:\n"
            '    """Report readiness.\n\n'
            "    Returns:\n        True for the fixture.\n"
            '    """\n'
            "    return True\n"
        ),
        ".js": "export const isEnabled = true;\n",
        ".md": "# Config\n\nThe API uses port 8080.\n",
    }[source_path.suffix]
    _stage(repository_root, relative_path, clean_content)
    paired_name = (
        f"test_{source_path.stem}.py"
        if source_path.suffix == ".py"
        else f"{source_path.stem}.test{source_path.suffix}"
    )
    paired_content = (
        f"from {source_path.stem} import is_ready\n\n"
        "def test_is_ready() -> None:\n    assert is_ready()\n"
        if source_path.suffix == ".py"
        else ""
    )
    _stage(repository_root, (source_path.parent / paired_name).as_posix(), paired_content)


@pytest.mark.parametrize(("rule_id", "relative_path", "content"), ALL_RULE_FIXTURES)
def test_valid_paired_content_passes_the_real_local_commit_linter(
    repository_root: Path,
    rule_id: str,
    relative_path: str,
    content: str,
) -> None:
    _stage_valid_pair(repository_root, relative_path)
    assert pre_commit.run_staged_policy_lint() == 0


def test_unstaged_fix_does_not_hide_staged_violation(repository_root: Path) -> None:
    target = _stage(repository_root, "docs/config.md", "Previously set via env var.\n")
    target.write_text("The API uses port 8080.\n", encoding="utf-8")
    assert pre_commit.run_staged_policy_lint() == 1


def test_alternate_git_index_is_checked(
    repository_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    alternate_index = repository_root / ".git" / "alternate-index"
    monkeypatch.setenv("GIT_INDEX_FILE", str(alternate_index))
    _git(repository_root, "read-tree", "HEAD")
    _stage(repository_root, "docs/config.md", "Previously set via env var.\n")
    assert pre_commit.run_staged_policy_lint() == 1
    monkeypatch.delenv("GIT_INDEX_FILE")
    assert pre_commit.run_staged_policy_lint() == 0


def test_missing_linter_does_not_allow_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        pre_commit, "resolve_policy_lint_script_path", lambda: tmp_path / "missing.py"
    )
    assert pre_commit.main() == 2


@pytest.mark.parametrize("exit_code", (1, 2, 3))
def test_linter_failure_reaches_git_before_legacy_gate(
    monkeypatch: pytest.MonkeyPatch,
    exit_code: int,
) -> None:
    monkeypatch.setattr(pre_commit, "run_staged_policy_lint", lambda: exit_code)
    all_gate_calls: list[object] = []
    monkeypatch.setattr(
        pre_commit,
        "resolve_gate_script_path",
        lambda: all_gate_calls.append("unexpected gate"),
    )
    assert pre_commit.main() == exit_code
    assert all_gate_calls == []


def test_timeout_is_an_infrastructure_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script_path = tmp_path / "lint.py"
    script_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(pre_commit, "resolve_policy_lint_script_path", lambda: script_path)

    def timed_out(*all_arguments: object, **all_options: object) -> object:
        raise subprocess.TimeoutExpired("lint fixture", POLICY_LINT_TIMEOUT_SECONDS)

    monkeypatch.setattr(pre_commit.subprocess, "run", timed_out)
    assert pre_commit.run_staged_policy_lint() == 2
