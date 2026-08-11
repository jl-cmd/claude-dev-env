# tdd_enforcer_parts

The concern modules `tdd_enforcer.py` wires together to run the TDD gate. Each
module owns one concern; the entry hook imports them and re-exports their
surface for the test suite.

## Modules

| File | Purpose |
|---|---|
| `path_classification.py` | Classifies a write target (docs, tests, `.claude` trees) the gate skips, and extracts the written text from a Write, Edit, or MultiEdit payload |
| `content_analysis.py` | Decides whether a payload is constants-only, and whether an Edit or MultiEdit merely removes or reorders imports |
| `candidate_paths.py` | Resolves the candidate test files whose freshness can satisfy the gate for a production file |
| `freshness.py` | Checks whether a candidate test was modified within the window and holds a real test function |
| `git_tracking.py` | Detects a write that restores a git-tracked file absent on disk, so a remove-then-Write rewrite is exempt from the gate |
| `decisions.py` | Builds the deny reason and writes the allow or deny decision JSON to stdout |
| `__init__.py` | Package marker |

## Subdirectories

| Entry | Description |
|---|---|
| `config/` | The freshness window, the ancestor-walk limit, the git-tracking command tokens, the source-file extension sets, and the join separator (`tdd_enforcer_constants.py`) |
| `tests/` | pytest suite with one test module per module above |

## Running tests

```bash
python -m pytest packages/claude-dev-env/hooks/blocking/tdd_enforcer_parts/tests/
```
