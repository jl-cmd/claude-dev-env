"""Behavioral tests for the per-work-tree code-review stamp store.

Each test builds a real git repository with a real origin remote and records or
reads real stamp files under an isolated home, so it exercises the same store
surface the push and PR-create gates call: record a clean stamp, then ask
whether it covers the live branch surface at a given effort.
"""

import importlib.util
import pathlib
import subprocess
import sys

import pytest

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

_store_spec = importlib.util.spec_from_file_location(
    "code_review_stamp_store",
    _HOOK_DIR / "code_review_stamp_store.py",
)
assert _store_spec is not None
assert _store_spec.loader is not None
_store_module = importlib.util.module_from_spec(_store_spec)
_store_spec.loader.exec_module(_store_module)

record_clean_stamp = _store_module.record_clean_stamp
stamp_covers_surface = _store_module.stamp_covers_surface
live_surface_hash = _store_module.live_surface_hash
stamp_path_for_repo = _store_module.stamp_path_for_repo

_constants_spec = importlib.util.spec_from_file_location(
    "code_review_enforcement_constants",
    _HOOK_DIR / "config" / "code_review_enforcement_constants.py",
)
assert _constants_spec is not None
assert _constants_spec.loader is not None
_constants_module = importlib.util.module_from_spec(_constants_spec)
_constants_spec.loader.exec_module(_constants_module)
PUSH_REQUIRED_EFFORT = _constants_module.PUSH_REQUIRED_EFFORT
PR_CREATE_REQUIRED_EFFORT = _constants_module.PR_CREATE_REQUIRED_EFFORT
ALL_EFFORT_TOKENS_IN_ASCENDING_ORDER = _constants_module.ALL_EFFORT_TOKENS_IN_ASCENDING_ORDER

PRODUCTION_SOURCE = "def add(left: int, right: int) -> int:\n    return left + right\n"
CHANGED_SOURCE = "def add(left: int, right: int) -> int:\n    return left - right\n"
FURTHER_CHANGED_SOURCE = "def add(left: int, right: int) -> int:\n    return left * right\n"


def _run_git(repo_dir: pathlib.Path, *git_arguments: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo_dir), *git_arguments],
        check=True,
        capture_output=True,
        text=True,
    )


def _make_repo_with_origin(tmp_path: pathlib.Path) -> pathlib.Path:
    origin_dir = tmp_path / "origin.git"
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    subprocess.run(
        ["git", "init", "--bare", "--initial-branch=main", str(origin_dir)],
        check=True,
        capture_output=True,
        text=True,
    )
    empty_hooks_dir = tmp_path / "nohooks"
    empty_hooks_dir.mkdir()
    _run_git(work_dir, "init", "--initial-branch=main")
    _run_git(work_dir, "config", "user.email", "tests@example.com")
    _run_git(work_dir, "config", "user.name", "Stamp Store Tests")
    _run_git(work_dir, "config", "core.hooksPath", str(empty_hooks_dir))
    (work_dir / "src").mkdir()
    (work_dir / "src" / "app.py").write_text(PRODUCTION_SOURCE, encoding="utf-8")
    _run_git(work_dir, "add", "-A")
    _run_git(work_dir, "commit", "-m", "base")
    _run_git(work_dir, "remote", "add", "origin", str(origin_dir))
    _run_git(work_dir, "push", "-u", "origin", "main")
    return work_dir


def _isolate_home(monkeypatch: pytest.MonkeyPatch, fake_home: pathlib.Path) -> None:
    home_text = str(fake_home)
    monkeypatch.setenv("HOME", home_text)
    monkeypatch.setenv("USERPROFILE", home_text)
    monkeypatch.delenv("HOMEDRIVE", raising=False)
    monkeypatch.delenv("HOMEPATH", raising=False)


def _repo_with_change(tmp_path: pathlib.Path, changed_source: str) -> pathlib.Path:
    work_dir = _make_repo_with_origin(tmp_path)
    (work_dir / "src" / "app.py").write_text(changed_source, encoding="utf-8")
    return work_dir


def test_recorded_low_stamp_covers_the_push_surface(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _isolate_home(monkeypatch, tmp_path / "home")
    work_dir = _repo_with_change(tmp_path, CHANGED_SOURCE)
    surface_hash = live_surface_hash(str(work_dir))
    assert surface_hash is not None
    record_clean_stamp(str(work_dir), surface_hash, PUSH_REQUIRED_EFFORT)
    assert stamp_covers_surface(str(work_dir), surface_hash, PUSH_REQUIRED_EFFORT) is True


def test_low_stamp_does_not_cover_the_pr_create_surface(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _isolate_home(monkeypatch, tmp_path / "home")
    work_dir = _repo_with_change(tmp_path, CHANGED_SOURCE)
    surface_hash = live_surface_hash(str(work_dir))
    assert surface_hash is not None
    record_clean_stamp(str(work_dir), surface_hash, PUSH_REQUIRED_EFFORT)
    assert stamp_covers_surface(str(work_dir), surface_hash, PR_CREATE_REQUIRED_EFFORT) is False


def test_xhigh_stamp_covers_both_push_and_pr_create(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _isolate_home(monkeypatch, tmp_path / "home")
    work_dir = _repo_with_change(tmp_path, CHANGED_SOURCE)
    surface_hash = live_surface_hash(str(work_dir))
    assert surface_hash is not None
    record_clean_stamp(str(work_dir), surface_hash, PR_CREATE_REQUIRED_EFFORT)
    assert stamp_covers_surface(str(work_dir), surface_hash, PUSH_REQUIRED_EFFORT) is True
    assert stamp_covers_surface(str(work_dir), surface_hash, PR_CREATE_REQUIRED_EFFORT) is True


def test_stamp_bound_to_one_hash_does_not_cover_a_different_hash(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _isolate_home(monkeypatch, tmp_path / "home")
    work_dir = _repo_with_change(tmp_path, CHANGED_SOURCE)
    surface_hash = live_surface_hash(str(work_dir))
    assert surface_hash is not None
    record_clean_stamp(str(work_dir), surface_hash, PUSH_REQUIRED_EFFORT)
    other_hash = "f" * len(surface_hash)
    assert stamp_covers_surface(str(work_dir), other_hash, PUSH_REQUIRED_EFFORT) is False


def test_editing_a_file_after_minting_drops_coverage(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _isolate_home(monkeypatch, tmp_path / "home")
    work_dir = _repo_with_change(tmp_path, CHANGED_SOURCE)
    minted_hash = live_surface_hash(str(work_dir))
    assert minted_hash is not None
    record_clean_stamp(str(work_dir), minted_hash, PUSH_REQUIRED_EFFORT)
    (work_dir / "src" / "app.py").write_text(FURTHER_CHANGED_SOURCE, encoding="utf-8")
    live_hash_after_edit = live_surface_hash(str(work_dir))
    assert live_hash_after_edit is not None
    assert live_hash_after_edit != minted_hash
    assert stamp_covers_surface(str(work_dir), live_hash_after_edit, PUSH_REQUIRED_EFFORT) is False


def test_no_stamp_file_reads_as_not_covered(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _isolate_home(monkeypatch, tmp_path / "home")
    work_dir = _repo_with_change(tmp_path, CHANGED_SOURCE)
    surface_hash = live_surface_hash(str(work_dir))
    assert surface_hash is not None
    assert not stamp_path_for_repo(str(work_dir)).exists()
    assert stamp_covers_surface(str(work_dir), surface_hash, PUSH_REQUIRED_EFFORT) is False


def test_recording_a_second_effort_keeps_the_first(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _isolate_home(monkeypatch, tmp_path / "home")
    work_dir = _repo_with_change(tmp_path, CHANGED_SOURCE)
    surface_hash = live_surface_hash(str(work_dir))
    assert surface_hash is not None
    record_clean_stamp(str(work_dir), surface_hash, PUSH_REQUIRED_EFFORT)
    record_clean_stamp(str(work_dir), surface_hash, PR_CREATE_REQUIRED_EFFORT)
    assert stamp_covers_surface(str(work_dir), surface_hash, PUSH_REQUIRED_EFFORT) is True
    assert stamp_covers_surface(str(work_dir), surface_hash, PR_CREATE_REQUIRED_EFFORT) is True


def test_live_surface_hash_is_none_when_nothing_changed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _isolate_home(monkeypatch, tmp_path / "home")
    work_dir = _make_repo_with_origin(tmp_path)
    assert live_surface_hash(str(work_dir)) is None


def test_push_required_effort_is_the_lowest_known_token() -> None:
    assert PUSH_REQUIRED_EFFORT == ALL_EFFORT_TOKENS_IN_ASCENDING_ORDER[0]
