# dev_env_scripts_constants

Named constants for scripts in `scripts/`. Follows the project convention that timeouts, delays, and retries live in `timing.py`.

## Modules

| File | Constants for |
|---|---|
| `timing.py` | `sweep_empty_dirs.py` — `DEFAULT_AGE_SECONDS` (smallest age before an empty directory is eligible for removal) and `DEFAULT_POLL_INTERVAL` (seconds between sweep passes in continuous-watch mode) |
| `__init__.py` | Empty package marker |

## Convention

Every constant is `UPPER_SNAKE_CASE` with an explicit type annotation and a docstring. Scripts import from here rather than embedding literal values in their bodies.
