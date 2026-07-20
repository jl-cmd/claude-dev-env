#!/usr/bin/env python3
"""SessionStart / SessionEnd hook: register host PID and tear down MCP children.

Claude Code and Grok start stdio MCP servers (mcpvault, playwright, serena) as
children of the agent host. Hosts often exit without reaping those trees, so
counts grow across sessions. This hook records the host PID at SessionStart and
terminates only MCP-matching descendants of that host at SessionEnd.

::

    SessionStart  -> write ~/.claude/cache/mcp-session-registry/mcp-host-<id>.json
    SessionEnd    -> taskkill /F /T only for MCP cmdline descendants of host_pid

Teardown is scoped by registered host PID plus MCP command-line markers. It
never issues a blanket kill by process name alone.
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import subprocess
import sys
import time
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.mcp_session_lifecycle_constants import (  # noqa: E402
    ALL_MCP_COMMAND_LINE_MARKERS,
    ALL_TASKKILL_ARGUMENTS,
    HOOK_EVENT_NAME_PAYLOAD_KEY,
    HOOK_EVENT_SESSION_END,
    HOOK_EVENT_SESSION_START,
    JSON_INDENT_SPACES,
    MCP_SESSION_REGISTRY_DIRECTORY,
    MCP_SESSION_REGISTRY_FILE_PREFIX,
    MCP_SESSION_REGISTRY_FILE_SUFFIX,
    PROCESS_LIST_POWERSHELL_COMMAND,
    PROCESS_LIST_SUBPROCESS_TIMEOUT_SECONDS,
    REGISTRY_HOST_PID_KEY,
    REGISTRY_RECORDED_AT_UNIX_KEY,
    REGISTRY_SESSION_ID_KEY,
    SESSION_ID_PAYLOAD_KEY,
    SESSION_ID_UNSAFE_CHARACTERS_PATTERN,
    SESSION_START_SOURCE_PAYLOAD_KEY,
    STATE_FILE_DEFAULT_SESSION_ID,
    TASKKILL_EXECUTABLE_NAME,
    TASKKILL_SUBPROCESS_TIMEOUT_SECONDS,
    UTF8_ENCODING,
    WINDOWS_PLATFORM_TAG,
)
from hooks_constants.pre_tool_use_stdin import (  # noqa: E402
    read_hook_input_dictionary_from_stdin,
)


def sanitize_session_id(session_id: str) -> str:
    """Return a filesystem-safe session id, or the default when empty.

    Args:
        session_id: Raw session id from the hook payload.

    Returns:
        Sanitized session id suitable for a registry file name.
    """
    sanitized_session_id = SESSION_ID_UNSAFE_CHARACTERS_PATTERN.sub("", session_id)
    return sanitized_session_id or STATE_FILE_DEFAULT_SESSION_ID


def registry_file_path_for_session(
    session_id: str,
    registry_directory: str,
) -> Path:
    """Build the registry path for one session.

    Args:
        session_id: Raw or sanitized session id.
        registry_directory: Directory that holds registry files.

    Returns:
        Path to the session's host-PID registry file.
    """
    safe_session_id = sanitize_session_id(session_id)
    file_name = (
        f"{MCP_SESSION_REGISTRY_FILE_PREFIX}"
        f"{safe_session_id}"
        f"{MCP_SESSION_REGISTRY_FILE_SUFFIX}"
    )
    return Path(registry_directory) / file_name


def command_line_matches_mcp_server(command_line: str) -> bool:
    """Report whether a process command line is a tracked MCP server tree.

    Args:
        command_line: Full process command line, possibly empty.

    Returns:
        True when any configured MCP marker appears in the command line.
    """
    if not command_line:
        return False
    lowered_command_line = command_line.casefold()
    for each_marker in ALL_MCP_COMMAND_LINE_MARKERS:
        if each_marker.casefold() in lowered_command_line:
            return True
    return False


def write_host_pid_registry(
    session_id: str,
    host_pid: int,
    registry_directory: str,
) -> Path:
    """Persist the agent host PID for a session.

    Args:
        session_id: Hook session id.
        host_pid: Parent process id of the hook (the agent host).
        registry_directory: Directory for registry files.

    Returns:
        Path written.
    """
    registry_path = registry_file_path_for_session(
        session_id=session_id,
        registry_directory=registry_directory,
    )
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_payload = {
        REGISTRY_SESSION_ID_KEY: sanitize_session_id(session_id),
        REGISTRY_HOST_PID_KEY: host_pid,
        REGISTRY_RECORDED_AT_UNIX_KEY: time.time(),
    }
    registry_path.write_text(
        json.dumps(registry_payload, indent=JSON_INDENT_SPACES) + "\n",
        encoding=UTF8_ENCODING,
    )
    return registry_path


def read_host_pid_registry(
    session_id: str,
    registry_directory: str,
) -> int | None:
    """Load the registered host PID for a session.

    Args:
        session_id: Hook session id.
        registry_directory: Directory for registry files.

    Returns:
        Host PID, or None when missing or invalid.
    """
    registry_path = registry_file_path_for_session(
        session_id=session_id,
        registry_directory=registry_directory,
    )
    if not registry_path.is_file():
        return None
    try:
        registry_payload = json.loads(
            registry_path.read_text(encoding=UTF8_ENCODING)
        )
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    if not isinstance(registry_payload, dict):
        return None
    host_pid_value = registry_payload.get(REGISTRY_HOST_PID_KEY)
    if not isinstance(host_pid_value, int):
        return None
    if host_pid_value <= 0:
        return None
    return host_pid_value


def delete_host_pid_registry(
    session_id: str,
    registry_directory: str,
) -> None:
    """Remove the registry file for a session when present.

    Args:
        session_id: Hook session id.
        registry_directory: Directory for registry files.
    """
    registry_path = registry_file_path_for_session(
        session_id=session_id,
        registry_directory=registry_directory,
    )
    try:
        registry_path.unlink()
    except FileNotFoundError:
        return
    except OSError:
        return


def parse_process_list_json(process_list_json: str) -> list[dict[str, object]]:
    """Parse ConvertTo-Json output from a Win32_Process listing.

    Args:
        process_list_json: JSON array or single object from PowerShell.

    Returns:
        List of process dictionaries with ProcessId, ParentProcessId, CommandLine.
    """
    if not process_list_json.strip():
        return []
    try:
        parsed_payload = json.loads(process_list_json)
    except json.JSONDecodeError:
        return []
    if isinstance(parsed_payload, list):
        return [each for each in parsed_payload if isinstance(each, dict)]
    if isinstance(parsed_payload, dict):
        return [parsed_payload]
    return []


def build_parent_pid_by_child_pid(
    all_processes: list[dict[str, object]],
) -> dict[int, int]:
    """Map each process id to its parent process id.

    Args:
        all_processes: Process rows from the process list.

    Returns:
        parent_pid_by_child_pid map.
    """
    parent_pid_by_child_pid: dict[int, int] = {}
    for each_process in all_processes:
        process_id = each_process.get("ProcessId")
        parent_process_id = each_process.get("ParentProcessId")
        if not isinstance(process_id, int):
            continue
        if not isinstance(parent_process_id, int):
            continue
        parent_pid_by_child_pid[process_id] = parent_process_id
    return parent_pid_by_child_pid


def is_descendant_of_host(
    process_id: int,
    host_pid: int,
    all_parent_pid_by_child_pid: dict[int, int],
) -> bool:
    """Report whether process_id is under host_pid in the parent chain.

    Args:
        process_id: Candidate process id.
        host_pid: Registered agent host pid.
        all_parent_pid_by_child_pid: Parent map for the live process table.

    Returns:
        True when host_pid appears as an ancestor, including direct parent.
    """
    if process_id == host_pid:
        return False
    visited_process_ids: set[int] = set()
    current_process_id = process_id
    while current_process_id in all_parent_pid_by_child_pid:
        if current_process_id in visited_process_ids:
            return False
        visited_process_ids.add(current_process_id)
        parent_process_id = all_parent_pid_by_child_pid[current_process_id]
        if parent_process_id == host_pid:
            return True
        if parent_process_id <= 0:
            return False
        current_process_id = parent_process_id
    return False


def collect_mcp_descendant_process_ids(
    host_pid: int,
    all_processes: list[dict[str, object]],
) -> list[int]:
    """Return MCP-matching process ids that descend from host_pid.

    Args:
        host_pid: Registered agent host pid.
        all_processes: Process rows from the process list.

    Returns:
        Deduplicated MCP process ids under the host, in process-table order.
    """
    all_parent_pid_by_child_pid = build_parent_pid_by_child_pid(all_processes)
    matched_process_ids: list[int] = []
    for each_process in all_processes:
        process_id = each_process.get("ProcessId")
        if not isinstance(process_id, int):
            continue
        command_line = each_process.get("CommandLine")
        command_line_text = command_line if isinstance(command_line, str) else ""
        if not command_line_matches_mcp_server(command_line_text):
            continue
        if not is_descendant_of_host(
            process_id=process_id,
            host_pid=host_pid,
            all_parent_pid_by_child_pid=all_parent_pid_by_child_pid,
        ):
            continue
        matched_process_ids.append(process_id)
    return list(dict.fromkeys(matched_process_ids))


def list_windows_processes() -> list[dict[str, object]]:
    """Return the live Win32 process table on Windows, else an empty list.

    Returns:
        Process dictionaries, or [] when not on Windows or listing fails.
    """
    if sys.platform != WINDOWS_PLATFORM_TAG:
        return []
    try:
        completed_process = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                PROCESS_LIST_POWERSHELL_COMMAND,
            ],
            capture_output=True,
            text=True,
            timeout=PROCESS_LIST_SUBPROCESS_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if completed_process.returncode != 0:
        return []
    return parse_process_list_json(completed_process.stdout)


def terminate_process_tree(process_id: int) -> bool:
    """Terminate one process tree by pid (Windows taskkill /T).

    Args:
        process_id: Root pid to terminate with its children.

    Returns:
        True when the kill command exits zero.
    """
    if process_id <= 0:
        return False
    if sys.platform != WINDOWS_PLATFORM_TAG:
        return False
    all_taskkill_arguments = list(ALL_TASKKILL_ARGUMENTS) + [str(process_id)]
    try:
        completed_process = subprocess.run(
            [TASKKILL_EXECUTABLE_NAME, *all_taskkill_arguments],
            capture_output=True,
            text=True,
            timeout=TASKKILL_SUBPROCESS_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed_process.returncode == 0


def teardown_mcp_descendants_for_host(
    host_pid: int,
    all_processes: list[dict[str, object]],
) -> list[int]:
    """Terminate MCP-matching descendant trees under host_pid.

    Args:
        host_pid: Registered agent host pid.
        all_processes: Process table to scan (empty list terminates nothing).

    Returns:
        Process ids for which terminate was attempted.
    """
    all_mcp_process_ids = collect_mcp_descendant_process_ids(
        host_pid=host_pid,
        all_processes=all_processes,
    )
    if all_mcp_process_ids:
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=len(all_mcp_process_ids)
        ) as executor:
            list(executor.map(terminate_process_tree, all_mcp_process_ids))
    return all_mcp_process_ids


def resolve_hook_event_name(payload_by_field: dict[str, object]) -> str:
    """Resolve SessionStart vs SessionEnd from the hook payload.

    Args:
        payload_by_field: Parsed hook stdin object.

    Returns:
        Hook event name string (SessionStart, SessionEnd, or empty).
    """
    explicit_event_name = payload_by_field.get(HOOK_EVENT_NAME_PAYLOAD_KEY)
    if isinstance(explicit_event_name, str) and explicit_event_name:
        return explicit_event_name
    if SESSION_START_SOURCE_PAYLOAD_KEY in payload_by_field:
        return HOOK_EVENT_SESSION_START
    return HOOK_EVENT_SESSION_END


def run_session_lifecycle(
    payload_by_field: dict[str, object],
    host_pid: int,
    registry_directory: str,
    all_processes: list[dict[str, object]],
) -> str:
    """Apply SessionStart registration or SessionEnd MCP teardown.

    Args:
        payload_by_field: Hook payload.
        host_pid: Process id of the agent host (hook parent).
        registry_directory: Registry directory (production or test temp).
        all_processes: Process table for teardown (empty list skips kill scan).

    Returns:
        Action label: ``registered``, ``torn_down``, or ``ignored``.
    """
    session_id = str(payload_by_field.get(SESSION_ID_PAYLOAD_KEY) or "")
    if not session_id:
        return "ignored"
    hook_event_name = resolve_hook_event_name(payload_by_field)
    if hook_event_name == HOOK_EVENT_SESSION_START:
        write_host_pid_registry(
            session_id=session_id,
            host_pid=host_pid,
            registry_directory=registry_directory,
        )
        return "registered"
    if hook_event_name == HOOK_EVENT_SESSION_END:
        registered_host_pid = read_host_pid_registry(
            session_id=session_id,
            registry_directory=registry_directory,
        )
        effective_host_pid = (
            registered_host_pid if registered_host_pid is not None else host_pid
        )
        teardown_mcp_descendants_for_host(
            host_pid=effective_host_pid,
            all_processes=all_processes,
        )
        delete_host_pid_registry(
            session_id=session_id,
            registry_directory=registry_directory,
        )
        return "torn_down"
    return "ignored"


def main() -> None:
    """Read the lifecycle payload and register or tear down MCP children.

    Exits zero on every branch so a lifecycle failure never blocks the session.
    """
    payload_by_field = read_hook_input_dictionary_from_stdin()
    if payload_by_field is None:
        return
    host_pid = os.getppid()
    hook_event_name = resolve_hook_event_name(payload_by_field)
    all_processes: list[dict[str, object]] = []
    if hook_event_name == HOOK_EVENT_SESSION_END:
        all_processes = list_windows_processes()
    run_session_lifecycle(
        payload_by_field=payload_by_field,
        host_pid=host_pid,
        registry_directory=MCP_SESSION_REGISTRY_DIRECTORY,
        all_processes=all_processes,
    )


if __name__ == "__main__":
    main()
