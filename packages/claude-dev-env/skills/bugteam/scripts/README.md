# Bugteam utility scripts

Scripts in this directory are **executed** by the lead or teammates. They are not loaded into context as instructions (see Anthropic [Skill authoring best practices — Progressive disclosure](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#progressive-disclosure-patterns)).

| Script | Purpose |
|--------|---------|
| `bugteam_preflight.py` | Run pytest (when configured) and optional `pre-commit` before `/bugteam`. Skill-path thin entry; implementation lives at package shared `_shared/pr-loop/scripts/preflight.py`. |
| `bugteam_fix_hookspath.py` | Auto-remediate a stale local `core.hooksPath` override, set canonical global value, re-run preflight. Skill-path thin entry; implementation lives at package shared `_shared/pr-loop/scripts/fix_hookspath.py`. Invoked by Claude when preflight reports a `core.hooksPath` failure. |
| `bugteam_code_rules_gate.py` | Thin skill-path entry that re-exports shared `_shared/pr-loop/scripts/code_rules_gate.py`. **Not the pre-audit gate of record** — invoke the shared script for live pre-audit (see `reference/audit-and-teammates.md`). |
| `windows_safe_rmtree.py` | Windows-safe recursive directory removal (strips ReadOnly, retries). Standalone helper with unit tests; run-temp teardown is `skills/_shared/pr-loop/scripts/teardown_worktrees.py` under `pr-loop-lifecycle` Close. |
| `probe_code_rules_enforcer_check.py` | Dynamically load `~/.claude/hooks/blocking/code_rules_enforcer.py` and invoke a named check function against a fixture file. Used by the historical Copilot gap-analysis investigation as a verification shape (see `reference/copilot-gap-analysis.md`). |

## `bugteam_preflight.py`

Skill-path thin entry; implementation lives at `_shared/pr-loop/scripts/preflight.py`.

From the repository root:

```bash
python "${CLAUDE_SKILL_DIR}/scripts/bugteam_preflight.py"
```

- Skips pytest when `BUGTEAM_PREFLIGHT_SKIP=1`.
- Skips pytest when `pytest.ini` / `pyproject.toml` exists but no `test_*.py` / `*_test.py` files are found under the repo root.
- Pytest exit code `5` (no tests collected) is treated as success.
- Add `--pre-commit` to run `pre-commit run --all-files` when `.pre-commit-config.yaml` exists.

## `bugteam_fix_hookspath.py`

Skill-path thin entry; implementation lives at `_shared/pr-loop/scripts/fix_hookspath.py`.

From the repository root:

```bash
python "${CLAUDE_SKILL_DIR}/scripts/bugteam_fix_hookspath.py"
```

- Removes any local-scope `core.hooksPath` value that does not end in `hooks/git-hooks`.
- Sets `git config --global core.hooksPath ~/.claude/hooks/git-hooks` when the global value is unset or non-canonical.
- Refuses to run (exit non-zero) when `~/.claude/hooks/git-hooks` does not exist on disk — install via `npx claude-dev-env .` first.
- Idempotent: a second invocation is a clean no-op.
- Re-runs package-shared `preflight.py --no-pytest` and propagates its exit code.

The bugteam SKILL invokes this automatically when preflight stderr indicates a `core.hooksPath` failure, so Claude does not surface the error to the user.

## `bugteam_code_rules_gate.py` (thin skill-path entry)

Skill-path thin entry; re-exports `main` from package-shared `_shared/pr-loop/scripts/code_rules_gate.py`.

**Not the pre-audit gate of record.** The live pre-audit gate is the package-shared script:

```bash
python "${CLAUDE_SKILL_DIR}/../_shared/pr-loop/scripts/code_rules_gate.py" --base origin/<baseRefName>
```

See `reference/audit-and-teammates.md`. Keep this wrap for callers that still invoke the skill-local path.

```bash
python "${CLAUDE_SKILL_DIR}/scripts/bugteam_code_rules_gate.py"
```

Optional explicit files instead of `git diff`:

```bash
python "${CLAUDE_SKILL_DIR}/scripts/bugteam_code_rules_gate.py" path/to/a.py path/to/b.ts
```

Both the wrap and the shared script load `validate_content` from `hooks/blocking/code_rules_enforcer.py` inside `claude-dev-env` (same logic as the PreToolUse hook). Exit `0` = mandatory checks pass on scanned files; exit `1` = violations printed to stderr.
