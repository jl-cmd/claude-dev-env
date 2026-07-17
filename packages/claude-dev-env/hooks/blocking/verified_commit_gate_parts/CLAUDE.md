# verified_commit_gate_parts

The concern modules `verified_commit_gate.py` wires together to run the
verified-commit gate. Each module owns one concern; the entry hook imports
them and re-exports their surface for the test suite.

## Modules

| File | Purpose |
|---|---|
| `command_tokenization.py` | Quote-aware tokenizing of a shell command: line-continuation collapse, quoted-span detection, and deciding whether a `git` word is a real invocation |
| `directory_resolution.py` | Resolves the active directory a `cd`/`pushd` verb leaves the shell in, and reads a directory-change verb's destination |
| `gated_invocations.py` | Finds every gated `git commit`/`git push` in a command and the directory each one targets |
| `deny_reason.py` | Decides whether a commit/push in a directory needs a passing verdict |
| `deny_payload.py` | Builds the PreToolUse deny payload, including the verify-skip context that goes with it |
| `__init__.py` | Package marker |

## Subdirectory

| Entry | Description |
|---|---|
| `tests/` | pytest suite with one test module per module above |

## Running tests

```bash
python -m pytest packages/claude-dev-env/hooks/blocking/verified_commit_gate_parts/tests/
```
