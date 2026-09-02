"""Constants for hook_timing_harness.py.

Extracted to satisfy the constants-location rule: production constants outside
``config/`` move here rather than sitting at module scope in the harness.
"""

DEFAULT_RUN_COUNT = 7
P50_FRACTION = 0.50
P95_FRACTION = 0.95
DEFAULT_TARGET_RELATIVE_PATH = "hooks/blocking/code_rules_shared.py"
SUBPROCESS_TIMEOUT_SECONDS = 60.0
ALL_WRITE_EDIT_MATCHER_PATTERNS = frozenset(
    {"Write|Edit", "Write|Edit|MultiEdit", "Write|Edit|MultiEdit|apply_patch"}
)
ALL_TIMED_EVENT_NAMES = ("PreToolUse", "PostToolUse")
RUN_ALL_VALIDATORS_LABEL = "run_all_validators"
CLAUDE_PLUGIN_ROOT_PLACEHOLDER = "${CLAUDE_PLUGIN_ROOT}"
PARENT_LEVELS_TO_PACKAGE_ROOT = 2
