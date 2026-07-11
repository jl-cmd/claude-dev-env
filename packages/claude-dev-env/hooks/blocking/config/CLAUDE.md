# hooks/blocking/config

A Python package that holds shared constants for the verified-commit gate family. Three modules in `blocking/` import from here:

- `verification_verdict_store.py`
- `verified_commit_gate.py`
- `verifier_verdict_minter.py`

## Key files

| File | Contents |
|---|---|
| `__init__.py` | Declares this as a regular package (not a namespace package) so it resolves first on `sys.path` |
| `verified_commit_constants.py` | All tunables for the gate: directory names, regex patterns for detecting verdict paths and obfuscation attempts, timeout values, git subcommand sets, bypass marker, and corrective messages |

## Key constants in `verified_commit_constants.py`

- `VERIFICATION_BYPASS_MARKER` — the `# verify-skip` comment that exempts a single commit/push from the gate
- `MINTING_AGENT_TYPE` — `"code-verifier"`, the agent type whose SubagentStop hook mints verdicts
- `VERDICT_DIRECTORY_NAME` — `"verification"`, the directory under `~/.claude/` that holds verdict JSON files
- `DOCS_ONLY_EXTENSIONS` — extensions (`.md`, `.txt`, images) whose changes are mechanically exempt from the gate
- `CORRECTIVE_MESSAGE` / `VERDICT_DIRECTORY_GUARD_MESSAGE` — user-facing block messages
