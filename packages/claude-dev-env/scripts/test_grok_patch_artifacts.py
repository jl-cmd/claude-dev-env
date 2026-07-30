"""Behavioral tests for patch artifact extraction and manifests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from grok_patch_artifacts import (  # noqa: E402
    compute_sha256_hex,
    extract_worktree_diff,
    write_patch_manifest,
)


def _init_repo(path: Path) -> str:
    subprocess.check_call(["git", "init"], cwd=path, stdout=subprocess.DEVNULL)
    subprocess.check_call(
        ["git", "config", "user.email", "test@example.com"], cwd=path, stdout=subprocess.DEVNULL
    )
    subprocess.check_call(
        ["git", "config", "user.name", "test"], cwd=path, stdout=subprocess.DEVNULL
    )
    sample = path / "sample.txt"
    sample.write_text("one\n", encoding="utf-8")
    subprocess.check_call(["git", "add", "sample.txt"], cwd=path, stdout=subprocess.DEVNULL)
    subprocess.check_call(
        ["git", "commit", "-m", "init"], cwd=path, stdout=subprocess.DEVNULL
    )
    base = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=path, text=True
    ).strip()
    sample.write_text("one\ntwo\n", encoding="utf-8")
    return base


def test_write_patch_manifest_binds_hash_paths_and_report(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    worktree.mkdir()
    base_sha = _init_repo(worktree)
    run_dir = tmp_path / "run"
    report_text = '{"status":"ok"}'
    manifest = write_patch_manifest(
        run_state_directory=run_dir,
        task_id="O-04",
        base_sha=base_sha,
        worktree_path=worktree,
        worker_report_text=report_text,
    )
    assert manifest["task_id"] == "O-04"
    assert manifest["base_sha"] == base_sha
    assert "sample.txt" in manifest["changed_paths"]
    patch_path = Path(str(manifest["patch_path"]))
    assert patch_path.is_file()
    assert manifest["content_sha256"] == compute_sha256_hex(patch_path.read_bytes())
    assert manifest["worker_report_sha256"] == compute_sha256_hex(
        report_text.encode("utf-8")
    )
    on_disk = json.loads((run_dir / "patch-manifest.json").read_text(encoding="utf-8"))
    assert on_disk["content_sha256"] == manifest["content_sha256"]


def test_compute_sha256_hex_is_stable() -> None:
    digest = compute_sha256_hex(b"abc")
    assert digest == compute_sha256_hex(b"abc")
    assert digest != compute_sha256_hex(b"abd")


def test_extract_worktree_diff_returns_paths(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    worktree.mkdir()
    base_sha = _init_repo(worktree)
    diff_text, all_changed_paths = extract_worktree_diff(
        worktree_path=worktree, base_sha=base_sha
    )
    assert "sample.txt" in all_changed_paths
    assert "two" in diff_text or "sample" in diff_text
