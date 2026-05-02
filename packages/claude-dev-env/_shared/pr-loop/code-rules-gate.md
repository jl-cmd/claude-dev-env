# CODE_RULES gate

Pre-audit validator run before each AUDIT (and pre-commit when applicable). Wraps `validate_content` from `~/.claude/hooks/blocking/code_rules_enforcer.py`.

## Script location

Canonical: `~/.claude/skills/bugteam/scripts/bugteam_code_rules_gate.py` after install.

Workflows reference it via:
- bugteam: `${CLAUDE_SKILL_DIR}/scripts/bugteam_code_rules_gate.py`
- qbug, pr-converge, monitor-many: `${CLAUDE_SKILL_DIR}/../bugteam/scripts/bugteam_code_rules_gate.py`

Cross-skill path traversal works because all four skills install as flat top-level dirs under `~/.claude/skills/`.

## Invocation

Default mode (full PR diff against base):
```bash
python "<gate_script>" --base origin/<base_branch>
```

Staged mode (pre-commit subset):
```bash
python "<gate_script>" --staged
```

Path-scoped mode:
```bash
python "<gate_script>" --base origin/<base_branch> --only-under <prefix> [--only-under <other_prefix>]
```

## Exit codes

- `0` — no violations on changed lines (advisories on touched-but-unchanged lines may still print)
- `1` — at least one blocking violation on changed lines; halt
- `2` — gate execution error (missing enforcer, git failure, malformed diff)

## Workflow integration

- **bugteam:** before every AUDIT in Step 3 of the loop. Non-zero → spawn clean-coder for standards fix; loop until exit 0 or 5 consecutive gate failures → `error: code rules gate failed pre-audit`.
- **qbug:** before every AUDIT inside the subagent's loop. Three consecutive failures → `error: code rules gate failed pre-audit`.
- **pr-converge:** before every push in the Fix protocol. Halt on non-zero, fix violations, re-run.
- **monitor-many:** before every commit during the fix loop. Halt on non-zero, fix violations, re-run.

## Coverage

- File-global UPPER_SNAKE constants (must live in `config/` outside exempt path families)
- Magic values in production function bodies (literals other than 0, 1, -1)
- Imports outside top of module
- New comments in production code (existing comments preserved untouched)
- File-global constants used by fewer than 2 functions/methods
- Logging format-arg violations
- Database column-name string magic (snake_case strings as first element of 2-tuples in function bodies)
- Public-wrapper-drops-optional-kwargs of same-file delegates

Test files (`test_*.py`, `*_test.py`, `*.spec.*`, `conftest.py`, paths under `/tests/`) are exempt from comment, magic-value, and constants-location rules.

## Halt-fix-rerun protocol

When the gate exits non-zero:
1. Capture stderr (gate prints `<file>: Line <N>: <issue>` per violation)
2. Group violations by file
3. Apply fixes in the smallest change set (extract constants to `config/`, rename collection params with `all_` prefix, replace literals with named constants, etc.)
4. Re-run the gate with the same arguments
5. Cap at 5 consecutive failures (bugteam, monitor-many) or 3 (qbug); on cap exceeded, exit `error`
