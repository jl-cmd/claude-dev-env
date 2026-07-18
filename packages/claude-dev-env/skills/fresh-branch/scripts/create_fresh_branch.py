#!/usr/bin/env python3
"""Create a fresh branch in an isolated git worktree under the agent scratch root.

::

    python create_fresh_branch.py --branch-name fix/example
    {"branch": "fix/example", "worktree_path": "...", "base_ref": "origin/main",
     "base_commit": "abc...", "agent": "claude", "repo_root": "..."}

Never runs ``git checkout -b`` in the caller's working tree. Fetches the base
ref, then ``git worktree add -b --no-track`` into ``Temp/<agent>/<branch>``
(Windows) or ``gettempdir()/<agent>/<branch>`` elsewhere. Exit 0 prints success
JSON; any failure prints ``{"error": ...}`` and exits non-zero.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

from fresh_branch_git_commands import (
    assert_git_accepts_branch_name,
    create_worktree_branch,
    fetch_base_ref,
    resolve_base_commit,
    resolve_repo_root,
)
from fresh_branch_scripts_constants.fresh_branch_cli_constants import (
    AGENT_SLUG_PATTERN,
    ALL_AGENT_DETECTION_MARKERS,
    ALL_WINDOWS_USER_SCRATCH_PARTS,
    DEFAULT_AGENT_SLUG,
    DEFAULT_BASE_REF,
    ERROR_AGENT_SLUG_INVALID,
    ERROR_BRANCH_NAME_REQUIRED,
    ERROR_BRANCH_NAME_UNSAFE,
    ERROR_CLI_ARGUMENTS,
    ERROR_UNIQUE_PATH_EXHAUSTED,
    ERROR_WORKTREE_PATH_OUTSIDE_ROOT,
    EXIT_CODE_FAILURE,
    EXIT_CODE_SUCCESS,
    FRESH_BRANCH_AGENT_ENV_VAR,
    GIT_REMOTE_PREFIX,
    MAXIMUM_UNIQUE_PATH_ATTEMPTS,
    PATH_SEGMENT_CURRENT,
    PATH_SEGMENT_PARENT,
    PAYLOAD_KEY_AGENT,
    PAYLOAD_KEY_BASE_COMMIT,
    PAYLOAD_KEY_BASE_REF,
    PAYLOAD_KEY_BRANCH,
    PAYLOAD_KEY_ERROR,
    PAYLOAD_KEY_REPO_ROOT,
    PAYLOAD_KEY_WORKTREE_PATH,
    UNIQUE_PATH_SUFFIX_START,
    USERPROFILE_ENV_VAR,
    WINDOWS_PLATFORM_PREFIX,
)


def resolve_agent_slug(maybe_flag_agent: str | None) -> str:
    """Return the short host label for the worktree path segment.

    ::

        resolve_agent_slug("Grok")  # ok: "grok"

    Args:
        maybe_flag_agent: Explicit ``--agent`` value, or None.

    Returns:
        Lowercase agent slug safe for a single path segment.

    Raises:
        ValueError: When the resolved slug fails the path-safety pattern.
    """
    if maybe_flag_agent is not None and maybe_flag_agent.strip():
        return _normalize_agent_slug(maybe_flag_agent)
    explicit_agent = os.environ.get(FRESH_BRANCH_AGENT_ENV_VAR)
    if explicit_agent is not None and explicit_agent.strip():
        return _normalize_agent_slug(explicit_agent)
    return _detect_agent_slug_from_environment()


def _detect_agent_slug_from_environment() -> str:
    for each_env_name, each_agent_slug in ALL_AGENT_DETECTION_MARKERS:
        maybe_marker = os.environ.get(each_env_name)
        if maybe_marker is not None and str(maybe_marker).strip():
            return each_agent_slug
    return DEFAULT_AGENT_SLUG


def resolve_agent_worktree_root(agent_slug: str) -> Path:
    """Return ``Temp/<agent>`` on Windows USERPROFILE, else gettempdir root.

    ::

        # win32 + USERPROFILE=C:/Users/x -> C:/Users/x/AppData/Local/Temp/grok
        resolve_agent_worktree_root("grok")

    Args:
        agent_slug: Short host label (one path segment).

    Returns:
        Directory that should hold per-branch worktree folders.
    """
    if sys.platform.startswith(WINDOWS_PLATFORM_PREFIX):
        user_profile = os.environ.get(USERPROFILE_ENV_VAR)
        if user_profile:
            return Path(user_profile).joinpath(
                *ALL_WINDOWS_USER_SCRATCH_PARTS,
                agent_slug,
            )
    return Path(tempfile.gettempdir()) / agent_slug


def resolve_unique_worktree_path(preferred_path: Path) -> Path:
    """Return preferred_path, or preferred_path-N when the path already exists.

    ::

        resolve_unique_worktree_path(Path("/tmp/claude/fix"))  # free path
        # when /tmp/claude/fix exists -> /tmp/claude/fix-2

    Args:
        preferred_path: First-choice worktree directory.

    Returns:
        A path that does not exist yet.

    Raises:
        RuntimeError: When no free suffix remains within the attempt budget.
    """
    if not preferred_path.exists():
        return preferred_path
    for each_suffix in range(
        UNIQUE_PATH_SUFFIX_START,
        UNIQUE_PATH_SUFFIX_START + MAXIMUM_UNIQUE_PATH_ATTEMPTS,
    ):
        candidate_path = preferred_path.parent / f"{preferred_path.name}-{each_suffix}"
        if not candidate_path.exists():
            return candidate_path
    raise RuntimeError(ERROR_UNIQUE_PATH_EXHAUSTED % preferred_path)


def normalize_base_ref(base_ref: str) -> str:
    """Return a remote-tracking ref for bare branch names.

    ::

        normalize_base_ref("main")         # ok: "origin/main"
        normalize_base_ref("origin/main")  # ok: "origin/main"
        normalize_base_ref("upstream/dev") # ok: "upstream/dev"

    Args:
        base_ref: User-supplied base ref or bare branch name.

    Returns:
        Normalized ref used for fetch, commit lookup, and worktree add.
    """
    cleaned_base_ref = base_ref.strip()
    if not cleaned_base_ref:
        return DEFAULT_BASE_REF
    if "/" not in cleaned_base_ref:
        return f"{GIT_REMOTE_PREFIX}{cleaned_base_ref}"
    return cleaned_base_ref


def create_fresh_branch(
    branch_name: str,
    repo_path: Path,
    agent_slug: str,
    base_ref: str,
) -> dict[str, str]:
    """Fetch base_ref and create an isolated worktree branch with no upstream.

    ::

        create_fresh_branch("fix/x", Path("."), "grok", "origin/main")
    """
    cleaned_branch = _require_safe_branch_name(branch_name)
    normalized_agent_slug = _normalize_agent_slug(agent_slug)
    resolved_base_ref, repo_root, base_commit = _resolve_branch_base(
        repo_path, base_ref,
    )
    worktree_path = _allocate_worktree_path(cleaned_branch, normalized_agent_slug)
    create_worktree_branch(
        repo_root,
        branch_name=cleaned_branch,
        worktree_path=worktree_path,
        base_ref=resolved_base_ref,
    )
    return _build_success_payload(
        cleaned_branch, worktree_path, resolved_base_ref, base_commit,
        normalized_agent_slug, repo_root,
    )


def _resolve_branch_base(
    repo_path: Path,
    base_ref: str,
) -> tuple[str, Path, str]:
    resolved_base_ref = normalize_base_ref(base_ref)
    repo_root = resolve_repo_root(repo_path)
    fetch_base_ref(repo_root, resolved_base_ref)
    base_commit = resolve_base_commit(repo_root, resolved_base_ref)
    return resolved_base_ref, repo_root, base_commit


def main() -> int:
    """CLI entry: create worktree branch and print JSON to stdout.

    Returns:
        Process exit code (0 success, 1 failure).
    """
    try:
        parsed_arguments = _parse_arguments()
        agent_slug = resolve_agent_slug(parsed_arguments.agent)
        success_payload = create_fresh_branch(
            branch_name=parsed_arguments.branch_name,
            repo_path=Path(parsed_arguments.repo).resolve(),
            agent_slug=agent_slug,
            base_ref=parsed_arguments.base,
        )
        print(json.dumps(success_payload))
        return EXIT_CODE_SUCCESS
    except (ValueError, RuntimeError, OSError) as error:
        print(json.dumps({PAYLOAD_KEY_ERROR: str(error)}))
        return EXIT_CODE_FAILURE


def _require_safe_branch_name(branch_name: str) -> str:
    cleaned_branch = branch_name.strip()
    if not cleaned_branch:
        raise ValueError(ERROR_BRANCH_NAME_REQUIRED)
    _validate_branch_name_for_worktree_path(cleaned_branch)
    return cleaned_branch


def _allocate_worktree_path(branch_name: str, agent_slug: str) -> Path:
    agent_worktree_root = resolve_agent_worktree_root(agent_slug)
    preferred_path = agent_worktree_root / branch_name
    _assert_path_is_under_agent_root(
        candidate_path=preferred_path,
        agent_worktree_root=agent_worktree_root,
    )
    worktree_path = resolve_unique_worktree_path(preferred_path)
    _assert_path_is_under_agent_root(
        candidate_path=worktree_path,
        agent_worktree_root=agent_worktree_root,
    )
    return worktree_path


def _build_success_payload(
    branch_name: str,
    worktree_path: Path,
    base_ref: str,
    base_commit: str,
    agent_slug: str,
    repo_root: Path,
) -> dict[str, str]:
    return {
        PAYLOAD_KEY_BRANCH: branch_name,
        PAYLOAD_KEY_WORKTREE_PATH: str(worktree_path.resolve()),
        PAYLOAD_KEY_BASE_REF: base_ref,
        PAYLOAD_KEY_BASE_COMMIT: base_commit,
        PAYLOAD_KEY_AGENT: agent_slug,
        PAYLOAD_KEY_REPO_ROOT: str(repo_root),
    }


def _normalize_agent_slug(raw_agent: str) -> str:
    agent_slug = raw_agent.strip().lower()
    if re.fullmatch(AGENT_SLUG_PATTERN, agent_slug) is None:
        raise ValueError(ERROR_AGENT_SLUG_INVALID)
    return agent_slug


def _validate_branch_name_for_worktree_path(branch_name: str) -> None:
    branch_as_path = Path(branch_name)
    if branch_as_path.is_absolute():
        raise ValueError(ERROR_BRANCH_NAME_UNSAFE)
    for each_segment in branch_as_path.parts:
        if each_segment in (PATH_SEGMENT_CURRENT, PATH_SEGMENT_PARENT):
            raise ValueError(ERROR_BRANCH_NAME_UNSAFE)
    assert_git_accepts_branch_name(branch_name)


def _assert_path_is_under_agent_root(
    candidate_path: Path,
    agent_worktree_root: Path,
) -> None:
    resolved_candidate = candidate_path.resolve()
    resolved_root = agent_worktree_root.resolve()
    if resolved_candidate == resolved_root:
        return
    try:
        resolved_candidate.relative_to(resolved_root)
    except ValueError as error:
        raise ValueError(
            ERROR_WORKTREE_PATH_OUTSIDE_ROOT % candidate_path,
        ) from error


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a fresh branch in an isolated git worktree.",
    )
    parser.add_argument(
        "--branch-name",
        required=True,
        help="Name of the new branch to create.",
    )
    parser.add_argument(
        "--repo",
        default=".",
        help="Path inside the source repository (default: current directory).",
    )
    parser.add_argument(
        "--agent",
        default=None,
        help="Host label for Temp/<agent>/ (default: detect from environment).",
    )
    parser.add_argument(
        "--base",
        default=DEFAULT_BASE_REF,
        help=f"Base ref to fetch and branch from (default: {DEFAULT_BASE_REF}).",
    )
    try:
        return parser.parse_args()
    except SystemExit as exit_error:
        if exit_error.code in (EXIT_CODE_SUCCESS, None):
            raise
        raise ValueError(ERROR_CLI_ARGUMENTS) from exit_error


if __name__ == "__main__":
    sys.exit(main())
