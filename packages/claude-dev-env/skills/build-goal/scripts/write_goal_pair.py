#!/usr/bin/env python3
"""Render a goal-cmd prompt and a human brief from a session-supplied packet.

The invoking session gathers its own objective, task list, and constraints
into a JSON packet and passes its path as this script's only argument. This
script validates the packet, fills the two fixed templates under
``templates/``, and writes both files atomically under the OS temp
directory, printing their absolute paths to stdout.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from build_goal_constants import write_goal_pair_constants as goal_constants


class GoalPacketError(ValueError):
    """Raised when a goal packet cannot be read or fails schema validation."""


@dataclass(frozen=True)
class GoalPacket:
    """A goal packet, normalized to the shapes the templates expect."""

    objective: str
    done_when: tuple[str, ...]
    in_scope: tuple[str, ...]
    out_of_scope: tuple[str, ...]
    tasks: tuple[dict[str, str], ...]
    context: dict[str, object]
    execution_notes: tuple[str, ...]


def load_goal_packet(packet_path: Path) -> dict[str, object]:
    """Read and JSON-decode a packet file, without checking its schema.

    Args:
        packet_path: Path to the session-supplied packet JSON file.

    Returns:
        The decoded JSON object.

    Raises:
        GoalPacketError: When the file is unreadable, not valid JSON, or its root is not a JSON object.
    """
    try:
        packet_text = packet_path.read_text(encoding=goal_constants.ENCODING_UTF8)
    except OSError as read_error:
        raise GoalPacketError(
            goal_constants.ERROR_PACKET_FILE_UNREADABLE % packet_path
        ) from read_error
    try:
        packet_object = json.loads(packet_text)
    except json.JSONDecodeError as decode_error:
        raise GoalPacketError(
            goal_constants.ERROR_PACKET_JSON_INVALID % decode_error.msg
        ) from decode_error
    if not isinstance(packet_object, dict):
        raise GoalPacketError(goal_constants.ERROR_PACKET_ROOT_NOT_OBJECT)
    return packet_object


def validate_goal_packet(all_packet_fields: dict[str, object]) -> GoalPacket:
    """Validate a decoded packet and normalize it into a GoalPacket.

    Args:
        all_packet_fields: The JSON object decoded from the packet file.

    Returns:
        A GoalPacket with every field normalized to its rendering shape.
    """
    objective = _require_non_empty_string(
        all_packet_fields.get(goal_constants.PACKET_KEY_OBJECTIVE),
        goal_constants.ERROR_OBJECTIVE_REQUIRED,
    )  # noqa: E501
    done_when = _require_non_empty_string_list(
        all_packet_fields.get(goal_constants.PACKET_KEY_DONE_WHEN),
        goal_constants.ERROR_DONE_WHEN_REQUIRED,
        goal_constants.ERROR_DONE_WHEN_ENTRY_INVALID,
    )  # noqa: E501
    return GoalPacket(
        objective=objective,
        done_when=done_when,
        in_scope=_scoped_list(
            all_packet_fields,
            goal_constants.PACKET_KEY_IN_SCOPE,
            goal_constants.ERROR_IN_SCOPE_ENTRY_INVALID,
        ),  # noqa: E501
        out_of_scope=_scoped_list(
            all_packet_fields,
            goal_constants.PACKET_KEY_OUT_OF_SCOPE,
            goal_constants.ERROR_OUT_OF_SCOPE_ENTRY_INVALID,
        ),  # noqa: E501
        tasks=_validate_tasks(all_packet_fields.get(goal_constants.PACKET_KEY_TASKS)),
        context=_validate_context(
            all_packet_fields.get(goal_constants.PACKET_KEY_CONTEXT)
        ),
        execution_notes=_scoped_list(
            all_packet_fields,
            goal_constants.PACKET_KEY_EXECUTION_NOTES,
            goal_constants.ERROR_EXECUTION_NOTES_ENTRY_INVALID,
        ),  # noqa: E501
    )


def render_bullet_lines(all_entries: Sequence[str]) -> str:
    """Render each entry as its own markdown bullet line, or "" when empty."""
    return goal_constants.NEWLINE_JOIN_SEPARATOR.join(
        f"{goal_constants.BULLET_LINE_PREFIX}{each_entry}" for each_entry in all_entries
    )  # noqa: E501


def render_numbered_table_rows(all_entries: Sequence[str]) -> str:
    """Render each entry as a numbered two-column markdown table row.

    Args:
        all_entries: Plain-text values to render, one per row.

    Returns:
        Table rows joined by newlines, or "" when all_entries is empty.
    """
    all_rows = [
        goal_constants.NUMBERED_TABLE_ROW_FORMAT.format(
            index=each_index, text=each_entry
        )
        for each_index, each_entry in enumerate(all_entries, 1)
    ]
    return goal_constants.NEWLINE_JOIN_SEPARATOR.join(all_rows)


def _render_task_lines(all_tasks: Sequence[dict[str, str]], line_format: str) -> str:
    """Render each task through a shared status/id/subject format string.

    Args:
        all_tasks: Task rows carrying id, status, and subject.
        line_format: A ``str.format`` template with mark/task_id/subject fields.

    Returns:
        Lines joined by newlines, or "" when all_tasks is empty.
    """
    all_lines = [
        line_format.format(
            mark=_task_status_mark(each_task[goal_constants.TASK_KEY_STATUS]),
            task_id=each_task[goal_constants.TASK_KEY_ID],
            subject=each_task[goal_constants.TASK_KEY_SUBJECT],
        )
        for each_task in all_tasks
    ]
    return goal_constants.NEWLINE_JOIN_SEPARATOR.join(all_lines)


def render_task_table_rows(all_tasks: Sequence[dict[str, str]]) -> str:
    """Render each task as a status/id/subject markdown table row.

    Args:
        all_tasks: Task rows carrying id, status, and subject.

    Returns:
        Table rows joined by newlines, or "" when all_tasks is empty.
    """
    return _render_task_lines(all_tasks, goal_constants.TASKS_TABLE_ROW_FORMAT)


def render_task_bullet_lines(all_tasks: Sequence[dict[str, str]]) -> str:
    """Render each task as a checkbox bullet line, id and subject verbatim.

    Args:
        all_tasks: Task rows carrying id, status, and subject.

    Returns:
        Bullet lines joined by newlines, or "" when all_tasks is empty.
    """
    return _render_task_lines(all_tasks, goal_constants.TASKS_BULLET_LINE_FORMAT)


def render_context_bullet_lines(all_context_fields: dict[str, object]) -> str:
    """Render the context facts a session supplied as markdown bullet lines.

    Args:
        all_context_fields: The normalized context object (repo, branch, pr, paths, constraints).

    Returns:
        Bullet lines joined by newlines, or "" when there are no facts.
    """
    all_lines = _context_scalar_lines(all_context_fields)
    all_paths = all_context_fields.get(goal_constants.CONTEXT_KEY_PATHS)
    if isinstance(all_paths, tuple) and all_paths:
        all_lines.append(
            f"{goal_constants.CONTEXT_PATHS_LABEL}{goal_constants.CONTEXT_PATHS_JOIN_SEPARATOR.join(all_paths)}"
        )  # noqa: E501
    all_constraints = all_context_fields.get(goal_constants.CONTEXT_KEY_CONSTRAINTS)
    if isinstance(all_constraints, tuple):
        all_lines.extend(all_constraints)
    return render_bullet_lines(all_lines)


def _context_scalar_lines(all_context_fields: dict[str, object]) -> list[str]:
    all_lines: list[str] = []
    for each_label, each_key in (
        (goal_constants.CONTEXT_REPO_LABEL, goal_constants.CONTEXT_KEY_REPO),
        (goal_constants.CONTEXT_BRANCH_LABEL, goal_constants.CONTEXT_KEY_BRANCH),
        (goal_constants.CONTEXT_PR_LABEL, goal_constants.CONTEXT_KEY_PR),
    ):
        each_field_content = all_context_fields.get(each_key)
        if isinstance(each_field_content, str):
            all_lines.append(f"{each_label}{each_field_content}")
    return all_lines


def _context_without_constraints(all_context_fields: dict[str, object]) -> dict[str, object]:
    return {
        each_key: each_field
        for each_key, each_field in all_context_fields.items()
        if each_key != goal_constants.CONTEXT_KEY_CONSTRAINTS
    }


def render_goal_cmd_document(packet: GoalPacket) -> str:
    """Fill the goal-cmd skeleton with one packet's rendered sections.

    Args:
        packet: A validated, normalized goal packet.

    Returns:
        The complete goal-cmd markdown document.
    """
    substitutions = {
        goal_constants.GOAL_CMD_PLACEHOLDER_OBJECTIVE: packet.objective,
        goal_constants.GOAL_CMD_PLACEHOLDER_DONE_WHEN: render_bullet_lines(
            packet.done_when
        ),
        goal_constants.GOAL_CMD_PLACEHOLDER_IN_SCOPE: render_bullet_lines(
            packet.in_scope
        ),
        goal_constants.GOAL_CMD_PLACEHOLDER_OUT_OF_SCOPE: render_bullet_lines(
            packet.out_of_scope
        ),
        goal_constants.GOAL_CMD_PLACEHOLDER_TASKS: render_task_bullet_lines(
            packet.tasks
        ),
        goal_constants.GOAL_CMD_PLACEHOLDER_CONTEXT: render_context_bullet_lines(
            packet.context
        ),
        goal_constants.GOAL_CMD_PLACEHOLDER_EXECUTION_NOTES: render_bullet_lines(
            packet.execution_notes
        ),
    }
    template_text = _read_template(goal_constants.GOAL_CMD_TEMPLATE_FILENAME)
    return _finalize_document(_substitute_placeholders(template_text, substitutions))


def render_human_brief_document(packet: GoalPacket) -> str:
    """Fill the human-brief skeleton with one packet's skim tables and lists.

    Args:
        packet: A validated, normalized goal packet.

    Returns:
        The complete human-brief markdown document.
    """
    context_constraints = packet.context.get(goal_constants.CONTEXT_KEY_CONSTRAINTS)
    all_constraints = (
        context_constraints if isinstance(context_constraints, tuple) else ()
    )
    substitutions = {
        goal_constants.HUMAN_BRIEF_PLACEHOLDER_OBJECTIVE: packet.objective,
        goal_constants.HUMAN_BRIEF_PLACEHOLDER_DONE_WHEN_ROWS: render_numbered_table_rows(
            packet.done_when
        ),
        goal_constants.HUMAN_BRIEF_PLACEHOLDER_TASKS_ROWS: render_task_table_rows(
            packet.tasks
        ),
        goal_constants.HUMAN_BRIEF_PLACEHOLDER_CONSTRAINTS_ROWS: render_numbered_table_rows(
            all_constraints
        ),
        goal_constants.HUMAN_BRIEF_PLACEHOLDER_IN_SCOPE: render_bullet_lines(
            packet.in_scope
        ),
        goal_constants.HUMAN_BRIEF_PLACEHOLDER_OUT_OF_SCOPE: render_bullet_lines(
            packet.out_of_scope
        ),
        goal_constants.HUMAN_BRIEF_PLACEHOLDER_CONTEXT: render_context_bullet_lines(
            _context_without_constraints(packet.context)
        ),
        goal_constants.HUMAN_BRIEF_PLACEHOLDER_EXECUTION_NOTES: render_bullet_lines(
            packet.execution_notes
        ),
    }
    template_text = _read_template(goal_constants.HUMAN_BRIEF_TEMPLATE_FILENAME)
    return _finalize_document(_substitute_placeholders(template_text, substitutions))


def write_goal_pair(packet_path: Path) -> tuple[Path, Path]:
    """Validate a goal packet and write the goal-cmd and human-brief pair.

    Args:
        packet_path: Path to the session-supplied packet JSON file.

    Returns:
        The absolute paths of the written goal-cmd file and human-brief file.
    """
    goal_packet = validate_goal_packet(load_goal_packet(packet_path))
    run_directory = _allocate_run_directory()
    goal_cmd_path = run_directory / goal_constants.GOAL_CMD_OUTPUT_FILENAME
    human_brief_path = run_directory / goal_constants.HUMAN_BRIEF_OUTPUT_FILENAME
    _write_text_atomically(goal_cmd_path, render_goal_cmd_document(goal_packet))
    _write_text_atomically(human_brief_path, render_human_brief_document(goal_packet))
    return goal_cmd_path.resolve(), human_brief_path.resolve()


def parse_arguments() -> argparse.Namespace:
    """Parse the CLI arguments.

    Returns:
        The parsed command-line arguments namespace.

    Raises:
        GoalPacketError: When the packet-path argument is missing or unparsable.
    """
    parser = argparse.ArgumentParser(
        description="Render the goal-cmd and human-brief file pair from a packet."
    )
    parser.add_argument("packet_path", type=Path)
    try:
        return parser.parse_args()
    except SystemExit as exit_error:
        if exit_error.code in (goal_constants.EXIT_CODE_SUCCESS, None):
            raise
        raise GoalPacketError(
            goal_constants.ERROR_PACKET_PATH_ARGUMENT_REQUIRED
        ) from exit_error


def main() -> int:
    """CLI entry: render both files and print their paths to stdout.

    Returns:
        Process exit code (0 success, 1 write failure, 2 invalid packet).
    """
    try:
        parsed_arguments = parse_arguments()
        goal_cmd_path, human_brief_path = write_goal_pair(parsed_arguments.packet_path)
    except GoalPacketError as packet_error:
        sys.stderr.write(f"{packet_error}\n")
        return goal_constants.EXIT_CODE_INVALID_PACKET
    except OSError as write_error:
        sys.stderr.write(f"{write_error}\n")
        return goal_constants.EXIT_CODE_WRITE_FAILED
    sys.stdout.write(f"{goal_constants.STDOUT_GOAL_CMD_PATH_PREFIX}{goal_cmd_path}\n")
    sys.stdout.write(
        f"{goal_constants.STDOUT_HUMAN_BRIEF_PATH_PREFIX}{human_brief_path}\n"
    )
    return goal_constants.EXIT_CODE_SUCCESS


def _task_status_mark(status: str) -> str:
    return (
        goal_constants.TASK_CHECKED_MARK
        if status == goal_constants.TASK_STATUS_COMPLETED
        else goal_constants.TASK_UNCHECKED_MARK
    )


def _substitute_placeholders(
    template_text: str, all_substitutions: dict[str, str]
) -> str:
    rendered_text = template_text
    for each_placeholder, each_replacement_text in all_substitutions.items():
        rendered_text = rendered_text.replace(each_placeholder, each_replacement_text)
    return rendered_text


def _finalize_document(rendered_text: str) -> str:
    collapsed_text = re.sub(
        goal_constants.BLANK_LINE_COLLAPSE_PATTERN,
        goal_constants.BLANK_LINE_COLLAPSE_REPLACEMENT,
        rendered_text,
    )  # noqa: E501
    return collapsed_text.strip() + "\n"


def _read_template(template_filename: str) -> str:
    template_path = _skill_templates_directory() / template_filename
    return template_path.read_text(encoding=goal_constants.ENCODING_UTF8)


@lru_cache(maxsize=1)
def _skill_templates_directory() -> Path:
    return (
        Path(__file__).resolve().parent.parent / goal_constants.TEMPLATES_DIRECTORY_NAME
    )


def _allocate_run_directory() -> Path:
    run_directory = (
        Path(tempfile.gettempdir())
        / goal_constants.TEMP_ROOT_SUBDIRECTORY_NAME
        / _build_run_id()
    )
    run_directory.mkdir(parents=True, exist_ok=True)
    return run_directory


def _build_run_id() -> str:
    timestamp_segment = datetime.now().strftime(goal_constants.RUN_ID_TIMESTAMP_FORMAT)
    random_segment = secrets.token_hex(goal_constants.RUN_ID_RANDOM_SUFFIX_BYTE_LENGTH)
    return f"{timestamp_segment}{goal_constants.RUN_ID_SEPARATOR}{random_segment}"


def _write_text_atomically(target_path: Path, document_text: str) -> None:
    temporary_path = target_path.with_name(
        target_path.name + goal_constants.ATOMIC_WRITE_TEMP_SUFFIX
    )
    temporary_path.write_text(document_text, encoding=goal_constants.ENCODING_UTF8)
    os.replace(temporary_path, target_path)


def _require_non_empty_string(raw_field: object, error_message: str) -> str:
    if not isinstance(raw_field, str) or not raw_field.strip():
        raise GoalPacketError(error_message)
    return raw_field.strip()


def _require_non_empty_string_list(
    raw_field: object, missing_error: str, entry_error: str
) -> tuple[str, ...]:
    if not isinstance(raw_field, list) or not raw_field:
        raise GoalPacketError(missing_error)
    return _validated_string_tuple(raw_field, entry_error)


def _scoped_list(
    all_packet_fields: dict[str, object], packet_key: str, entry_error: str
) -> tuple[str, ...]:
    raw_field = all_packet_fields.get(packet_key)
    if raw_field is None:
        return ()
    if not isinstance(raw_field, list):
        raise GoalPacketError(entry_error)
    return _validated_string_tuple(raw_field, entry_error)


def _validated_string_tuple(
    all_raw_entries: list[object], entry_error: str
) -> tuple[str, ...]:
    all_entries: list[str] = []
    for each_entry in all_raw_entries:
        if not isinstance(each_entry, str):
            raise GoalPacketError(entry_error)
        if not each_entry.strip():
            raise GoalPacketError(entry_error)
        all_entries.append(each_entry.strip())
    return tuple(all_entries)


def _validate_tasks(raw_field: object) -> tuple[dict[str, str], ...]:
    if raw_field is None:
        return ()
    if not isinstance(raw_field, list):
        raise GoalPacketError(goal_constants.ERROR_TASKS_NOT_LIST)
    return tuple(_validate_task_entry(each_task) for each_task in raw_field)


def _validate_task_entry(raw_task: object) -> dict[str, str]:
    if not isinstance(raw_task, dict):
        raise GoalPacketError(goal_constants.ERROR_TASK_ENTRY_INVALID)
    task_id = raw_task.get(goal_constants.TASK_KEY_ID)
    subject = raw_task.get(goal_constants.TASK_KEY_SUBJECT)
    status = raw_task.get(goal_constants.TASK_KEY_STATUS)
    if not isinstance(task_id, str) or not task_id.strip():
        raise GoalPacketError(goal_constants.ERROR_TASK_ENTRY_INVALID)
    if not isinstance(subject, str) or not subject.strip():
        raise GoalPacketError(goal_constants.ERROR_TASK_ENTRY_INVALID)
    if (
        not isinstance(status, str)
        or status not in goal_constants.ALL_VALID_TASK_STATUSES
    ):
        raise GoalPacketError(goal_constants.ERROR_TASK_STATUS_INVALID)
    return {
        goal_constants.TASK_KEY_ID: task_id.strip(),
        goal_constants.TASK_KEY_STATUS: status,
        goal_constants.TASK_KEY_SUBJECT: subject.strip(),
    }  # noqa: E501


def _validate_context(raw_field: object) -> dict[str, object]:
    if raw_field is None:
        return {}
    if not isinstance(raw_field, dict):
        raise GoalPacketError(goal_constants.ERROR_CONTEXT_NOT_OBJECT)
    context_object: dict[str, object] = raw_field
    normalized_context: dict[str, object] = {}
    for each_key in (
        goal_constants.CONTEXT_KEY_REPO,
        goal_constants.CONTEXT_KEY_BRANCH,
        goal_constants.CONTEXT_KEY_PR,
    ):
        each_field_content = context_object.get(each_key)
        if each_field_content is not None:
            normalized_context[each_key] = _require_non_empty_string(
                each_field_content, goal_constants.ERROR_CONTEXT_SCALAR_FIELD_INVALID
            )  # noqa: E501
    normalized_context[goal_constants.CONTEXT_KEY_PATHS] = _scoped_list(
        context_object,
        goal_constants.CONTEXT_KEY_PATHS,
        goal_constants.ERROR_CONTEXT_PATHS_NOT_LIST,
    )  # noqa: E501
    normalized_context[goal_constants.CONTEXT_KEY_CONSTRAINTS] = _scoped_list(
        context_object,
        goal_constants.CONTEXT_KEY_CONSTRAINTS,
        goal_constants.ERROR_CONTEXT_CONSTRAINTS_NOT_LIST,
    )  # noqa: E501
    return normalized_context


if __name__ == "__main__":
    sys.exit(main())
