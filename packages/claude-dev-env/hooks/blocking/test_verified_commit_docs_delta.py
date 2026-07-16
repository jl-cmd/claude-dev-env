"""Gate behavior for docs-only deltas and the cross-work-tree deny message.

Each test builds a real git repository with a real origin remote and drives
``deny_reason_for_directory`` — the same decision the verified_commit_gate hook
runs — so the docs-only exemption, the docs-after-verified-code block, and the
denial message's work-tree keying are asserted against live git state.
"""

import importlib.util
import pathlib
import subprocess
import sys

import pytest

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

gate_spec = importlib.util.spec_from_file_location(
    "verified_commit_gate",
    _HOOK_DIR / "verified_commit_gate.py",
)
assert gate_spec is not None
assert gate_spec.loader is not None
gate_module = importlib.util.module_from_spec(gate_spec)
gate_spec.loader.exec_module(gate_module)
deny_reason_for_directory = gate_module.deny_reason_for_directory

store_spec = importlib.util.spec_from_file_location(
    "verification_verdict_store",
    _HOOK_DIR / "verification_verdict_store.py",
)
assert store_spec is not None
assert store_spec.loader is not None
store_module = importlib.util.module_from_spec(store_spec)
store_spec.loader.exec_module(store_module)
resolve_merge_base = store_module.resolve_merge_base
branch_surface_manifest = store_module.branch_surface_manifest
manifest_sha256 = store_module.manifest_sha256
write_verdict = store_module.write_verdict

PRODUCTION_SOURCE = "def add(left: int, right: int) -> int:\n    return left + right\n"
BEHAVIORAL_EDIT_SOURCE = "def add(left: int, right: int) -> int:\n    return left - right\n"


def _run_git(repo_dir: pathlib.Path, *git_arguments: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo_dir), *git_arguments],
        check=True,
        capture_output=True,
        text=True,
    )


def _isolate_home(monkeypatch: pytest.MonkeyPatch, fake_home: pathlib.Path) -> None:
    home_text = str(fake_home)
    monkeypatch.setenv("HOME", home_text)
    monkeypatch.setenv("USERPROFILE", home_text)
    monkeypatch.delenv("HOMEDRIVE", raising=False)
    monkeypatch.delenv("HOMEPATH", raising=False)


def _empty_hooks_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    hooks_dir = tmp_path / "nohooks"
    hooks_dir.mkdir(exist_ok=True)
    return hooks_dir


def _empty_transcript(tmp_path: pathlib.Path) -> pathlib.Path:
    transcript_path = tmp_path / "projects" / "demo" / "sess1.jsonl"
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text("", encoding="utf-8")
    return transcript_path


def _init_pushed_repo(tmp_path: pathlib.Path) -> pathlib.Path:
    origin_dir = tmp_path / "origin.git"
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    subprocess.run(
        ["git", "init", "--bare", "--initial-branch=main", str(origin_dir)],
        check=True,
        capture_output=True,
        text=True,
    )
    _run_git(work_dir, "init", "--initial-branch=main")
    _run_git(work_dir, "config", "user.email", "tests@example.com")
    _run_git(work_dir, "config", "user.name", "Docs Delta Tests")
    _run_git(work_dir, "config", "core.hooksPath", str(_empty_hooks_dir(tmp_path)))
    (work_dir / "app.py").write_text(PRODUCTION_SOURCE, encoding="utf-8")
    (work_dir / "README.md").write_text("# base\n", encoding="utf-8")
    _run_git(work_dir, "add", "-A")
    _run_git(work_dir, "commit", "-m", "base")
    _run_git(work_dir, "remote", "add", "origin", str(origin_dir))
    _run_git(work_dir, "push", "-u", "origin", "main")
    return work_dir


def _make_docs_only_repo(tmp_path: pathlib.Path) -> pathlib.Path:
    work_dir = _init_pushed_repo(tmp_path)
    (work_dir / "README.md").write_text("# base\n\nUpdated docs.\n", encoding="utf-8")
    return work_dir


def _make_behavioral_code_repo(tmp_path: pathlib.Path) -> pathlib.Path:
    work_dir = _init_pushed_repo(tmp_path)
    (work_dir / "app.py").write_text(BEHAVIORAL_EDIT_SOURCE, encoding="utf-8")
    return work_dir


def _live_surface_hash(work_dir: pathlib.Path) -> str:
    merge_base_sha = resolve_merge_base(str(work_dir))
    assert merge_base_sha is not None
    surface_manifest_text = branch_surface_manifest(str(work_dir), merge_base_sha)
    assert surface_manifest_text is not None
    return manifest_sha256(surface_manifest_text)


def test_pure_docs_only_branch_is_allowed_without_verdict(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    _isolate_home(monkeypatch, fake_home)
    work_dir = _make_docs_only_repo(tmp_path)
    transcript_path = _empty_transcript(tmp_path)
    assert deny_reason_for_directory(str(work_dir), str(transcript_path)) is None


def test_readme_change_after_verified_code_commit_is_denied(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    _isolate_home(monkeypatch, fake_home)
    work_dir = _make_behavioral_code_repo(tmp_path)
    code_surface_hash = _live_surface_hash(work_dir)
    write_verdict(str(work_dir), code_surface_hash, True, [], "agent-x")
    transcript_path = _empty_transcript(tmp_path)
    assert deny_reason_for_directory(str(work_dir), str(transcript_path)) is None
    _run_git(work_dir, "add", "-A")
    _run_git(work_dir, "commit", "-m", "verified code change")
    (work_dir / "README.md").write_text("# added after verification\n", encoding="utf-8")
    deny_reason = deny_reason_for_directory(str(work_dir), str(transcript_path))
    assert deny_reason is not None
    assert "VERIFIED_COMMIT_GATE" in deny_reason


def test_readme_added_beside_unverified_code_is_denied(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    _isolate_home(monkeypatch, fake_home)
    work_dir = _make_behavioral_code_repo(tmp_path)
    (work_dir / "README.md").write_text("# docs beside code\n", encoding="utf-8")
    transcript_path = _empty_transcript(tmp_path)
    deny_reason = deny_reason_for_directory(str(work_dir), str(transcript_path))
    assert deny_reason is not None
    assert "VERIFIED_COMMIT_GATE" in deny_reason


def test_deny_reason_for_directory_names_worktree_keying_and_remedy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    _isolate_home(monkeypatch, fake_home)
    work_dir = _make_behavioral_code_repo(tmp_path)
    transcript_path = _empty_transcript(tmp_path)
    deny_reason = deny_reason_for_directory(str(work_dir), str(transcript_path))
    assert deny_reason is not None
    lowered_reason = deny_reason.lower()
    assert "work tree" in lowered_reason
    assert "run this command from the work tree" in lowered_reason
