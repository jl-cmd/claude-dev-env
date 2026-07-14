# codex-review/scripts/codex_review_scripts_constants

Python package of named constants imported by codex-review scripts. Importing from this package keeps magic values out of script bodies.

## Modules

| File | Constants for |
|---|---|
| `__init__.py` | Package marker and package docstring. |
| `run_constants.py` | Binary name, flag strings, custom-instructions prompt, version-probe pattern, timeout default, JSONL keys, and outcome class labels for `run_codex_review.py`. |
| `findings_constants.py` | Finding field keys, fenced-JSON and freeform patterns for `parse_codex_findings.py`. |
| `classifier_constants.py` | Failure class names and stream markers for `codex_down_classifier.py`. |
| `codex_usage_probe_constants.py` | Gate threshold, probe report JSON keys, app-server JSON-RPC surface, rate-limit field keys, weekly-window sizing, text-status patterns, source labels, and exit codes for `codex_usage_probe.py`. |

## Convention

Scripts import from this package at module scope. No constant is defined inline in a script body — the hook enforces this at write time.
