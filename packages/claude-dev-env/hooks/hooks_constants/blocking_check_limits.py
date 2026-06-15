"""Caps and lookup sets for the new B-series blocking checks in code_rules_enforcer.py.

Each constant is consumed by exactly one check function in the enforcer. They
live here (not at module scope of the enforcer) so the enforcer file stays
under the file-global-constants use-count rule (CODE_RULES §file-global-constants).
"""

from __future__ import annotations


MAX_BANNED_PREFIX_ISSUES: int = 3
MAX_STUB_IMPLEMENTATION_ISSUES: int = 3
MAX_TYPED_DICT_PAIR_ISSUES: int = 3
MAX_TEST_BRANCHING_ISSUES: int = 3
MAX_BARE_EXCEPT_ISSUES: int = 3
MAX_BOUNDARY_TYPE_ISSUES: int = 5
ALL_BANNED_PREFIX_NAMES: tuple[str, ...] = ("handle_", "process_", "manage_", "do_")
MAX_DOCSTRING_FORMAT_ISSUES: int = 5
MAX_DOCSTRING_ARGS_SIGNATURE_ISSUES: int = 5
MAX_IGNORED_MUST_CHECK_RETURN_ISSUES: int = 5
MAX_TYPE_ESCAPE_HATCH_ISSUES: int = 5
MAX_THIN_WRAPPER_ISSUES: int = 1
MAX_ZERO_PAYLOAD_ALIAS_ISSUES: int = 3
MAX_LOGGING_FSTRING_ISSUES: int = 3
MAX_WINDOWS_API_NONE_ISSUES: int = 3
MAX_E2E_TEST_NAMING_ISSUES: int = 3
DOCSTRING_TRIVIAL_FUNCTION_BODY_LINE_LIMIT: int = 3

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
