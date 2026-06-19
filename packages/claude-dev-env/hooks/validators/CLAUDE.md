# hooks/validators

A library of check modules used by the validation hooks. Each module focuses on one concern; `run_all_validators.py` runs them all and collects results. These modules do not hook into Claude Code directly — they are imported by the validation hooks.

## Core infrastructure

| File | Role |
|---|---|
| `validator_base.py` | Defines the `Violation` dataclass (`file`, `line`, `message`) used by every check module |
| `validator_defaults.py` | Default configuration values shared across check modules |
| `exempt_paths.py` | Path exemption logic — paths that checks skip (e.g. vendored code) |
| `output_formatter.py` | Formats `Violation` lists into human-readable output |
| `run_all_validators.py` | Entry point — runs every check module and aggregates results |
| `health_check.py` | Verifies that all validator dependencies (ruff, mypy) are reachable |

## Check modules

| Module | What it checks |
|---|---|
| `abbreviation_checks.py` | Abbreviated names in Python code |
| `code_quality_checks.py` | General code quality concerns (dead code, stub bodies, etc.) |
| `comment_checks.py` | Inline comment presence and content |
| `file_structure_checks.py` | File-level structural rules (line count, module layout) |
| `git_checks.py` | Git-state checks (untracked files, merge conflicts) |
| `magic_value_checks.py` | Magic numbers and strings |
| `mypy_integration.py` | Runs mypy and converts its output to `Violation` objects |
| `pr_reference_checks.py` | PR references in commit messages and changelogs |
| `python_antipattern_checks.py` | Python-specific anti-patterns (bare `except`, `Any`, etc.) |
| `python_style_checks.py` | Python style rules (naming, imports, type hints) |
| `react_checks.py` | React/TSX-specific checks (class component patterns, PureComponent usage) |
| `ruff_integration.py` | Runs ruff and converts its output to `Violation` objects |
| `security_checks.py` | Security anti-patterns (hardcoded secrets, unsafe calls) |
| `todo_checks.py` | TODO/FIXME markers without an associated issue reference |
| `type_safety_checks.py` | Type-safety rules (no `Any`, no `cast`, no `# type: ignore`) |
| `useless_test_checks.py` | Tests that check only existence or constant values |
| `verify_paths.py` | Validates that file paths referenced in code actually exist |

## Subdirectory

| Directory | Role |
|---|---|
| `test_files/` | Fixture files used by the validator tests — not checked-in test code |

## Conventions

- Every check module exposes one or more functions that take file content or an AST and return a list of `Violation` objects.
- Test files live beside the modules they test: `test_<module>.py`. Run with `python -m pytest validators/test_<name>.py`.
- `conftest.py` provides shared test fixtures (sample files, fixture paths).
- `README.md` in this directory documents the validator design and how to add a new check.
