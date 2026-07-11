#!/usr/bin/env python3
"""
BDD Automate-phase gate (production code touch).

Blocks writes to production source files when no matching test exists
or the matching test has not been modified within the configured
freshness window. Enforces "TDD IS NON-NEGOTIABLE" from CLAUDE.md.
"""
import ast
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path


_hooks_root_path_string = str(Path(__file__).resolve().parent.parent)
_blocking_directory_path_string = str(Path(__file__).resolve().parent)
if _hooks_root_path_string not in sys.path:
    sys.path.insert(0, _hooks_root_path_string)
if _blocking_directory_path_string not in sys.path:
    sys.path.insert(0, _blocking_directory_path_string)

from code_rules_shared import is_ephemeral_script_path  # noqa: E402

from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402
from hooks_constants.messages import USER_FACING_TDD_NOTICE  # noqa: E402

PRODUCTION_EXTENSIONS = {'.py', '.ts', '.tsx', '.js', '.jsx'}
SKIP_PATTERNS = {
    'test_', '_test.', '.test.', 'tests/', '__tests__/',
    'conftest', 'fixture', 'mock', 'stub'
}
SKIP_EXTENSIONS = {'.md', '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.txt'}
DOTCLAUDE_PATH_SEGMENTS = frozenset({".claude"})


def _is_inside_dotclaude_segment(file_path_string: str) -> bool:
    normalized_path = file_path_string.replace("\\", "/")
    for each_segment in normalized_path.split("/"):
        if each_segment and each_segment in DOTCLAUDE_PATH_SEGMENTS:
            return True
    return False


def _freshness_seconds() -> int:
    return 600


def _constants_only_allowed_node_types() -> tuple[type, ...]:
    return (
        ast.Import,
        ast.ImportFrom,
        ast.Assign,
        ast.AnnAssign,
    )


def _is_module_docstring_expression(module_level_node: ast.stmt) -> bool:
    if not isinstance(module_level_node, ast.Expr):
        return False
    expression_value = module_level_node.value
    if not isinstance(expression_value, ast.Constant):
        return False
    return isinstance(expression_value.value, str)


def _safe_constant_functions() -> frozenset[str]:
    """Unqualified function names treated as safe value constructors."""
    return frozenset({"Path", "frozenset"})


def _safe_constant_attribute_calls() -> frozenset[tuple[str, str]]:
    """(module, attr) pairs treated as safe value constructors."""
    return frozenset({("re", "compile")})


def _rhs_has_unsafe_call(rhs_node: ast.AST) -> bool:
    """Return True when rhs_node contains a function call outside the safe allowlist.

    Safe calls are value constructors (``Path(...)``, ``re.compile(...)``)
    that create objects without side effects. Any other call pattern is
    treated as unsafe import-time behavior.
    """
    safe_functions = _safe_constant_functions()
    safe_attribute_calls = _safe_constant_attribute_calls()
    for each_subnode in ast.walk(rhs_node):
        if isinstance(each_subnode, ast.Call):
            function_node = each_subnode.func
            if isinstance(function_node, ast.Name):
                if function_node.id not in safe_functions:
                    return True
            elif isinstance(function_node, ast.Attribute):
                if isinstance(function_node.value, ast.Name):
                    pair = (function_node.value.id, function_node.attr)
                    if pair not in safe_attribute_calls:
                        return True
                else:
                    return True
            else:
                return True
        elif isinstance(
            each_subnode,
            (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.Lambda),
        ):
            return True
    return False


def _is_constants_only_python_content(content: str) -> bool:
    if not content.strip():
        return False
    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return False
    if not parsed_tree.body:
        return False
    allowed_node_types = _constants_only_allowed_node_types()
    for each_top_level_node in parsed_tree.body:
        if isinstance(each_top_level_node, allowed_node_types):
            if isinstance(each_top_level_node, (ast.Assign, ast.AnnAssign)):
                rhs = each_top_level_node.value
                if rhs is not None and _rhs_has_unsafe_call(rhs):
                    return False
            continue
        if _is_module_docstring_expression(each_top_level_node):
            continue
        return False
    return True


def _apply_edit_to_content(
    existing_content: str, old_str: str, new_str: str, should_replace_all: bool
) -> str:
    """Apply an edit's replacement to content the way the Edit tool would.

    Args:
        existing_content: The text being edited.
        old_str: The substring the edit replaces.
        new_str: The replacement substring.
        should_replace_all: Replace every occurrence when True (matching the
            Edit tool's ``replace_all`` flag), otherwise only the first.

    Returns:
        The post-edit content.
    """
    if should_replace_all:
        return existing_content.replace(old_str, new_str)
    return existing_content.replace(old_str, new_str, 1)


def _future_module_name() -> str:
    return "__future__"


def _is_future_import(node: ast.stmt) -> bool:
    """Return whether a statement is a ``from __future__`` import.

    Args:
        node: A top-level module statement.

    Returns:
        True when the statement imports from ``__future__``, whose presence
        affects module-wide compilation semantics.
    """
    return isinstance(node, ast.ImportFrom) and node.module == _future_module_name()


def _is_removable_import(node: ast.stmt) -> bool:
    """Return whether a statement is an import that removes or reorders cleanly.

    Args:
        node: A top-level module statement.

    Returns:
        True for plain ``import`` and ``from`` imports. ``from __future__``
        imports return False because their presence affects module-wide
        compilation semantics, so the gate treats them as behavior-bearing
        statements rather than removable imports; every non-import statement
        also returns False.
    """
    if isinstance(node, ast.Import):
        return True
    if isinstance(node, ast.ImportFrom):
        return not _is_future_import(node)
    return False


def _future_import_signatures(content: str) -> list[str] | None:
    """Return the ``ast.dump`` signatures of a module's ``from __future__`` imports.

    Args:
        content: Python source text to parse.

    Returns:
        The future-import signatures in source order, or ``None`` when the
        content does not parse.
    """
    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return None
    return [ast.dump(each_node) for each_node in parsed_tree.body if _is_future_import(each_node)]


def _is_post_edit_constants_only(existing_content: str, tool_name: str, tool_input: dict) -> bool:
    """Check if post-edit content remains constants-only after Edit or MultiEdit.

    Both the existing content and the post-edit result must be constants-only
    to prevent edits on files with behavior from bypassing the TDD gate. Editing
    a ``from __future__`` import also fails this check, so a future-import edit
    on a constants-only file faces the gate rather than slipping through the
    constants exemption.
    """
    if not _is_constants_only_python_content(existing_content):
        return False

    if tool_name == "Edit":
        old_str = tool_input.get("old_string", "") or ""
        new_str = tool_input.get("new_string", "") or ""
        if not old_str:
            return False
        should_replace_all = bool(tool_input.get("replace_all", False))
        post_edit_content = _apply_edit_to_content(existing_content, old_str, new_str, should_replace_all)
    elif tool_name == "MultiEdit":
        all_edits = tool_input.get("edits", []) or []
        post_edit_content = existing_content
        for each_edit in all_edits:
            if not isinstance(each_edit, dict):
                return False
            each_old = each_edit.get("old_string", "") or ""
            each_new = each_edit.get("new_string", "") or ""
            if not each_old:
                return False
            should_replace_all = bool(each_edit.get("replace_all", False))
            post_edit_content = _apply_edit_to_content(
                post_edit_content, each_old, each_new, should_replace_all
            )
    else:
        return False

    if _future_import_signatures(existing_content) != _future_import_signatures(post_edit_content):
        return False
    return _is_constants_only_python_content(post_edit_content)


def _top_level_signatures(content: str) -> tuple[list[str], list[str]] | None:
    """Split a module's top-level statements into removable-import and other signatures.

    Args:
        content: Python source text to parse.

    Returns:
        A pair ``(import_signatures, non_import_signatures)`` of ``ast.dump``
        strings in source order, or ``None`` when the content does not parse.
        Plain imports populate the first list; ``from __future__`` imports and
        every non-import statement populate the second, so editing a future
        import reads as a behavior edit rather than a removable-import edit.
        Signatures omit line and column attributes, so statements that only
        shift position compare equal.
    """
    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return None
    import_signatures: list[str] = []
    non_import_signatures: list[str] = []
    for each_node in parsed_tree.body:
        if _is_removable_import(each_node):
            import_signatures.append(ast.dump(each_node))
        else:
            non_import_signatures.append(ast.dump(each_node))
    return import_signatures, non_import_signatures


def _is_post_edit_import_only(existing_content: str, tool_name: str, tool_input: dict) -> bool:
    """Check whether an Edit or MultiEdit only removes or reorders imports.

    The top-level statements are split into imports and the rest, before and
    after applying the edit. The edit is exempt only when the non-import
    statements are unchanged and every post-edit import statement already
    appears among the pre-edit imports, so removing or reordering imports is
    exempt while adding, swapping, or retargeting an import stays gated: those
    can change behavior through a new symbol in scope, a different
    implementation bound to the same name, or `from __future__` semantics. An
    edit that leaves the parsed module identical (a comment- or whitespace-only
    change) also stays gated. Reading the resulting file rather than the edit
    fragments keeps the exemption from firing on import text inside a string
    literal, and lets it fire on edits whose old string carries surrounding
    context for uniqueness.

    Args:
        existing_content: Current text of the file under edit.
        tool_name: The intercepted tool (Edit or MultiEdit).
        tool_input: The intercepted tool's input payload.

    Returns:
        True when the edit leaves the non-import statements unchanged and the
        post-edit imports are a reordering or removal of the pre-edit imports.
    """
    existing_signatures = _top_level_signatures(existing_content)
    if existing_signatures is None:
        return False

    if tool_name == "Edit":
        old_str = tool_input.get("old_string", "") or ""
        new_str = tool_input.get("new_string", "") or ""
        if not old_str:
            return False
        should_replace_all = bool(tool_input.get("replace_all", False))
        post_edit_content = _apply_edit_to_content(existing_content, old_str, new_str, should_replace_all)
    elif tool_name == "MultiEdit":
        all_edits = tool_input.get("edits", []) or []
        if not all_edits:
            return False
        post_edit_content = existing_content
        for each_edit in all_edits:
            if not isinstance(each_edit, dict):
                return False
            each_old = each_edit.get("old_string", "") or ""
            each_new = each_edit.get("new_string", "") or ""
            if not each_old:
                return False
            should_replace_all = bool(each_edit.get("replace_all", False))
            post_edit_content = _apply_edit_to_content(
                post_edit_content, each_old, each_new, should_replace_all
            )
    else:
        return False

    post_edit_signatures = _top_level_signatures(post_edit_content)
    if post_edit_signatures is None:
        return False
    existing_imports, existing_rest = existing_signatures
    post_imports, post_rest = post_edit_signatures
    if post_rest != existing_rest or post_imports == existing_imports:
        return False
    return Counter(post_imports) <= Counter(existing_imports)


def _tests_directory_name() -> str:
    return "tests"


def _parent_walk_limit() -> int:
    return 10


def _repo_boundary_sentinels() -> frozenset[str]:
    return frozenset({".git", "pyproject.toml", "package.json", "Cargo.toml", "go.mod"})


def _test_function_patterns() -> tuple[re.Pattern[str], ...]:
    return (
        re.compile(r"\bdef\s+test_"),
        re.compile(r"\b(?:it|test|describe)\s*\("),
    )


def _directory_skip_components() -> frozenset[str]:
    return frozenset({
        "conftest", "fixture", "fixtures", "mock", "mocks", "stub", "stubs",
    })


def _is_repo_boundary(candidate_directory: Path) -> bool:
    for each_sentinel in _repo_boundary_sentinels():
        if (candidate_directory / each_sentinel).exists():
            return True
    return False


def _ancestor_tests_directories(start_directory: Path) -> list[tuple[Path, Path]]:
    """Collect each ancestor's sibling tests directory up to the repo boundary.

    Args:
        start_directory: Directory of the production file under edit.

    Returns:
        Ordered (ancestor, tests_directory) pairs; nearer ancestors first.
    """
    all_pairs: list[tuple[Path, Path]] = []
    current_directory = start_directory
    for _ in range(_parent_walk_limit()):
        sibling_tests = current_directory / _tests_directory_name()
        if sibling_tests.is_dir():
            all_pairs.append((current_directory, sibling_tests))
        if _is_repo_boundary(current_directory):
            break
        if current_directory.parent == current_directory:
            break
        current_directory = current_directory.parent
    return all_pairs


def _split_module_stem_prefix() -> str:
    return "code_rules_"


def _split_test_family_glob() -> str:
    return "test_code_rules_enforcer_*.py"


def _split_family_candidates(directory: Path, stem: str) -> list[Path]:
    if not stem.startswith(_split_module_stem_prefix()):
        return []
    return sorted(directory.glob(_split_test_family_glob()))


def candidate_test_paths_for(production_path: Path) -> list[Path]:
    """Return the test files whose freshness can satisfy the gate for a production file.

    Every ancestor ``tests`` directory contributes a flat candidate
    (``tests/test_<stem>.py``) and package-mirroring nested candidates
    (``tests/<subpackage path>/test_<stem>.py``), so repos that keep tests
    either beside the package or in a category tree both resolve.

    For ``code_rules_*`` Python modules the candidate list is extended with the
    sibling split test family (``test_code_rules_enforcer_*.py``), because that
    family collectively covers the split check modules; a fresh edit to any
    family file satisfies the RED step for editing one of those modules. The
    glob is directory-local, so ``code_rules_*`` files elsewhere gain no extra
    candidates. Plain stem-derived candidates always come first.

    Args:
        production_path: The production source file being written or edited.

    Returns:
        Ordered candidate test paths; stem-derived siblings precede any
        split-family additions.
    """
    directory = production_path.parent
    stem = production_path.stem
    extension = production_path.suffix.lower()
    all_candidates: list[Path] = []

    if extension == ".py":
        all_candidates.append(directory / f"test_{stem}.py")
        all_candidates.append(directory / f"{stem}_test.py")
        for each_ancestor, each_tests_directory in _ancestor_tests_directories(directory):
            all_candidates.append(each_tests_directory / f"test_{stem}.py")
            nested_directory = each_tests_directory
            for each_relative_part in directory.relative_to(each_ancestor).parts:
                nested_directory = nested_directory / each_relative_part
                all_candidates.append(nested_directory / f"test_{stem}.py")
        all_candidates.extend(_split_family_candidates(directory, stem))
        return all_candidates

    if extension in {".tsx", ".ts", ".jsx", ".js"}:
        all_candidates.append(directory / f"{stem}.test{extension}")
        all_candidates.append(directory / f"{stem}.spec{extension}")
        return all_candidates

    return all_candidates


def _test_file_encoding() -> str:
    return "utf-8"


def _safe_mtime(candidate_path: Path) -> float | None:
    try:
        return candidate_path.stat().st_mtime
    except (FileNotFoundError, OSError):
        return None


def _read_candidate_text(candidate_path: Path) -> str | None:
    try:
        with candidate_path.open("r", encoding=_test_file_encoding(), errors="ignore") as each_file:
            return each_file.read()
    except (FileNotFoundError, OSError):
        return None


def _contains_test_evidence(candidate_path: Path) -> bool:
    test_file_content = _read_candidate_text(candidate_path)
    if test_file_content is None:
        return False
    for each_pattern in _test_function_patterns():
        if each_pattern.search(test_file_content):
            return True
    return False


def has_fresh_test(
    all_candidates: list[Path],
    freshness_seconds: int,
) -> bool:
    current_time = time.time()
    for each_candidate in all_candidates:
        candidate_mtime = _safe_mtime(each_candidate)
        if candidate_mtime is None:
            continue
        age_seconds = current_time - candidate_mtime
        if age_seconds > freshness_seconds:
            continue
        if not _contains_test_evidence(each_candidate):
            continue
        return True
    return False


def build_deny_reason(production_path: Path, all_candidates: list[Path]) -> str:
    candidate_lines = "\n".join(f"  - {each_path}" for each_path in all_candidates)
    hook_source_path = Path(__file__).resolve()
    return (
        f"[TDD] Blocking write to production file: {production_path}\n"
        f"No matching test file exists, or it has not been modified within the last "
        f"{_freshness_seconds()} seconds.\n"
        f"Expected one of:\n{candidate_lines}\n"
        f"Write a failing test first (RED), then the minimum code to pass it (GREEN).\n\n"
        f"If this file legitimately does not need a test (for example, a module containing only "
        f"module-level constants with no behavior), that is a hook enhancement, not a bypass. "
        f"Propose an exemption rule in {hook_source_path} so every similar file benefits "
        f"automatically. Do not add escape-hatch markers to production files."
    )


def emit_allow() -> None:
    allow_payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
        }
    }
    print(json.dumps(allow_payload))


def emit_deny(reason: str) -> None:
    deny_payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        },
        "suppressOutput": True,
        "systemMessage": USER_FACING_TDD_NOTICE,
    }
    log_hook_block(
        calling_hook_name="tdd_enforcer.py",
        hook_event="PreToolUse",
        block_reason=reason,
    )
    print(json.dumps(deny_payload))


def _matches_any_skip_pattern(name_lower: str, path_with_forward_slashes: str) -> bool:
    path_components_lower = [each_part for each_part in path_with_forward_slashes.split("/") if each_part]
    directory_components = path_components_lower[:-1]
    skip_directory_components = _directory_skip_components()
    for each_directory_component in directory_components:
        if each_directory_component in skip_directory_components:
            return True
    for each_pattern in SKIP_PATTERNS:
        if each_pattern.endswith("/"):
            if each_pattern in path_with_forward_slashes:
                return True
            continue
        if each_pattern in name_lower:
            return True
    return False


def _extract_written_content(tool_name: str, tool_input: dict) -> str:
    if tool_name == "Write":
        return tool_input.get("content", "") or ""
    if tool_name == "Edit":
        return tool_input.get("new_string", "") or ""
    if tool_name == "MultiEdit":
        all_edits = tool_input.get("edits", []) or []
        joined_new_strings: list[str] = []
        for each_edit in all_edits:
            if isinstance(each_edit, dict):
                joined_new_strings.append(each_edit.get("new_string", "") or "")
        return "\n".join(joined_new_strings)
    return ""


def main() -> None:
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if not file_path:
        sys.exit(0)

    if _is_inside_dotclaude_segment(file_path) or is_ephemeral_script_path(file_path):
        sys.exit(0)

    path = Path(file_path)
    ext = path.suffix.lower()

    # Skip config/docs
    if ext in SKIP_EXTENSIONS:
        sys.exit(0)

    # Skip non-production code files
    if ext not in PRODUCTION_EXTENSIONS:
        sys.exit(0)

    # Skip test files
    name_lower = path.name.lower()
    path_str = str(path).lower().replace("\\", "/")
    if _matches_any_skip_pattern(name_lower, path_str):
        sys.exit(0)

    # Block production code - require confirmation
    # Exempt constants-only content for Write (full content provided)
    written_content = _extract_written_content(tool_name, tool_input)
    if tool_name == "Write" and ext == ".py" and _is_constants_only_python_content(written_content):
        emit_allow()
        sys.exit(0)

    # Exempt Edit/MultiEdit on constants-only files when post-edit content remains constants-only
    if tool_name in ("Edit", "MultiEdit") and ext == ".py" and path.exists():
        existing_content = _read_candidate_text(path)
        if existing_content is not None:
            if _is_post_edit_import_only(existing_content, tool_name, tool_input):
                emit_allow()
                sys.exit(0)
            if _is_post_edit_constants_only(existing_content, tool_name, tool_input):
                emit_allow()
                sys.exit(0)

    all_candidates = candidate_test_paths_for(path)
    if has_fresh_test(all_candidates, _freshness_seconds()):
        emit_allow()
        sys.exit(0)

    emit_deny(build_deny_reason(path, all_candidates))
    sys.exit(0)


if __name__ == "__main__":
    main()
