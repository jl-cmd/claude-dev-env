"""Timing constants for sweep_empty_dirs.

Per the project's configuration conventions, timeouts, delays, and retries
live in dev_env_scripts_constants/timing.py.
"""

DEFAULT_AGE_SECONDS: int = 120
"""Minimum age before an empty directory is eligible for deletion."""

DEFAULT_POLL_INTERVAL: int = 30
"""Seconds between sweep passes in continuous-watch mode."""
