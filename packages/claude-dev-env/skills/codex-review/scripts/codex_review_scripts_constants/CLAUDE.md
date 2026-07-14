# codex-review/scripts/codex_review_scripts_constants

Python package of named constants imported by codex-review scripts. Importing from this package keeps magic values out of script bodies.

## Modules

| File | Constants for |
|---|---|
| `__init__.py` | Package marker and package docstring. |
| `run_constants.py` | Binary name, flag strings, custom-instructions prompt, version-probe pattern, timeout default, decode/timeout exit sentinels, flag_token_pattern suffix (whole-token shape match), JSONL keys, JSONL capture filename and newline mode, and capture outcome class labels for `run_codex_review.py`. |
| `codex_usage_probe_constants.py` | The weekly-usage probe CLI: gate threshold, report JSON keys, app-server JSON-RPC surface, rate-limit field keys, weekly-window sizing, text-status parse patterns, source labels, and exit codes. |

## Convention

Scripts import from this package at module scope. No constant is defined inline in a script body — the hook enforces this at write time.
