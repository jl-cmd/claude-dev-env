"""Read and write the per-work-tree code-review stamp files.

A stamp records that a clean ``/code-review`` pass ran against an exact branch
surface at a given effort. Each work tree keeps one JSON file under
``~/.claude/code-review-stamps/`` mapping an effort token to the surface hash it
was earned against, so a later push or pull-request gate can ask whether a
clean review at the needed effort already covers the live surface. This module
only reads and writes those files; it runs no review.

::

    record_clean_stamp(root, hash_a, "low")
    stamp_covers_surface(root, hash_a, "low")   -> True   (recorded, matching)
    stamp_covers_surface(root, hash_a, "xhigh") -> False  (low is below xhigh)
    stamp_covers_surface(root, hash_b, "low")   -> False  (surface hash differs)

Coverage fails closed: a missing, unreadable, or malformed stamp file, a hash
that does not match, and an effort below the threshold all read as not covered.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

_blocking_directory = str(Path(__file__).resolve().parent)

try:
    from code_review_enforcement_config_bootstrap import (
        register_code_review_enforcement_constants,
    )
    from verified_commit_config_bootstrap import register_verified_commit_constants
except ModuleNotFoundError:
    if _blocking_directory not in sys.path:
        sys.path.insert(0, _blocking_directory)
    from code_review_enforcement_config_bootstrap import (
        register_code_review_enforcement_constants,
    )
    from verified_commit_config_bootstrap import register_verified_commit_constants

register_code_review_enforcement_constants()
register_verified_commit_constants()

try:
    from config.code_review_enforcement_constants import (
        STAMP_DIRECTORY_NAME,
        STAMP_KEY_EFFORT,
        STAMP_KEY_MANIFEST_SHA256,
        STAMP_KEY_RECORDED_AT_EPOCH,
        effort_meets_threshold,
    )
    from config.verified_commit_constants import (
        CLAUDE_HOME_DIRECTORY_NAME,
        VERDICT_JSON_INDENT,
    )
    from verification_verdict_store import (
        branch_surface_manifest,
        empty_surface_hash,
        manifest_sha256,
        resolve_merge_base,
        resolve_repo_root,
        root_key_for_repo,
    )
except ModuleNotFoundError:
    if _blocking_directory not in sys.path:
        sys.path.insert(0, _blocking_directory)
    from config.code_review_enforcement_constants import (
        STAMP_DIRECTORY_NAME,
        STAMP_KEY_EFFORT,
        STAMP_KEY_MANIFEST_SHA256,
        STAMP_KEY_RECORDED_AT_EPOCH,
        effort_meets_threshold,
    )
    from config.verified_commit_constants import (
        CLAUDE_HOME_DIRECTORY_NAME,
        VERDICT_JSON_INDENT,
    )
    from verification_verdict_store import (
        branch_surface_manifest,
        empty_surface_hash,
        manifest_sha256,
        resolve_merge_base,
        resolve_repo_root,
        root_key_for_repo,
    )


def stamp_directory() -> Path:
    """Return the shared directory holding every work tree's stamp file.

    Stamps live outside any repository (under the user's Claude home) so no repo
    accumulates untracked stamp files; every work tree's stamp shares this one
    directory, distinguished by file name.

    Returns:
        The stamp directory under the user's Claude home.
    """
    return Path.home() / CLAUDE_HOME_DIRECTORY_NAME / STAMP_DIRECTORY_NAME


def stamp_path_for_repo(repo_root: str) -> Path:
    """Derive the stamp file path for a repository work tree.

    Keyed by the shared ``root_key_for_repo`` derivation, so every work tree
    gets its own stamp file and a subdirectory of a work tree resolves to the
    same key as its root.

    Args:
        repo_root: The repository top-level directory.

    Returns:
        The stamp file path for this work tree.
    """
    return stamp_directory() / f"{root_key_for_repo(repo_root)}.json"


def _read_stamps_by_effort(stamp_file: Path) -> dict[str, object]:
    """Read the per-effort stamp records for a work tree, or an empty map.

    ::

        <root-key>.json holds {"low": {...}, "xhigh": {...}}  -> that map
        file missing / unreadable / not a JSON object          -> {}

    A missing, unreadable, or malformed stamp file yields an empty map, so a
    caller reading it sees no coverage and fails closed.

    Args:
        stamp_file: The per-work-tree stamp file path.

    Returns:
        The mapping of effort token to its stored record, or an empty map when
        the file is absent, unreadable, or not a JSON object.
    """
    try:
        parsed_stamps = json.loads(stamp_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(parsed_stamps, dict):
        return {}
    return parsed_stamps


def record_clean_stamp(repo_root: str, bound_manifest_sha256: str, effort: str) -> Path:
    """Write one effort's clean-review stamp for a work tree.

    Reads any existing per-effort records, sets this effort's entry to the given
    surface hash and the current epoch, and writes the map back. Recording a
    second effort keeps the first; recording the same effort again overwrites
    its bound hash.

    Args:
        repo_root: The repository top-level directory.
        bound_manifest_sha256: Hash of the branch surface the clean review covered.
        effort: The effort token the clean review ran at.

    Returns:
        The stamp file path the record was written to.
    """
    stamp_file = stamp_path_for_repo(repo_root)
    stamp_file.parent.mkdir(parents=True, exist_ok=True)
    all_stamps_by_effort = _read_stamps_by_effort(stamp_file)
    all_stamps_by_effort[effort] = {
        STAMP_KEY_EFFORT: effort,
        STAMP_KEY_MANIFEST_SHA256: bound_manifest_sha256,
        STAMP_KEY_RECORDED_AT_EPOCH: int(time.time()),
    }
    stamp_file.write_text(
        json.dumps(all_stamps_by_effort, indent=VERDICT_JSON_INDENT), encoding="utf-8"
    )
    return stamp_file


def stamp_covers_surface(repo_root: str, live_manifest_sha256: str, required_effort: str) -> bool:
    """Decide whether a clean stamp covers the live surface at the needed effort.

    A stored entry covers the surface when its bound hash equals the live hash
    exactly and its effort ranks at or above the required effort. Any missing,
    unreadable, or malformed stamp reads as not covered.

    Args:
        repo_root: The repository top-level directory.
        live_manifest_sha256: Hash of the live branch surface the gate checks.
        required_effort: The effort the gate demands for the action.

    Returns:
        True as soon as one stored entry matches the live hash and meets the
        required effort; False when none match.
    """
    all_stamps_by_effort = _read_stamps_by_effort(stamp_path_for_repo(repo_root))
    for each_stamp_record in all_stamps_by_effort.values():
        if not isinstance(each_stamp_record, dict):
            continue
        if each_stamp_record.get(STAMP_KEY_MANIFEST_SHA256) != live_manifest_sha256:
            continue
        stored_effort = each_stamp_record.get(STAMP_KEY_EFFORT)
        if not isinstance(stored_effort, str):
            continue
        if effort_meets_threshold(stored_effort, required_effort):
            return True
    return False


def live_surface_hash(work_tree_directory: str) -> str | None:
    """Compute the live branch-surface manifest hash for a work tree.

    Resolves the work tree's repo root and merge base, then hashes the current
    change surface — every changed path and untracked file bound by its content
    digest — so the hash tracks the exact bytes under review.

    Args:
        work_tree_directory: A directory inside the work tree to hash.

    Returns:
        The surface manifest hash, or None when the directory is outside a work
        tree, the merge base or manifest cannot be resolved, or the change
        surface is empty (HEAD equals the merge base, so nothing is under review).
    """
    repo_root = resolve_repo_root(work_tree_directory)
    if repo_root is None:
        return None
    merge_base_sha = resolve_merge_base(repo_root)
    if merge_base_sha is None:
        return None
    surface_manifest_text = branch_surface_manifest(repo_root, merge_base_sha)
    if surface_manifest_text is None:
        return None
    surface_hash = manifest_sha256(surface_manifest_text)
    if surface_hash == empty_surface_hash():
        return None
    return surface_hash
