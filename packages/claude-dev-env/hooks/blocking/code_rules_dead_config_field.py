"""Dead config-dataclass field check: cross-module scan for config-like @dataclass fields.

A config-like ``@dataclass`` — any class whose name ends in ``"Config"`` or
``"Selectors"`` — is defined in one module but constructed and consumed in
others, so the per-file dead-field check in
``code_rules_dead_dataclass_field`` cannot judge its fields — it skips any class
that is not constructed in the same file. This check resolves the enclosing
package tree — the scan root — and flags a config-like dataclass field whose
name appears as an attribute read (``obj.field``) in no production module
anywhere under that root. A selectors dataclass is the same shape as a config
dataclass: it is bound to a module-level singleton (``binary_selectors =
BinarySelectors()``) and its fields are read across files, so an unwired
selector field is caught the same way as a dead config field.

The scan is deliberately conservative to keep false positives near zero:

- Only ``@dataclass`` classes whose name ends in ``"Config"`` or ``"Selectors"``
  participate; other dataclasses are covered by the per-file check.
- Test and migration files are exempt as write destinations, so a field added to
  a config dataclass inside a test is never flagged.
- Production modules under the scan root are scanned for attribute reads; test
  and migration modules are deliberately excluded so a field read only by test
  code is still flagged as dead-in-production.
- Field reads are collected as ``ast.Attribute.attr`` values (``obj.field``),
  augmented-assignment targets (``cfg.field += 1`` reads ``field`` before
  writing it), string literals (covers ``getattr(obj, "field")``),
  keyword-argument names on non-constructor calls (covers
  ``replace(cfg, debug_port=1)``), and match-pattern keyword attribute names
  (``case Config(field=found)``). Two field-write forms are excluded because they
  name a field without consuming it: a keyword that writes a field in a constructor
  of a known ``*Config`` dataclass defined under the scan root
  (``ThemeUpdateConfig(debug_port=1)``, excluded per keyword node so a same-named
  keyword on a ``replace`` call stays a read, and a factory function whose name
  merely ends in ``"Config"`` is not excluded), and a self-referential attribute
  read inside a ``*Config`` field's own default-value expression in the class body
  whose attribute name equals the field being defined
  (``debug_port: int = source.debug_port``) — a field written only these ways and
  read by no module is the dead-config case this check exists to catch. A default
  that sources a differently-named field on another object
  (``timeout_ms: int = other_config.base_timeout``) leaves that read counted, so
  ``base_timeout`` stays a live consumer. Plain
  ``ast.Name`` references are excluded — a local variable named ``debug_port`` is
  not a read of ``config.debug_port``.
- A production module that reflectively reads a whole instance — a bare or
  ``dataclasses``-qualified call to ``asdict``, ``astuple``, ``fields``,
  ``replace``, or ``vars``, or a read of ``obj.__dict__`` — consumes every field
  at once without naming any single field, so the check is suppressed for the
  whole tree (returns ``[]``).
- A scan root whose total file count exceeds the configured cap cannot prove any
  field dead, so the check returns ``[]`` on a cap hit.
- A field read only by a module outside the resolved scan root is treated as dead
  — the same conservative scoping the dead-module-constant check accepts.

Unlike the per-file dead-dataclass-field check, this cross-module check does NOT
suppress on a dataclass-dunder whole-instance read — instance comparison
(``cfg == other``), set or dict membership, formatted-string conversion
(``f"{cfg}"``), or whole-instance stringification
(``str(cfg)``/``repr(cfg)``/``format(cfg)``). Those syntactic forms are not bound
to a config instance, and tree-wide one incidental match anywhere would disable
the check on any realistic package. The consequence is a documented, rare
limitation: a ``*Config`` field read ONLY via whole-instance dunder comparison or
stringification, and never read directly anywhere in production, may be flagged.
The augmented-assignment read mechanism (``cfg.field += 1`` reads ``field``
before writing it) is precise and remains a counted read.
"""

import ast
import os
import sys
from collections.abc import Iterator
from pathlib import Path

_blocking_directory = str(Path(__file__).resolve().parent)
_hooks_directory = str(Path(__file__).resolve().parent.parent)
if _blocking_directory not in sys.path:
    sys.path.insert(0, _blocking_directory)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from code_rules_dead_dataclass_field import (  # noqa: E402
    _augmented_assignment_attribute_names,
    _dataclass_field_definitions,
    _is_dataclass,
)
from code_rules_dead_module_constant import (  # noqa: E402
    _scan_root_for_constants_module,
)
from code_rules_shared import (  # noqa: E402
    is_migration_file,
    is_test_file,
)

from hooks_constants.dead_config_field_constants import (  # noqa: E402
    ALL_CONFIG_CLASS_NAME_SUFFIXES,
    ALL_REFLECTIVE_FIELD_CONSUMER_NAMES,
    DATACLASSES_MODULE_NAME,
    DEAD_CONFIG_FIELD_GUIDANCE,
    MAX_DEAD_CONFIG_FIELD_ISSUES,
    MAX_SCAN_ROOT_FILE_COUNT,
    PYTHON_SOURCE_SUFFIX,
    WHOLE_INSTANCE_DICT_ATTRIBUTE_NAME,
)


def _is_config_dataclass(class_node: ast.ClassDef) -> bool:
    """Return whether a class is a @dataclass whose name ends in a config-like suffix.

    A config-like surface is a ``@dataclass`` whose name ends in ``"Config"`` or
    ``"Selectors"``. Both shapes are defined in one module, bound to a
    module-level singleton, and read across files, so the per-file dead-field
    check cannot judge their fields and the cross-module scan covers them here.

    Args:
        class_node: The class definition node to test.

    Returns:
        True when the class carries a ``@dataclass`` decorator and its name ends
        in one of ``ALL_CONFIG_CLASS_NAME_SUFFIXES``.
    """
    return _is_dataclass(class_node) and class_node.name.endswith(
        ALL_CONFIG_CLASS_NAME_SUFFIXES
    )


def _reads_whole_instance_reflectively(tree: ast.Module) -> bool:
    """Return whether a module consumes a whole instance via a reflective read.

    Detects a bare call to any reflective whole-instance consumer (``asdict``,
    ``astuple``, ``fields``, ``replace``, ``vars`` imported from ``dataclasses``),
    a ``dataclasses``-qualified call to the same consumers
    (``dataclasses.asdict(cfg)``, ``dataclasses.replace(cfg, ...)``), and a read
    of the ``__dict__`` attribute. The method-call form must be ``dataclasses``-
    qualified — an unrelated ``"text".replace(...)`` or ``frame.fields(...)`` on
    another object does not match. Each matched form reads every field of an
    instance at once without naming any single field, so a module that uses one
    cannot prove a config field unread.

    Args:
        tree: The parsed module to inspect.

    Returns:
        True when the module makes a bare or ``dataclasses``-qualified call to a
        reflective whole-instance consumer, or reads ``obj.__dict__``.
    """
    for each_node in ast.walk(tree):
        if isinstance(each_node, ast.Attribute):
            if each_node.attr == WHOLE_INSTANCE_DICT_ATTRIBUTE_NAME:
                return True
            continue
        if not isinstance(each_node, ast.Call):
            continue
        function_node = each_node.func
        if isinstance(function_node, ast.Name) and function_node.id in ALL_REFLECTIVE_FIELD_CONSUMER_NAMES:
            return True
        if (
            isinstance(function_node, ast.Attribute)
            and isinstance(function_node.value, ast.Name)
            and function_node.value.id == DATACLASSES_MODULE_NAME
            and function_node.attr in ALL_REFLECTIVE_FIELD_CONSUMER_NAMES
        ):
            return True
    return False


def _config_dataclass_names(tree: ast.Module) -> set[str]:
    """Return names of ``*Config`` ``@dataclass`` classes defined in a module.

    A constructor-keyword exclusion fires only for a callee that names a genuine
    config dataclass, so the caller first gathers the config dataclass names a
    module defines, then unions those names across the scan root.

    Args:
        tree: The parsed module to inspect.

    Returns:
        Every class name in the module that is a ``@dataclass`` whose name ends in
        the config class name suffix.
    """
    config_dataclass_names: set[str] = set()
    for each_node in ast.walk(tree):
        if isinstance(each_node, ast.ClassDef) and _is_config_dataclass(each_node):
            config_dataclass_names.add(each_node.name)
    return config_dataclass_names


def _call_constructs_config_class(
    call_node: ast.Call, all_known_config_class_names: set[str]
) -> bool:
    """Return whether a call constructs a known ``*Config`` dataclass.

    A call whose callee names a ``*Config`` dataclass defined under the scan root —
    ``AppInfoConfig(...)`` or a qualified ``module.AppInfoConfig(...)`` —
    constructs a config instance, and its keyword arguments write the named fields
    rather than read them. A factory function whose name merely ends in
    ``"Config"`` (``getThemeConfig(...)``) is not a known config dataclass, so its
    keyword arguments stay genuine reads.

    Args:
        call_node: The call expression to test.
        all_known_config_class_names: Names of ``*Config`` dataclasses defined under
            the scan root.

    Returns:
        True when the callee names a known ``*Config`` dataclass.
    """
    callee_node = call_node.func
    if isinstance(callee_node, ast.Name):
        return callee_node.id in all_known_config_class_names
    if isinstance(callee_node, ast.Attribute):
        return callee_node.attr in all_known_config_class_names
    return False


def _config_constructor_keyword_node_ids(
    tree: ast.Module, all_known_config_class_names: set[str]
) -> set[int]:
    """Return ids of keyword nodes that write fields in a known ``*Config`` constructor.

    A keyword in an ``AppInfoConfig(field=value)`` call sets ``field`` rather than
    reading it, so its node id is collected for the caller to exclude. The
    exclusion is keyed per keyword node, not by name, so a same-named keyword in a
    ``replace(cfg, field=value)`` call — which reuses a live instance and stays a
    read — keeps its own distinct node and is not stripped.

    Args:
        tree: The parsed module to inspect.
        all_known_config_class_names: Names of ``*Config`` dataclasses defined under
            the scan root.

    Returns:
        The ``id()`` of every keyword node passed to a known ``*Config``
        constructor call.
    """
    constructor_keyword_node_ids: set[int] = set()
    for each_node in ast.walk(tree):
        if not isinstance(each_node, ast.Call):
            continue
        if not _call_constructs_config_class(each_node, all_known_config_class_names):
            continue
        for each_keyword in each_node.keywords:
            if each_keyword.arg is not None:
                constructor_keyword_node_ids.add(id(each_keyword))
    return constructor_keyword_node_ids


def _self_referential_default_attribute_node_ids(
    field_name: str, default_value: ast.expr
) -> set[int]:
    """Return ids of attribute reads in a default whose name equals the field.

    Walks a ``*Config`` field's default-value expression and collects the ``id()``
    of each ``ast.Attribute`` read whose ``.attr`` equals ``field_name``. Such a
    read — ``sound_upload_timeout_ms: int = submission_timing.sound_upload_timeout_ms``
    — names the field being defined inside the class body, so it is not a consumer
    of the field. An attribute read of a differently-named field
    (``timeout_ms: int = other_config.base_timeout``) is a genuine consumer and is
    left out of the returned set.

    Args:
        field_name: The name of the field being defined.
        default_value: The default-value expression of that field.

    Returns:
        The ``id()`` of every self-referential attribute read inside the
        default-value expression.
    """
    self_referential_node_ids: set[int] = set()
    for each_inner_node in ast.walk(default_value):
        if isinstance(each_inner_node, ast.Attribute) and each_inner_node.attr == field_name:
            self_referential_node_ids.add(id(each_inner_node))
    return self_referential_node_ids


def _config_field_default_value_nodes(tree: ast.Module) -> set[int]:
    """Return ids of self-referential attribute reads in ``*Config`` field defaults.

    A field default such as ``sound_upload_timeout_ms: int =``
    ``submission_timing.sound_upload_timeout_ms`` is an attribute read whose name
    matches the field being defined. That self-referential read inside the config
    class body is not a consumer of the field, so its node id is collected here for
    the caller to exclude from the attribute-read set. Only the attribute read
    whose ``.attr`` equals the field name is collected; a default that sources a
    differently-named field on another object
    (``timeout_ms: int = other_config.base_timeout``) leaves that read counted, so
    ``base_timeout`` stays a live consumer.

    Args:
        tree: The parsed module to inspect.

    Returns:
        The ``id()`` of every self-referential attribute read within the
        default-value expression of a field declared in a ``*Config`` dataclass
        body.
    """
    default_value_node_ids: set[int] = set()
    for each_node in ast.walk(tree):
        if not isinstance(each_node, ast.ClassDef) or not _is_config_dataclass(each_node):
            continue
        for each_statement in each_node.body:
            if not isinstance(each_statement, ast.AnnAssign):
                continue
            if each_statement.value is None:
                continue
            if not isinstance(each_statement.target, ast.Name):
                continue
            default_value_node_ids |= _self_referential_default_attribute_node_ids(
                each_statement.target.id, each_statement.value
            )
    return default_value_node_ids


def _attribute_read_names_in_tree(
    tree: ast.Module, all_known_config_class_names: set[str]
) -> tuple[set[str], bool]:
    """Return attribute names read in a parsed module and a suppression flag.

    Collects attribute names via five mechanisms: ``ast.Attribute.attr`` values
    in Load context, augmented-assignment targets (so ``cfg.debug_port += 1``
    contributes ``"debug_port"`` because ``+=`` reads the attribute before
    writing it), string literals (so ``getattr(obj, "field")`` contributes
    ``"field"``), keyword-argument names (so ``replace(cfg, debug_port=1)``
    contributes ``"debug_port"``), and ``ast.MatchClass.kwd_attrs`` names (so
    ``case Config(field=x)`` contributes ``"field"``). Two field-write forms are
    excluded because they name a field without consuming it: a keyword that writes
    a field in a known ``*Config`` constructor (``AppInfoConfig(field=value)``,
    excluded per keyword node so a same-named ``replace`` keyword stays a read),
    and a self-referential attribute read inside a ``*Config`` dataclass field's
    own default-value expression (``field: int = source.field`` in the class body,
    excluded only when the read name equals the field name) — counting either
    would hide a field that is written but read by no module. A keyword passed to a
    factory function whose name merely ends in ``"Config"`` is not a known config
    constructor, so it stays a read. The boolean reports whether the module
    suppresses the dead-field check, which it does only when it reflectively reads a
    whole instance — a bare or ``dataclasses``-qualified
    ``asdict``/``astuple``/``fields``/``replace``/``vars`` call, or an
    ``obj.__dict__`` read — because that pattern reads every field at once without
    naming any single field, so the caller treats it as "cannot prove any field
    dead".

    Args:
        tree: The parsed module to inspect.
        all_known_config_class_names: Names of ``*Config`` dataclasses defined under
            the scan root, used to scope the constructor-keyword exclusion to
            genuine config constructors.

    Returns:
        A (read_names, suppresses_dead_field_check) pair. The name set is every
        attribute name the module reads via the mechanisms above, excluding known
        ``*Config`` constructor keyword nodes and self-referential config-field
        default-value attribute reads; suppresses_dead_field_check is True only when
        a reflective whole-instance read is present.
    """
    all_read_names: set[str] = _augmented_assignment_attribute_names(tree)
    config_constructor_keyword_node_ids = _config_constructor_keyword_node_ids(
        tree, all_known_config_class_names
    )
    config_field_default_node_ids = _config_field_default_value_nodes(tree)
    for each_node in ast.walk(tree):
        if (
            isinstance(each_node, ast.Attribute)
            and isinstance(each_node.ctx, ast.Load)
            and id(each_node) not in config_field_default_node_ids
        ):
            all_read_names.add(each_node.attr)
        elif isinstance(each_node, ast.Constant) and isinstance(each_node.value, str):
            all_read_names.add(each_node.value)
        elif isinstance(each_node, ast.MatchClass):
            all_read_names.update(each_node.kwd_attrs)
        elif (
            isinstance(each_node, ast.keyword)
            and each_node.arg is not None
            and id(each_node) not in config_constructor_keyword_node_ids
        ):
            all_read_names.add(each_node.arg)
    suppresses_dead_field_check = _reads_whole_instance_reflectively(tree)
    return all_read_names, suppresses_dead_field_check


def _iter_production_module_sources(
    scan_root: Path,
    written_path: Path,
    written_content: str,
) -> Iterator[str | None]:
    """Yield the source of each production module under the scan root.

    Yields ``written_content`` for the written module so the current edit is
    included, then each sibling production module's source (excluding test and
    migration files). A sibling whose text cannot be read is skipped. A single
    ``None`` is yielded when the production module count exceeds the configured
    file cap, signalling the caller that no field can be proven dead.

    Args:
        scan_root: The directory tree to scan.
        written_path: The resolved path of the module being written.
        written_content: The post-edit text of the written module.

    Yields:
        Each production module's source text, or a single ``None`` on a cap hit.
    """
    yield written_content
    written_path_key = os.path.normcase(str(written_path))
    scanned_file_count = 1
    for each_path in scan_root.rglob("*" + PYTHON_SOURCE_SUFFIX):
        if not each_path.is_file():
            continue
        if os.path.normcase(str(each_path.resolve())) == written_path_key:
            continue
        if is_test_file(str(each_path)):
            continue
        if is_migration_file(str(each_path)):
            continue
        scanned_file_count += 1
        if scanned_file_count > MAX_SCAN_ROOT_FILE_COUNT:
            yield None
            return
        try:
            yield each_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue


def _all_production_read_names_under_root(
    scan_root: Path,
    written_path: Path,
    written_content: str,
) -> tuple[set[str], bool, bool]:
    """Return read names, a cap-hit flag, and a suppression flag for the tree.

    Reads and AST-parses every production ``.py`` module under ``scan_root``
    (excluding test and migration files) at most once: the module sources are
    materialized once, a first pass over the cached sources gathers every
    ``*Config`` dataclass name defined under the root so the constructor-keyword
    exclusion fires only for a genuine config constructor, and a second pass over
    the same cached sources collects attribute reads. The written module's
    post-edit content replaces its on-disk text so the current edit is included.
    Scanning stops at the configured file cap. A module that reflectively reads a
    whole instance — a bare or ``dataclasses``-qualified
    ``asdict``/``astuple``/``fields``/``replace``/``vars`` call, or an
    ``obj.__dict__`` read — sets the suppression flag, signalling the caller that
    no field can be proven dead.

    Args:
        scan_root: The directory tree to scan.
        written_path: The resolved path of the module being written.
        written_content: The post-edit text of the written module.

    Returns:
        A (read_names, cap_was_hit, suppresses_dead_field_check) triple. The name
        set is the union of attribute reads across every scanned production
        module; cap_was_hit is True when the scan stopped at the configured file
        cap before finishing the tree; suppresses_dead_field_check is True when
        any scanned module reflectively reads a whole instance.
    """
    all_module_sources = list(
        _iter_production_module_sources(scan_root, written_path, written_content)
    )
    if None in all_module_sources:
        return set(), True, False
    all_production_trees: list[ast.Module] = []
    for each_source in all_module_sources:
        if each_source is None:
            continue
        try:
            all_production_trees.append(ast.parse(each_source))
        except SyntaxError:
            continue
    all_known_config_class_names: set[str] = set()
    for each_tree in all_production_trees:
        all_known_config_class_names |= _config_dataclass_names(each_tree)
    all_read_names: set[str] = set()
    suppresses_dead_field_check = False
    for each_tree in all_production_trees:
        module_read_names, module_suppresses_dead_field_check = _attribute_read_names_in_tree(
            each_tree, all_known_config_class_names
        )
        all_read_names |= module_read_names
        suppresses_dead_field_check = (
            suppresses_dead_field_check or module_suppresses_dead_field_check
        )
    return all_read_names, False, suppresses_dead_field_check


def check_dead_config_dataclass_fields(
    content: str, file_path: str, full_file_content: str | None = None
) -> list[str]:
    """Flag a config-like @dataclass field read by no production module in the package tree.

    Runs a cross-module scan restricted to ``@dataclass`` classes whose name ends
    in ``"Config"`` or ``"Selectors"`` — both are config-like surfaces bound to a
    module-level singleton and read across files. For each such dataclass in the
    written file, every
    instance field whose name does not appear as an attribute read (``obj.field``),
    augmented-assignment target (``cfg.field += 1``), string literal,
    non-constructor keyword-argument name (``replace`` keyword), or match-pattern
    keyword attribute in any production module under the enclosing scan root is
    flagged as dead. A keyword that writes a field in a ``*Config`` constructor
    (``ThemeUpdateConfig(debug_port=1)``) is a write, not a read, so it does not
    clear a field — a field set by a constructor keyword and read by no module is
    flagged. When any production module under the scan root reflectively
    reads a whole instance — a bare or ``dataclasses``-qualified call to
    ``asdict``, ``astuple``, ``fields``, ``replace``, or ``vars``, or a read of
    ``obj.__dict__`` — the check is suppressed for the whole tree and returns
    ``[]``, since that pattern reads every field at once without naming any single
    field. Test and
    migration files are exempt as write destinations; production modules under the
    scan root are scanned while test and migration modules in the tree are excluded
    so fields read only by test code are still flagged as dead-in-production.
    Whole-file analysis runs against ``full_file_content`` when supplied so an Edit
    fragment is judged against the reconstructed post-edit file. A scan root
    exceeding the file cap returns ``[]`` (cannot prove dead). The scan root is
    resolved the same way as the dead-module-constant check: a ``config/`` module's
    root is its parent directory, a module in a package directory's root is the
    package's parent, and a top-level module's root is its enclosing directory.

    Args:
        content: The new content under validation (Edit fragment or whole file).
        file_path: The destination path, used for the test/migration exemptions
            and scan-root resolution.
        full_file_content: The reconstructed post-edit whole-file content for an
            Edit, or None for a Write where ``content`` is already the whole file.

    Returns:
        One violation message per dead config dataclass field, capped at the
        configured maximum. Returns an empty list when the file is exempt, no
        qualifying config dataclass is found, the scan root exceeds the file cap,
        or a SyntaxError prevents parsing.
    """
    if is_test_file(file_path):
        return []
    if is_migration_file(file_path):
        return []
    effective_content = content if full_file_content is None else full_file_content
    try:
        tree = ast.parse(effective_content)
    except SyntaxError:
        return []
    all_config_classes = [
        each_node
        for each_node in ast.walk(tree)
        if isinstance(each_node, ast.ClassDef) and _is_config_dataclass(each_node)
    ]
    if not all_config_classes:
        return []
    scan_root = _scan_root_for_constants_module(file_path)
    written_path = Path(file_path).resolve()
    all_read_names, cap_was_hit, suppresses_dead_field_check = (
        _all_production_read_names_under_root(
            scan_root,
            written_path,
            effective_content,
        )
    )
    if cap_was_hit:
        return []
    if suppresses_dead_field_check:
        return []
    all_issues: list[str] = []
    for each_class in all_config_classes:
        for each_field_name, each_field_line in _dataclass_field_definitions(each_class):
            if each_field_name in all_read_names:
                continue
            all_issues.append(
                f"Line {each_field_line}: config dataclass field {each_field_name!r}"
                f" on {each_class.name} - {DEAD_CONFIG_FIELD_GUIDANCE}"
            )
            if len(all_issues) >= MAX_DEAD_CONFIG_FIELD_ISSUES:
                return all_issues
    return all_issues
