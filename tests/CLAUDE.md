# tests/

Root-level Python test suite covering repo-level scripts, contracts, and cross-file integrity.

## Purpose

Holds tests for the scripts in `scripts/`, the `.github/scripts/` listener, the
`AGENTS.md`/`BUGBOT.md` rules contract, and cross-repo doc integrity checks. These
tests are separate from the hook tests (which live beside their hooks under
`packages/claude-dev-env/hooks/`) and from the JS installer tests
(`packages/claude-dev-env/bin/*.test.mjs`).

## Supported run commands

Two Python suites share the root `pytest.ini`. Run them as **separate** sessions so the
two `config` packages (repo-root `config/` and
`packages/claude-dev-env/hooks/blocking/config/`) do not collide during collection.

| Scope | Command |
|-------|---------|
| Root suite only (`tests/`) | `python -m pytest tests/` |
| Package suite (`packages/claude-dev-env`) | `python -m pytest packages/claude-dev-env` |
| Default bare invocation | `python -m pytest` |
| Root suite in parallel | `python -m pytest tests/ -n auto` |
| Package suite in parallel | `python -m pytest packages/claude-dev-env -n auto` |
| One Python test file | `python -m pytest tests/test_fan_out_dispatch.py` |
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

`pytest.ini` at the repo root sets `--import-mode=importlib`, adds `.` and
`.github/scripts` to `pythonpath`, scopes default collection to `tests/` via
`testpaths`, and collects both `test_*` and `should_*` functions.

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
| Native git hooks / `verified_commit_gate` | Tests run in CI | Production hook surface is local (installed under the user Claude config). The unit tests run in the package suite. |
| Live Neon logging | Tests run in CI | Production logging needs Neon credentials. Tests mock the boundary and run in CI. |

### Deselection provenance

- **Lists (what):** `.github/ci/*.txt` — node IDs CI passes to `--deselect` (and, for Windows-semantics, the windows-latest select set).
- **Register (why):** this section.

Do not edit workflow behaviour from this file. Change a deselect only by editing the
matching list under `.github/ci/` with an owner disposition for that node ID.

## Files

| File | What it covers |
|------|----------------|
| `test_fan_out_dispatch.py` | Unit specs for `scripts/fan_out_dispatch.py`: repo filtering (`is_target_repo`), dispatch retry logic, polling, exit-code computation, and summary formatting. |
| `test_fan_out_conclusion_report.py` | Unit specs for `scripts/fan_out_conclusion_report.py`: private-target redaction, dispatch-correlation filtering by run `created_at`, the 404-to-`listener-missing` mapping, and the `no-matching-run` fallback. |
| `test_local_identity.py` | Unit specs for `config/local_identity.py`: owner-scope resolution from the environment, a git-ignored local file, and the placeholder default, plus token environment-variable naming. |
| `test_sync_ai_rules.py` | Specs for `.github/scripts/sync_ai_rules.py`: destination path logic, canonical-repo behaviour (writes `.cursor/BUGBOT.md` only), drift detection, and the listener's write logic against a real temporary git repo. |
| `test_bugbot_rules_contract.py` | Contract test: verifies that `AGENTS.md` and `.cursor/BUGBOT.md` list the same CODE_RULES exemptions as `code_rules_enforcer.py`. Keeps the LLM review docs in step with the hook-enforced gate. |
| `test_bugteam_code_rules_gate.py` | Exercises the `code_rules_gate.py` CLI in `_shared/pr-loop/scripts/` against a known example module, confirming the gate exits zero on help and non-zero on violations. |
| `test_bugteam_permission_scripts.py` | Verifies the bugteam grant/revoke permission scripts exist, are runnable, and produce expected exit codes. |
| `test_bugteam_preflight.py` | Checks the bugteam preflight script logic. |
| `test_doc_cross_references.py` | Walks Python docstrings and Markdown files for repo-relative path references and confirms each path exists on disk. |

## Fixtures

`fixtures/sync-ai-rules/` holds a `source_body.md` file used as the canonical source
body in `test_sync_ai_rules.py` integration tests.

## Conventions

- Test functions use `should_*` naming to describe behaviour, not `test_*` unless
  the function is a plain `def test_*` (both are collected).
- Tests run against production code paths; no logic is duplicated for the test.
- Do not use `@pytest.mark.skip` or similar skip decorators — a missing dependency
  makes the test fail with a clear error.
