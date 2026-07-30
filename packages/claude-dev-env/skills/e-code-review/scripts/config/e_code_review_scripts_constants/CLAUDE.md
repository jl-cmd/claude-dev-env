# e-code-review/scripts/config/e_code_review_scripts_constants

Named constants for `e_code_review_scripts_constants` consumers under this skill. Scripts import from this package so magic values stay out of script bodies.

## Modules

| File | Constants for |
|---|---|
| `__init__.py` | Package marker and package docstring. |
| `grok_code_review_constants.py` | Schema version, eight finder angles, verification verdicts, severities, and text encoding for `grok_code_review.py`. |

## Convention

Scripts import from this package at module scope. No constant is defined inline in a script body — the hook enforces this at write time.
