"""Boolean-naming and banned-identifier checks for JavaScript and TypeScript source.

These mirror the Python ``check_boolean_naming`` and ``check_banned_identifiers``
rules for the ``.mjs`` / ``.js`` family so a JavaScript declaration receives the
same naming discipline the Python checks apply. Detection is line-regex based
over a copy of the source whose string, comment, and regex regions are blanked,
so a boolean assignment inside a prompt string or a comment never fires. The
``@param {boolean}`` scan reads the raw source instead, because JSDoc lives
inside a block comment the blanking step removes.
"""

import sys
from pathlib import Path

_blocking_directory = str(Path(__file__).resolve().parent)
_hooks_directory = str(Path(__file__).resolve().parent.parent)
if _blocking_directory not in sys.path:
    sys.path.insert(0, _blocking_directory)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from code_rules_imports_logging import (  # noqa: E402
    _blank_non_code_regions,
)
from code_rules_shared import (  # noqa: E402
    _scope_violations_to_changed_lines,
    get_file_extension,
    is_hook_infrastructure,
    is_test_file,
)

from hooks_constants.banned_identifiers_constants import (  # noqa: E402
    BANNED_IDENTIFIER_MESSAGE_SUFFIX,
)
from hooks_constants.code_rules_enforcer_constants import (  # noqa: E402
    ALL_JAVASCRIPT_EXTENSIONS,
)
from hooks_constants.js_conventions_constants import (  # noqa: E402
    ALL_JAVASCRIPT_BANNED_IDENTIFIERS,
    BOOLEAN_PREFIX_GUIDANCE,
    JAVASCRIPT_BOOLEAN_DECLARATION_PATTERN,
    JAVASCRIPT_BOOLEAN_JSDOC_PARAMETER_PATTERN,
    JAVASCRIPT_BOOLEAN_PREFIX_PATTERN,
    JAVASCRIPT_DECLARATION_NAME_PATTERN,
    MAX_JAVASCRIPT_BANNED_IDENTIFIER_ISSUES,
    MAX_JAVASCRIPT_BOOLEAN_NAMING_ISSUES,
    SINGLE_CHARACTER_NAME_LENGTH,
)


def _is_javascript_target(file_path: str) -> bool:
    """Return whether a check should run on this path.

    Args:
        file_path: The destination path of the write or edit.

    Returns:
        True when the path carries a JavaScript extension and is neither a test
        file nor hook infrastructure; False for every exempt path.
    """
    if is_test_file(file_path) or is_hook_infrastructure(file_path):
        return False
    return get_file_extension(file_path) in ALL_JAVASCRIPT_EXTENSIONS


def _boolean_name_lacks_prefix(name: str) -> bool:
    """Return whether a boolean name needs a naming prefix it does not carry.

    A single-character name, an all-uppercase constant name, and a name already
    carrying an ``is``/``has``/``should``/``can``/``was``/``did`` prefix are all
    accepted.

    Args:
        name: The declared boolean identifier.

    Returns:
        True when the name should carry a boolean prefix and does not.
    """
    if len(name) <= SINGLE_CHARACTER_NAME_LENGTH:
        return False
    if name.isupper():
        return False
    return JAVASCRIPT_BOOLEAN_PREFIX_PATTERN.match(name) is None


def _boolean_declaration_violations(
    blanked_content: str,
) -> list[tuple[range, str]]:
    """Return one span-tagged violation per unprefixed boolean declaration.

    Args:
        blanked_content: The source with string, comment, and regex regions
            replaced by spaces so only structural code is scanned.

    Returns:
        ``(line_range, message)`` pairs in source order.
    """
    all_violations: list[tuple[range, str]] = []
    for each_line_number, each_line in enumerate(blanked_content.split("\n"), 1):
        for each_match in JAVASCRIPT_BOOLEAN_DECLARATION_PATTERN.finditer(each_line):
            name = each_match.group("name")
            if not _boolean_name_lacks_prefix(name):
                continue
            message = (
                f"Line {each_line_number}: Boolean {name} - {BOOLEAN_PREFIX_GUIDANCE}"
            )
            all_violations.append(
                (range(each_line_number, each_line_number + 1), message)
            )
    return all_violations


def _boolean_jsdoc_parameter_violations(content: str) -> list[tuple[range, str]]:
    """Return one span-tagged violation per unprefixed ``@param {boolean}`` name.

    The raw source is scanned rather than the blanked copy because JSDoc lives
    inside a block comment the blanking step removes.

    Args:
        content: The raw source text.

    Returns:
        ``(line_range, message)`` pairs in source order.
    """
    all_violations: list[tuple[range, str]] = []
    for each_line_number, each_line in enumerate(content.split("\n"), 1):
        for each_match in JAVASCRIPT_BOOLEAN_JSDOC_PARAMETER_PATTERN.finditer(
            each_line
        ):
            name = each_match.group("name")
            if not _boolean_name_lacks_prefix(name):
                continue
            message = (
                f"Line {each_line_number}: Boolean parameter {name} - "
                f"{BOOLEAN_PREFIX_GUIDANCE}"
            )
            all_violations.append(
                (range(each_line_number, each_line_number + 1), message)
            )
    return all_violations


def check_js_boolean_naming(
    content: str,
    file_path: str,
    all_changed_lines: set[int] | None = None,
    defer_scope_to_caller: bool = False,
) -> list[str]:
    """Flag JavaScript boolean declarations and JSDoc params lacking a prefix.

    A ``const``/``let``/``var`` declaration whose right-hand side is a boolean
    literal, or a negation that is the entire right-hand side (``= !ready;`` or
    ``= !obj.prop`` or ``= !call(...)``, ending the statement with no ``?``,
    ``&&``, ``||``, or ``,`` combining the negated operand), and a
    ``@param {boolean}`` JSDoc entry, all name a boolean. A ``!``-headed side
    that a ternary or logical operator continues (``!active ? "on" : "off"``,
    ``!err && getName()``) is an ordinary expression, not a boolean, and is left
    alone. When the boolean name lacks an ``is``/``has``/``should``/``can``/
    ``was``/``did`` prefix (camelCase forms such as ``isReady``), the check flags
    it, so a reader learns a value is a boolean from its name. Findings scope to
    *all_changed_lines* so an edit blocks on the unprefixed boolean it just
    introduced while a pre-existing one on an untouched line does not block.

    Args:
        content: The source text to inspect.
        file_path: The path the source will be written to, used for exemptions.
        all_changed_lines: Post-edit line numbers the current edit touched, or
            None to treat the whole file as in scope. When provided, a violation
            blocks only when its line intersects the changed lines.
        defer_scope_to_caller: When True, return every violation so the
            commit/push gate scopes by added line through its ``Line N:``
            partitioning.

    Returns:
        One issue per unprefixed boolean declaration and JSDoc parameter, scoped
        to the changed lines unless *defer_scope_to_caller* is True or
        *all_changed_lines* is None, capped at the module limit.
    """
    if not _is_javascript_target(file_path):
        return []
    blanked_content = _blank_non_code_regions(content)
    all_violations_in_source_order = _boolean_declaration_violations(blanked_content)
    all_violations_in_source_order.extend(_boolean_jsdoc_parameter_violations(content))
    scoped_issues = _scope_violations_to_changed_lines(
        all_violations_in_source_order,
        all_changed_lines,
        defer_scope_to_caller,
    )
    if defer_scope_to_caller:
        return scoped_issues
    return scoped_issues[:MAX_JAVASCRIPT_BOOLEAN_NAMING_ISSUES]


def check_js_banned_identifiers(
    content: str,
    file_path: str,
    all_changed_lines: set[int] | None = None,
    defer_scope_to_caller: bool = False,
) -> list[str]:
    """Flag JavaScript declarations bound to a banned identifier name.

    A ``const``/``let``/``var`` declaration whose name is one of the banned
    placeholder names (``result``, ``data``, ``response``, ``ctx``, and the rest)
    is flagged so the author picks a domain-specific name. Findings scope to
    *all_changed_lines* so a pre-existing ``result`` on an untouched line never
    blocks while a newly written one does.

    Args:
        content: The source text to inspect.
        file_path: The path the source will be written to, used for exemptions.
        all_changed_lines: Post-edit line numbers the current edit touched, or
            None to treat the whole file as in scope. When provided, a violation
            blocks only when its line intersects the changed lines.
        defer_scope_to_caller: When True, return every violation so the
            commit/push gate scopes by added line through its ``Line N:``
            partitioning.

    Returns:
        One issue per banned declaration name, scoped to the changed lines unless
        *defer_scope_to_caller* is True or *all_changed_lines* is None, capped at
        the module limit.
    """
    if not _is_javascript_target(file_path):
        return []
    blanked_content = _blank_non_code_regions(content)
    all_violations_in_source_order: list[tuple[range, str]] = []
    for each_line_number, each_line in enumerate(blanked_content.split("\n"), 1):
        for each_match in JAVASCRIPT_DECLARATION_NAME_PATTERN.finditer(each_line):
            name = each_match.group("name")
            if name not in ALL_JAVASCRIPT_BANNED_IDENTIFIERS:
                continue
            message = (
                f"Line {each_line_number}: Banned identifier '{name}' - "
                f"{BANNED_IDENTIFIER_MESSAGE_SUFFIX}"
            )
            all_violations_in_source_order.append(
                (range(each_line_number, each_line_number + 1), message)
            )
    scoped_issues = _scope_violations_to_changed_lines(
        all_violations_in_source_order,
        all_changed_lines,
        defer_scope_to_caller,
    )
    if defer_scope_to_caller:
        return scoped_issues
    return scoped_issues[:MAX_JAVASCRIPT_BANNED_IDENTIFIER_ISSUES]
