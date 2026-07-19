"""Environment variable names used when ruff emits plain diagnostics.

The PreToolUse gate parses ``path:line:col:`` prefixes. Forcing ``NO_COLOR`` and
clearing ``FORCE_COLOR`` keeps ANSI codes out of those fields so baseline
scoping can locate each finding.
"""

__all__ = [
    "FORCE_COLOR_ENVIRONMENT_VARIABLE_NAME",
    "NO_COLOR_ENABLED_VALUE",
    "NO_COLOR_ENVIRONMENT_VARIABLE_NAME",
]

NO_COLOR_ENVIRONMENT_VARIABLE_NAME: str = "NO_COLOR"
FORCE_COLOR_ENVIRONMENT_VARIABLE_NAME: str = "FORCE_COLOR"
NO_COLOR_ENABLED_VALUE: str = "1"
