"""Store staged rule-gate success bound to one worktree index snapshot."""

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pr_loop_shared_constants.code_rules_gate_constants import (
    ALL_GIT_INDEX_TREE_OID_COMMAND,
    ALL_GIT_HEAD_OID_COMMAND,
    ALL_GIT_SYMBOLIC_HEAD_COMMAND,
    ALL_GIT_TOP_LEVEL_AND_PRIVATE_DIRECTORY_COMMAND,
    EXPECTED_TOP_LEVEL_AND_PRIVATE_DIRECTORY_LINE_COUNT,
    STAGED_ATTESTATION_ENCODING,
    STAGED_ATTESTATION_FILENAME,
    STAGED_ATTESTATION_GIT_TIMEOUT_SECONDS,
    STAGED_ATTESTATION_HEAD_OID_KEY,
    STAGED_ATTESTATION_INDEX_TREE_OID_KEY,
    STAGED_ATTESTATION_SCHEMA_VERSION,
    STAGED_ATTESTATION_SCHEMA_VERSION_KEY,
    STAGED_ATTESTATION_TEMPORARY_PREFIX,
    STAGED_ATTESTATION_WORKTREE_KEY,
    UNBORN_HEAD_OID,
)
from terminology_sweep import repository_environment


@dataclass(frozen=True)
class StagedAttestation:
    """The immutable git identity that a staged gate run proves."""

    worktree: str
    head_oid: str
    index_tree_oid: str


def _read_git_text(repository_root: Path, all_arguments: tuple[str, ...]) -> str | None:
    try:
        completed_process = subprocess.run(
            ["git", "-C", str(repository_root), *all_arguments],
            check=False,
            capture_output=True,
            text=True,
            encoding=STAGED_ATTESTATION_ENCODING,
            errors="replace",
            env=repository_environment(),
            timeout=STAGED_ATTESTATION_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed_process.returncode != 0:
        return None
    return completed_process.stdout.strip()


def _normalized_worktree(repository_root: Path) -> str:
    return str(repository_root.resolve()).replace("\\", "/").lower()


def _resolved_git_directory(repository_root: Path, git_directory_text: str | None) -> Path | None:
    if not git_directory_text:
        return None
    git_directory = Path(git_directory_text)
    if git_directory.is_absolute():
        return git_directory.resolve()
    return (repository_root / git_directory).resolve()


def _top_level_and_private_git_directory(repository_root: Path) -> tuple[Path, Path] | None:
    identity_text = _read_git_text(
        repository_root, ALL_GIT_TOP_LEVEL_AND_PRIVATE_DIRECTORY_COMMAND
    )
    if identity_text is None:
        return None
    all_identity_lines = identity_text.splitlines()
    if len(all_identity_lines) != EXPECTED_TOP_LEVEL_AND_PRIVATE_DIRECTORY_LINE_COUNT:
        return None
    top_level_root = Path(all_identity_lines[0]).resolve()
    private_git_directory = _resolved_git_directory(top_level_root, all_identity_lines[1])
    if private_git_directory is None:
        return None
    return top_level_root, private_git_directory


def _snapshot_with_attestation_path(
    repository_root: Path,
) -> tuple[StagedAttestation, Path] | None:
    top_level_and_git_directory = _top_level_and_private_git_directory(repository_root)
    if top_level_and_git_directory is None:
        return None
    top_level_root, private_git_directory = top_level_and_git_directory
    head_oid = _read_git_text(top_level_root, ALL_GIT_HEAD_OID_COMMAND)
    if head_oid is None:
        symbolic_head = _read_git_text(top_level_root, ALL_GIT_SYMBOLIC_HEAD_COMMAND)
        if symbolic_head is None:
            return None
        head_oid = UNBORN_HEAD_OID
    index_tree_oid = _read_git_text(repository_root, ALL_GIT_INDEX_TREE_OID_COMMAND)
    if not head_oid or not index_tree_oid:
        return None
    attestation = StagedAttestation(_normalized_worktree(top_level_root), head_oid, index_tree_oid)
    return attestation, private_git_directory / STAGED_ATTESTATION_FILENAME


def attestation_path(repository_root: Path) -> Path | None:
    """Return this worktree's private staged-attestation path.

    Args:
        repository_root: The Git worktree whose private metadata holds proof.

    Returns:
        The attestation path, or None when Git cannot resolve the worktree.
    """
    top_level_and_git_directory = _top_level_and_private_git_directory(repository_root)
    if top_level_and_git_directory is None:
        return None
    _, private_git_directory = top_level_and_git_directory
    return private_git_directory / STAGED_ATTESTATION_FILENAME


def snapshot_staged_attestation(repository_root: Path) -> StagedAttestation | None:
    """Capture the current worktree, HEAD, and staged index identity.

    Args:
        repository_root: The Git worktree whose staged state is captured.

    Returns:
        The bound identity, or None when Git cannot provide every value.
    """
    snapshot_and_path = _snapshot_with_attestation_path(repository_root)
    if snapshot_and_path is None:
        return None
    return snapshot_and_path[0]


def clear_staged_attestation(repository_root: Path) -> bool:
    """Remove the staged proof before a new staged gate run.

    Args:
        repository_root: The Git worktree whose existing proof is removed.

    Returns:
        True when no proof remains; False when its private path is unavailable.
    """
    stored_attestation_path = attestation_path(repository_root)
    if stored_attestation_path is None:
        return False
    try:
        stored_attestation_path.unlink(missing_ok=True)
    except OSError:
        return False
    return True


def _attestation_payload(attestation: StagedAttestation) -> dict[str, int | str]:
    return {
        STAGED_ATTESTATION_SCHEMA_VERSION_KEY: STAGED_ATTESTATION_SCHEMA_VERSION,
        STAGED_ATTESTATION_WORKTREE_KEY: attestation.worktree,
        STAGED_ATTESTATION_HEAD_OID_KEY: attestation.head_oid,
        STAGED_ATTESTATION_INDEX_TREE_OID_KEY: attestation.index_tree_oid,
    }


def mint_staged_attestation(repository_root: Path, before: StagedAttestation) -> bool:
    """Atomically store proof when the staged snapshot stayed unchanged.

    Args:
        repository_root: The Git worktree whose successful proof is stored.
        before: The snapshot captured before the staged rule gate and tests ran.

    Returns:
        True when the unchanged snapshot is stored atomically; False otherwise.
    """
    snapshot_and_path = _snapshot_with_attestation_path(repository_root)
    if snapshot_and_path is None:
        return False
    after, stored_attestation_path = snapshot_and_path
    if after != before:
        return False
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding=STAGED_ATTESTATION_ENCODING,
            dir=stored_attestation_path.parent,
            prefix=STAGED_ATTESTATION_TEMPORARY_PREFIX,
            delete=False,
        ) as temporary_file:
            json.dump(_attestation_payload(after), temporary_file, sort_keys=True)
            temporary_path = Path(temporary_file.name)
        os.replace(temporary_path, stored_attestation_path)
    except OSError:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
        return False
    return True


def has_current_staged_attestation(repository_root: Path) -> bool:
    """Report whether stored proof exactly matches the current staged identity.

    Args:
        repository_root: The Git worktree whose current staged identity is read.

    Returns:
        True when valid schema-bound proof matches worktree, HEAD, and index.
    """
    snapshot_and_path = _snapshot_with_attestation_path(repository_root)
    if snapshot_and_path is None:
        return False
    expected_attestation, stored_attestation_path = snapshot_and_path
    try:
        stored_payload = json.loads(stored_attestation_path.read_text(STAGED_ATTESTATION_ENCODING))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    return stored_payload == _attestation_payload(expected_attestation)
