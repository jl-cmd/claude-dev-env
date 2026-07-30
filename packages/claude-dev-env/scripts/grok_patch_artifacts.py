#!/usr/bin/env python3
"""Extract patch artifacts and SHA-256 manifests from isolated worktrees.

::

    manifest = write_patch_manifest(
        run_state_directory=run_dir,
        task_id="O-04",
        base_sha="abc",
        worktree_path=worktree,
        worker_report_text="ok",
    )
    ok: manifest carries content hash and changed paths
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from dev_env_scripts_constants.grok_run_ledger_constants import (
    JSON_INDENT,
    LEDGER_SCHEMA_VERSION,
    PATCH_MANIFEST_FILENAME,
    UTF8_ENCODING,
)


def compute_sha256_hex(content: bytes) -> str:
    """Return the hex SHA-256 digest of raw bytes.

    Args:
        content: Bytes to hash.

    Returns:
        Lowercase hex digest string.
    """
    return hashlib.sha256(content).hexdigest()


def extract_worktree_diff(
    *,
    worktree_path: Path,
    base_sha: str,
) -> tuple[str, tuple[str, ...]]:
    """Return unified diff text and changed paths against base_sha.

    Args:
        worktree_path: Isolated worker worktree.
        base_sha: Base commit SHA the worker started from.

    Returns:
        ``(diff_text, changed_paths)``.
    """
    diff_text = subprocess.check_output(
        ["git", "-C", str(worktree_path), "diff", base_sha],
        text=True,
        encoding=UTF8_ENCODING,
    )
    changed_paths_listing = subprocess.check_output(
        ["git", "-C", str(worktree_path), "diff", "--name-only", base_sha],
        text=True,
        encoding=UTF8_ENCODING,
    )
    changed_paths = tuple(
        each_line.strip()
        for each_line in changed_paths_listing.splitlines()
        if each_line.strip()
    )
    return diff_text, changed_paths


def write_patch_manifest(
    *,
    run_state_directory: Path,
    task_id: str,
    base_sha: str,
    worktree_path: Path,
    worker_report_text: str,
    patch_filename: str | None = None,
) -> dict[str, object]:
    """Write a patch file and JSON manifest binding hashes and paths.

    Args:
        run_state_directory: Directory that holds ledger and patch artifacts.
        task_id: Task the patch belongs to.
        base_sha: Base commit SHA.
        worktree_path: Worker worktree to diff.
        worker_report_text: Worker report body bound into the manifest.
        patch_filename: Optional override for the ``.patch`` filename.

    Returns:
        The manifest document written to disk.
    """
    run_state_directory = Path(run_state_directory)
    run_state_directory.mkdir(parents=True, exist_ok=True)
    diff_text, changed_paths = extract_worktree_diff(
        worktree_path=Path(worktree_path),
        base_sha=base_sha,
    )
    patch_name = patch_filename or f"{task_id}.patch"
    patch_path = run_state_directory / patch_name
    patch_bytes = diff_text.encode(UTF8_ENCODING)
    patch_path.write_bytes(patch_bytes)
    content_hash = compute_sha256_hex(patch_bytes)
    report_hash = compute_sha256_hex(worker_report_text.encode(UTF8_ENCODING))
    manifest = {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "task_id": task_id,
        "base_sha": base_sha,
        "changed_paths": list(changed_paths),
        "patch_path": str(patch_path),
        "content_sha256": content_hash,
        "worker_report_sha256": report_hash,
    }
    manifest_path = run_state_directory / PATCH_MANIFEST_FILENAME
    manifest_path.write_text(
        json.dumps(manifest, indent=JSON_INDENT) + "\n",
        encoding=UTF8_ENCODING,
    )
    return manifest
