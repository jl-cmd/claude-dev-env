# config/

Python package providing shared constants for the AI rules fan-out sync system.

## Purpose

Holds the repo-level Python configuration package. It gathers typed constants for the
`.github/` scripts and the root `scripts/` dispatcher — paths, metric labels, message
templates, and environment-variable names — into one package rather than scattering them
across scripts. Each script imports only the module it needs. One loader, `local_identity.py`,
resolves the private fan-out owner scopes from the environment or a git-ignored file.

## Files

| File | Role |
|------|------|
| `__init__.py` | Package marker; makes `config` resolve as a Python package rather than a flat module. |
| `sync_ai_rules_paths.py` | Defines the source and destination path strings for the AI rules sync: `SOURCE_FILE_PATH`, `BUGBOT_DESTINATION_PATH`, `AGENTS_DESTINATION_PATH`, `DESTINATION_PATHS`, and `BUGBOT_ONLY_DESTINATION_PATHS`. |
| `constants.py` | Metric labels, summary-table strings, GitHub Actions annotation templates, and environment-variable names for `scripts/fan_out_dispatch.py`, plus the per-repo conclusion-report status labels, the private-target redaction format, and the listener-runs query template for `scripts/fan_out_conclusion_report.py`. |
| `local_identity.py` | Resolves the fan-out owner scopes and each owner's token environment-variable name from the `FANOUT_OWNER_SCOPES` env var or the git-ignored `config/local-identity.json`, with a placeholder default. |
| `local-identity.example.json` | Committed template for the git-ignored `config/local-identity.json`; carries placeholder owner scopes and NAS host, user, and port. |

## Usage

Scripts import from this package directly:

```python
from config.sync_ai_rules_paths import DESTINATION_PATHS, BUGBOT_ONLY_DESTINATION_PATHS
```

The `pytest.ini` at the repo root puts `.` on `pythonpath`, so `import config` resolves
from any test or script that runs from the repo root.

## Conventions

- Constants follow `UPPER_SNAKE_CASE` and are typed (`tuple[str, ...]` for path groups).
- Most modules hold values only. `local_identity.py` is the one loader: it reads the git-ignored `config/local-identity.json` or the environment to resolve private values, and keeps a committed placeholder default.
- New path constants for the sync system belong in `sync_ai_rules_paths.py`.
