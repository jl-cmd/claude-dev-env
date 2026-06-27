"""Caps and lookup sets for the new B-series blocking checks in code_rules_enforcer.py.

Each constant is consumed by exactly one check function in the enforcer. They
live here (not at module scope of the enforcer) so the enforcer file stays
under the file-global-constants use-count rule (CODE_RULES §file-global-constants).
"""

from __future__ import annotations

import re

MAX_BANNED_PREFIX_ISSUES: int = 3
MAX_STUB_IMPLEMENTATION_ISSUES: int = 3
MAX_TYPED_DICT_PAIR_ISSUES: int = 3
MAX_TEST_BRANCHING_ISSUES: int = 3
MAX_BARE_EXCEPT_ISSUES: int = 3
MAX_BOUNDARY_TYPE_ISSUES: int = 5
ALL_BANNED_PREFIX_NAMES: tuple[str, ...] = ("handle_", "process_", "manage_", "do_")
MAX_DOCSTRING_FORMAT_ISSUES: int = 5
MAX_DOCSTRING_ARGS_SIGNATURE_ISSUES: int = 5
MAX_CLASS_DOCSTRING_PUBLIC_METHOD_ISSUES: int = 5
MINIMUM_PUBLIC_METHODS_FOR_CLASS_DOCSTRING_BREADTH: int = 2
MAX_IGNORED_MUST_CHECK_RETURN_ISSUES: int = 5
MAX_TYPE_ESCAPE_HATCH_ISSUES: int = 5
MAX_THIN_WRAPPER_ISSUES: int = 1
MAX_ZERO_PAYLOAD_ALIAS_ISSUES: int = 3
MAX_LOGGING_FSTRING_ISSUES: int = 3
MAX_LOGGING_PRINTF_TOKEN_ISSUES: int = 3
MAX_WINDOWS_API_NONE_ISSUES: int = 3
MAX_E2E_TEST_NAMING_ISSUES: int = 3
MAX_IMPORT_BLOCK_SORT_ISSUES: int = 1
IMPORT_BLOCK_SORT_RUFF_TIMEOUT_SECONDS: int = 15
IMPORT_BLOCK_SORT_RULE_CODE: str = "I001"
RUFF_STDIN_ENCODING: str = "utf-8"
RUFF_PYPROJECT_CONFIG_FILENAME: str = "pyproject.toml"
RUFF_PYPROJECT_TOOL_TABLE_MARKER: str = "[tool.ruff"
ALL_RUFF_STANDALONE_CONFIG_FILENAMES: tuple[str, ...] = ("ruff.toml", ".ruff.toml")
ALL_IMPORT_BLOCK_SORT_RUFF_COMMAND_PREFIX: tuple[str, ...] = (
    "ruff",
    "check",
    "--select",
    "I001",
    "--no-cache",
    "--output-format",
    "json",
)
MAX_JS_RESUME_TASK_ENUMERATION_ISSUES: int = 5
MINIMUM_RESUME_TASK_ENUMERATION_ITEMS: int = 2
DOCSTRING_TRIVIAL_FUNCTION_BODY_LINE_LIMIT: int = 3
MAX_DOCSTRING_FALLBACK_BRANCH_ISSUES: int = 3
DOCSTRING_FALLBACK_BRANCH_MINIMUM_ROUTE_COUNT: int = 2
MAX_DOCSTRING_NO_CONSUMER_CLAIM_ISSUES: int = 3
MAX_DOCSTRING_UNGUARDED_PAYLOAD_CLAIM_ISSUES: int = 3
MAX_STALE_TEST_NAME_TARGET_ISSUES: int = 3
STALE_TEST_NAME_MINIMUM_SHARED_TOKEN_COUNT: int = 2
MAX_MODULE_DOCSTRING_CHECK_ROSTER_ISSUES: int = 5
MINIMUM_PUBLIC_CHECKS_FOR_MODULE_DOCSTRING_ROSTER: int = 2
MAX_DOCSTRING_TUPLE_ENUMERATION_ISSUES: int = 5
MINIMUM_TUPLE_MEMBERS_FOR_DOCSTRING_ENUMERATION: int = 2
MAX_DOCSTRING_STEP_DISPATCH_ISSUES: int = 5
MINIMUM_NAMED_LINEAR_STEPS_FOR_DISPATCH_CHECK: int = 2
MINIMUM_TOKENS_FOR_DISPATCH_CALLEE: int = 2
MAX_DOCSTRING_UNDEFINED_CONSTANT_ISSUES: int = 3
MAX_DOCSTRING_RETURNS_PLURAL_CARDINALITY_ISSUES: int = 5
SINGLE_DICT_KEY_COUNT_FOR_PLURAL_CARDINALITY_DRIFT: int = 1
MAX_DOCSTRING_RAISES_LARGEZIPFILE_ISSUES: int = 5
DOCSTRING_LARGE_ZIP_FILE_EXCEPTION_NAME: str = "LargeZipFile"
ZIPFILE_WRITER_CLASS_NAME: str = "ZipFile"
ZIPFILE_MODE_KEYWORD: str = "mode"
ZIPFILE_MODE_POSITIONAL_INDEX: int = 1
ZIPFILE_ALLOW_ZIP64_KEYWORD: str = "allowZip64"
ZIPFILE_ALLOW_ZIP64_POSITIONAL_INDEX: int = 3
ALL_ZIPFILE_WRITE_MODE_VALUES: frozenset[str] = frozenset({"w", "a", "x"})
MAX_DOCSTRING_ARGS_SPAN_SCOPE_ISSUES: int = 3
ALL_DOCSTRING_SINGLE_LINE_SCOPE_PHRASES: tuple[str, ...] = (
    "anchor line is among the changed lines",
    "anchor line is among the edited lines",
    "anchor line is among the changed",
    "first line is among the changed lines",
    "start line is among the changed lines",
)
ALL_DOCSTRING_SPAN_SCOPE_OVERRIDE_PHRASES: tuple[str, ...] = (
    "any line of",
    "any line in",
    "any of its lines",
    "any span line",
)
ALL_DOCSTRING_SPAN_RANGE_BODY_CALLEE_NAMES: tuple[str, ...] = (
    "_scope_violations_to_changed_lines",
    "_scope_violations",
)
MAX_DOCSTRING_CARDINAL_FAMILY_ISSUES: int = 5
MINIMUM_CONSTANT_FAMILY_MEMBERS_FOR_CARDINAL_CHECK: int = 2
MINIMUM_DOCSTRING_FAMILY_OVERLAP_FOR_CARDINAL_CHECK: int = 2
ALL_NAMING_CONVENTION_DESCRIPTOR_TOKENS: frozenset[str] = frozenset(
    {
        "UPPER_SNAKE_CASE",
        "SCREAMING_SNAKE_CASE",
        "UPPER_CASE",
        "SNAKE_CASE",
        "CAMEL_CASE",
        "PASCAL_CASE",
        "KEBAB_CASE",
        "TITLE_CASE",
    }
)
ALL_DOCSTRING_NON_CONSTANT_REFERENCE_MARKERS: frozenset[str] = frozenset(
    {
        "rule",
        "rules",
        "doc",
        "docs",
        "document",
        "file",
        "env",
        "environment",
        "variable",
        "set",
        "reads",
        "read",
        "per",
        "follows",
        "following",
        "see",
    }
)
ALL_DOCSTRING_FILE_REFERENCE_SUFFIXES: tuple[str, ...] = (
    ".md",
    ".py",
    ".txt",
    ".json",
)
DOCSTRING_REFERENCE_MARKER_WINDOW: int = 2
ALL_GENERIC_CHECK_NAME_TOKENS: frozenset[str] = frozenset(
    {"check", "checks", "test", "tests", "in", "for", "and", "the"}
)
ALL_FORMAT_LOGGER_FUNCTION_NAMES: frozenset[str] = frozenset(
    {
        "log_debug",
        "log_info",
        "log_ok",
        "log_error",
        "log_warning",
        "log_batch",
        "log_background",
    }
)
DOCSTRING_RUNON_SENTENCE_WORD_LIMIT: int = 30
MAX_DOCSTRING_RUNON_SENTENCE_ISSUES: int = 5
ALL_DOCSTRING_RUNON_JOINER_MARKERS: tuple[str, ...] = ("—", " -- ", ";")
DOCSTRING_RUNON_SENTENCE_BOUNDARY_PATTERN: re.Pattern[str] = re.compile(r"(?<=[.!?])\s+")

ALL_DOCSTRING_NO_CONSUMER_CLAIM_PHRASES: tuple[str, ...] = (
    "no consumer reads",
    "no consumer yet",
    "no submission-run consumer reads",
    "producer-only artifact",
    "no reader consumes",
    "nothing reads it yet",
    "no one reads it yet",
    "not yet read by any consumer",
)

ALL_DOCSTRING_GUARDED_FAILURE_CLAIM_PHRASES: tuple[str, ...] = (
    "malformed payload resolves to none",
    "malformed payload returns none",
    "malformed response resolves to none",
    "malformed response returns none",
    "bad payload resolves to none",
    "invalid payload resolves to none",
    "malformed payload yields none",
)

MAX_DOCSTRING_INLINE_LITERAL_CLAIM_ISSUES: int = 3
ALL_DOCSTRING_NO_INLINE_LITERAL_CLAIM_PHRASES: tuple[str, ...] = (
    "no literals appear inline",
    "no literal appears inline",
    "no literals inline",
    "no inline literals",
    "no string literals appear inline",
    "without any inline literals",
    "no hardcoded literals remain",
)

ALL_DOCSTRING_EXCLUSIVE_SCOPE_PHRASES: tuple[str, ...] = (
    "only when",
    "only if",
    "falls back to",
    "falling back to",
    "fall back to",
)

ALL_DOCSTRING_MULTIPLE_CONDITION_JOINING_PHRASES: tuple[str, ...] = (
    " or ",
    "either",
    "both",
)

ALL_BARE_EXCEPT_BANNED_HANDLER_NAMES: frozenset[str] = frozenset({"Exception", "BaseException"})
ALL_BOUNDARY_TYPE_EXEMPT_FILENAMES: frozenset[str] = frozenset({"protocols.py", "types.py"})
ALL_DOCSTRING_IMPLICIT_INSTANCE_PARAMETER_NAMES: frozenset[str] = frozenset({"self", "cls"})
ALL_DOCSTRING_EXEMPT_DECORATOR_NAMES: frozenset[str] = frozenset(
    {"property", "abstractmethod", "abstractproperty", "abc.abstractmethod", "overload"}
)
ALL_TEST_INDICATING_ENVIRONMENT_VARIABLE_NAMES: frozenset[str] = frozenset(
    {
        "TESTING",
        "PYTEST_CURRENT_TEST",
        "TEST_MODE",
        "IS_TEST",
        "IS_TESTING",
        "UNIT_TEST",
    }
)
