"""Configuration constants for the hook_prose_detector_consistency PreToolUse hook."""

WRITE_TOOL_NAME: str = "Write"
EDIT_TOOL_NAME: str = "Edit"

HOOK_MODULE_PATH_SEGMENT: str = "/hooks/"
PYTHON_FILE_SUFFIX: str = ".py"
CONSTANTS_MODULE_SUFFIX: str = "_constants.py"
TEST_MODULE_PREFIX: str = "test_"

PATH_SEPARATOR_CLASS_PATTERN: str = (
    r"\[[^\]/]*\\\\[^\]/]*\]|\[[^\]]*\\\\?/[^\]]*\]|\[[^\]]*/\\\\?[^\]]*\]"
)
OVERSTATED_OUTPUT_KEY_PHRASE_PATTERN: str = r"output[- ]key\s+segment"

CORRECTIVE_MESSAGE: str = (
    "BLOCKED [hook-prose-detector-consistency]: Align the hook module's user-facing "
    "prose with its detector. The detector matches a per-iteration path segment "
    "next to a path separator (`\\` or `/`). Replace the phrase 'output-key segment' "
    "with 'per-iteration path segment' in the docstring lead narrative and "
    "CORRECTIVE_MESSAGE. Keep both surfaces aligned with the regex contract."
)
