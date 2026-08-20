"""Configuration constants for the probe_code_rules_enforcer_check script."""

from pathlib import Path

DEFAULT_REPORTED_PATH: str = "fixture.py"
EXIT_CODE_USAGE_ERROR: int = 2
MINIMUM_ARGUMENT_COUNT: int = 3
MAXIMUM_ARGUMENT_COUNT: int = 4
ENFORCER_RELATIVE_PATH: Path = (
    Path(".claude") / "hooks" / "blocking" / "code_rules_enforcer.py"
)
ENFORCER_MODULE_NAME: str = "code_rules_enforcer"
