# claude_md_orphan_file_blocker_parts

The concern modules `claude_md_orphan_file_blocker.py` wires together to block a
per-directory `CLAUDE.md` that names a file absent from its subtree. The entry
hook imports them and re-exports their surface for the test suite.

## Modules

| File | Purpose |
|---|---|
| `references.py` | Extracts the bare filenames a table cell names and the scripts a fenced run command invokes, honoring the `../` relative-path exemptions |
| `subtree_scan.py` | Resolves the scan root and reports which referenced filenames are absent from it, with a bounded walk plus a direct probe fallback |
| `scan_plan.py` | Builds the Write/Edit/MultiEdit scan plan and collects the orphan filenames the change introduces, excluding pre-existing orphans |
| `decision.py` | Builds the deny payload listing the missing files and closing with the retry hint, and emits the decision JSON |
| `__init__.py` | Package marker |

## Subdirectories

| Entry | Description |
|---|---|
| `config/` | The region-join newline and the retry hint the deny reason closes with (`orphan_blocker_constants.py`) |
| `tests/` | pytest suite with one test module per module above |

## Running tests

```bash
python -m pytest packages/claude-dev-env/hooks/blocking/claude_md_orphan_file_blocker_parts/tests/
```
