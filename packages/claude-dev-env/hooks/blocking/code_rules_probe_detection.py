"""Home-directory and shared-temp value-reference detection for the test-isolation check."""

import ast
import sys
from pathlib import Path

_blocking_directory = str(Path(__file__).resolve().parent)
_hooks_directory = str(Path(__file__).resolve().parent.parent)
if _blocking_directory not in sys.path:
    sys.path.insert(0, _blocking_directory)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from code_rules_probe_chains import (  # noqa: E402
    _dotted_call_attribute_chain,
    _environ_key_string_from_call,
    _environ_key_string_from_subscript,
    _resolve_chain_through_aliases,
)

from hooks_constants.code_rules_enforcer_constants import (  # noqa: E402
    ALL_HOME_DIRECTORY_ENV_VAR_NAMES,
    ALL_PATHLIB_PATH_CONSTRUCTOR_CANONICAL_NAMES,
    ALL_SHARED_TEMP_SOURCE_PROBE_DOTTED_NAMES,
    ENVIRONMENT_VARIABLE_REFERENCE_PATTERN,
    HOME_DIRECTORY_TILDE_PREFIX,
    PATHLIB_EXPANDUSER_METHOD_NAME,
    TEMPFILE_FACTORY_ISOLATION_DIRECTORY_KEYWORD,
    WINDOWS_PERCENT_VARIABLE_REFERENCE_PATTERN,
)


def _pathlib_path_construction_uses_home_tilde(
    node: ast.expr, all_canonical_names_by_alias: dict[str, str],
) -> bool:
    """Return True for a ``pathlib.Path('~...')`` construction with a home tilde.

    The node is a Path construction when its callee chain resolves (directly,
    aliased, or fully qualified) to a member of
    ``ALL_PATHLIB_PATH_CONSTRUCTOR_CANONICAL_NAMES``. It uses the home tilde
    when its first argument is a literal string beginning with ``~``. A
    tilde-free or dynamic first argument expands no home directory and returns
    False, mirroring ``_expanduser_argument_references_home``.

    Args:
        node: The candidate ``Path(...)`` construction expression.
        all_canonical_names_by_alias: Import-alias map from
            ``_build_alias_canonicalization_map``.

    Returns:
        True when *node* constructs a ``pathlib.Path`` from a leading-tilde
        literal string.
    """
    if not isinstance(node, ast.Call):
        return False
    constructor_chain = _dotted_call_attribute_chain(node)
    if constructor_chain is None:
        return False
    canonical_chain = _resolve_chain_through_aliases(
        constructor_chain, all_canonical_names_by_alias
    )
    if canonical_chain not in ALL_PATHLIB_PATH_CONSTRUCTOR_CANONICAL_NAMES:
        return False
    return _expanduser_argument_references_home(node)


def _expanduser_method_call_targets_pathlib_path(
    call_node: ast.Call,
    all_canonical_names_by_alias: dict[str, str],
    all_path_local_bindings: set[str],
) -> bool:
    """Return True for a ``.expanduser()`` call on a home-tilde ``pathlib.Path``.

    ``Path.expanduser`` expands the ``~`` bound into the receiver Path, so the
    call resolves the home directory only when that receiver carries a leading
    tilde. The receiver carries a tilde when it is a ``pathlib.Path('~...')``
    construction (directly, aliased, or fully qualified) or a local variable
    previously bound to such a construction. A tilde-free or dynamic receiver
    (``Path('/tmp/x').expanduser()`` / ``Path(some_path).expanduser()``)
    expands no home directory and is not flagged, keeping the form symmetric
    with ``os.path.expanduser`` argument inspection.

    Args:
        call_node: The call whose callee attribute is ``expanduser``.
        all_canonical_names_by_alias: Import-alias map from
            ``_build_alias_canonicalization_map``.
        all_path_local_bindings: Local names bound to a home-tilde
            ``pathlib.Path`` construction from
            ``_collect_pathlib_path_local_binding_names``.

    Returns:
        True when the ``expanduser`` receiver resolves to a home-tilde
        ``pathlib.Path``.
    """
    callee = call_node.func
    if not isinstance(callee, ast.Attribute):
        return False
    if callee.attr != PATHLIB_EXPANDUSER_METHOD_NAME:
        return False
    receiver = callee.value
    if isinstance(receiver, ast.Name):
        return receiver.id in all_path_local_bindings
    return _pathlib_path_construction_uses_home_tilde(receiver, all_canonical_names_by_alias)


def _expandvars_argument_references_home_or_temp(call_node: ast.Call) -> bool:
    """Return True when an ``expandvars`` call expands a home/temp env var.

    Inspects the first string argument for dollar-style ``$NAME`` / ``${NAME}``
    references and Windows percent-style ``%NAME%`` references, then reports
    whether any referenced name is a home/temp env var. ``os.path.expandvars``
    expands percent syntax on Windows, so both forms reach the same home/temp
    env-var name set. A non-constant or absent argument is treated as not
    referencing a home/temp variable, mirroring the conservative env-name
    filtering applied to ``os.getenv``.

    Args:
        call_node: The ``os.path.expandvars(...)`` call node.

    Returns:
        True when at least one expanded variable name is in
        ``ALL_HOME_DIRECTORY_ENV_VAR_NAMES``.
    """
    if not call_node.args:
        return False
    first_argument = call_node.args[0]
    if not (
        isinstance(first_argument, ast.Constant)
        and isinstance(first_argument.value, str)
    ):
        return False
    dollar_style_names = ENVIRONMENT_VARIABLE_REFERENCE_PATTERN.findall(
        first_argument.value
    )
    percent_style_names = WINDOWS_PERCENT_VARIABLE_REFERENCE_PATTERN.findall(
        first_argument.value
    )
    all_referenced_names = dollar_style_names + percent_style_names
    return any(
        each_name in ALL_HOME_DIRECTORY_ENV_VAR_NAMES
        for each_name in all_referenced_names
    )


def _expanduser_argument_references_home(call_node: ast.Call) -> bool:
    """Return True when an ``expanduser`` call expands the home directory.

    ``os.path.expanduser`` only substitutes a leading ``~`` (``~`` alone or
    ``~user``); a string without a leading tilde is returned unchanged and
    never touches HOME. A non-constant or absent argument is treated as not
    referencing home, mirroring the conservative argument inspection applied
    to ``expandvars``.

    Args:
        call_node: The ``os.path.expanduser(...)`` call node.

    Returns:
        True when the first string argument begins with the home-directory
        tilde prefix.
    """
    if not call_node.args:
        return False
    first_argument = call_node.args[0]
    if not (
        isinstance(first_argument, ast.Constant)
        and isinstance(first_argument.value, str)
    ):
        return False
    return first_argument.value.startswith(HOME_DIRECTORY_TILDE_PREFIX)


def _tempfile_factory_call_is_isolated_by_dir(
    call_node: ast.Call,
    all_canonical_names_by_alias: dict[str, str],
    all_environ_local_bindings: set[str],
) -> bool:
    """Return True when a tempfile factory's ``dir=`` sandboxes the allocation.

    A ``dir=`` keyword sandboxes the allocation only when its value is a
    plausibly isolated path (typically the pytest ``tmp_path`` fixture). A
    ``dir=`` value that resolves to the shared temp directory does not isolate
    the call and is treated as absent:

    - a constant ``None`` selects the default shared temp directory; and
    - a shared-temp source — ``os.getenv('TMPDIR'|'TEMP'|'TMP')`` /
      ``os.environ['TMPDIR'|...]`` / ``os.environ.get('TMPDIR'|...)``, or
      ``tempfile.gettempdir()`` / ``tempfile.gettempprefix()`` — returns the
      shared temp directory.

    Only an explicit ``dir=`` keyword counts; a ``**kwargs`` ``dir`` cannot be
    resolved statically and is treated as absent, mirroring the conservative
    argument inspection applied to ``expandvars`` and ``expanduser``.

    Args:
        call_node: The tempfile factory call node.
        all_canonical_names_by_alias: Import-alias map used to resolve aliased
            shared-temp sources passed as the ``dir=`` value.
        all_environ_local_bindings: Local names bound to ``os.environ`` within
            the test function, used to recognize aliased ``os.environ`` reads.

    Returns:
        True when an explicit ``dir=`` keyword is present and its value is not
        a recognized shared-temp source.
    """
    for each_keyword in call_node.keywords:
        if each_keyword.arg != TEMPFILE_FACTORY_ISOLATION_DIRECTORY_KEYWORD:
            continue
        return not _dir_value_resolves_to_shared_temp(
            each_keyword.value,
            all_canonical_names_by_alias,
            all_environ_local_bindings,
        )
    return False


def _dir_value_resolves_to_shared_temp(
    dir_value: ast.expr,
    all_canonical_names_by_alias: dict[str, str],
    all_environ_local_bindings: set[str],
) -> bool:
    """Return True when a tempfile ``dir=`` value points at the shared temp dir.

    Args:
        dir_value: The expression supplied as the factory's ``dir=`` value.
        all_canonical_names_by_alias: Import-alias map used to resolve aliased
            ``os.getenv`` / ``os.environ`` / ``tempfile`` references.
        all_environ_local_bindings: Local names bound to ``os.environ`` within
            the test function.

    Returns:
        True when the value is a constant ``None``, a call or subscript that
        reads a home or temp environment variable named in
        ``ALL_HOME_DIRECTORY_ENV_VAR_NAMES``, or a call whose dotted chain is
        a recognized shared-temp source in
        ``ALL_SHARED_TEMP_SOURCE_PROBE_DOTTED_NAMES``.
    """
    if isinstance(dir_value, ast.Constant) and dir_value.value is None:
        return True
    if isinstance(dir_value, ast.Call):
        environ_key = _environ_key_string_from_call(
            dir_value, all_canonical_names_by_alias, all_environ_local_bindings
        )
        if environ_key in ALL_HOME_DIRECTORY_ENV_VAR_NAMES:
            return True
        raw_chain = _dotted_call_attribute_chain(dir_value)
        if raw_chain is None:
            return False
        canonical_chain = _resolve_chain_through_aliases(
            raw_chain, all_canonical_names_by_alias
        )
        return canonical_chain in ALL_SHARED_TEMP_SOURCE_PROBE_DOTTED_NAMES
    if isinstance(dir_value, ast.Subscript):
        environ_key = _environ_key_string_from_subscript(
            dir_value, all_canonical_names_by_alias, all_environ_local_bindings
        )
        return environ_key in ALL_HOME_DIRECTORY_ENV_VAR_NAMES
    return False
