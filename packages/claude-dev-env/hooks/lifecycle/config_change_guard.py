#!/usr/bin/env python3
# pragma: no-tdd-gate
from datetime import datetime
import json
import os
import sys

AUDIT_LOG = os.path.expanduser("~/.claude/cache/config-change-audit.log")
# pragma: no-tdd-gate
DEFAULT_KNOWN_HOOK_COUNT_FILE = os.path.expanduser("~/.claude/cache/known-hook-count.txt")


def get_known_hook_count_file() -> str:
    return os.environ.get("KNOWN_HOOK_COUNT_FILE", DEFAULT_KNOWN_HOOK_COUNT_FILE)


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


# pragma: no-tdd-gate
def guard_hook_injection(file_path: str) -> None:
    current_count = count_hooks_in_settings(file_path)
    known_hook_count_file = get_known_hook_count_file()

    if not os.path.exists(known_hook_count_file):
        try:
            with open(known_hook_count_file, "w") as count_file:
                count_file.write(str(current_count))
        except OSError:
            pass
        return

    try:
        with open(known_hook_count_file) as count_file:
            stored_count = int(count_file.read().strip())
    except (OSError, ValueError):
        stored_count = current_count

    # pragma: no-tdd-gate
    if current_count > stored_count:
        block_reason = (
            f"Hook count increased from {stored_count} to {current_count}. "
            f"Review the added hook entries before proceeding. "
            f"Delete known-hook-count.txt to reset."
        )
        block_payload = {
            "decision": "block",
            "reason": block_reason,
        }
        print(json.dumps(block_payload))
        return

    try:
        with open(known_hook_count_file, "w") as count_file:
            count_file.write(str(current_count))
    except OSError:
        pass


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
