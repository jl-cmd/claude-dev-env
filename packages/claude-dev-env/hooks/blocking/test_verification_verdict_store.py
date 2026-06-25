"""Tests for the mechanical commit-gate exemption in verification_verdict_store.

Each test builds a real git repository with a real origin remote and asserts
the exemption decision against the live work tree, exercising the same code
path the verified_commit_gate hook runs.
"""

import importlib.util
import json
import pathlib
import subprocess
import sys

import pytest

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
manifest_sha256 = store_module.manifest_sha256
workflow_verdict_covers_surface = store_module.workflow_verdict_covers_surface
minted_verdict_covers_surface = store_module.minted_verdict_covers_surface
write_verdict = store_module.write_verdict
worktree_path_for_branch = store_module.worktree_path_for_branch
empty_surface_hash = store_module.empty_surface_hash

constants_spec = importlib.util.spec_from_file_location(
    "verified_commit_constants",
    _HOOK_DIR / "config" / "verified_commit_constants.py",
)
assert constants_spec is not None
assert constants_spec.loader is not None
constants_module = importlib.util.module_from_spec(constants_spec)
constants_spec.loader.exec_module(constants_module)
CORRECTIVE_MESSAGE = constants_module.CORRECTIVE_MESSAGE
EMPTY_SURFACE_GUARD_MESSAGE = constants_module.EMPTY_SURFACE_GUARD_MESSAGE
BRANCH_WORKTREE_ABSENT_MESSAGE = constants_module.BRANCH_WORKTREE_ABSENT_MESSAGE

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


MATCHING_MANIFEST_SHA256 = "a" * 64
OTHER_MANIFEST_SHA256 = "b" * 64
VERIFIER_AGENT_TYPE = "code-verifier"


def _verdict_transcript_text(is_all_pass: bool, bound_manifest_sha256: str) -> str:
    verdict_record = {
        "all_pass": is_all_pass,
        "findings": [],
        "manifest_sha256": bound_manifest_sha256,
    }
    assistant_text = (
        "Verification complete.\n\n```verdict\n"
        + json.dumps(verdict_record)
        + "\n```\n"
    )
    assistant_entry = {
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": assistant_text}]},
    }
    return json.dumps(assistant_entry) + "\n"


def _write_agent_transcript(
    subagents_dir: pathlib.Path,
    agent_id: str,
    agent_type: str,
    transcript_text: str,
    should_write_sidecar: bool,
) -> None:
    workflow_dir = subagents_dir / "workflows" / "wf_x"
    workflow_dir.mkdir(parents=True, exist_ok=True)
    (workflow_dir / f"agent-{agent_id}.jsonl").write_text(
        transcript_text, encoding="utf-8"
    )
    if should_write_sidecar:
        (workflow_dir / f"agent-{agent_id}.meta.json").write_text(
            json.dumps({"agentType": agent_type}), encoding="utf-8"
        )


def _session_transcript_path(tmp_path: pathlib.Path, session_id: str) -> pathlib.Path:
    session_root = tmp_path / "projects" / "demo"
    session_root.mkdir(parents=True)
    transcript_path = session_root / f"{session_id}.jsonl"
    transcript_path.write_text("", encoding="utf-8")
    return transcript_path


def test_workflow_verdict_covers_surface_true_for_matching_passing_verifier(
    tmp_path: pathlib.Path,
) -> None:
    transcript_path = _session_transcript_path(tmp_path, "sess1")
    subagents_dir = tmp_path / "projects" / "demo" / "sess1" / "subagents"
    _write_agent_transcript(
        subagents_dir,
        "01",
        VERIFIER_AGENT_TYPE,
        _verdict_transcript_text(True, MATCHING_MANIFEST_SHA256),
        should_write_sidecar=True,
    )
    assert (
        workflow_verdict_covers_surface(
            str(transcript_path), MATCHING_MANIFEST_SHA256
        )
        is True
    )


def test_workflow_verdict_covers_surface_false_for_nonmatching_hash(
    tmp_path: pathlib.Path,
) -> None:
    transcript_path = _session_transcript_path(tmp_path, "sess1")
    subagents_dir = tmp_path / "projects" / "demo" / "sess1" / "subagents"
    _write_agent_transcript(
        subagents_dir,
        "01",
        VERIFIER_AGENT_TYPE,
        _verdict_transcript_text(True, OTHER_MANIFEST_SHA256),
        should_write_sidecar=True,
    )
    assert (
        workflow_verdict_covers_surface(
            str(transcript_path), MATCHING_MANIFEST_SHA256
        )
        is False
    )


def test_workflow_verdict_covers_surface_false_for_all_pass_false(
    tmp_path: pathlib.Path,
) -> None:
    transcript_path = _session_transcript_path(tmp_path, "sess1")
    subagents_dir = tmp_path / "projects" / "demo" / "sess1" / "subagents"
    _write_agent_transcript(
        subagents_dir,
        "01",
        VERIFIER_AGENT_TYPE,
        _verdict_transcript_text(False, MATCHING_MANIFEST_SHA256),
        should_write_sidecar=True,
    )
    assert (
        workflow_verdict_covers_surface(
            str(transcript_path), MATCHING_MANIFEST_SHA256
        )
        is False
    )


def test_workflow_verdict_covers_surface_false_for_non_verifier_sidecar(
    tmp_path: pathlib.Path,
) -> None:
    transcript_path = _session_transcript_path(tmp_path, "sess1")
    subagents_dir = tmp_path / "projects" / "demo" / "sess1" / "subagents"
    _write_agent_transcript(
        subagents_dir,
        "01",
        "clean-coder",
        _verdict_transcript_text(True, MATCHING_MANIFEST_SHA256),
        should_write_sidecar=True,
    )
    assert (
        workflow_verdict_covers_surface(
            str(transcript_path), MATCHING_MANIFEST_SHA256
        )
        is False
    )


def test_workflow_verdict_covers_surface_false_for_missing_sidecar_with_verdict(
    tmp_path: pathlib.Path,
) -> None:
    transcript_path = _session_transcript_path(tmp_path, "sess1")
    subagents_dir = tmp_path / "projects" / "demo" / "sess1" / "subagents"
    _write_agent_transcript(
        subagents_dir,
        "01",
        VERIFIER_AGENT_TYPE,
        _verdict_transcript_text(True, MATCHING_MANIFEST_SHA256),
        should_write_sidecar=False,
    )
    assert (
        workflow_verdict_covers_surface(
            str(transcript_path), MATCHING_MANIFEST_SHA256
        )
        is False
    )


def test_workflow_verdict_covers_surface_false_for_corrupt_sidecar_with_verdict(
    tmp_path: pathlib.Path,
) -> None:
    transcript_path = _session_transcript_path(tmp_path, "sess1")
    subagents_dir = tmp_path / "projects" / "demo" / "sess1" / "subagents"
    _write_agent_transcript(
        subagents_dir,
        "01",
        VERIFIER_AGENT_TYPE,
        _verdict_transcript_text(True, MATCHING_MANIFEST_SHA256),
        should_write_sidecar=False,
    )
    corrupt_sidecar = (
        subagents_dir / "workflows" / "wf_x" / "agent-01.meta.json"
    )
    corrupt_sidecar.write_text("{not valid json", encoding="utf-8")
    assert (
        workflow_verdict_covers_surface(
            str(transcript_path), MATCHING_MANIFEST_SHA256
        )
        is False
    )


def test_workflow_verdict_covers_surface_false_for_invalid_utf8_sidecar(
    tmp_path: pathlib.Path,
) -> None:
    transcript_path = _session_transcript_path(tmp_path, "sess1")
    subagents_dir = tmp_path / "projects" / "demo" / "sess1" / "subagents"
    _write_agent_transcript(
        subagents_dir,
        "01",
        VERIFIER_AGENT_TYPE,
        _verdict_transcript_text(True, MATCHING_MANIFEST_SHA256),
        should_write_sidecar=False,
    )
    invalid_utf8_sidecar = subagents_dir / "workflows" / "wf_x" / "agent-01.meta.json"
    invalid_utf8_sidecar.write_bytes(b'{"agentType": "\xff\xfe bad"}')
    assert (
        workflow_verdict_covers_surface(
            str(transcript_path), MATCHING_MANIFEST_SHA256
        )
        is False
    )


def test_workflow_verdict_covers_surface_false_for_invalid_utf8_transcript(
    tmp_path: pathlib.Path,
) -> None:
    transcript_path = _session_transcript_path(tmp_path, "sess1")
    subagents_dir = tmp_path / "projects" / "demo" / "sess1" / "subagents"
    workflow_dir = subagents_dir / "workflows" / "wf_x"
    workflow_dir.mkdir(parents=True, exist_ok=True)
    (workflow_dir / "agent-01.jsonl").write_bytes(b'{"type": "assistant"}\xff\xfe\n')
    (workflow_dir / "agent-01.meta.json").write_text(
        json.dumps({"agentType": VERIFIER_AGENT_TYPE}), encoding="utf-8"
    )
    assert (
        workflow_verdict_covers_surface(
            str(transcript_path), MATCHING_MANIFEST_SHA256
        )
        is False
    )


def test_workflow_verdict_covers_surface_false_for_missing_subagents_dir(
    tmp_path: pathlib.Path,
) -> None:
    transcript_path = _session_transcript_path(tmp_path, "sess1")
    assert (
        workflow_verdict_covers_surface(
            str(transcript_path), MATCHING_MANIFEST_SHA256
        )
        is False
    )


def test_workflow_verdict_covers_surface_true_when_transcript_is_under_subagents(
    tmp_path: pathlib.Path,
) -> None:
    subagents_dir = tmp_path / "projects" / "demo" / "sess1" / "subagents"
    _write_agent_transcript(
        subagents_dir,
        "01",
        VERIFIER_AGENT_TYPE,
        _verdict_transcript_text(True, MATCHING_MANIFEST_SHA256),
        should_write_sidecar=True,
    )
    caller_transcript_path = (
        subagents_dir / "workflows" / "wf_x" / "agent-00.jsonl"
    )
    caller_transcript_path.write_text("", encoding="utf-8")
    assert (
        workflow_verdict_covers_surface(
            str(caller_transcript_path), MATCHING_MANIFEST_SHA256
        )
        is True
    )


def test_manifest_hash_cli_prints_live_surface_hash(tmp_path: pathlib.Path) -> None:
    work_dir = _make_repo_with_origin(tmp_path)
    (work_dir / "src" / "app.py").write_text(
        "def add(left: int, right: int) -> int:\n    return left - right\n",
        encoding="utf-8",
    )
    merge_base_sha = resolve_merge_base(str(work_dir))
    assert merge_base_sha is not None
    surface_manifest_text = branch_surface_manifest(str(work_dir), merge_base_sha)
    assert surface_manifest_text is not None
    expected_hash = manifest_sha256(surface_manifest_text)
    completed_process = subprocess.run(
        [
            sys.executable,
            str(_HOOK_DIR / "verification_verdict_store.py"),
            "--manifest-hash",
            str(work_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed_process.stdout.strip() == expected_hash


def _isolate_home(monkeypatch: pytest.MonkeyPatch, fake_home: pathlib.Path) -> None:
    home_text = str(fake_home)
    monkeypatch.setenv("HOME", home_text)
    monkeypatch.setenv("USERPROFILE", home_text)
    monkeypatch.delenv("HOMEDRIVE", raising=False)
    monkeypatch.delenv("HOMEPATH", raising=False)


def test_minted_verdict_covers_surface_matches_other_worktree_by_hash(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    _isolate_home(monkeypatch, fake_home)
    write_verdict(
        str(tmp_path / "other" / "worktree"),
        MATCHING_MANIFEST_SHA256,
        True,
        [],
        "agent-x",
    )
    assert minted_verdict_covers_surface(MATCHING_MANIFEST_SHA256) is True


def test_minted_verdict_covers_surface_false_for_other_hash(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    _isolate_home(monkeypatch, fake_home)
    write_verdict(
        str(tmp_path / "other" / "worktree"),
        OTHER_MANIFEST_SHA256,
        True,
        [],
        "agent-x",
    )
    assert minted_verdict_covers_surface(MATCHING_MANIFEST_SHA256) is False


def test_minted_verdict_covers_surface_false_for_failing_verdict(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    _isolate_home(monkeypatch, fake_home)
    write_verdict(
        str(tmp_path / "other" / "worktree"),
        MATCHING_MANIFEST_SHA256,
        False,
        [{"severity": "P0", "summary": "boom"}],
        "agent-x",
    )
    assert minted_verdict_covers_surface(MATCHING_MANIFEST_SHA256) is False


def test_minted_verdict_covers_surface_false_when_directory_absent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    _isolate_home(monkeypatch, fake_home)
    assert minted_verdict_covers_surface(MATCHING_MANIFEST_SHA256) is False


def _make_repo_with_branch_worktree(
    tmp_path: pathlib.Path, branch_name: str
) -> tuple[pathlib.Path, pathlib.Path]:
    """Create a repo with a branch checked out in a separate worktree.

    Returns:
        A tuple of (main worktree path, branch worktree path).
    """
    empty_hooks_dir = tmp_path / "nohooks"
    empty_hooks_dir.mkdir()

    main_dir = tmp_path / "main"
    main_dir.mkdir()
    _run_git(main_dir, "init", "--initial-branch=main")
    _run_git(main_dir, "config", "user.email", "tests@example.com")
    _run_git(main_dir, "config", "user.name", "Worktree Tests")
    _run_git(main_dir, "config", "core.hooksPath", str(empty_hooks_dir))
    (main_dir / "app.py").write_text(PRODUCTION_SOURCE, encoding="utf-8")
    _run_git(main_dir, "add", "-A")
    _run_git(main_dir, "commit", "-m", "base")

    origin_dir = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "--bare", "--initial-branch=main", str(origin_dir)],
        check=True,
        capture_output=True,
        text=True,
    )
    _run_git(main_dir, "remote", "add", "origin", str(origin_dir))
    _run_git(main_dir, "push", "-u", "origin", "main")

    _run_git(main_dir, "branch", branch_name)

    branch_worktree_dir = tmp_path / "branch-worktree"
    _run_git(main_dir, "worktree", "add", str(branch_worktree_dir), branch_name)

    return main_dir, branch_worktree_dir


def test_worktree_path_for_branch_returns_path_when_branch_present(
    tmp_path: pathlib.Path,
) -> None:
    _main_dir, branch_worktree_dir = _make_repo_with_branch_worktree(
        tmp_path, "feature-x"
    )
    resolved_path = worktree_path_for_branch(str(branch_worktree_dir), "feature-x")
    assert resolved_path is not None
    assert pathlib.Path(resolved_path).resolve() == branch_worktree_dir.resolve()


def test_worktree_path_for_branch_returns_none_when_branch_absent(
    tmp_path: pathlib.Path,
) -> None:
    main_dir, _branch_worktree_dir = _make_repo_with_branch_worktree(
        tmp_path, "feature-x"
    )
    resolved_path = worktree_path_for_branch(str(main_dir), "branch-never-checked-out")
    assert resolved_path is None


def test_empty_surface_hash_equals_hash_of_empty_string() -> None:
    assert empty_surface_hash() == manifest_sha256("")


def test_manifest_hash_cli_empty_surface_writes_guard_message_to_stderr(
    tmp_path: pathlib.Path,
) -> None:
    work_dir = _make_repo_with_origin(tmp_path)
    completed_process = subprocess.run(
        [
            sys.executable,
            str(_HOOK_DIR / "verification_verdict_store.py"),
            "--manifest-hash",
            str(work_dir),
        ],
        capture_output=True,
        text=True,
    )
    assert completed_process.returncode != 0
    assert completed_process.stdout.strip() == ""
    lowered_stderr = completed_process.stderr.lower()
    assert "wrong work tree" in lowered_stderr or "empty" in lowered_stderr


def test_manifest_hash_cli_empty_surface_prints_nothing_on_stdout(
    tmp_path: pathlib.Path,
) -> None:
    work_dir = _make_repo_with_origin(tmp_path)
    completed_process = subprocess.run(
        [
            sys.executable,
            str(_HOOK_DIR / "verification_verdict_store.py"),
            "--manifest-hash",
            str(work_dir),
        ],
        capture_output=True,
        text=True,
    )
    assert completed_process.stdout.strip() == ""


def test_manifest_hash_for_branch_cli_prints_same_hash_as_explicit_dir(
    tmp_path: pathlib.Path,
) -> None:
    _main_dir, branch_worktree_dir = _make_repo_with_branch_worktree(
        tmp_path, "feature-branch"
    )
    (branch_worktree_dir / "app.py").write_text(
        "def add(left: int, right: int) -> int:\n    return left - right\n",
        encoding="utf-8",
    )
    direct_process = subprocess.run(
        [
            sys.executable,
            str(_HOOK_DIR / "verification_verdict_store.py"),
            "--manifest-hash",
            str(branch_worktree_dir),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    branch_process = subprocess.run(
        [
            sys.executable,
            str(_HOOK_DIR / "verification_verdict_store.py"),
            "--manifest-hash-for-branch",
            "feature-branch",
        ],
        capture_output=True,
        text=True,
        check=True,
        cwd=str(branch_worktree_dir),
    )
    assert direct_process.stdout.strip() == branch_process.stdout.strip()
    assert direct_process.stdout.strip() != ""


def test_manifest_hash_for_branch_cli_returns_nonzero_when_branch_absent(
    tmp_path: pathlib.Path,
) -> None:
    main_dir, _branch_worktree_dir = _make_repo_with_branch_worktree(
        tmp_path, "feature-branch"
    )
    completed_process = subprocess.run(
        [
            sys.executable,
            str(_HOOK_DIR / "verification_verdict_store.py"),
            "--manifest-hash-for-branch",
            "branch-never-checked-out",
        ],
        capture_output=True,
        text=True,
        cwd=str(main_dir),
    )
    assert completed_process.returncode != 0
    assert completed_process.stdout.strip() == ""
