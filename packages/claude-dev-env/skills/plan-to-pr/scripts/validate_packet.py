"""Validate a completed Plan-to-PR packet using only the Python standard library."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from pathlib import Path

if str(Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent))

from config.constants import (
    COMMAND_SEPARATOR,
    HANDOFF_ACCEPTANCE_PREFIX,
    HANDOFF_ALLOWED_FILES_PREFIX,
    HANDOFF_APPROVAL_LINE,
    HANDOFF_PACKET_PREFIX,
    HANDOFF_TASK_ORDER_PREFIX,
    HANDOFF_TASK_LINE_PATTERN,
    HANDOFF_TEST_PREFIX,
    HANDOFF_VERIFICATION_PREFIX,
    MARKDOWN_FIELD_SEPARATOR,
    PACKET_VALIDATION_ERROR_EXIT_CODE,
    PATH_TRAVERSAL_TOKEN,
    REPRODUCIBILITY_BLOCK_PATTERN,
    ALL_REQUIRED_PACKET_FILES,
    SLUG_PATTERN,
    ALL_SOURCE_FIELDS,
    SOURCE_LOCATOR_PATTERN,
    ALL_TASK_COMMAND_FIELDS,
    ALL_TASK_FIELDS,
    TASK_LINE_PREFIX,
    UNRESOLVED_TEXT_PATTERN,
    DOCS_DIRECTORY_NAME,
    MARKDOWN_HEADING_TEMPLATE,
    NEWLINE_SEPARATOR,
    PACKET_DIRECTORY_MINIMUM_PARTS,
    PACKET_PARENT_PARTS_SLICE_START,
    PACKET_SLUG_PARTS_SLICE_END,
    ALL_PACKET_FIELDS,
    ALL_PACKET_REQUIRED_FIELDS,
    ALL_TASK_CONTRACT_FIELDS,
    ALL_VALIDATION_FIELDS,
)


def validate_packet(packet_directory: Path) -> list[str]:
    """Return field-level diagnostics for a packet directory.

    Args:
        packet_directory: Packet directory to validate.
    Returns:
        Diagnostics, with an empty list for a valid packet.
    """
    errors: list[str] = []
    errors.extend(_validate_packet_boundary(packet_directory))
    errors.extend(_validate_required_files(packet_directory))
    packet_payload, packet_errors = _read_packet_payload(packet_directory)
    errors.extend(packet_errors)
    if packet_payload is None:
        return errors
    errors.extend(_validate_packet_fields(packet_payload, packet_directory))
    errors.extend(_validate_sources(packet_payload, packet_directory))
    errors.extend(_validate_tasks(packet_payload, packet_directory))
    errors.extend(_validate_markdown(packet_payload, packet_directory))
    return errors


def _validate_packet_boundary(packet_directory: Path) -> list[str]:
    """Ensure the argument names a repository packet under docs/plans."""
    resolved_path = packet_directory.resolve()
    parts = resolved_path.parts
    if len(parts) < PACKET_DIRECTORY_MINIMUM_PARTS or parts[
        PACKET_PARENT_PARTS_SLICE_START:PACKET_SLUG_PARTS_SLICE_END
    ] != (
        DOCS_DIRECTORY_NAME,
        "plans",
    ):
        return ["packet path must be within docs/plans/<slug>"]
    if not SLUG_PATTERN.fullmatch(parts[-1]):
        return ["packet path slug must contain lowercase letters, numbers, and hyphens"]
    return []


def _validate_required_files(packet_directory: Path) -> list[str]:
    """Check the packet files required by the contract."""
    return [
        f"missing required file: {relative_path}"
        for relative_path in ALL_REQUIRED_PACKET_FILES
        if not (packet_directory / relative_path).is_file()
    ]


def _read_packet_payload(
    packet_directory: Path,
) -> tuple[dict[str, object] | None, list[str]]:
    """Read packet.json and report parse or top-level shape errors."""
    packet_file = packet_directory / "packet.json"
    if not packet_file.is_file():
        return None, []
    try:
        parsed_packet: object = json.loads(packet_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as packet_error:
        return None, [f"packet.json: invalid JSON: {packet_error}"]
    if not isinstance(parsed_packet, dict):
        return None, ["packet.json: expected an object"]
    return parsed_packet, []


def _validate_packet_fields(
    all_packet: dict[str, object], packet_directory: Path
) -> list[str]:
    """Validate packet metadata and its repository-relative boundaries."""
    errors = _validate_packet_field_names(all_packet)
    errors.extend(_validate_packet_metadata(all_packet, packet_directory))
    errors.extend(_validate_packet_lists(all_packet))
    return errors


def _validate_packet_field_names(all_packet: dict[str, object]) -> list[str]:
    """Report unknown and missing packet fields."""
    errors = [
        f"packet.json: unknown field: {each_field}"
        for each_field in sorted(set(all_packet) - set(ALL_PACKET_FIELDS))
    ]
    errors.extend(
        f"packet.json.{each_field}: required"
        for each_field in ALL_PACKET_REQUIRED_FIELDS
        if each_field not in all_packet
    )
    return errors


def _validate_packet_metadata(
    all_packet: dict[str, object], packet_directory: Path
) -> list[str]:
    """Validate packet version, identity, status, and request."""
    errors: list[str] = []
    if all_packet.get("schema_version") != 1:
        errors.append("packet.json.schema_version: must be 1")
    if all_packet.get("slug") != packet_directory.name:
        errors.append("packet.json.slug: must match the packet directory")
    if all_packet.get("status") != "approved":
        errors.append("packet.json.status: must be approved")
    request = all_packet.get("request")
    if not isinstance(request, str) or not request.strip():
        errors.append("packet.json.request: must be a non-empty string")
    errors.extend(
        _validate_path_list(
            all_packet.get("allowed_files"), "packet.json.allowed_files"
        )
    )
    errors.extend(_validate_validation_record(all_packet.get("validation")))
    return errors


def _validate_packet_lists(all_packet: dict[str, object]) -> list[str]:
    """Validate packet decisions and resolved questions."""
    errors: list[str] = []
    decisions = all_packet.get("decisions")
    if (
        not isinstance(decisions, list)
        or not decisions
        or any(
            not isinstance(each_decision, str) or not each_decision.strip()
            for each_decision in decisions
        )
    ):
        errors.append("packet.json.decisions: must be a non-empty string list")
    open_questions = all_packet.get("open_questions")
    if not isinstance(open_questions, list) or any(
        not isinstance(each_question, str) or not each_question.strip()
        for each_question in open_questions
    ):
        errors.append("packet.json.open_questions: must be a string list")
    if all_packet.get("open_questions") != []:
        errors.append("packet.json.open_questions: must be empty")
    return errors


def _validate_path_list(all_paths: object, field_name: str) -> list[str]:
    """Validate a repository-relative path list."""
    if not isinstance(all_paths, list) or not all_paths:
        return [f"{field_name}: must be a non-empty list"]
    errors: list[str] = []
    for each_index, each_path in enumerate(all_paths):
        if (
            not isinstance(each_path, str)
            or not each_path.strip()
            or Path(each_path).is_absolute()
            or "\\" in each_path
            or PATH_TRAVERSAL_TOKEN in each_path
        ):
            errors.append(
                f"{field_name}[{each_index}]: must be a repository-relative path"
            )
    path_names = [each_path for each_path in all_paths if isinstance(each_path, str)]
    if len(set(path_names)) != len(path_names):
        errors.append(f"{field_name}: entries must be unique")
    return errors


def _validate_validation_record(validation_record: object) -> list[str]:
    """Validate the packet validation evidence fields."""
    if not isinstance(validation_record, dict):
        return ["packet.json.validation: must be an object"]
    allowed_fields = set(ALL_VALIDATION_FIELDS)
    errors = [
        f"packet.json.validation: unknown field: {each_field}"
        for each_field in sorted(set(validation_record) - allowed_fields)
    ]
    for each_field in ALL_VALIDATION_FIELDS[:-1]:
        if validation_record.get(each_field) is not True:
            errors.append(f"packet.json.validation.{each_field}: must be true")
    if validation_record.get("validated_by") != "native-plan-to-pr":
        errors.append("packet.json.validation.validated_by: must be native-plan-to-pr")
    return errors


def _validate_sources(
    all_packet: dict[str, object], packet_directory: Path
) -> list[str]:
    """Ensure every source reference points to a non-empty repository file."""
    sources = all_packet.get("sources")
    if not isinstance(sources, list) or not sources:
        return ["packet.json.sources: must be a list"]
    repository_root = packet_directory.parents[2]
    errors: list[str] = []
    for each_index, each_source in enumerate(sources):
        if not isinstance(each_source, dict):
            errors.append(f"packet.json.sources[{each_index}]: must be an object")
            continue
        allowed_fields = set(ALL_SOURCE_FIELDS)
        errors.extend(
            f"packet.json.sources[{each_index}]: unknown field: {each_field}"
            for each_field in sorted(set(each_source) - allowed_fields)
        )
        for each_field in ALL_SOURCE_FIELDS:
            if (
                not isinstance(each_source.get(each_field), str)
                or not each_source[each_field].strip()
            ):
                errors.append(
                    f"packet.json.sources[{each_index}].{each_field}: required non-empty string"
                )
        source_path = each_source.get("path")
        if not isinstance(source_path, str):
            continue
        locator = each_source.get("locator")
        if isinstance(locator, str) and not SOURCE_LOCATOR_PATTERN.fullmatch(
            locator.strip()
        ):
            errors.append(
                f"packet.json.sources[{each_index}].locator: must be line, lines, or section locator"
            )
        if "\\" in source_path or PATH_TRAVERSAL_TOKEN in source_path:
            errors.append(
                f"packet.json.sources[{each_index}].path: must be a repository-relative path"
            )
            continue
        source_file = (repository_root / source_path).resolve()
        if not _is_within(source_file, repository_root) or not source_file.is_file():
            errors.append(
                f"packet.json.sources[{each_index}].path: file does not exist"
            )
        elif not source_file.read_text(encoding="utf-8").strip():
            errors.append(
                f"packet.json.sources[{each_index}].path: source file is empty"
            )
    return errors


def _validate_tasks(all_packet: dict[str, object], packet_directory: Path) -> list[str]:
    """Validate task identity, scope, dependencies, and commands."""
    tasks = all_packet.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        return ["packet.json.tasks: must be a non-empty list"]
    allowed_files = all_packet.get("allowed_files", [])
    all_task_ids: set[str] = set()
    dependencies_by_task: dict[str, list[str]] = {}
    errors: list[str] = []
    for each_index, each_task in enumerate(tasks):
        if not isinstance(each_task, dict):
            errors.append(f"packet.json.tasks[{each_index}]: must be an object")
            continue
        allowed_fields = set(ALL_TASK_CONTRACT_FIELDS)
        errors.extend(
            f"packet.json.tasks[{each_index}]: unknown field: {each_field}"
            for each_field in sorted(set(each_task) - allowed_fields)
        )
        task_id = each_task.get("id")
        if not isinstance(task_id, str) or not re.fullmatch(r"task-[0-9]+", task_id):
            errors.append(f"packet.json.tasks[{each_index}].id: must match task-N")
            continue
        if task_id in all_task_ids:
            errors.append(f"packet.json.tasks[{each_index}].id: duplicate {task_id}")
        all_task_ids.add(task_id)
        for each_field in ALL_TASK_FIELDS:
            if (
                not isinstance(each_task.get(each_field), str)
                or not each_task[each_field].strip()
            ):
                errors.append(
                    f"packet.json.tasks[{each_index}].{each_field}: required non-empty string"
                )
        task_files = each_task.get("allowed_files")
        errors.extend(
            _validate_path_list(
                task_files, f"packet.json.tasks[{each_index}].allowed_files"
            )
        )
        if isinstance(task_files, list) and isinstance(allowed_files, list):
            errors.extend(
                f"packet.json.tasks[{each_index}].allowed_files[{each_file_index}]: outside packet scope"
                for each_file_index, each_path in enumerate(task_files)
                if each_path not in allowed_files
            )
        if each_task.get("commit") != 1:
            errors.append(f"packet.json.tasks[{each_index}].commit: must be 1")
        for each_command_field in ALL_TASK_COMMAND_FIELDS:
            command = each_task.get(each_command_field)
            if isinstance(command, str) and not _is_reproducible_command(command):
                errors.append(
                    f"packet.json.tasks[{each_index}].{each_command_field}: must be a concrete reproducible command"
                )
        dependencies_by_task[task_id] = _validate_dependencies(
            each_task, task_id, all_task_ids, errors
        )
    errors.extend(_validate_dependency_cycles(dependencies_by_task))
    return errors


def _validate_dependencies(
    all_task: dict[str, object],
    task_id: str,
    all_task_ids: set[str],
    all_errors: list[str],
) -> list[str]:
    """Validate one task's optional dependency list."""
    dependencies = all_task.get("dependencies", [])
    if not isinstance(dependencies, list):
        all_errors.append(f"packet.json.tasks[{task_id}].dependencies: must be a list")
        return []
    dependency_names = [
        each_dependency
        for each_dependency in dependencies
        if isinstance(each_dependency, str)
    ]
    if len(set(dependency_names)) != len(dependency_names):
        all_errors.append(
            f"packet.json.tasks[{task_id}].dependencies: entries must be unique"
        )
    valid_dependencies: list[str] = []
    for each_dependency in dependencies:
        if not isinstance(each_dependency, str) or not re.fullmatch(
            r"task-[0-9]+", each_dependency
        ):
            all_errors.append(
                f"packet.json.tasks[{task_id}].dependencies: invalid task ID"
            )
        elif each_dependency == task_id:
            all_errors.append(
                f"packet.json.tasks[{task_id}].dependencies: cannot depend on itself"
            )
        else:
            valid_dependencies.append(each_dependency)
    return valid_dependencies


def _validate_dependency_cycles(
    dependencies_by_task: dict[str, list[str]],
) -> list[str]:
    """Return diagnostics for missing dependencies and directed cycles."""
    errors = [
        f"dependency references unknown task: {each_dependency}"
        for all_dependencies in dependencies_by_task.values()
        for each_dependency in all_dependencies
        if each_dependency not in dependencies_by_task
    ]
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str) -> None:
        """Visit one dependency node.

        Args:
            task_id: Dependency node to inspect.
        """
        if task_id in visiting:
            errors.append(f"dependency cycle detected at {task_id}")
            return
        if task_id in visited:
            return
        visiting.add(task_id)
        for each_dependency in dependencies_by_task.get(task_id, []):
            if each_dependency in dependencies_by_task:
                visit(each_dependency)
        visiting.remove(task_id)
        visited.add(task_id)

    for each_task_id in dependencies_by_task:
        visit(each_task_id)
    return errors


def _validate_markdown(
    all_packet: dict[str, object], packet_directory: Path
) -> list[str]:
    """Validate required markdown sections and packet-wide unresolved text."""
    errors = _validate_markdown_sections(packet_directory)
    task_text = _read_markdown_file(packet_directory, "tasks.md")
    all_tasks = all_packet.get("tasks", [])
    if not isinstance(all_tasks, list):
        return errors
    errors.extend(_validate_task_markdown(all_tasks, task_text))
    handoff_text = _read_markdown_file(packet_directory, "handoff.md")
    errors.extend(_validate_handoff(handoff_text, all_packet, packet_directory.name))
    return errors


def _validate_markdown_sections(packet_directory: Path) -> list[str]:
    """Validate required markdown headings and unresolved text."""
    errors: list[str] = []
    sections_by_file = {
        "context.md": (
            "Request",
            "Repository Facts",
            "Constraints",
            "Source References",
        ),
        "plan.md": ("Implementation", "Decisions", "Dependencies", "Risks"),
        "tasks.md": ("Tasks",),
        "handoff.md": ("Approval", "Task Order"),
    }
    for each_filename, each_headings in sections_by_file.items():
        each_text = _read_markdown_file(packet_directory, each_filename)
        for each_heading in each_headings:
            if not re.search(
                MARKDOWN_HEADING_TEMPLATE.format(re.escape(each_heading)),
                each_text,
                re.MULTILINE | re.IGNORECASE,
            ):
                errors.append(f"{each_filename}: missing section {each_heading}")
        if _has_unresolved_text(each_text):
            errors.append(
                f"{each_filename}: contains unresolved questions or placeholders"
            )
    return errors


def _read_markdown_file(packet_directory: Path, filename: str) -> str:
    """Read one packet markdown file or return empty text when absent."""
    packet_file = packet_directory / filename
    if not packet_file.is_file():
        return ""
    return packet_file.read_text(encoding="utf-8")


def _validate_task_markdown(all_tasks: list[object], task_text: str) -> list[str]:
    """Ensure tasks.md repeats every task field and file."""
    errors: list[str] = []
    for each_task in all_tasks:
        if (
            isinstance(each_task, dict)
            and isinstance(each_task.get("id"), str)
            and each_task["id"] not in task_text
        ):
            errors.append(f"tasks.md: missing task {each_task['id']}")
        if isinstance(each_task, dict):
            task_id = each_task.get("id")
            if not isinstance(task_id, str):
                continue
            for each_field_name in ALL_TASK_FIELDS:
                field_text = each_task.get(each_field_name)
                if isinstance(field_text, str):
                    is_field_present = (
                        _contains_exact_command(task_text, field_text)
                        if each_field_name in ALL_TASK_COMMAND_FIELDS
                        else field_text in task_text
                    )
                else:
                    is_field_present = False
                if not is_field_present:
                    errors.append(f"tasks.md: task {task_id} missing {each_field_name}")
            all_task_files = each_task.get("allowed_files")
            if isinstance(all_task_files, list):
                for each_file_path in all_task_files:
                    if (
                        isinstance(each_file_path, str)
                        and each_file_path not in task_text
                    ):
                        errors.append(
                            f"tasks.md: task {task_id} missing file {each_file_path}"
                        )
    return errors


def _contains_exact_command(markdown_text: str, command_text: str) -> bool:
    """Return whether a task command appears as one complete Markdown field."""
    return any(
        each_segment.strip() == command_text.strip()
        for each_line in markdown_text.splitlines()
        for each_segment in each_line.split(MARKDOWN_FIELD_SEPARATOR)
    )


def _validate_handoff(
    handoff_text: str, all_packet: dict[str, object], packet_slug: str
) -> list[str]:
    """Ensure the host task seed restates the approved packet tasks exactly."""
    all_handoff_lines = handoff_text.splitlines()
    handoff_lines = set(all_handoff_lines)
    errors = _validate_handoff_headers(handoff_lines, packet_slug)
    all_tasks = all_packet.get("tasks", [])
    if not isinstance(all_tasks, list):
        return errors
    all_task_ids = [
        each_task["id"]
        for each_task in all_tasks
        if isinstance(each_task, dict) and isinstance(each_task.get("id"), str)
    ]
    if len(all_task_ids) != len(all_tasks):
        return errors
    declared_task_ids = _declared_handoff_task_ids(all_handoff_lines)
    if declared_task_ids != all_task_ids:
        errors.append("handoff.md: declared tasks do not match packet.json")
    task_order_line = (
        f"{HANDOFF_TASK_ORDER_PREFIX}{COMMAND_SEPARATOR.join(all_task_ids)}"
    )
    if task_order_line not in handoff_lines:
        errors.append("handoff.md: task order does not match packet.json")
    errors.extend(_validate_handoff_task_fields(handoff_lines, all_tasks))
    return errors


def _validate_handoff_headers(
    all_handoff_lines: set[str], packet_slug: str
) -> list[str]:
    """Return missing packet identity and approval diagnostics."""
    required_lines = {
        "packet slug": f"{HANDOFF_PACKET_PREFIX}{packet_slug}",
        "approval state": HANDOFF_APPROVAL_LINE,
    }
    return [
        f"handoff.md: missing {each_field_name}"
        for each_field_name, each_required_line in required_lines.items()
        if each_required_line not in all_handoff_lines
    ]


def _declared_handoff_task_ids(all_handoff_lines: list[str]) -> list[str]:
    """Return task identifiers declared by handoff task lines."""
    declared_task_ids: list[str] = []
    for each_line in all_handoff_lines:
        task_match = HANDOFF_TASK_LINE_PATTERN.match(each_line)
        if task_match is not None:
            declared_task_ids.append(task_match.group(1))
    return declared_task_ids


def _validate_handoff_task_fields(
    all_handoff_lines: set[str], all_tasks: list[object]
) -> list[str]:
    """Return diagnostics for every packet task field in the handoff."""
    errors: list[str] = []
    for each_task in all_tasks:
        if not isinstance(each_task, dict) or not isinstance(each_task.get("id"), str):
            continue
        task_id = each_task["id"]
        all_task_files = each_task.get("allowed_files", [])
        task_file_names = (
            [
                each_file_path
                for each_file_path in all_task_files
                if isinstance(each_file_path, str)
            ]
            if isinstance(all_task_files, list)
            else []
        )
        task_lines = _handoff_task_lines(task_id, each_task, task_file_names)
        errors.extend(
            f"handoff.md: task {task_id} missing {each_field_name}"
            for each_field_name, each_required_line in task_lines.items()
            if each_required_line not in all_handoff_lines
        )
    return errors


def _handoff_task_lines(
    task_id: str, all_task: dict[str, object], all_task_files: list[str]
) -> dict[str, str]:
    """Build exact handoff lines for one packet task."""
    return {
        "deliverable": f"{TASK_LINE_PREFIX}{task_id}: {all_task.get('deliverable', '')}",
        "allowed files": f"{HANDOFF_ALLOWED_FILES_PREFIX}{COMMAND_SEPARATOR.join(all_task_files)}",
        "acceptance command": f"{HANDOFF_ACCEPTANCE_PREFIX}{all_task.get('acceptance_command', '')}",
        "test command": f"{HANDOFF_TEST_PREFIX}{all_task.get('test_command', '')}",
        "verification command": f"{HANDOFF_VERIFICATION_PREFIX}{all_task.get('verification_command', '')}",
    }


def _has_unresolved_text(text: str) -> bool:
    """Detect unresolved questions and common template markers outside code."""
    prose = re.sub(r"```[\s\S]*?```|`[^`]+`", "", text)
    return bool(UNRESOLVED_TEXT_PATTERN.search(prose))


def _is_reproducible_command(command: str) -> bool:
    """Accept a concrete shell command with no placeholders or randomness."""
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False
    return (
        bool(tokens)
        and not _has_unresolved_text(command)
        and not REPRODUCIBILITY_BLOCK_PATTERN.search(command)
    )


def _is_within(candidate_path: Path, parent_path: Path) -> bool:
    """Return whether a resolved path is within a resolved directory."""
    try:
        candidate_path.relative_to(parent_path)
    except ValueError:
        return False
    return True


def _parse_arguments() -> argparse.Namespace:
    """Parse the packet directory argument."""
    parser = argparse.ArgumentParser(description="Validate a Plan-to-PR packet.")
    parser.add_argument("packet_directory", type=Path)
    return parser.parse_args()


def main() -> int:
    """Run validation and return the CLI status code.

    Returns:
        The process status code.
    """
    errors = validate_packet(_parse_arguments().packet_directory)
    if errors:
        print(NEWLINE_SEPARATOR.join(errors), file=sys.stderr)
        return PACKET_VALIDATION_ERROR_EXIT_CODE
    print("packet validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
