# tests/

Root-level Python test suite covering repo-level scripts, contracts, and cross-file integrity.

## Purpose

Holds tests for the repository contracts and cross-file integrity checks. These
tests are separate from the hook tests (which live beside their hooks under
`packages/claude-dev-env/hooks/`) and from the JS installer tests
(`packages/claude-dev-env/bin/*.test.mjs`).

## Supported run commands

Two Python suites share the root `pytest.ini`. Run them as **separate** sessions so each
suite keeps its own collection scope.

| Scope | Command |
|-------|---------|
| Root suite only (`tests/`) | `python -m pytest tests/` |
| Package suite (`packages/claude-dev-env`) | `python -m pytest packages/claude-dev-env` |
| Default bare invocation | `python -m pytest` |
| Root suite in parallel | `python -m pytest tests/ -n auto` |
| Package suite in parallel | `python -m pytest packages/claude-dev-env -n auto` |
| JS suite (installer + skill scripts) | `cd packages/claude-dev-env && npm test` |
| Quality gate (ruff + mypy + enforcer tests) | `pwsh -File packages/claude-dev-env/scripts/check.ps1` |

Bare `python -m pytest` is scoped to `tests/` via `testpaths` in `pytest.ini`.
It is the same root-suite session as `python -m pytest tests/`.

CI (`.github/workflows/ci-tests.yml`) runs the same split Python sessions (with
`-n auto`) and the JS suite when path filters match on PRs; push to `main`
always runs both suites. Deselect node IDs live under `.github/ci/`; see
[Local-only register](#local-only-register) for the why.

### Parallel runs (`pytest-xdist`)

Install the optional dev extra (or the plugin alone):

```bash
pip install -e "packages/claude-dev-env[dev]"
# or: pip install pytest-xdist
```

Then pass `-n auto` on a **single** suite session (same split as serial):

```bash
python -m pytest tests/ -n auto
python -m pytest packages/claude-dev-env -n auto
```

Do not merge the two suites into one session. CI runs both suite sessions with
`-n auto` (pytest-xdist is installed in the workflow). Local use is supported
once the plugin is installed.

`pytest.ini` at the repo root sets `--import-mode=importlib`, adds `.` to
`pythonpath`, scopes default collection to `tests/` via `testpaths`, and collects
both `test_*` and `should_*` functions.

## Local-only register

Some tests or surfaces do not run on the ubuntu CI Python suite, or are not the
CI quality gate. The node-ID lists under `.github/ci/` are the deselect source;
this register is the why.

| Family | Status | Why |
|--------|--------|-----|
| LivePostAuditThreadTests (12) | Deselected on CI | Authenticated `gh` and real repo state. List: `.github/ci/live-post-audit-deselects.txt`. |
| Author-swap restore family (8) | Deselected on CI | Issue #21 protocol; no `gh auth switch` credentials on runners. List: `.github/ci/author-swap-deselects.txt`. |
| Windows-semantics (7) | CI on windows-latest | Deselected on ubuntu; covered on windows-latest from the same list. Not local-only. List: `.github/ci/windows-semantics-node-ids.txt`. |
| Known-pending deselects | Deselected on CI | Pending #20 disposition or venue-dependent failures. List: `.github/ci/known-pending-deselects.txt`. |
| Linux `is_ephemeral` OS-temp assertion | Deselected on CI | Out-of-scope production gap (#18). Listed in `.github/ci/known-pending-deselects.txt`. |
| Full `check.ps1` ruff + mypy green | CI quality gate | The quality-gate job runs `check.ps1 -SkipTests` (ruff + mypy); the enforcer pytest suite runs in the package-suite job. For a pytest-only `check.ps1` pass locally, use `-SkipRuff -SkipMypy`. |
| Native git hooks / commit controls | Tests run in CI | Production hook surface is local (installed under the user Claude config). The unit tests run in the package suite. |
| Live Neon logging | Tests run in CI | Production logging needs Neon credentials. Tests mock the boundary and run in CI. |

### Deselection provenance

- **Lists (what):** `.github/ci/*.txt` — node IDs CI passes to `--deselect` (and, for Windows-semantics, the windows-latest select set).
- **Register (why):** this section.

Do not edit workflow behaviour from this file. Change a deselect only by editing the
matching list under `.github/ci/` with an owner disposition for that node ID.

## Files

| File | What it covers |
|------|----------------|
| `test_bugbot_rules_contract.py` | Contract tests for `.cursor/BUGBOT.md` review rules and the hook-enforced CODE_RULES exemptions. |
| `test_bugteam_code_rules_gate.py` | Exercises the `code_rules_gate.py` CLI in `_shared/pr-loop/scripts/` against a known example module, confirming the gate exits zero on help and non-zero on violations. |
| `test_bugteam_permission_scripts.py` | Verifies the bugteam grant/revoke permission scripts exist, are runnable, and produce expected exit codes. |
| `test_bugteam_preflight.py` | Checks the bugteam preflight script logic. |
| `test_doc_cross_references.py` | Walks Python docstrings and Markdown files for repo-relative path references and confirms each path exists on disk. |
| `test_session_start_refresh.py` | Runs the `.claude/hooks/session_start_refresh.py` SessionStart hook as a subprocess against a sandbox home with fake `npm`/`npx` shims, plus static checks binding the `.claude/settings.json` registration and timeout budget to the hook's constants. |

## Conventions

- Test functions use `should_*` naming to describe behaviour, not `test_*` unless
  the function is a plain `def test_*` (both are collected).
- Tests run against production code paths; no logic is duplicated for the test.
- Do not use `@pytest.mark.skip` or similar skip decorators — a missing dependency
  makes the test fail with a clear error.
