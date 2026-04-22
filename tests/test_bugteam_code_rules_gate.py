from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GATE_SCRIPT = (
    REPO_ROOT
    / "packages"
    / "claude-dev-env"
    / "skills"
    / "bugteam"
    / "scripts"
    / "bugteam_code_rules_gate.py"
)
SRC_RELATIVE_PATH = "packages/claude-dev-env/skills/bugteam/example_module.py"


def test_gate_help_exits_zero() -> None:
    completed = subprocess.run(
        [sys.executable, str(GATE_SCRIPT), "--help"],
        cwd=str(REPO_ROOT),
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0


def run_git(working_directory: Path, *git_arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *git_arguments],
        cwd=str(working_directory),
        check=True,
        capture_output=True,
        text=True,
    )


def disable_inherited_git_hooks(repository_root: Path) -> None:
    isolation_directory = repository_root / ".git" / "pytest-hook-isolation"
    isolation_directory.mkdir(parents=True, exist_ok=True)
    run_git(repository_root, "config", "core.hooksPath", str(isolation_directory))


def init_repo_with_main(repository_root: Path) -> None:
    run_git(repository_root, "init", "--initial-branch=main")
    disable_inherited_git_hooks(repository_root)
    run_git(repository_root, "config", "user.email", "test@example.com")
    run_git(repository_root, "config", "user.name", "Test User")


def write_file(repository_root: Path, relative_path: str, content: str) -> None:
    absolute = repository_root / relative_path
    absolute.parent.mkdir(parents=True, exist_ok=True)
    absolute.write_text(content, encoding="utf-8")


def stage_and_commit(repository_root: Path, commit_message: str) -> None:
    run_git(repository_root, "add", "-A")
    run_git(repository_root, "commit", "--no-verify", "-m", commit_message)


def copy_enforcer_into(repository_root: Path) -> None:
    blocking_source = REPO_ROOT / "packages" / "claude-dev-env" / "hooks" / "blocking"
    blocking_destination = (
        repository_root / "packages" / "claude-dev-env" / "hooks" / "blocking"
    )
    blocking_destination.mkdir(parents=True, exist_ok=True)
    for filename in ("code_rules_enforcer.py", "code_rules_path_utils.py"):
        source_path = blocking_source / filename
        destination_path = blocking_destination / filename
        destination_path.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")


def copy_gate_script_into(repository_root: Path) -> Path:
    destination = (
        repository_root
        / "packages"
        / "claude-dev-env"
        / "skills"
        / "bugteam"
        / "scripts"
        / "bugteam_code_rules_gate.py"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(GATE_SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
    return destination


def invoke_gate(
    repository_root: Path,
    extra_arguments: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    gate_path = (
        repository_root
        / "packages"
        / "claude-dev-env"
        / "skills"
        / "bugteam"
        / "scripts"
        / "bugteam_code_rules_gate.py"
    )
    command = [sys.executable, str(gate_path), "--base", "main"]
    if extra_arguments:
        command.extend(extra_arguments)
    return subprocess.run(
        command,
        cwd=str(repository_root),
        check=False,
        capture_output=True,
        text=True,
    )


def set_up_fixture_repo(tmp_path: Path) -> Path:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    init_repo_with_main(repository_root)
    copy_gate_script_into(repository_root)
    copy_enforcer_into(repository_root)
    return repository_root


def test_preexisting_violation_on_untouched_line_is_advisory(tmp_path: Path) -> None:
    repository_root = set_up_fixture_repo(tmp_path)
    baseline_content = (
        "def compute() -> int:\n"
        "    local_number = 9999\n"
        "    return local_number\n"
        "\n"
        "\n"
        "def unrelated() -> int:\n"
        "    return 0\n"
    )
    write_file(repository_root, SRC_RELATIVE_PATH, baseline_content)
    stage_and_commit(repository_root, "baseline")
    run_git(repository_root, "checkout", "-b", "feature")
    changed_content = baseline_content.replace(
        "def unrelated() -> int:\n    return 0\n",
        "def unrelated() -> int:\n    return 0\n\n\ndef added_noop() -> int:\n    return 0\n",
    )
    write_file(repository_root, SRC_RELATIVE_PATH, changed_content)
    stage_and_commit(repository_root, "feature change")
    completed = invoke_gate(repository_root)
    combined_stderr = completed.stderr
    assert completed.returncode == 0, combined_stderr
    assert "pre-existing violation(s) in touched files (advisory, not blocking)" in combined_stderr
    assert "9999" in combined_stderr
    assert "introduced on changed lines" not in combined_stderr


def test_new_violation_on_added_line_is_blocking(tmp_path: Path) -> None:
    repository_root = set_up_fixture_repo(tmp_path)
    baseline_content = (
        "def compute() -> int:\n"
        "    return 0\n"
    )
    write_file(repository_root, SRC_RELATIVE_PATH, baseline_content)
    stage_and_commit(repository_root, "baseline")
    run_git(repository_root, "checkout", "-b", "feature")
    changed_content = (
        "def compute() -> int:\n"
        "    local_number = 7777\n"
        "    return local_number\n"
    )
    write_file(repository_root, SRC_RELATIVE_PATH, changed_content)
    stage_and_commit(repository_root, "introduce magic")
    completed = invoke_gate(repository_root)
    combined_stderr = completed.stderr
    assert completed.returncode == 1, combined_stderr
    assert "introduced on changed lines" in combined_stderr
    assert "7777" in combined_stderr


def test_mixed_preexisting_and_new_violations_split_correctly(tmp_path: Path) -> None:
    repository_root = set_up_fixture_repo(tmp_path)
    baseline_content = (
        "def compute() -> int:\n"
        "    old_number = 9999\n"
        "    return old_number\n"
        "\n"
        "\n"
        "def neighbor() -> int:\n"
        "    return 0\n"
    )
    write_file(repository_root, SRC_RELATIVE_PATH, baseline_content)
    stage_and_commit(repository_root, "baseline with pre-existing magic")
    run_git(repository_root, "checkout", "-b", "feature")
    changed_content = (
        "def compute() -> int:\n"
        "    old_number = 9999\n"
        "    return old_number\n"
        "\n"
        "\n"
        "def neighbor() -> int:\n"
        "    new_number = 7777\n"
        "    return new_number\n"
    )
    write_file(repository_root, SRC_RELATIVE_PATH, changed_content)
    stage_and_commit(repository_root, "add new magic on changed line")
    completed = invoke_gate(repository_root)
    combined_stderr = completed.stderr
    assert completed.returncode == 1, combined_stderr
    assert "introduced on changed lines" in combined_stderr
    assert "pre-existing violation(s)" in combined_stderr
    assert "7777" in combined_stderr
    assert "9999" in combined_stderr


def test_explicit_paths_invocation_does_full_file_scan(tmp_path: Path) -> None:
    repository_root = set_up_fixture_repo(tmp_path)
    baseline_content = (
        "def compute() -> int:\n"
        "    old_number = 9999\n"
        "    return old_number\n"
    )
    write_file(repository_root, SRC_RELATIVE_PATH, baseline_content)
    stage_and_commit(repository_root, "baseline with pre-existing magic")
    run_git(repository_root, "checkout", "-b", "feature")
    completed = invoke_gate(repository_root, extra_arguments=[SRC_RELATIVE_PATH])
    combined_stderr = completed.stderr
    assert completed.returncode == 1, combined_stderr
    assert "9999" in combined_stderr
    assert "pre-existing violation(s)" not in combined_stderr
    assert "introduced on changed lines" not in combined_stderr
