# gate_skip_token

The per-session skip-token store the gate hooks read to escalate a deny to a
human permission prompt. When a gate denies an edit and the user approves a
refactor deadlock, the agent records a token bound to the write target and the
sha256 of the proposed content. On the retry write, the gate reads the token and,
under the default permission mode with a subset of the on-disk findings, emits an
"ask" and consumes the token. A token never carries a new violation past, and the
human click on the "ask" prompt is the grant.

## Modules

| File | Purpose |
|---|---|
| `records.py` | Hash the proposed content, record, check, and consume the per-session skip tokens, and decide whether a deny may escalate to an ask; a missing or corrupt store reads as no tokens |
| `__init__.py` | Package marker |

## Subdirectories

| Entry | Description |
|---|---|
| `config/` | The token-file name shape, the freshness window, the list key, the token field names, and the default permission mode (`gate_skip_token_constants.py`) |
| `tests/` | pytest suite for the records store |

## Running tests

```bash
python -m pytest packages/claude-dev-env/hooks/blocking/gate_skip_token/tests/
```
