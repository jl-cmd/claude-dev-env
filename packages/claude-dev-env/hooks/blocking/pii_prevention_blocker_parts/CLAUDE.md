# pii_prevention_blocker_parts

The concern modules `pii_prevention_blocker.py` wires together. The entry hook
imports them and re-exports their surface for the test suite.

## Modules

| File | Purpose |
|---|---|
| `repository_exemption.py` | Resolves a commit's origin owner/repo slug and decides whether the repository skips the staged PII scan |
| `repository_resolution.py` | Reads the repository a commit command targets — composing multiple `-C` values and a leading `cd`/`pushd` — and builds the deny reason naming the path when the repository root does not resolve |
| `__init__.py` | Package marker |

## Subdirectories

| Entry | Description |
|---|---|
| `config/` | The repository-resolution deny-message template and the session-cwd label (`repository_resolution_constants.py`) |

## Running tests

```bash
python -m pytest packages/claude-dev-env/hooks/blocking/tests/
```
