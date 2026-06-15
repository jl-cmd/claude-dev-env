"""Dead config-dataclass field check: cross-module scan for ``*Config`` @dataclass fields.

A config ``@dataclass`` (any class whose name ends in ``"Config"``) is defined
in one module but constructed and consumed in others, so the per-file dead-field
check in ``code_rules_dead_dataclass_field`` cannot judge its fields — it skips
any class that is not constructed in the same file. This check resolves the
enclosing package tree — the scan root — and flags a ``*Config`` dataclass field
whose name appears as an attribute read (``obj.field``) in no production module
anywhere under that root.

The scan is deliberately conservative to keep false positives near zero:

- Only ``@dataclass`` classes whose name ends in ``"Config"`` participate; other
  dataclasses are covered by the per-file check.
- Test and migration files are exempt as write destinations, so a field added to
  a config dataclass inside a test is never flagged.
- Production modules under the scan root are scanned for attribute reads; test
  and migration modules are deliberately excluded so a field read only by test
  code is still flagged as dead-in-production.
- Field reads are collected as ``ast.Attribute.attr`` values (``obj.field``),
  string literals (covers ``getattr(obj, "field")``), and match-pattern keyword
  attribute names (``case Config(field=found)``). Plain ``ast.Name`` references
  are excluded — a local variable named ``debug_port`` is not a read of
  ``config.debug_port``.
- A scan root whose total file count exceeds the configured cap cannot prove any
  field dead, so the check returns ``[]`` on a cap hit.
- A field read only by a module outside the resolved scan root is treated as dead
  — the same conservative scoping the dead-module-constant check accepts.
"""

import ast
import os
import sys
from pathlib import Path

_blocking_directory = str(Path(__file__).resolve().parent)
_hooks_directory = str(Path(__file__).resolve().parent.parent)
if _blocking_directory not in sys.path:
    sys.path.insert(0, _blocking_directory)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from code_rules_dead_dataclass_field import (  # noqa: E402
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
    CONFIG_CLASS_NAME_SUFFIX,
    DEAD_CONFIG_FIELD_GUIDANCE,
    MAX_DEAD_CONFIG_FIELD_ISSUES,
    MAX_SCAN_ROOT_FILE_COUNT,
    PYTHON_SOURCE_SUFFIX,
)


def _is_config_dataclass(class_node: ast.ClassDef) -> bool:
    """Return whether a class is a @dataclass whose name ends in ``"Config"``.

    Args:
        class_node: The class definition node to test.

    Returns:
        True when the class carries a ``@dataclass`` decorator and its name ends
        in ``"Config"``.
    """
    return _is_dataclass(class_node) and class_node.name.endswith(CONFIG_CLASS_NAME_SUFFIX)


def _attribute_read_names_in_source(source: str) -> set[str]:
    """Return the set of attribute names read anywhere in a module's source.

    Collects ``ast.Attribute.attr`` values in Load context, string literals
    (so ``getattr(obj, "field")`` contributes ``"field"``), and
    ``ast.MatchClass.kwd_attrs`` names (so ``case Config(field=x)`` contributes
    ``"field"``). A ``SyntaxError`` contributes no names.

    Args:
        source: The full text of a ``.py`` module.

    Returns:
        Every attribute name the module reads, via any of the three mechanisms
        above.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    all_read_names: set[str] = set()
    for each_node in ast.walk(tree):
        if isinstance(each_node, ast.Attribute) and isinstance(each_node.ctx, ast.Load):
            all_read_names.add(each_node.attr)
        elif isinstance(each_node, ast.Constant) and isinstance(each_node.value, str):
            all_read_names.add(each_node.value)
        elif isinstance(each_node, ast.MatchClass):
            all_read_names.update(each_node.kwd_attrs)
    return all_read_names


def _all_production_read_names_under_root(
    scan_root: Path,
    written_path: Path,
    written_content: str,
) -> tuple[set[str], bool]:
    """Return attribute names read by production modules under the scan root.

    Scans every production ``.py`` module under ``scan_root`` (excluding test and
    migration files) for attribute reads. The written module's post-edit content
    replaces its on-disk text so the current edit is included. Scanning stops at
    the configured file cap; the boolean signals the caller to treat a cap hit as
    "cannot prove dead".

    Args:
        scan_root: The directory tree to scan.
        written_path: The resolved path of the module being written.
        written_content: The post-edit text of the written module.

    Returns:
        A (read_names, cap_was_hit) pair. The name set is the union of attribute
        reads across every scanned production module; cap_was_hit is True when
        the scan stopped at the configured file cap before finishing the tree.
    """
    all_read_names = _attribute_read_names_in_source(written_content)
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
            return all_read_names, True
        try:
            sibling_source = each_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        all_read_names |= _attribute_read_names_in_source(sibling_source)
    return all_read_names, False


def check_dead_config_dataclass_fields(
    content: str, file_path: str, full_file_content: str | None = None
) -> list[str]:
    """Flag a ``*Config`` @dataclass field read by no production module in the package tree.

    Runs a cross-module scan restricted to ``@dataclass`` classes whose name ends
    in ``"Config"``. For each such config dataclass in the written file, every
    instance field whose name does not appear as an attribute read (``obj.field``),
    string literal, or match-pattern keyword attribute in any production module
    under the enclosing scan root is flagged as dead. Test and migration files are
    exempt as write destinations; production modules under the scan root are scanned
    while test and migration modules in the tree are excluded so fields read only
    by test code are still flagged as dead-in-production. Whole-file analysis runs
    against ``full_file_content`` when supplied so an Edit fragment is judged
    against the reconstructed post-edit file. A scan root exceeding the file cap
    returns ``[]`` (cannot prove dead). The scan root is resolved the same way as
    the dead-module-constant check: a ``config/`` module's root is its parent
    directory, a module in a package directory's root is the package's parent, and
    a top-level module's root is its enclosing directory.

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
    all_read_names, cap_was_hit = _all_production_read_names_under_root(
        scan_root,
        written_path,
        effective_content,
    )
    if cap_was_hit:
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
