"""Tests for the mechanical commit-gate exemption in verification_verdict_store.

Each test builds a real git repository with a real origin remote and asserts
the exemption decision against the live work tree, exercising the same code
path the verified_commit_gate hook runs.
"""

import importlib.util
import pathlib
import subprocess
import sys

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

store_spec = importlib.util.spec_from_file_location(
    "verification_verdict_store",
    _HOOK_DIR / "verification_verdict_store.py",
)
assert store_spec is not None
assert store_spec.loader is not None
store_module = importlib.util.module_from_spec(store_spec)
store_spec.loader.exec_module(store_module)
is_verification_exempt_diff = store_module.is_verification_exempt_diff
resolve_merge_base = store_module.resolve_merge_base
branch_surface_manifest = store_module.branch_surface_manifest

constants_spec = importlib.util.spec_from_file_location(
    "verified_commit_constants",
    _HOOK_DIR / "config" / "verified_commit_constants.py",
)
assert constants_spec is not None
assert constants_spec.loader is not None
constants_module = importlib.util.module_from_spec(constants_spec)
constants_spec.loader.exec_module(constants_module)
CORRECTIVE_MESSAGE = constants_module.CORRECTIVE_MESSAGE

PRODUCTION_SOURCE = "def add(left: int, right: int) -> int:\n    return left + right\n"
TEST_SOURCE = "def test_add() -> None:\n    assert 1 + 1 == 2\n"


def _run_git(repo_dir: pathlib.Path, *git_arguments: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo_dir), *git_arguments],
        check=True,
        capture_output=True,
        text=True,
    )


def _make_repo_on_branch(
    tmp_path: pathlib.Path, branch_name: str
) -> pathlib.Path:
    origin_dir = tmp_path / "origin.git"
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    subprocess.run(
        ["git", "init", "--bare", f"--initial-branch={branch_name}", str(origin_dir)],
        check=True,
        capture_output=True,
        text=True,
    )
    empty_hooks_dir = tmp_path / "nohooks"
    empty_hooks_dir.mkdir()
    _run_git(work_dir, "init", f"--initial-branch={branch_name}")
    _run_git(work_dir, "config", "user.email", "tests@example.com")
    _run_git(work_dir, "config", "user.name", "Verdict Store Tests")
    _run_git(work_dir, "config", "core.hooksPath", str(empty_hooks_dir))
    (work_dir / "src").mkdir()
    (work_dir / "tests").mkdir()
    (work_dir / "src" / "app.py").write_text(PRODUCTION_SOURCE, encoding="utf-8")
    (work_dir / "tests" / "test_app.py").write_text(TEST_SOURCE, encoding="utf-8")
    (work_dir / "README.md").write_text("# Fixture repo\n", encoding="utf-8")
    _run_git(work_dir, "add", "-A")
    _run_git(work_dir, "commit", "-m", "base")
    _run_git(work_dir, "remote", "add", "origin", str(origin_dir))
    _run_git(work_dir, "push", "-u", "origin", branch_name)
    return work_dir


def _make_repo_with_origin(tmp_path: pathlib.Path) -> pathlib.Path:
    return _make_repo_on_branch(tmp_path, "main")


def _exemption_for(work_dir: pathlib.Path) -> bool:
    merge_base_sha = resolve_merge_base(str(work_dir))
    assert merge_base_sha is not None
    return is_verification_exempt_diff(str(work_dir), merge_base_sha)


def test_production_change_is_gated(tmp_path: pathlib.Path) -> None:
    work_dir = _make_repo_with_origin(tmp_path)
    (work_dir / "src" / "app.py").write_text(
        "def add(left: int, right: int) -> int:\n    return left - right\n",
        encoding="utf-8",
    )
    assert _exemption_for(work_dir) is False


def test_docs_only_change_is_exempt(tmp_path: pathlib.Path) -> None:
    work_dir = _make_repo_with_origin(tmp_path)
    (work_dir / "README.md").write_text(
        "# Fixture repo\n\nUpdated.\n", encoding="utf-8"
    )
    assert _exemption_for(work_dir) is True


def test_docstring_only_python_change_is_exempt(tmp_path: pathlib.Path) -> None:
    work_dir = _make_repo_with_origin(tmp_path)
    (work_dir / "src" / "app.py").write_text(
        'def add(left: int, right: int) -> int:\n    """Add two integers."""\n'
        "    return left + right\n",
        encoding="utf-8",
    )
    assert _exemption_for(work_dir) is True


def test_modified_test_file_is_exempt(tmp_path: pathlib.Path) -> None:
    work_dir = _make_repo_with_origin(tmp_path)
    (work_dir / "tests" / "test_app.py").write_text(
        TEST_SOURCE + "\n\ndef test_add_zero() -> None:\n    assert 0 + 0 == 0\n",
        encoding="utf-8",
    )
    assert _exemption_for(work_dir) is True


def test_untracked_test_prefix_file_is_exempt(tmp_path: pathlib.Path) -> None:
    work_dir = _make_repo_with_origin(tmp_path)
    (work_dir / "tests" / "test_extra.py").write_text(TEST_SOURCE, encoding="utf-8")
    assert _exemption_for(work_dir) is True


def test_untracked_test_suffix_file_is_exempt(tmp_path: pathlib.Path) -> None:
    work_dir = _make_repo_with_origin(tmp_path)
    (work_dir / "tests" / "app_test.py").write_text(TEST_SOURCE, encoding="utf-8")
    assert _exemption_for(work_dir) is True


def test_modified_conftest_is_exempt(tmp_path: pathlib.Path) -> None:
    work_dir = _make_repo_with_origin(tmp_path)
    (work_dir / "tests" / "conftest.py").write_text(
        "import pytest\n\n\n@pytest.fixture\ndef sample() -> int:\n    return 3\n",
        encoding="utf-8",
    )
    assert _exemption_for(work_dir) is True


def test_deleted_test_file_is_exempt(tmp_path: pathlib.Path) -> None:
    work_dir = _make_repo_with_origin(tmp_path)
    (work_dir / "tests" / "test_app.py").unlink()
    assert _exemption_for(work_dir) is True


def test_mixed_test_and_production_change_is_gated(tmp_path: pathlib.Path) -> None:
    work_dir = _make_repo_with_origin(tmp_path)
    (work_dir / "tests" / "test_app.py").write_text(
        TEST_SOURCE + "\n", encoding="utf-8"
    )
    (work_dir / "src" / "app.py").write_text(
        "def add(left: int, right: int) -> int:\n    return left * right\n",
        encoding="utf-8",
    )
    assert _exemption_for(work_dir) is False


def test_untracked_production_file_is_gated(tmp_path: pathlib.Path) -> None:
    work_dir = _make_repo_with_origin(tmp_path)
    (work_dir / "src" / "extra.py").write_text(PRODUCTION_SOURCE, encoding="utf-8")
    assert _exemption_for(work_dir) is False


def test_production_file_named_like_test_outside_python_is_gated(
    tmp_path: pathlib.Path,
) -> None:
    work_dir = _make_repo_with_origin(tmp_path)
    (work_dir / "src" / "test_data.json").write_text("{}", encoding="utf-8")
    assert _exemption_for(work_dir) is False


def test_comment_only_change_in_non_python_file_is_gated(
    tmp_path: pathlib.Path,
) -> None:
    work_dir = _make_repo_with_origin(tmp_path)
    shell_script_path = work_dir / "src" / "deploy.sh"
    shell_script_path.write_text("# build the project\nmake build\n", encoding="utf-8")
    _run_git(work_dir, "add", "-A")
    _run_git(work_dir, "commit", "-m", "add deploy script")
    shell_script_path.write_text(
        "# build the release artifact\nmake build\n", encoding="utf-8"
    )
    assert _exemption_for(work_dir) is False


def test_corrective_message_scopes_comment_exemption_to_python() -> None:
    lowered_message = CORRECTIVE_MESSAGE.lower()
    assert "comment" in lowered_message
    assert "python" in lowered_message
    assert "comment-, and test-only surfaces are exempt" not in lowered_message


def test_untracked_claude_production_hook_is_gated(tmp_path: pathlib.Path) -> None:
    work_dir = _make_repo_with_origin(tmp_path)
    new_hook_dir = work_dir / ".claude" / "hooks" / "blocking"
    new_hook_dir.mkdir(parents=True)
    (new_hook_dir / "evil_new_hook.py").write_text(PRODUCTION_SOURCE, encoding="utf-8")
    assert _exemption_for(work_dir) is False


def test_untracked_claude_production_hook_is_in_surface_manifest(
    tmp_path: pathlib.Path,
) -> None:
    work_dir = _make_repo_with_origin(tmp_path)
    new_hook_dir = work_dir / ".claude" / "hooks" / "blocking"
    new_hook_dir.mkdir(parents=True)
    (new_hook_dir / "evil_new_hook.py").write_text(PRODUCTION_SOURCE, encoding="utf-8")
    merge_base_sha = resolve_merge_base(str(work_dir))
    assert merge_base_sha is not None
    surface_manifest_text = branch_surface_manifest(str(work_dir), merge_base_sha)
    assert surface_manifest_text is not None
    assert ".claude/hooks/blocking/evil_new_hook.py" in surface_manifest_text


def test_untracked_claude_worktree_scratch_copy_stays_filtered(
    tmp_path: pathlib.Path,
) -> None:
    work_dir = _make_repo_with_origin(tmp_path)
    scratch_dir = work_dir / ".claude" / "worktrees" / "feature" / "src"
    scratch_dir.mkdir(parents=True)
    (scratch_dir / "app.py").write_text(PRODUCTION_SOURCE, encoding="utf-8")
    assert _exemption_for(work_dir) is True
    merge_base_sha = resolve_merge_base(str(work_dir))
    assert merge_base_sha is not None
    surface_manifest_text = branch_surface_manifest(str(work_dir), merge_base_sha)
    assert surface_manifest_text == ""


def _git_output(work_dir: pathlib.Path, *git_arguments: str) -> str:
    completed_process = subprocess.run(
        ["git", "-C", str(work_dir), *git_arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed_process.stdout.strip()


def test_resolve_merge_base_finds_nonstandard_default_branch(
    tmp_path: pathlib.Path,
) -> None:
    work_dir = _make_repo_on_branch(tmp_path, "develop")
    subprocess.run(
        ["git", "-C", str(work_dir), "remote", "set-head", "origin", "--delete"],
        check=True,
        capture_output=True,
        text=True,
    )
    expected_merge_base = _git_output(
        work_dir, "merge-base", "HEAD", "origin/develop"
    )
    assert resolve_merge_base(str(work_dir)) == expected_merge_base


def test_production_change_is_gated_on_nonstandard_default_branch(
    tmp_path: pathlib.Path,
) -> None:
    work_dir = _make_repo_on_branch(tmp_path, "develop")
    subprocess.run(
        ["git", "-C", str(work_dir), "remote", "set-head", "origin", "--delete"],
        check=True,
        capture_output=True,
        text=True,
    )
    (work_dir / "src" / "app.py").write_text(
        "def add(left: int, right: int) -> int:\n    return left - right\n",
        encoding="utf-8",
    )
    assert _exemption_for(work_dir) is False
