#!/usr/bin/env python3
from datetime import datetime
import json
import os
import sys

AUDIT_LOG = os.path.expanduser("~/.claude/cache/config-change-audit.log")
KNOWN_HOOK_COUNT_FILE = os.path.expanduser("~/.claude/cache/known-hook-count.txt")


def count_hooks_in_settings(file_path: str) -> int:
    try:
        with open(file_path) as settings_file:
            settings = json.load(settings_file)
    except (OSError, json.JSONDecodeError):
        return 0
    hooks_section = settings.get("hooks", {})
    total_count = 0
    for event_hook_groups in hooks_section.values():
        for hook_configuration in event_hook_groups:
            total_count += len(hook_configuration.get("hooks", []))
    return total_count


def write_audit_entry(source: str, file_path: str) -> None:
    audit_entry = f"{datetime.now().isoformat()} source={source} file={file_path}\n"
    try:
        os.makedirs(os.path.dirname(AUDIT_LOG), exist_ok=True)
        with open(AUDIT_LOG, "a") as audit_file:
            audit_file.write(audit_entry)
    except OSError:
        pass


def guard_hook_injection(file_path: str) -> None:
    current_count = count_hooks_in_settings(file_path)

    if not os.path.exists(KNOWN_HOOK_COUNT_FILE):
        try:
            with open(KNOWN_HOOK_COUNT_FILE, "w") as count_file:
                count_file.write(str(current_count))
        except OSError:
            pass
        return

    try:
        with open(KNOWN_HOOK_COUNT_FILE) as count_file:
            stored_count = int(count_file.read().strip())
    except (OSError, ValueError):
        stored_count = current_count

    try:
        with open(KNOWN_HOOK_COUNT_FILE, "w") as count_file:
            count_file.write(str(current_count))
    except OSError:
        pass

    if current_count > stored_count:
        block_decision = {
            "decision": "block",
            "reason": f"Hook count changed {stored_count} -> {current_count}. Delete known-hook-count.txt to reset.",
        }
        print(json.dumps(block_decision))


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    source = hook_input.get("source", "")
    file_path = hook_input.get("file_path", "")

    write_audit_entry(source, file_path)

    if source == "user_settings" and file_path:
        guard_hook_injection(file_path)

    sys.exit(0)


if __name__ == "__main__":
    main()
