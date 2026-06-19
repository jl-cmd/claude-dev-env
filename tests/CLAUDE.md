# tests/

Root-level Python test suite covering repo-level scripts, contracts, and cross-file integrity.

## Purpose

Holds tests for the scripts in `scripts/`, the `.github/scripts/` listener, the
`AGENTS.md`/`BUGBOT.md` rules contract, and cross-repo doc integrity checks. These
tests are separate from the hook tests (which live beside their hooks under
`packages/claude-dev-env/hooks/`) and from the JS installer tests
(`packages/claude-dev-env/bin/*.test.mjs`).

Run the full suite from the repo root:

```bash
python -m pytest
```

Or target a single file:

```bash
python -m pytest tests/test_fan_out_dispatch.py
```

`pytest.ini` at the repo root sets `--import-mode=importlib`, adds `.` and
`.github/scripts` to `pythonpath`, and collects both `test_*` and `should_*` functions.

## Files

| File | What it covers |
|------|----------------|
| `test_fan_out_dispatch.py` | Unit specs for `scripts/fan_out_dispatch.py`: repo filtering (`is_target_repo`), dispatch retry logic, polling, exit-code computation, and summary formatting. |
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
