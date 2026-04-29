import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    log_path = Path.home() / ".claude" / "logs" / "instructions_loaded.jsonl"
    payload_fields = (
        "file_path",
        "load_reason",
        "memory_type",
        "trigger_file_path",
        "parent_file_path",
        "globs",
        "session_id",
    )
    try:
        payload = json.load(sys.stdin)
        record = {"timestamp": datetime.now(timezone.utc).isoformat()}
        for each_field_name in payload_fields:
            record[each_field_name] = payload.get(each_field_name)
    except Exception as exception:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(exception),
        }
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(record) + "\n")
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
