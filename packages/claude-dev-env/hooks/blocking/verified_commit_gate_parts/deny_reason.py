"""Decide whether a commit/push in a directory needs a passing verdict.

::

    branch has no upstream base       -> allow (nothing to verify against)
    diff is docs/tests/AST-unchanged  -> allow (mechanically exempt)
    a minted or workflow verdict binds -> allow
    otherwise                          -> deny, quoting the surface hash

A verdict binds by the content hash of the live change surface, not by
work-tree location, so a verdict minted while verifying any work tree of the
same surface clears the commit.
"""

from __future__ import annotations

from config.verified_commit_constants import CORRECTIVE_MESSAGE, HASH_PREVIEW_LENGTH
from verification_verdict_store import (
    branch_surface_manifest,
    is_verification_exempt_diff,
    load_valid_verdict,
    manifest_sha256,
    minted_verdict_covers_surface,
    resolve_merge_base,
    resolve_repo_root,
    workflow_verdict_covers_surface,
)


def _resolve_repo_and_base(target_directory: str) -> tuple[str, str] | None:
    """Resolve the repo root and merge-base for a directory, or None."""
    repo_root = resolve_repo_root(target_directory)
    if repo_root is None:
        return None
    merge_base_sha = resolve_merge_base(repo_root)
    if merge_base_sha is None:
        return None
    return repo_root, merge_base_sha


def _verdict_covers_surface(
    repo_root: str, live_manifest_sha256: str, transcript_path: str
) -> bool:
    """Decide whether any passing verdict already binds to the live surface.

    A workflow-spawned code-verifier's own transcript covers the workflow
    case, where SubagentStop never fires to mint a verdict file.
    """
    if load_valid_verdict(repo_root, live_manifest_sha256) is not None:
        return True
    if minted_verdict_covers_surface(live_manifest_sha256):
        return True
    return workflow_verdict_covers_surface(transcript_path, live_manifest_sha256)


def deny_reason_for_directory(target_directory: str, transcript_path: str) -> str | None:
    """Decide whether a commit/push in a directory must be blocked.

    Args:
        target_directory: The directory the git command targets.
        transcript_path: The live session's transcript path from the payload.

    Returns:
        The deny reason when the branch diff needs a verdict and none binds
        to it; None when the command may proceed.
    """
    repo_and_base = _resolve_repo_and_base(target_directory)
    if repo_and_base is None:
        return None
    repo_root, merge_base_sha = repo_and_base
    if is_verification_exempt_diff(repo_root, merge_base_sha):
        return None
    surface_manifest_text = branch_surface_manifest(repo_root, merge_base_sha)
    if surface_manifest_text is None:
        return f"{CORRECTIVE_MESSAGE} (surface manifest failed in {repo_root})"
    live_manifest_sha256 = manifest_sha256(surface_manifest_text)
    if _verdict_covers_surface(repo_root, live_manifest_sha256, transcript_path):
        return None
    hash_preview = live_manifest_sha256[:HASH_PREVIEW_LENGTH]
    return f"{CORRECTIVE_MESSAGE} (repo: {repo_root}, surface sha256 {hash_preview}...)"
