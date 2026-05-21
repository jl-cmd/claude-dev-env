"""Constants for code_rules_enforcer.py.

Extracted from code_rules_enforcer.py to satisfy the constants-location rule.
"""

import re

ALL_PYTHON_EXTENSIONS = {".py"}
ALL_JAVASCRIPT_EXTENSIONS = {".js", ".ts", ".tsx", ".jsx"}
ALL_CODE_EXTENSIONS = ALL_PYTHON_EXTENSIONS | ALL_JAVASCRIPT_EXTENSIONS

ALL_TEST_PATH_PATTERNS = {"test_", "_test.", ".test.", ".spec.", "/tests/", "\\tests\\", "/tests.py", "\\tests.py"}
ALL_HOOK_INFRASTRUCTURE_PATTERNS = {"/.claude/hooks/", "\\.claude\\hooks\\", "\\.claude/hooks/", "/packages/claude-dev-env/hooks/", "\\packages\\claude-dev-env\\hooks\\"}
ALL_WORKFLOW_REGISTRY_PATTERNS = {"/workflow/", "\\workflow\\", "_tab.py", "/states.py", "\\states.py", "/modules.py", "\\modules.py"}
ALL_MIGRATION_PATH_PATTERNS = {"/migrations/", "\\migrations\\"}

ADVISORY_LINE_THRESHOLD_SOFT = 400
ADVISORY_LINE_THRESHOLD_HARD = 1000

ALL_BOOLEAN_NAME_PREFIXES: tuple[str, ...] = ("is_", "has_", "should_", "can_")
UPPER_SNAKE_CONSTANT_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")


TYPE_CHECKING_BLOCK_PATTERN = re.compile(r"^(?P<indent>\s*)if\s+(typing\.)?TYPE_CHECKING\s*:\s*$")
ALL_IMPORT_STATEMENT_PREFIXES: tuple[str, ...] = ("import ", "from ")
NOT_INSIDE_TYPE_CHECKING_BLOCK = -1
TRIPLE_QUOTE_PARITY_DIVISOR = 2
TRIPLE_DOUBLE_QUOTE_DELIMITER = '"""'
TRIPLE_SINGLE_QUOTE_DELIMITER = "'''"
FILE_GLOBAL_UPPER_SNAKE_PATTERN = re.compile(r"^_?[A-Z][A-Z0-9_]*$")

ALL_COLLECTION_TYPE_NAMES: frozenset[str] = frozenset({
    "list", "tuple", "set", "frozenset",
    "Iterable", "Sequence", "Mapping", "MutableMapping", "FrozenSet",
})
ALL_SUBSCRIPT_ONLY_COLLECTION_TYPE_NAMES: frozenset[str] = frozenset({"dict"})
COLLECTION_BY_NAME_PATTERN: re.Pattern[str] = re.compile(r"^[a-z][a-z0-9]*_by_[a-z][a-z0-9_]*$")
ALL_CLI_FILE_PATH_MARKERS: tuple[str, ...] = ("/scripts/", "\\scripts\\", "_cli.py", "/cli.py", "\\cli.py")

LOGGING_FSTRING_PATTERN = re.compile(
    r'\b(?:log_(?:debug|info|warning|error|critical|exception)'
    r'|(?:logger|logging|log)\.(?:debug|info|warning|error|critical|exception))'
    r'\s*\(\s*(?:[rR][fF]|[fF][rR]?)["\']'
)
ALL_BUILTIN_DICT_METHOD_NAMES: frozenset[str] = frozenset({
    "get", "items", "keys", "values", "update", "pop",
    "setdefault", "copy", "clear",
})
ALL_UNION_TYPING_NAMES: frozenset[str] = frozenset({"Optional", "Union"})
ALL_SELF_AND_CLS_PARAMETER_NAMES: frozenset[str] = frozenset({"self", "cls"})
ALL_LOOP_INDEX_LETTER_EXEMPTIONS: frozenset[str] = frozenset({"i", "j", "k", "_"})
EACH_PREFIX = "each_"
BARE_EACH_TOKEN = "each"
INLINE_COLLECTION_MIN_LENGTH = 3
ALL_CAPS_WITH_UNDERSCORE_PATTERN = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$")
DOTTED_SEGMENT_PATTERN = re.compile(r"^\.[a-z][a-z0-9_]*$")
