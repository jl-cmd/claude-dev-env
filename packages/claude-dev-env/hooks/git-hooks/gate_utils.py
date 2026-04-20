"""Shared utilities for the claude-dev-env git-hook entry points."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from config import (
    CLAUDE_HOME_DEFAULT_SUBDIRECTORY,
    CLAUDE_HOME_ENV_VAR,
    GATE_PATH_OVERRIDE_ENV_VAR,
    GATE_SCRIPT_RELATIVE_PATH,
)


def resolve_gate_script_path() -> tuple[Path, Path | None]:
    """Return (gate_path, exact_allowed_override_or_none).

    When CODE_RULES_GATE_PATH is set the second element is the resolved
    override path — the only path is_safe_regular_file will accept.
    When falling back to CLAUDE_HOME / default the second element is None,
    signalling that the trusted prefix (Path.home() / '.claude') applies.

    Capturing both values here eliminates the TOCTOU window that would arise
    when the same env vars are read again inside is_safe_regular_file.
    """
    override_path_raw = os.environ.get(GATE_PATH_OVERRIDE_ENV_VAR, "").strip()
    if override_path_raw:
        exact_override = Path(override_path_raw).resolve()
        return exact_override, exact_override
    claude_home_override = os.environ.get(CLAUDE_HOME_ENV_VAR, "").strip()
    if claude_home_override:
        claude_home_directory = Path(claude_home_override).resolve()
    else:
        claude_home_directory = Path.home() / CLAUDE_HOME_DEFAULT_SUBDIRECTORY
    gate_path = claude_home_directory.joinpath(*GATE_SCRIPT_RELATIVE_PATH)
    return gate_path, None


def is_safe_regular_file(candidate_path: Path, exact_allowed_path: Path | None) -> bool:
    """Return True only when candidate_path is a regular file at a trusted location.

    When exact_allowed_path is not None candidate_path must resolve to that
    exact path (CODE_RULES_GATE_PATH override case).  When it is None the
    resolved candidate must fall within Path.home() / '.claude' — CLAUDE_HOME
    is intentionally excluded from the trust boundary because it is
    attacker-settable via the process environment.

    The candidate is resolved to its real path before any containment check,
    preventing symlinks inside the trusted tree from redirecting execution
    outside it.
    """
    resolved_candidate = candidate_path.resolve()
    if not _is_resolved_candidate_allowed(resolved_candidate, exact_allowed_path):
        return False
    try:
        path_stat = os.stat(resolved_candidate)
    except OSError:
        return False
    return stat.S_ISREG(path_stat.st_mode)


def _resolve_trust_root() -> Path:
    claude_home_override = os.environ.get(CLAUDE_HOME_ENV_VAR, "").strip()
    if claude_home_override:
        return Path(claude_home_override).resolve()
    return (Path.home() / CLAUDE_HOME_DEFAULT_SUBDIRECTORY).resolve()


def _is_resolved_candidate_allowed(
    resolved_candidate: Path,
    exact_allowed_path: Path | None,
) -> bool:
    if exact_allowed_path is not None:
        return resolved_candidate == exact_allowed_path
    trusted_prefix = _resolve_trust_root()
    return _is_within_directory(resolved_candidate, trusted_prefix)


def _is_within_directory(candidate_path: Path, directory: Path) -> bool:
    try:
        candidate_path.relative_to(directory)
        return True
    except ValueError:
        return False
