"""Translate Claude capability requests into declarative Codex records."""

import argparse
import json
import re
import sys
from pathlib import Path


class CapabilityArgumentError(ValueError):
    """Raised when bridge command-line input cannot be translated."""


class CapabilityArgumentParser(argparse.ArgumentParser):
    """Parse bridge arguments while keeping failures inside the JSON contract."""

    def error(self, message: str) -> None:
        raise CapabilityArgumentError(f"invalid bridge arguments: {message}")


def _load_capability_map() -> dict[str, object]:
    capability_map_path = Path(__file__).resolve().parents[1] / "codex-capability-map.json"
    with capability_map_path.open(encoding="utf-8") as map_file:
        return json.load(map_file)


def _build_error_record(source_surface: str, message: str) -> dict[str, object]:
    return {"source": source_surface, "status": "error", "error": message}


def _parse_command_arguments() -> argparse.Namespace:
    argument_parser = CapabilityArgumentParser()
    argument_parser.add_argument("source_surface")
    argument_parser.add_argument("payload_json", nargs="?")
    return argument_parser.parse_args()


def _read_payload(payload_json: str) -> object:
    try:
        return json.loads(payload_json)
    except json.JSONDecodeError as payload_error:
        raise CapabilityArgumentError("payload must be valid JSON") from payload_error


def _capability_by_surface() -> dict[str, dict[str, object]]:
    all_capabilities = _load_capability_map()["capabilities"]
    capability_by_surface: dict[str, dict[str, object]] = {}
    for each_capability in all_capabilities:
        capability_by_surface[each_capability["source"].casefold()] = each_capability
        for each_alias in each_capability["aliases"]:
            capability_by_surface[each_alias.casefold()] = each_capability
    return capability_by_surface


def _contains_unsafe_path(all_capability_payload: object) -> bool:
    path_pattern = re.compile(
        r"(?:^[A-Za-z]:[\\/]|^\\\\|^/|^~(?:[\\/]|$)|^(?:%[^%]+%|\$\{?[A-Za-z_][A-Za-z0-9_]*\}?)(?:[\\/]|$)|(?:^|[\\/])(?:Users|home|\.ssh|\.codex)(?:[\\/]|$)|(?:^|[\\/])\.\.(?:[\\/]|$))",
        re.IGNORECASE,
    )
    if isinstance(all_capability_payload, str):
        return bool(path_pattern.search(all_capability_payload))
    if isinstance(all_capability_payload, dict):
        return any(_contains_unsafe_path(each_payload_entry) for each_payload_entry in all_capability_payload.values())
    if isinstance(all_capability_payload, list):
        return any(_contains_unsafe_path(each_payload_entry) for each_payload_entry in all_capability_payload)
    return False


def _status_by_source() -> dict[str, str]:
    return {"pending": "pending", "queued": "pending", "in_progress": "in_progress", "in-progress": "in_progress", "active": "in_progress", "completed": "completed", "complete": "completed", "done": "completed"}


def _task_plan_entry(all_capability_payload: dict[str, object]) -> dict[str, str] | None:
    task_name = all_capability_payload.get("subject", all_capability_payload.get("name", all_capability_payload.get("title")))
    task_status = all_capability_payload.get("status", "pending")
    status_by_source = _status_by_source()
    if not isinstance(task_name, str) or not task_name.strip():
        return None
    if not isinstance(task_status, str) or task_status.casefold() not in status_by_source:
        return None
    return {"step": task_name, "status": status_by_source[task_status.casefold()]}


def _has_required_fields(all_capability_payload: dict[str, object], all_required_field_definitions: dict[str, str]) -> bool:
    status_by_source = _status_by_source()
    for each_required_field_name, each_required_field_schema in all_required_field_definitions.items():
        required_field_content = all_capability_payload.get(each_required_field_name)
        if each_required_field_schema == "string" and (not isinstance(required_field_content, str) or not required_field_content.strip()):
            return False
        if each_required_field_schema == "status" and (not isinstance(required_field_content, str) or required_field_content.casefold() not in status_by_source):
            return False
    return True


def _has_valid_plan(all_capability_payload: dict[str, object]) -> bool:
    all_task_entries = all_capability_payload.get("plan")
    return isinstance(all_task_entries, list) and all(isinstance(each_task_entry, dict) and _task_plan_entry(each_task_entry) is not None for each_task_entry in all_task_entries)


def translate_capability(source_surface: str, payload: object) -> dict[str, object]:
    """Translate one capability request into a deterministic declarative record.

    The dispatcher selects a mapped target, rejects unsafe or malformed payloads,
    conditionally dispatches TaskList plans through ``_has_valid_plan``, and emits
    manual-review records for unsupported scheduling requests.

    Args:
        source_surface: Claude capability name or configured alias.
        payload: JSON-compatible request payload.

    Returns:
        A declarative translation record that never executes the target action.
    """
    capability = _capability_by_surface().get(source_surface.casefold())
    if capability is None:
        return {"source": source_surface, "status": "unknown", "error": "unknown source surface"}
    if _contains_unsafe_path(payload):
        return {"source": capability["source"], "status": "rejected", "error": "path-bearing payload is not allowed"}
    if not isinstance(payload, dict):
        return {"source": capability["source"], "status": "malformed", "error": "payload must be a JSON object"}
    if capability["status"] == "unsupported":
        return {"source": capability["source"], "target": None, "status": "unsupported", "manual_review": True, "error": "scheduling is unavailable"}
    if capability["target"] == "update_plan":
        if capability["source"] == "TaskList":
            if not _has_valid_plan(payload):
                return {"source": capability["source"], "status": "malformed", "error": "TaskList requires a plan of named tasks"}
            return {"source": capability["source"], "target": capability["target"], "transformation": "snapshot", "payload": {"plan": payload["plan"]}, "manual_review": True, "status": "mapped"}
        task_plan_entry = _task_plan_entry(payload)
        if task_plan_entry is None:
            return {"source": capability["source"], "status": "malformed", "error": "task requires a name and supported status"}
        operation = "status mutation" if capability["source"] == "TaskUpdate" else "replace-plan-item" if payload.get("operation") == "replace" else "append"
        return {"source": capability["source"], "target": capability["target"], "transformation": operation, "payload": {"plan": [task_plan_entry]}, "status": "mapped"}
    all_required_field_definitions = capability.get("required_fields", {})
    if not isinstance(all_required_field_definitions, dict) or not _has_required_fields(payload, all_required_field_definitions):
        return {"source": capability["source"], "status": "malformed", "error": "payload is missing required fields"}
    return {"source": capability["source"], "target": capability["target"], "transformation": capability["transformation"], "payload": payload, "manual_review": capability["manual_review"], "status": "mapped"}


def main() -> int:
    """Dispatch a command-line request and print its JSON translation record.

    The dispatcher reads an optional payload argument or stdin, translates it
    through the public capability dispatcher, and emits JSON.

    Args:
        None. Command-line arguments are read from the process argument vector.

    Returns:
        Zero after the translation record is written.
    """
    try:
        command_arguments = _parse_command_arguments()
        payload_json = command_arguments.payload_json or sys.stdin.read()
        capability_payload = _read_payload(payload_json)
        translated_record = translate_capability(command_arguments.source_surface, capability_payload)
        all_translation_error_statuses = ("unknown", "rejected", "malformed")
        if translated_record["status"] in all_translation_error_statuses:
            print(json.dumps(translated_record, sort_keys=True, separators=(",", ":")))
            return 2
        print(json.dumps(translated_record, sort_keys=True, separators=(",", ":")))
        return 0
    except CapabilityArgumentError as argument_error:
        print(json.dumps(_build_error_record("unknown", str(argument_error)), separators=(",", ":")))
        return 2
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as configuration_error:
        print(json.dumps(_build_error_record("unknown", f"bridge configuration error: {configuration_error}"), separators=(",", ":")))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
