"""Constants naming where the system keeps temporary directories."""

from __future__ import annotations

# A run reaches its temp root through any of these, so a walk that stops at
# that boundary checks all four rather than gettempdir() alone. RUNNER_TEMP
# is the hosted-CI case: pytest writes there while gettempdir() stays /tmp.
ALL_SYSTEM_TEMPORARY_ROOT_ENVIRONMENT_VARIABLE_NAMES: frozenset[str] = frozenset(
    {
        "TEMP",
        "TMP",
        "TMPDIR",
        "RUNNER_TEMP",
    }
)
