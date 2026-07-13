# codex-review/scripts/codex_review_scripts_constants

Python package of named constants for codex-review. This package's `scripts/` tree holds constants only; the headless wrapper entrypoint is sister work.

## Modules

| File | Constants for |
|---|---|
| `__init__.py` | Package marker and package docstring. |

## Convention

Consumers import from this package at module scope. No constant is defined inline in a consumer body — the hook enforces this at write time.
