"""Timing constants for sweep_empty_dirs, the grok batch launcher, and code-review.

Per the project's configuration conventions, timeouts, delays, and retries
live in dev_env_scripts_constants/timing.py.
"""

DEFAULT_AGE_SECONDS: int = 120
"""Minimum age before an empty directory is eligible for deletion."""

DEFAULT_POLL_INTERVAL: int = 30
"""Seconds between sweep passes in continuous-watch mode."""

WORKER_STAGGER_SECONDS: int = 15
"""Seconds between staggered headless grok worker process starts in a batch."""

DEFAULT_CODE_REVIEW_TIMEOUT_SECONDS: int = 600
"""Default timeout applied to one headless `/code-review` chain invocation, in seconds."""
