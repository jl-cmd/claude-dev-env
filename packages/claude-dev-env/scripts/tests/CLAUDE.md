# scripts/tests

pytest suite for the Python scripts in `scripts/`.

## Test files

| File | Covers |
|---|---|
| `test_setup_project_paths.py` | `setup_project_paths.py` — discovery, filtering, and `project-paths.json` writing |
| `test_setup_project_paths_config.py` | Configuration constants used by `setup_project_paths.py` |
| `test_sweep_empty_dirs.py` | `sweep_empty_dirs.py` — age check, one-shot mode, and continuous-watch behavior |
| `test_sync_to_cursor.py` | `sync_to_cursor/` package — mapping, hashing, manifest, and path resolution |

## Running

```bash
python -m pytest packages/claude-dev-env/scripts/tests/
```
