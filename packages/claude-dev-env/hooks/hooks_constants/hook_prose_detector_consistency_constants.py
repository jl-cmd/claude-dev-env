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
    "BLOCKED [hook-prose-detector-consistency]: A hook module's user-facing prose "
    "(its docstring lead narrative or CORRECTIVE_MESSAGE) claims the hook blocks an "
    "'output-key segment', but the module's detector keys off a path separator only "
    "(it matches a token next to `\\` or `/`). A quoted structured-output key alone "
    "never triggers a block, so the prose overstates the contract: an author whose "
    "only per-iteration token is an output key would never see this message, and an "
    "author who does see it is told an output key caused a block it cannot cause.\n\n"
    "Describe only the trigger the detector implements: a per-iteration path segment "
    "next to a path separator. Drop 'or output-key segment' (or restate it as 'a "
    "per-iteration path segment') so the message and docstring match what the regex "
    "catches.\n\n"
    "Invariant: a hook's docstring and corrective message describe exactly the shapes "
    "its detector flags -- no broader trigger surface than the regex enforces."
)
