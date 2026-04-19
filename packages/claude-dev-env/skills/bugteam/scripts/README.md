# Bugteam utility scripts

Scripts in this directory are **executed** by the lead or teammates. They are not loaded into context as instructions (see Anthropic [Skill authoring best practices — Progressive disclosure](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#progressive-disclosure-patterns)).

| Script | Purpose |
|--------|---------|
| `bugteam_preflight.py` | Run pytest (when configured) and optional `pre-commit` before `/bugteam`. |
| `bugteam_code_rules_gate.py` | Run `validate_content` from `code-rules-enforcer.py` on PR-scoped files (`git diff` vs merge-base). Exit `1` if any mandatory rule fails. Invoked **before each audit**; the fixer clears it before the auditor runs. |
| `grant_project_claude_permissions.py` | Idempotent grant of Edit/Write/Read on `cwd/.claude/**` into `~/.claude/settings.json`. |
| `revoke_project_claude_permissions.py` | Removes the matching grant entries from `~/.claude/settings.json`. |
| `test_claude_permissions_common.py` | Pytest module for path normalization and glob-metacharacter guards in `_claude_permissions_common.py`. |
| `_claude_permissions_common.py` | Shared helpers for the grant/revoke scripts (atomic JSON writes, settings sections). |

## `bugteam_preflight.py`

From the repository root:

```bash
python "${CLAUDE_SKILL_DIR}/scripts/bugteam_preflight.py"
```

- Skips pytest when `BUGTEAM_PREFLIGHT_SKIP=1`.
- Skips pytest when `pytest.ini` / `pyproject.toml` exists but no `test_*.py` / `*_test.py` files are found under the repo root.
- Pytest exit code `5` (no tests collected) is treated as success.
- Add `--pre-commit` to run `pre-commit run --all-files` when `.pre-commit-config.yaml` exists.

## `bugteam_code_rules_gate.py`

From the repository root (same merge-base rules as the PR head vs base — default `--base origin/main`):

```bash
python "${CLAUDE_SKILL_DIR}/scripts/bugteam_code_rules_gate.py"
```

Optional explicit files instead of `git diff`:

```bash
python "${CLAUDE_SKILL_DIR}/scripts/bugteam_code_rules_gate.py" path/to/a.py path/to/b.ts
```

This loads `validate_content` from `hooks/blocking/code-rules-enforcer.py` inside `claude-dev-env` (same logic as the PreToolUse hook). Exit `0` = mandatory checks pass on scanned files; exit `1` = violations printed to stderr.
