# codex-review/scripts/codex_review_scripts_constants

Python package of named constants imported by codex-review scripts. Importing from this package keeps magic values out of script bodies.

## Modules

| File | Constants for |
|---|---|
| `__init__.py` | Package marker and package docstring. |
| `run_constants.py` | Binary name, flag strings, custom-instructions prompt, version-probe pattern, timeout default, decode/timeout exit sentinels, shape-flag token tail, JSONL keys, and capture outcome class labels for `run_codex_review.py`. |

## Convention

Scripts import from this package at module scope. No constant is defined inline in a script body — the hook enforces this at write time.
