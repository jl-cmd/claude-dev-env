# config/

Python package providing path constants for the AI rules fan-out sync system.

## Purpose

Holds the repo-level Python configuration package. It exposes typed constants that
the `.github/` scripts and the root `scripts/` dispatcher share, keeping all path
strings in one place rather than scattered across multiple scripts.

## Files

| File | Role |
|------|------|
| `__init__.py` | Package marker; makes `config` resolve as a Python package rather than a flat module. |
| `sync_ai_rules_paths.py` | Defines the source and destination path strings for the AI rules sync: `SOURCE_FILE_PATH`, `BUGBOT_DESTINATION_PATH`, `AGENTS_DESTINATION_PATH`, `DESTINATION_PATHS`, and `BUGBOT_ONLY_DESTINATION_PATHS`. |

## Usage

Scripts import from this package directly:

```python
from config.sync_ai_rules_paths import DESTINATION_PATHS, BUGBOT_ONLY_DESTINATION_PATHS
```

The `pytest.ini` at the repo root puts `.` on `pythonpath`, so `import config` resolves
from any test or script that runs from the repo root.

## Conventions

- Constants follow `UPPER_SNAKE_CASE` and are typed (`tuple[str, ...]` for path groups).
- Do not add runtime logic here; this package holds values only.
- New path constants for the sync system belong in `sync_ai_rules_paths.py`.
