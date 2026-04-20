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
from pathlib import Path

_hooks_root_path_string = str(Path(__file__).resolve().parent.parent)
if _hooks_root_path_string not in sys.path:
    sys.path.insert(0, _hooks_root_path_string)

from config.messages import USER_FACING_TDD_NOTICE

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
            continue
        if _is_module_docstring_expression(each_top_level_node):
            continue
        return False
    return True


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


def find_nearest_tests_directory(start_directory: Path) -> Path | None:
    current_directory = start_directory
    for _ in range(_parent_walk_limit()):
        sibling_tests = current_directory / _tests_directory_name()
        if sibling_tests.is_dir():
            return sibling_tests
        if _is_repo_boundary(current_directory):
            return None
        if current_directory.parent == current_directory:
            return None
        current_directory = current_directory.parent
    return None


def candidate_test_paths_for(production_path: Path) -> list[Path]:
    directory = production_path.parent
    stem = production_path.stem
    extension = production_path.suffix.lower()
    all_candidates: list[Path] = []

    if extension == ".py":
        all_candidates.append(directory / f"test_{stem}.py")
        all_candidates.append(directory / f"{stem}_test.py")
        nearest_tests_directory = find_nearest_tests_directory(directory)
        if nearest_tests_directory is not None:
            all_candidates.append(nearest_tests_directory / f"test_{stem}.py")
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

    if _is_inside_dotclaude_segment(file_path):
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
    written_content = _extract_written_content(tool_name, tool_input)
    if tool_name == "Write" and ext == ".py" and _is_constants_only_python_content(written_content):
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
