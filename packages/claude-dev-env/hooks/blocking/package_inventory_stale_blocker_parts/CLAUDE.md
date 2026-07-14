# package_inventory_stale_blocker_parts

The concern modules `package_inventory_stale_blocker.py` wires together to block a
new production file its package inventory omits. The entry hook imports them and
re-exports their surface for the test suite.

## Modules

| File | Purpose |
|---|---|
| `inventory_detection.py` | Surveys a directory's `README.md`/`CLAUDE.md`/`SKILL.md`, collects the filenames they name, and reports whether a maintained inventory omits the file being written |
| `decision.py` | Builds the deny payload naming the omitted file and closing with the retry hint, and emits the decision JSON |
| `__init__.py` | Package marker |

## Subdirectories

| Entry | Description |
|---|---|
| `config/` | The retry hint the deny reason closes with and the inventory-name join separator (`inventory_blocker_constants.py`) |
| `tests/` | pytest suite with one test module per module above |

## Running tests

```bash
python -m pytest packages/claude-dev-env/hooks/blocking/package_inventory_stale_blocker_parts/tests/
```
