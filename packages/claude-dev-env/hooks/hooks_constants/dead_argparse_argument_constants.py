"""Constants for the dead argparse-argument detector in ``code_rules_enforcer``.

Lives under the hooks-tree ``hooks_constants`` package so module-level
UPPER_SNAKE constants satisfy the CODE_RULES "constants live in config"
requirement and share a home with the other hook-tree configuration.
"""

ADD_ARGUMENT_METHOD_NAME: str = "add_argument"
ALL_PARSE_METHOD_NAMES: frozenset[str] = frozenset({"parse_args", "parse_known_args"})
DEST_KEYWORD_NAME: str = "dest"
ACTION_KEYWORD_NAME: str = "action"
ALL_SUPPRESSED_ACTION_NAMES: frozenset[str] = frozenset({"help", "version"})
GETATTR_FUNCTION_NAME: str = "getattr"
GETATTR_NAME_ARGUMENT_MINIMUM: int = 2
ATTRGETTER_FUNCTION_NAME: str = "attrgetter"
VARS_FUNCTION_NAME: str = "vars"
NAMESPACE_DICT_ATTRIBUTE_NAME: str = "__dict__"
OPTION_PREFIX: str = "-"
LONG_OPTION_PREFIX: str = "--"
DEST_WORD_SEPARATOR: str = "-"
DEST_WORD_JOINER: str = "_"
EXPORTED_NAMES_ATTRIBUTE: str = "__all__"
MAX_DEAD_ARGPARSE_ARGUMENT_ISSUES: int = 25
DEAD_ARGPARSE_ARGUMENT_GUIDANCE: str = (
    "optional CLI flag whose parsed value is never read in this file - remove the"
    " add_argument call (argparse silently accepts an unused flag), or read the"
    " parsed value where it is needed (CODE_RULES §9.8)"
)
