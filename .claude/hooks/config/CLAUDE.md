# .claude/hooks/config

Constants for the repo-committed hooks in the parent directory.

## Key files

| File | Role |
|---|---|
| `__init__.py` | Declares this as a regular package (not a namespace package) so it wins `config` resolution on `sys.path` over any other `config` package. |
| `session_start_refresh_constants.py` | Package name, manifest file name, the config-dir and remote-session variable names, and the probe and install timeouts for the session refresh hook. |
