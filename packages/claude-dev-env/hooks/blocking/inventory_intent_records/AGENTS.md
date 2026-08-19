# inventory_intent_records

The shared pending-intent store that lets `package_inventory_stale_blocker.py`
and `claude_md_orphan_file_blocker.py` add a new file and its inventory row in
one change, in either order. When one blocker denies, it records a note; the
sibling blocker reads that note to allow the matching second write.

## Modules

| File | Purpose |
|---|---|
| `records.py` | Read, record, peek, and consume the per-session file and row intents; a missing or corrupt store reads as no notes |
| `__init__.py` | Package marker |

## Subdirectories

| Entry | Description |
|---|---|
| `config/` | The records-file name shape, the freshness window, the list keys, and the note field names (`intent_records_constants.py`) |
| `tests/` | pytest suite for the records store |

## Running tests

```bash
python -m pytest packages/claude-dev-env/hooks/blocking/inventory_intent_records/tests/
```
