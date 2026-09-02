# Lazy-load probe hook

Optional empirical check for the `auditing-claude-config` skill. When the audit's
recommendations rest on assumptions about lazy-load behavior — especially
`@`-imports nested inside path-scoped rules — install this probe hook to capture
every `InstructionsLoaded` event. The hub ([`../SKILL.md`](../SKILL.md) §
Empirical verification) points here.

## Hook script

Path: `~/.claude/hooks/observability/instructions_loaded_logger.py`

```python
#!/usr/bin/env python3
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    log_path = Path.home() / ".claude" / "logs" / "instructions_loaded.jsonl"
    try:
        payload = json.load(sys.stdin)
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "file_path": payload.get("file_path"),
            "load_reason": payload.get("load_reason"),
            "memory_type": payload.get("memory_type"),
            "trigger_file_path": payload.get("trigger_file_path"),
            "parent_file_path": payload.get("parent_file_path"),
            "globs": payload.get("globs"),
            "session_id": payload.get("session_id"),
        }
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
```

## settings.json registration

Merge under `hooks.InstructionsLoaded` in `~/.claude/settings.json`:

```json
{
  "matcher": "session_start|nested_traversal|path_glob_match|include|compact",
  "hooks": [
    {
      "type": "command",
      "command": "python ~/.claude/hooks/observability/instructions_loaded_logger.py"
    }
  ]
}
```

## Test protocol

1. Start a fresh Claude Code session in a directory with no test files (`*.test.*`, `test_*.py`, etc.).
2. Read `~/.claude/logs/instructions_loaded.jsonl`. Every entry should have `load_reason: "session_start"` (plus any `nested_traversal` for ancestor CLAUDE.md files). Entries for path-scoped rules should be absent.
3. Open a `.test.tsx` (or `test_foo.py`) file. Re-read the log. New entries should have `load_reason: "path_glob_match"` for the rule itself, and `load_reason: "include"` (with `parent_file_path` pointing at the rule) for any `@`-imports nested inside it.
4. Acceptance: a rule classified as path-scoped does not appear in step 2 but does appear in step 3. Its nested imports follow the same pattern.
