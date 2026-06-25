"""Constants for code_rules_enforcer.py.

Extracted from code_rules_enforcer.py to satisfy the constants-location rule.
"""

import re
import tokenize

ALL_PYTHON_TOKENIZE_FAILURE_EXCEPTIONS: tuple[type[BaseException], ...] = (
    tokenize.TokenError,
    IndentationError,
    SyntaxError,
)

ALL_PYTHON_EXTENSIONS = {".py"}
ALL_JAVASCRIPT_EXTENSIONS = {".js", ".ts", ".tsx", ".jsx"}
ALL_CODE_EXTENSIONS = ALL_PYTHON_EXTENSIONS | ALL_JAVASCRIPT_EXTENSIONS

ALL_TEST_PATH_PATTERNS = {"test_", "_test.", ".test.", ".spec.", "/tests/", "\\tests\\", "/tests.py", "\\tests.py"}
STRICT_TEST_FILE_BASENAME_PATTERN: re.Pattern[str] = re.compile(
    r"^(test_.*|.*_test|.*\.test|.*\.spec)\.[^.]+$|^conftest\.py$"
)
ALL_STRICT_TEST_DIRECTORY_SEGMENTS: tuple[str, ...] = ("/tests/",)
ALL_ROOT_ANCHORED_EPHEMERAL_DIRECTORIES: tuple[str, str] = ("/tmp", "/temp")
CLAUDE_JOB_DIR_ENVIRONMENT_VARIABLE_NAME: str = "CLAUDE_JOB_DIR"
CLAUDE_JOB_DIR_SCRATCH_SUBDIRECTORY: str = "tmp"
EPHEMERAL_EXEMPT_DISABLE_ENVIRONMENT_VARIABLE_NAME: str = "CLAUDE_CODE_RULES_DISABLE_EPHEMERAL_EXEMPT"
ALL_EPHEMERAL_EXEMPT_DISABLE_TRUTHY_VALUES: frozenset[str] = frozenset({"1", "true", "yes", "on"})
LEADING_DRIVE_LETTER_PATTERN: re.Pattern[str] = re.compile(r"^[a-z]:")
ALL_HOOK_INFRASTRUCTURE_PATTERNS = {"/.claude/hooks/", "\\.claude\\hooks\\", "\\.claude/hooks/", "/packages/claude-dev-env/hooks/", "\\packages\\claude-dev-env\\hooks\\"}
ALL_WORKFLOW_REGISTRY_PATTERNS = {"/workflow/", "\\workflow\\", "_tab.py", "/states.py", "\\states.py", "/modules.py", "\\modules.py"}
ALL_MIGRATION_PATH_PATTERNS = {"/migrations/", "\\migrations\\"}

ADVISORY_LINE_THRESHOLD_SOFT = 400
ADVISORY_LINE_THRESHOLD_HARD = 1000

DENY_REASON_ISSUE_PREVIEW_COUNT = 10

ALL_BOOLEAN_NAME_PREFIXES: tuple[str, ...] = ("is_", "has_", "should_", "can_", "was_", "did_")
UPPER_SNAKE_CONSTANT_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")

ALL_MUST_CHECK_RETURN_FUNCTION_NAMES: frozenset[str] = frozenset({"find_and_click", "write_outcome"})

DOCSTRING_ARG_ENTRY_PATTERN: re.Pattern[str] = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*[:(]")
DOCSTRING_PLURAL_FAMILY_STOP_PATTERN: re.Pattern[str] = re.compile(
    r"\bthe\s+([a-z][a-z]+)\s+stops\b"
)
INLINE_CODE_TOKEN_PATTERN: re.Pattern[str] = re.compile(r"``?(\.?[A-Za-z_][A-Za-z0-9_.]*)``?")
IDENTIFIER_SHAPED_TUPLE_MEMBER_PATTERN: re.Pattern[str] = re.compile(r"^\.?[A-Za-z_][A-Za-z0-9_]*$")
ALL_DOCSTRING_ARGS_SECTION_HEADERS: tuple[str, ...] = ("Args:", "Arguments:")
ALL_DOCSTRING_TERMINATING_SECTION_HEADERS: frozenset[str] = frozenset({
    "Returns:",
    "Yields:",
    "Raises:",
    "Examples:",
    "Example:",
    "Note:",
    "Notes:",
})


TYPE_CHECKING_BLOCK_PATTERN = re.compile(r"^(?P<indent>\s*)if\s+(typing\.)?TYPE_CHECKING\s*:\s*$")
ALL_IMPORT_STATEMENT_PREFIXES: tuple[str, ...] = ("import ", "from ")
ALL_TOKEN_ANCHORED_EXEMPT_COMMENT_BODIES: tuple[str, ...] = (
    "noqa",
    "pylint:",
    "pragma:",
)
ALL_TOKEN_ANCHORED_DIRECTIVE_BOUNDARY_CHARACTERS: frozenset[str] = frozenset({":"})
ALL_FREE_FORM_EXEMPT_COMMENT_BODIES: tuple[str, ...] = (
    "type:",
    "TODO",
    "FIXME",
    "HACK",
    "XXX",
)
CHAINED_INLINE_COMMENT_PATTERN = re.compile(r"#")
ALL_JAVASCRIPT_EXEMPT_COMMENT_PREFIXES: tuple[str, ...] = (
    "// @ts-",
    "// eslint-",
    "// prettier-",
    "/// ",
    "// TODO",
    "// FIXME",
    "// HACK",
    "// XXX",
)
ALL_JAVASCRIPT_EXEMPT_INLINE_COMMENT_PREFIXES: tuple[str, ...] = (
    "TODO",
    "FIXME",
    "HACK",
    "XXX",
)
MAX_COMMENT_ISSUES = 3
NOT_INSIDE_TYPE_CHECKING_BLOCK = -1
TRIPLE_QUOTE_PARITY_DIVISOR = 2
TRIPLE_DOUBLE_QUOTE_DELIMITER = '"""'
TRIPLE_SINGLE_QUOTE_DELIMITER = "'''"
MAX_MAGIC_VALUE_ISSUES = 3
STRING_LITERAL_QUOTE_PAIR_LENGTH = 2
MINIMUM_FSTRING_LITERAL_LENGTH = 2
MAX_FSTRING_STRUCTURAL_LITERAL_ISSUES = 100
ALL_ALLOWED_MAGIC_NUMBER_LITERALS: frozenset[str] = frozenset({"0", "1", "-1", "0.0", "1.0"})
ALL_NON_MAGIC_FSTRING_STRIPPED_VALUES: frozenset[str] = frozenset({"", "True", "False"})
DUPLICATED_FORMAT_MINIMUM_REPETITION_COUNT = 3
DUPLICATED_FORMAT_MINIMUM_LITERAL_CHARACTER_COUNT = 5
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
LOGGING_PRINTF_TOKEN_PATTERN: re.Pattern[str] = re.compile(
    r"(?<!%)%[#0\- +]?[0-9.*]*[sdrixfgeEcoX](?![a-zA-Z])"
)
MINIMUM_FORMAT_LOGGER_ARGUMENT_COUNT = 2
ALL_BUILTIN_DICT_METHOD_NAMES: frozenset[str] = frozenset({
    "get", "items", "keys", "values", "update", "pop",
    "setdefault", "copy", "clear",
})
ALL_UNION_TYPING_NAMES: frozenset[str] = frozenset({"Optional", "Union"})
ALL_SELF_AND_CLS_PARAMETER_NAMES: frozenset[str] = frozenset({"self", "cls"})
ANNOTATION_BY_PYTEST_FIXTURE: dict[str, str] = {
    "tmp_path": "Path",
    "tmp_path_factory": "pytest.TempPathFactory",
    "monkeypatch": "pytest.MonkeyPatch",
    "capsys": "pytest.CaptureFixture[str]",
    "capfd": "pytest.CaptureFixture[str]",
    "caplog": "pytest.LogCaptureFixture",
    "request": "pytest.FixtureRequest",
}
KNOWN_PYTEST_FIXTURE_ANNOTATION_MESSAGE_SUFFIX: str = (
    "known pytest fixture parameter must carry its single documented type "
    "(CODE_RULES §6; pytest builtin fixture reference "
    "https://docs.pytest.org/en/stable/reference/fixtures.html)"
)
UNUSED_PYTEST_FIXTURE_PARAMETER_MESSAGE_SUFFIX: str = (
    "known pytest fixture parameter is declared but never referenced in the "
    "function body; pytest still materializes its setup, so drop the unused "
    "parameter (pytest builtin fixture reference "
    "https://docs.pytest.org/en/stable/reference/fixtures.html)"
)
ALL_LOOP_INDEX_LETTER_EXEMPTIONS: frozenset[str] = frozenset({"i", "j", "k", "_"})
EACH_PREFIX = "each_"
BARE_EACH_TOKEN = "each"
INLINE_COLLECTION_MIN_LENGTH = 3
ALL_CAPS_WITH_UNDERSCORE_PATTERN = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$")
DOTTED_SEGMENT_PATTERN = re.compile(r"^\.[a-z][a-z0-9_]*$")

ALL_DIFF_CHANGED_OPCODE_TAGS: tuple[str, str] = ("replace", "insert")

FUNCTION_LENGTH_BLOCKING_THRESHOLD: int = 60
FUNCTION_LENGTH_BLOCKING_MESSAGE_SUFFIX: str = (
    "exceeds blocking threshold - split into helpers (small functions: Robert C. "
    "Martin, Clean Code Ch. 3 'Functions'; Google Python Style Guide ~40-line "
    "function review hint)"
)

PRECHECK_USAGE_EXIT_CODE: int = 2
PRECHECK_USAGE_MESSAGE: str = (
    "usage: code_rules_enforcer.py --check <candidate> [--as <target>]\n"
)

BANNED_NOUN_SPAN_FRAGMENT_TEMPLATE: str = (
    "(binding span at line {definition_line}, spanning {line_span} lines)"
)

ALL_PYTEST_FILESYSTEM_ISOLATION_FIXTURE_NAMES: frozenset[str] = frozenset({
    "monkeypatch",
})
PYTEST_USEFIXTURES_MARKER_NAME: str = "usefixtures"
PYTEST_TEST_CLASS_NAME_PREFIX: str = "Test"
ALL_HOME_DIRECTORY_ENV_VAR_NAMES: frozenset[str] = frozenset({
    "HOME",
    "USERPROFILE",
    "XDG_CONFIG_HOME",
    "XDG_DATA_HOME",
    "TMPDIR",
    "TEMP",
    "TMP",
})
ALL_FILESYSTEM_HOME_PROBE_DOTTED_NAMES: frozenset[str] = frozenset({
    "Path.home",
    "pathlib.Path.home",
    "tempfile.gettempdir",
    "tempfile.gettempdirb",
    "tempfile.gettempprefix",
    "tempfile.mkstemp",
    "tempfile.mkdtemp",
    "tempfile.mktemp",
    "tempfile.NamedTemporaryFile",
    "tempfile.TemporaryFile",
    "tempfile.TemporaryDirectory",
    "tempfile.SpooledTemporaryFile",
})
ALL_DIR_ACCEPTING_TEMPFILE_FACTORY_DOTTED_NAMES: frozenset[str] = frozenset({
    "tempfile.mkstemp",
    "tempfile.mkdtemp",
    "tempfile.mktemp",
    "tempfile.NamedTemporaryFile",
    "tempfile.TemporaryFile",
    "tempfile.TemporaryDirectory",
    "tempfile.SpooledTemporaryFile",
})
TEMPFILE_FACTORY_ISOLATION_DIRECTORY_KEYWORD: str = "dir"
ALL_SHARED_TEMP_SOURCE_PROBE_DOTTED_NAMES: frozenset[str] = frozenset({
    "tempfile.gettempdir",
    "tempfile.gettempdirb",
    "tempfile.gettempprefix",
})
EXPANDVARS_DOTTED_NAME: str = "os.path.expandvars"
EXPANDUSER_DOTTED_NAME: str = "os.path.expanduser"
ALL_PATHLIB_STATIC_EXPANDUSER_DOTTED_NAMES: frozenset[str] = frozenset({
    "Path.expanduser",
    "pathlib.Path.expanduser",
})
PATHLIB_EXPANDUSER_METHOD_NAME: str = "expanduser"
ALL_PATHLIB_PATH_CONSTRUCTOR_CANONICAL_NAMES: frozenset[str] = frozenset({
    "Path",
    "pathlib.Path",
})
ALL_PROBE_ALIASABLE_CANONICAL_PREFIXES: frozenset[str] = frozenset({
    "os",
    "os.path",
    "os.environ",
    "os.getenv",
    "pathlib",
    "pathlib.Path",
    "Path",
    "tempfile",
})
HOME_DIRECTORY_TILDE_PREFIX: str = "~"
ENVIRONMENT_VARIABLE_REFERENCE_PATTERN: re.Pattern[str] = re.compile(
    r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?"
)
WINDOWS_PERCENT_VARIABLE_REFERENCE_PATTERN: re.Pattern[str] = re.compile(
    r"%([A-Za-z_][A-Za-z0-9_]*)%"
)
OS_GETENV_DOTTED_NAME: str = "os.getenv"
OS_ENVIRON_GET_DOTTED_NAME: str = "os.environ.get"
OS_ENVIRON_DOTTED_NAME: str = "os.environ"
ENVIRON_GET_METHOD_NAME: str = "get"
ALL_ENVIRONMENT_GETTER_DOTTED_NAMES: frozenset[str] = frozenset({
    OS_GETENV_DOTTED_NAME,
    OS_ENVIRON_GET_DOTTED_NAME,
})
ALL_PROBE_RELEVANT_MODULE_CANONICAL_NAMES: frozenset[str] = frozenset({
    "os",
    "os.path",
    "pathlib",
    "tempfile",
})
ALL_CANONICAL_DOTTED_NAMES_BY_BARE_IMPORT: dict[tuple[str, str], str] = {
    ("os.path", "expanduser"): "os.path.expanduser",
    ("os.path", "expandvars"): "os.path.expandvars",
    ("os", "path"): "os.path",
    ("os", "getenv"): "os.getenv",
    ("os", "environ"): "os.environ",
    ("tempfile", "gettempdir"): "tempfile.gettempdir",
    ("tempfile", "gettempdirb"): "tempfile.gettempdirb",
    ("tempfile", "gettempprefix"): "tempfile.gettempprefix",
    ("tempfile", "mkstemp"): "tempfile.mkstemp",
    ("tempfile", "mkdtemp"): "tempfile.mkdtemp",
    ("tempfile", "mktemp"): "tempfile.mktemp",
    ("tempfile", "NamedTemporaryFile"): "tempfile.NamedTemporaryFile",
    ("tempfile", "TemporaryFile"): "tempfile.TemporaryFile",
    ("tempfile", "TemporaryDirectory"): "tempfile.TemporaryDirectory",
    ("tempfile", "SpooledTemporaryFile"): "tempfile.SpooledTemporaryFile",
    ("pathlib", "Path"): "Path",
}
TEST_ISOLATION_MESSAGE_SUFFIX: str = (
    "must take a monkeypatch fixture and route HOME/TMP env reads through "
    "monkeypatch.setenv; tmp_path / tmpdir allocate a sandbox path but do "
    "not intercept env reads, so they leak across the suite (CODE_RULES — "
    "see audits 2026-05-22 Theme M)"
)
