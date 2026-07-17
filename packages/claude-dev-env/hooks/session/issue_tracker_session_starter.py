#!/usr/bin/env python3
"""SessionStart hook: ask Claude to start the issue-tracker for this session.

At a fresh or cleared session start this hook injects a directive telling Claude
to run the issue-tracker skill or agent, so the session records its work as
GitHub issues from the outset. The hook stays silent — writing nothing — when the
session continues an existing conversation, when the ``CLAUDE_ISSUE_TRACKER``
toggle is off, when the session's repository has no GitHub origin remote, or when
the issue-tracker skill and agent files are absent from ``~/.claude``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import _path_setup  # noqa: F401

from hooks_constants.issue_tracker_session_starter_constants import (  # noqa: E402
    ALL_GIT_ORIGIN_REMOTE_URL_ARGUMENTS,
    ALL_ISSUE_TRACKER_PRESENCE_PATH_FRAGMENTS,
    CLAUDE_CONFIG_DIRECTORY_NAME,
    GIT_DIRECTORY_FLAG,
    GIT_EXECUTABLE_NAME,
    GIT_REMOTE_PROBE_TIMEOUT_SECONDS,
    GITHUB_REMOTE_HOST_MARKER,
    ISSUE_TRACKER_ENV_VAR_NAME,
    ISSUE_TRACKER_START_DIRECTIVE,
)
from hooks_constants.pre_tool_use_stdin import (  # noqa: E402
    read_hook_input_dictionary_from_stdin,
)
from hooks_constants.session_start_injector import (  # noqa: E402
    build_session_start_payload,
    is_eligible_source,
    is_injection_enabled,
)
from hooks_constants.session_start_injector_constants import (  # noqa: E402
    SESSION_CWD_FIELD_KEY,
    SESSION_SOURCE_FIELD_KEY,
)


def build_issue_tracker_directive() -> str:
    """Return the directive that asks Claude to start the issue tracker."""
    return ISSUE_TRACKER_START_DIRECTIVE


def _session_working_directory(payload_by_field: dict[str, object]) -> str:
    """Return the session working directory from the payload, or the process cwd."""
    payload_cwd = payload_by_field.get(SESSION_CWD_FIELD_KEY)
    if isinstance(payload_cwd, str) and payload_cwd:
        return payload_cwd
    return os.getcwd()


def _has_github_origin_remote(working_directory: str) -> bool:
    """Report whether the repository at working_directory has a GitHub origin remote."""
    probe_command = [
        GIT_EXECUTABLE_NAME,
        GIT_DIRECTORY_FLAG,
        working_directory,
        *ALL_GIT_ORIGIN_REMOTE_URL_ARGUMENTS,
    ]
    try:
        completed_process = subprocess.run(
            probe_command,
            check=False,
            capture_output=True,
            text=True,
            timeout=GIT_REMOTE_PROBE_TIMEOUT_SECONDS,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False
    if completed_process.returncode != 0:
        return False
    return GITHUB_REMOTE_HOST_MARKER in completed_process.stdout.strip().lower()


def _issue_tracker_files_present() -> bool:
    """Report whether both issue-tracker probe files exist under ~/.claude."""
    claude_config_directory = Path.home() / CLAUDE_CONFIG_DIRECTORY_NAME
    return all(
        (claude_config_directory / each_fragment).exists()
        for each_fragment in ALL_ISSUE_TRACKER_PRESENCE_PATH_FRAGMENTS
    )


def main() -> None:
    """Inject the issue-tracker directive when every gate passes, else stay silent."""
    payload_by_field = read_hook_input_dictionary_from_stdin()
    if payload_by_field is None:
        sys.exit(0)
    session_source = str(payload_by_field.get(SESSION_SOURCE_FIELD_KEY) or "")
    if not is_eligible_source(session_source):
        sys.exit(0)
    if not is_injection_enabled(ISSUE_TRACKER_ENV_VAR_NAME):
        sys.exit(0)
    if not _has_github_origin_remote(_session_working_directory(payload_by_field)):
        sys.exit(0)
    if not _issue_tracker_files_present():
        sys.exit(0)
    directive_payload = build_session_start_payload(build_issue_tracker_directive())
    sys.stdout.write(json.dumps(directive_payload) + "\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
