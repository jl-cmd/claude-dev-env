# hooks/blocking/config

A Python package that holds shared constants for blocking hooks. Verified-commit gate modules and opinionated prose-style gates import from here.

## Key files

| File | Contents |
|---|---|
| `__init__.py` | Declares this as a regular package (not a namespace package) so it resolves first on `sys.path` |
| `code_review_enforcement_constants.py` | Stamp and effort tunables for the code-review enforcement gates |
| `prose_style_enforcement_constants.py` | `CLAUDE_PROSE_STYLE_ENFORCEMENT` opt-in (default off) for opinionated prose gates |
| `verified_commit_constants.py` | All tunables for the gate: directory names, regex patterns for detecting verdict paths and obfuscation attempts, timeout values, git subcommand sets, bypass marker, and corrective messages |
| `verified_commit_context_constants.py` | `VERIFY_SKIP_ADDITIONAL_CONTEXT`, the ``# verify-skip`` usage rule the gate attaches to a deny payload's `additionalContext` |
| `verified_commit_gate_output_constants.py` | `PRE_TOOL_USE_HOOK_EVENT_NAME` and `DENY_PERMISSION_DECISION` (the deny payload's event name and decision string), `GATE_HOOK_MODULE_NAME` (the gate's own module name for block logging), and `REGEX_ALTERNATION_SEPARATOR` (the `\|` join for the directory-change verb alternation in `gated_invocations.py`) |

## Key constants in `verified_commit_constants.py`

- `VERIFICATION_BYPASS_MARKER` — the `# verify-skip` comment that exempts a single commit/push from the gate
- `MINTING_AGENT_TYPE` — `"code-verifier"`, the agent type whose SubagentStop hook mints verdicts
- `VERDICT_DIRECTORY_NAME` — `"verification"`, the directory under `~/.claude/` that holds verdict JSON files
- `DOCS_ONLY_EXTENSIONS` — extensions (`.md`, `.txt`, images) whose changes are mechanically exempt from the gate
- `CORRECTIVE_MESSAGE` / `VERDICT_DIRECTORY_GUARD_MESSAGE` — user-facing block messages
