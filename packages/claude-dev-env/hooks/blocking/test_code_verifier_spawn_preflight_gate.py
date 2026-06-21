"""Behavior tests for the code_verifier_spawn_preflight_gate PreToolUse hook.

Each test builds a real git repository in a temporary directory, writes real
files (real merge conflicts, real CODE_RULES violations), and runs the hook
script as a subprocess with a real Agent PreToolUse JSON payload on stdin —
the exact production invocation path. No mocks. The harness mirrors
test_precommit_code_rules_gate.py lines 1-70.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

HOOK_PATH = Path(__file__).resolve().parent / "code_verifier_spawn_preflight_gate.py"

CLEAN_MODULE_SOURCE = '''"""Increment helper used by the preflight gate tests."""


def add_one(number: int) -> int:
    """Return *number* plus one.

    Args:
        number: The integer to increment.

    Returns:
        The incremented integer.
    """
    return number + 1
'''

CLEAN_MODULE_SOURCE_EDITED = '''"""Increment helper used by the preflight gate tests."""


def add_one(number: int) -> int:
    """Return *number* plus two.

    Args:
        number: The integer to increment.

    Returns:
        The incremented integer.
    """
    return number + 2
'''

VIOLATING_MODULE_SOURCE = '''"""Module carrying a banned identifier for the preflight gate tests."""


def compute_total() -> int:
    """Return a fixed total.

    Returns:
        The fixed total.
    """
    result = 1
    return result
'''

CLEAN_TWO_FUNCTION_SOURCE = '''"""Two-function helper used by the preflight gate tests."""


def add_one(number: int) -> int:
    """Return *number* plus one.

    Args:
        number: The integer to increment.

    Returns:
        The incremented integer.
    """
    return number + 1


def add_two(number: int) -> int:
    """Return *number* plus two.

    Args:
        number: The integer to increment.

    Returns:
        The integer plus two.
    """
    return number + 2
'''

PREEXISTING_VIOLATION_BASE_SOURCE = '''"""Module that already carries a banned identifier at the base commit."""


def compute_total() -> int:
    """Return a fixed total.

    Returns:
        The fixed total.
    """
    result = 1
    return result


def add_one(number: int) -> int:
    """Return *number* plus one.

    Args:
        number: The integer to increment.

    Returns:
        The incremented integer.
    """
    return number + 1
'''

PREEXISTING_VIOLATION_EDITED_SOURCE = '''"""Module that already carries a banned identifier at the base commit."""


def compute_total() -> int:
    """Return a fixed total.

    Returns:
        The fixed total.
    """
    result = 1
    return result


def add_one(number: int) -> int:
    """Return *number* plus two.

    Args:
        number: The integer to increment.

    Returns:
        The integer plus two.
    """
    return number + 2
'''

SHARED_BASE_SOURCE = '''"""Shared module the conflict fixture edits on both sides."""


def shared_value() -> int:
    """Return the shared base value.

    Returns:
        The shared integer.
    """
    return 100
'''

SHARED_FEATURE_SOURCE = '''"""Shared module the conflict fixture edits on both sides."""


def shared_value() -> int:
    """Return the shared base value.

    Returns:
        The shared integer.
    """
    return 200
'''

SHARED_DIVERGENT_SOURCE = '''"""Shared module the conflict fixture edits on both sides."""


def shared_value() -> int:
    """Return the shared base value.

    Returns:
        The shared integer.
    """
    return 300
'''

OTHER_DIVERGENT_SOURCE = '''"""Unrelated module the divergent base edits for the behind-but-clean case."""


def other_value() -> int:
    """Return the unrelated value.

    Returns:
        The unrelated integer.
    """
    return 42
'''


def run_git(repository_root: Path, *git_arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository_root), *git_arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def disable_native_git_hooks(repository_root: Path) -> None:
    empty_hooks_directory = repository_root.parent / "nohooks"
    empty_hooks_directory.mkdir(exist_ok=True)
    run_git(repository_root, "config", "core.hooksPath", str(empty_hooks_directory))


def initialize_repository(repository_root: Path) -> None:
    run_git(repository_root, "init")
    run_git(repository_root, "config", "user.email", "tests@example.com")
    run_git(repository_root, "config", "user.name", "Preflight Tests")
    disable_native_git_hooks(repository_root)
    run_git(repository_root, "checkout", "-b", "main")
    (repository_root / "base.py").write_text(CLEAN_MODULE_SOURCE, encoding="utf-8")
    run_git(repository_root, "add", "base.py")
    run_git(repository_root, "commit", "-m", "initial")
    main_sha = run_git(repository_root, "rev-parse", "HEAD")
    run_git(repository_root, "update-ref", "refs/remotes/origin/main", main_sha)
    resolved_base = run_git(repository_root, "merge-base", "HEAD", "origin/main")
    assert resolved_base, "fixture must resolve a merge base against origin/main"


def commit_file(repository_root: Path, relative_name: str, source_text: str, message: str) -> str:
    (repository_root / relative_name).write_text(source_text, encoding="utf-8")
    run_git(repository_root, "add", relative_name)
    run_git(repository_root, "commit", "-m", message)
    return run_git(repository_root, "rev-parse", "HEAD")


def write_working_tree_file(repository_root: Path, relative_name: str, source_text: str) -> None:
    (repository_root / relative_name).write_text(source_text, encoding="utf-8")


def write_invalid_utf8_file(repository_root: Path, relative_name: str) -> None:
    (repository_root / relative_name).write_bytes(b"\xff\xfe invalid utf-8 bytes\n")


def advance_origin_main_divergent(
    repository_root: Path, base_sha: str, relative_name: str, source_text: str
) -> None:
    run_git(repository_root, "checkout", "-b", "divergent", base_sha)
    commit_file(repository_root, relative_name, source_text, "divergent edit")
    divergent_sha = run_git(repository_root, "rev-parse", "HEAD")
    run_git(repository_root, "update-ref", "refs/remotes/origin/main", divergent_sha)
    run_git(repository_root, "checkout", "feature")


def write_agent_payload(subagent_type: str, prompt: str, cwd: Path) -> str:
    return json.dumps(
        {
            "tool_name": "Agent",
            "tool_input": {"subagent_type": subagent_type, "prompt": prompt},
            "cwd": str(cwd),
        }
    )


def run_hook(payload: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        check=False,
        input=payload,
        capture_output=True,
        text=True,
        cwd=str(cwd),
        timeout=120,
    )


def is_allow(result: subprocess.CompletedProcess[str]) -> bool:
    stdout_text = result.stdout.strip()
    if not stdout_text:
        return True
    parsed = json.loads(stdout_text)
    hook_output = parsed.get("hookSpecificOutput", {})
    return hook_output.get("permissionDecision") != "deny"


def deny_reason(result: subprocess.CompletedProcess[str]) -> str:
    parsed = json.loads(result.stdout.strip())
    return parsed["hookSpecificOutput"]["permissionDecisionReason"]


def make_conflict_repository(tmp_path: Path) -> Path:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    initialize_repository(repository_root)
    base_sha = commit_file(repository_root, "shared.py", SHARED_BASE_SOURCE, "add shared")
    run_git(repository_root, "checkout", "-b", "feature")
    commit_file(repository_root, "shared.py", SHARED_FEATURE_SOURCE, "feature edit")
    advance_origin_main_divergent(repository_root, base_sha, "shared.py", SHARED_DIVERGENT_SOURCE)
    return repository_root


def test_non_code_verifier_agent_is_no_op(tmp_path: Path) -> None:
    repository_root = make_conflict_repository(tmp_path)
    write_working_tree_file(repository_root, "violator.py", VIOLATING_MODULE_SOURCE)
    payload = write_agent_payload("clean-coder", "do an audit", repository_root)
    result = run_hook(payload, repository_root)
    assert is_allow(result)


def test_non_agent_tool_is_no_op(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    initialize_repository(repository_root)
    payload = json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(repository_root)}
    )
    result = run_hook(payload, repository_root)
    assert is_allow(result)


def test_clean_surface_allows(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    initialize_repository(repository_root)
    run_git(repository_root, "checkout", "-b", "feature")
    write_working_tree_file(repository_root, "feature.py", CLEAN_MODULE_SOURCE)
    payload = write_agent_payload("code-verifier", "verify the change", repository_root)
    result = run_hook(payload, repository_root)
    assert is_allow(result)


def test_real_conflict_denies_naming_files(tmp_path: Path) -> None:
    repository_root = make_conflict_repository(tmp_path)
    payload = write_agent_payload("code-verifier", "verify the change", repository_root)
    result = run_hook(payload, repository_root)
    assert not is_allow(result)
    reason = deny_reason(result)
    assert "shared.py" in reason
    assert "Merge conflicts vs" in reason


def test_real_code_rules_violation_on_added_line_denies(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    initialize_repository(repository_root)
    run_git(repository_root, "checkout", "-b", "feature")
    commit_file(repository_root, "tracked.py", CLEAN_MODULE_SOURCE, "add tracked")
    write_working_tree_file(repository_root, "tracked.py", VIOLATING_MODULE_SOURCE)
    payload = write_agent_payload("code-verifier", "verify the change", repository_root)
    result = run_hook(payload, repository_root)
    assert not is_allow(result)
    reason = deny_reason(result)
    assert "tracked.py" in reason
    assert "Line " in reason


def test_preexisting_violation_on_untouched_line_allows(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    initialize_repository(repository_root)
    carrier_sha = commit_file(
        repository_root, "carrier.py", PREEXISTING_VIOLATION_BASE_SOURCE, "add carrier"
    )
    run_git(repository_root, "update-ref", "refs/remotes/origin/main", carrier_sha)
    run_git(repository_root, "checkout", "-b", "feature")
    write_working_tree_file(repository_root, "carrier.py", PREEXISTING_VIOLATION_EDITED_SOURCE)
    payload = write_agent_payload("code-verifier", "verify the change", repository_root)
    result = run_hook(payload, repository_root)
    assert is_allow(result)


def test_untracked_new_violating_file_denies(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    initialize_repository(repository_root)
    run_git(repository_root, "checkout", "-b", "feature")
    write_working_tree_file(repository_root, "fresh.py", VIOLATING_MODULE_SOURCE)
    payload = write_agent_payload("code-verifier", "verify the change", repository_root)
    result = run_hook(payload, repository_root)
    assert not is_allow(result)
    reason = deny_reason(result)
    assert "fresh.py" in reason


def test_tooling_scratch_file_is_ignored(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    initialize_repository(repository_root)
    run_git(repository_root, "checkout", "-b", "feature")
    scratch_directory = repository_root / ".claude" / "verification"
    scratch_directory.mkdir(parents=True)
    (scratch_directory / "x.py").write_text(VIOLATING_MODULE_SOURCE, encoding="utf-8")
    payload = write_agent_payload("code-verifier", "verify the change", repository_root)
    result = run_hook(payload, repository_root)
    assert is_allow(result)


def test_missing_base_ref_fails_open(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    run_git(repository_root, "init")
    run_git(repository_root, "config", "user.email", "tests@example.com")
    run_git(repository_root, "config", "user.name", "Preflight Tests")
    disable_native_git_hooks(repository_root)
    (repository_root / "base.py").write_text(CLEAN_MODULE_SOURCE, encoding="utf-8")
    run_git(repository_root, "add", "base.py")
    run_git(repository_root, "commit", "-m", "initial")
    payload = write_agent_payload("code-verifier", "verify the change", repository_root)
    result = run_hook(payload, repository_root)
    assert is_allow(result)


def test_non_repo_cwd_fails_open(tmp_path: Path) -> None:
    non_repo_directory = tmp_path / "plain"
    non_repo_directory.mkdir()
    payload = write_agent_payload("code-verifier", "verify the change", non_repo_directory)
    result = run_hook(payload, non_repo_directory)
    assert is_allow(result)


def test_behind_but_conflict_free_allows(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    initialize_repository(repository_root)
    base_sha = commit_file(repository_root, "shared.py", SHARED_BASE_SOURCE, "add shared")
    run_git(repository_root, "checkout", "-b", "feature")
    commit_file(repository_root, "shared.py", SHARED_FEATURE_SOURCE, "feature edit")
    advance_origin_main_divergent(repository_root, base_sha, "other.py", OTHER_DIVERGENT_SOURCE)
    payload = write_agent_payload("code-verifier", "verify the change", repository_root)
    result = run_hook(payload, repository_root)
    assert is_allow(result)


def test_unreadable_changed_file_alone_fails_open(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    initialize_repository(repository_root)
    run_git(repository_root, "checkout", "-b", "feature")
    write_invalid_utf8_file(repository_root, "binary.py")
    payload = write_agent_payload("code-verifier", "verify the change", repository_root)
    result = run_hook(payload, repository_root)
    assert is_allow(result)


def test_unreadable_changed_file_does_not_mask_real_violation(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    initialize_repository(repository_root)
    run_git(repository_root, "checkout", "-b", "feature")
    write_invalid_utf8_file(repository_root, "binary.py")
    write_working_tree_file(repository_root, "fresh.py", VIOLATING_MODULE_SOURCE)
    payload = write_agent_payload("code-verifier", "verify the change", repository_root)
    result = run_hook(payload, repository_root)
    assert not is_allow(result)
    reason = deny_reason(result)
    assert "fresh.py" in reason


def test_conflict_and_violation_single_deny_names_both(tmp_path: Path) -> None:
    repository_root = make_conflict_repository(tmp_path)
    write_working_tree_file(repository_root, "violator.py", VIOLATING_MODULE_SOURCE)
    payload = write_agent_payload("code-verifier", "verify the change", repository_root)
    result = run_hook(payload, repository_root)
    assert not is_allow(result)
    reason = deny_reason(result)
    assert "Merge conflicts vs" in reason
    assert "shared.py" in reason
    assert "CODE_RULES violations on changed lines:" in reason
    assert "violator.py" in reason


def test_hook_imports_real_config_when_parent_holds_shadowing_config(
    tmp_path: Path,
) -> None:
    real_hooks_directory = HOOK_PATH.parent.parent
    real_package_directory = real_hooks_directory.parent

    staged_package_directory = tmp_path / "claude-dev-env"
    shutil.copytree(
        real_hooks_directory,
        staged_package_directory / "hooks",
    )
    shutil.copytree(
        real_package_directory / "_shared",
        staged_package_directory / "_shared",
    )

    shadowing_config_directory = staged_package_directory / "hooks" / "config"
    shadowing_config_directory.mkdir(parents=True, exist_ok=True)
    (shadowing_config_directory / "__init__.py").write_text("", encoding="utf-8")
    (shadowing_config_directory / "unrelated_constants.py").write_text(
        "UNRELATED_VALUE = 1\n", encoding="utf-8"
    )

    staged_hook = (
        staged_package_directory
        / "hooks"
        / "blocking"
        / "code_verifier_spawn_preflight_gate.py"
    )
    payload = write_agent_payload("general-purpose", "unrelated work", tmp_path)
    completed = subprocess.run(
        [sys.executable, str(staged_hook)],
        check=False,
        input=payload,
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        timeout=120,
    )

    assert "ModuleNotFoundError" not in completed.stderr
    assert completed.returncode == 0
