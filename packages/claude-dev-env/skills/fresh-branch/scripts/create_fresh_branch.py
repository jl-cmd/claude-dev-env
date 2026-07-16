#!/usr/bin/env python3
"""Create a fresh branch in an isolated git worktree under the agent scratch root.

::

    python create_fresh_branch.py --branch-name fix/example
    {"branch": "fix/example", "worktree_path": "...", "base_ref": "origin/main",
     "base_commit": "abc...", "agent": "claude", "repo_root": "..."}

Never runs ``git checkout -b`` in the caller's working tree. Fetches the base
ref, then ``git worktree add -b`` into ``Temp/<agent>/<branch>`` (Windows) or
``gettempdir()/<agent>/<branch>`` elsewhere. Exit 0 prints success JSON; any
failure prints ``{"error": ...}`` and exits non-zero.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from fresh_branch_scripts_constants.fresh_branch_cli_constants import (
    AGENT_SLUG_PATTERN,
    ALL_AGENT_DETECTION_MARKERS,
    ALL_WINDOWS_USER_SCRATCH_PARTS,
    DEFAULT_AGENT_SLUG,
    DEFAULT_BASE_REF,
    ERROR_AGENT_SLUG_INVALID,
    ERROR_BASE_COMMIT_LOOKUP,
    ERROR_BASE_REF_MISSING,
    ERROR_BRANCH_NAME_REQUIRED,
    ERROR_FETCH_FAILED,
    ERROR_REPO_NOT_GIT,
    ERROR_UNIQUE_PATH_EXHAUSTED,
    ERROR_WORKTREE_FAILED,
    EXIT_CODE_FAILURE,
    EXIT_CODE_SUCCESS,
    FRESH_BRANCH_AGENT_ENV_VAR,
    GIT_BRANCH_FLAG,
    GIT_COMMAND,
    GIT_FETCH,
    GIT_QUIET_FLAG,
    GIT_REFS_REMOTES_PREFIX,
    GIT_REMOTE_PREFIX,
    GIT_REV_PARSE,
    GIT_SHOW_REF,
    GIT_SHOW_TOPLEVEL,
    GIT_VERIFY_FLAG,
    GIT_WORKTREE,
    GIT_WORKTREE_ADD,
    MAXIMUM_UNIQUE_PATH_ATTEMPTS,
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

        resolve_agent_slug("Grok")  # ok: "grok" (flag wins)
        # FRESH_BRANCH_AGENT=codex, no flag -> "codex"
        # CURSOR_TRACE_ID set, no flag/env  -> "cursor"
        # no flag, env, or markers          -> "claude"

    Order: ``--agent`` flag, then ``FRESH_BRANCH_AGENT``, then the first set
    marker in ``ALL_AGENT_DETECTION_MARKERS``, else ``DEFAULT_AGENT_SLUG``.

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


def create_fresh_branch(
    branch_name: str,
    repo_path: Path,
    agent_slug: str,
    base_ref: str,
) -> dict[str, str]:
    """Fetch base_ref and create an isolated worktree branch.

    ::

        create_fresh_branch("fix/x", Path("."), "grok", "origin/main")
        # ok: worktree at Temp/grok/fix/x; source checkout stays on its branch

    Args:
        branch_name: New branch to create.
        repo_path: Path inside the source repository.
        agent_slug: Host label for the scratch root segment.
        base_ref: Base ref (default ``origin/main``).

    Returns:
        Success payload mapping.

    Raises:
        ValueError: When branch_name is empty.
        RuntimeError: On git or path failures.
    """
    cleaned_branch = branch_name.strip()
    if not cleaned_branch:
        raise ValueError(ERROR_BRANCH_NAME_REQUIRED)
    repo_root = _resolve_repo_root(repo_path)
    _fetch_base_ref(repo_root, base_ref)
    base_commit = _resolve_base_commit(repo_root, base_ref)
    agent_worktree_root = resolve_agent_worktree_root(agent_slug)
    preferred_path = agent_worktree_root / cleaned_branch
    worktree_path = resolve_unique_worktree_path(preferred_path)
    _create_worktree_branch(
        repo_root,
        branch_name=cleaned_branch,
        worktree_path=worktree_path,
        base_ref=base_ref,
    )
    return {
        PAYLOAD_KEY_BRANCH: cleaned_branch,
        PAYLOAD_KEY_WORKTREE_PATH: str(worktree_path.resolve()),
        PAYLOAD_KEY_BASE_REF: base_ref,
        PAYLOAD_KEY_BASE_COMMIT: base_commit,
        PAYLOAD_KEY_AGENT: agent_slug,
        PAYLOAD_KEY_REPO_ROOT: str(repo_root),
    }


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


def _normalize_agent_slug(raw_agent: str) -> str:
    agent_slug = raw_agent.strip().lower()
    if re.fullmatch(AGENT_SLUG_PATTERN, agent_slug) is None:
        raise ValueError(ERROR_AGENT_SLUG_INVALID)
    return agent_slug


def _resolve_repo_root(repo_path: Path) -> Path:
    completed = _run_git(
        [GIT_REV_PARSE, GIT_SHOW_TOPLEVEL],
        working_directory=repo_path,
    )
    if completed.returncode != 0:
        raise RuntimeError(ERROR_REPO_NOT_GIT % repo_path)
    return Path(completed.stdout.strip())


def _fetch_base_ref(repo_root: Path, base_ref: str) -> None:
    remote_name, remote_branch = _split_remote_ref(base_ref)
    completed = _run_git(
        [GIT_FETCH, remote_name, remote_branch],
        working_directory=repo_root,
    )
    if completed.returncode != 0:
        stderr_text = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(ERROR_FETCH_FAILED % (base_ref, stderr_text))
    if not _is_ref_present(repo_root, base_ref):
        raise RuntimeError(ERROR_BASE_REF_MISSING % base_ref)


def _resolve_base_commit(repo_root: Path, base_ref: str) -> str:
    completed = _run_git(
        [GIT_REV_PARSE, base_ref],
        working_directory=repo_root,
    )
    if completed.returncode != 0:
        stderr_text = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(ERROR_BASE_COMMIT_LOOKUP % (base_ref, stderr_text))
    return completed.stdout.strip()


def _create_worktree_branch(
    repo_root: Path,
    branch_name: str,
    worktree_path: Path,
    base_ref: str,
) -> None:
    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    completed = _run_git(
        [
            GIT_WORKTREE,
            GIT_WORKTREE_ADD,
            GIT_BRANCH_FLAG,
            branch_name,
            str(worktree_path),
            base_ref,
        ],
        working_directory=repo_root,
    )
    if completed.returncode != 0:
        stderr_text = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(ERROR_WORKTREE_FAILED % stderr_text)


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
    return parser.parse_args()


def _split_remote_ref(base_ref: str) -> tuple[str, str]:
    if base_ref.startswith(GIT_REMOTE_PREFIX):
        return GIT_REMOTE_PREFIX.rstrip("/"), base_ref[len(GIT_REMOTE_PREFIX) :]
    if "/" in base_ref:
        remote_name, remote_branch = base_ref.split("/", 1)
        return remote_name, remote_branch
    return GIT_REMOTE_PREFIX.rstrip("/"), base_ref


def _is_ref_present(repo_root: Path, base_ref: str) -> bool:
    remote_ref = f"{GIT_REFS_REMOTES_PREFIX}{base_ref}"
    completed = _run_git(
        [GIT_SHOW_REF, GIT_VERIFY_FLAG, GIT_QUIET_FLAG, remote_ref],
        working_directory=repo_root,
    )
    if completed.returncode == 0:
        return True
    completed = _run_git(
        [GIT_REV_PARSE, GIT_VERIFY_FLAG, GIT_QUIET_FLAG, base_ref],
        working_directory=repo_root,
    )
    return completed.returncode == 0


def _run_git(
    all_git_arguments: list[str],
    working_directory: Path,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [GIT_COMMAND, *all_git_arguments],
        cwd=str(working_directory),
        check=False,
        capture_output=True,
        text=True,
    )


if __name__ == "__main__":
    sys.exit(main())
