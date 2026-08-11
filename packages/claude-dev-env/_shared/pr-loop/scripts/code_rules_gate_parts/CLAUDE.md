# code_rules_gate_parts

The modules `code_rules_gate.py` wires together to run the code-rules gate. Each
module owns one concern; the entry script imports them and re-exports their
surface for the test suite.

## Modules

| File | Purpose |
|---|---|
| `enforcer_loading.py` | Locates and loads `code_rules_enforcer.validate_content` from disk with the hooks directory on `sys.path` |
| `git_file_sets.py` | Resolves the diff, staged, and untracked file sets from git, plus prefix filtering and staged line-span helpers |
| `git_blob_readers.py` | Reads the committed and staged content of one file, and probes staged-index presence |
| `added_line_maps.py` | Maps each changed file to the line numbers the current diff added, resolving renames and new files |
| `violation_scoping.py` | Recovers a violation's line span from the enforcer message and partitions violations into blocking versus advisory |
| `wrapper_plumb_check.py` | Flags a public wrapper that drops a same-file delegate's optional keyword arguments; holds the code-path and test-path classifiers |
| `gate_running.py` | Validates the eligible file set, reports the inspected-file count, and prints the partitioned violation report |
| `staged_test_running.py` | Runs one staged-test group, grouped by its owning pytest config and by top-level directory when no config owns it, in command-line-length-safe pytest batches, optionally writing a JUnit XML report per batch |
| `staged_test_regression.py` | Discovers the staged test files, runs every group, and blocks only on a failure the staged change introduces — a group that fails is re-run against the HEAD baseline (a throwaway detached checkout made with `git worktree add --detach` under the OS temp root, deleted with `git worktree remove --force`) and only a failure absent there blocks |
| `baseline_import_isolation.py` | Points the baseline run's imports at the baseline worktree — rebases every repository import root onto the front of its `PYTHONPATH` — and installs the pytest plugin that reports which modules the run loaded out of the user's own tree, so a route that survives the rebase is measured and the baseline discarded |
| `gate_arguments.py` | Parses the gate's command-line arguments |
| `__init__.py` | Package marker |

## Staged-test grouping boundaries

The top-level fallback in `staged_test_running.py` fires only in a repository
whose root holds no pytest config, and it splits top-level neighbors alone:

- Config-less packages that sit deeper under one shared top-level directory, such as `pkgs/alpha` and `pkgs/beta`, share that directory's single pytest session, so a module name they both expose still shadows.
- A `conftest.py` at the repository root stays unloaded for those groups, because each session works from the top-level directory and the root file falls outside the tree pytest treats as its root.

## Subdirectory

| Entry | Description |
|---|---|
| `tests/` | pytest suite with one test module per module above, plus `_repo_test_helpers.py` (shared real-git-repository builders) |

## Running tests

```bash
python -m pytest packages/claude-dev-env/_shared/pr-loop/scripts/code_rules_gate_parts/tests/
```
