"""Path and payload classification for the TDD-enforcer gate.

Decides which write targets the gate skips silently (docs, tests, files inside a
``.claude`` tree) and pulls the written text out of a Write, Edit, or MultiEdit
payload so the gate can inspect it.
"""

from tdd_enforcer_parts.config.tdd_enforcer_constants import (
    ALL_DIRECTORY_SKIP_COMPONENTS,
    ALL_DOTCLAUDE_PATH_SEGMENTS,
    ALL_PRODUCTION_EXTENSIONS,
    ALL_SKIP_EXTENSIONS,
    ALL_SKIP_NAME_PATTERNS,
    NEWLINE_JOIN_SEPARATOR,
)


def production_extensions() -> frozenset[str]:
    """Return the source-file extensions the gate treats as production code."""
    return ALL_PRODUCTION_EXTENSIONS


def skip_extensions() -> frozenset[str]:
    """Return the config and documentation extensions the gate skips."""
    return ALL_SKIP_EXTENSIONS


def _skip_patterns() -> frozenset[str]:
    return ALL_SKIP_NAME_PATTERNS


def _dotclaude_path_segments() -> frozenset[str]:
    return ALL_DOTCLAUDE_PATH_SEGMENTS


def _directory_skip_components() -> frozenset[str]:
    return ALL_DIRECTORY_SKIP_COMPONENTS


def _is_inside_dotclaude_segment(file_path_string: str) -> bool:
    """Return whether any path segment is exactly a ``.claude`` directory.

    Args:
        file_path_string: The write target path, in either separator style.

    Returns:
        True when a ``.claude`` directory sits on the path, so the gate leaves
        agent-config edits alone.
    """
    normalized_path = file_path_string.replace("\\", "/")
    dotclaude_segments = _dotclaude_path_segments()
    for each_segment in normalized_path.split("/"):
        if each_segment and each_segment in dotclaude_segments:
            return True
    return False


def _path_has_skip_directory_component(path_with_forward_slashes: str) -> bool:
    all_components = [each_part for each_part in path_with_forward_slashes.split("/") if each_part]
    directory_components = all_components[:-1]
    skip_directory_components = _directory_skip_components()
    return any(each in skip_directory_components for each in directory_components)


def _skip_pattern_matches(pattern: str, name_lower: str, path_with_forward_slashes: str) -> bool:
    if pattern.endswith("/"):
        return pattern in path_with_forward_slashes
    return pattern in name_lower


def _name_or_path_matches_skip_pattern(name_lower: str, path_with_forward_slashes: str) -> bool:
    for each_pattern in _skip_patterns():
        if _skip_pattern_matches(each_pattern, name_lower, path_with_forward_slashes):
            return True
    return False


def _matches_any_skip_pattern(name_lower: str, path_with_forward_slashes: str) -> bool:
    """Return whether a path names a test, fixture, mock, or stub file.

    Args:
        name_lower: The lower-cased file name.
        path_with_forward_slashes: The lower-cased path with forward slashes.

    Returns:
        True when a skip directory component or a skip name pattern matches.
    """
    if _path_has_skip_directory_component(path_with_forward_slashes):
        return True
    return _name_or_path_matches_skip_pattern(name_lower, path_with_forward_slashes)


def _multiedit_new_strings(all_edits: list) -> list[str]:
    all_new_strings: list[str] = []
    for each_edit in all_edits:
        if isinstance(each_edit, dict):
            all_new_strings.append(each_edit.get("new_string", "") or "")
    return all_new_strings


def _extract_written_content(tool_name: str, tool_input: dict) -> str:
    """Return the text a Write, Edit, or MultiEdit payload would introduce.

    Args:
        tool_name: The intercepted tool name.
        tool_input: The intercepted tool's input payload.

    Returns:
        The written content for Write, the replacement for Edit, the joined
        replacements for MultiEdit, or an empty string for any other tool.
    """
    if tool_name == "Write":
        return tool_input.get("content", "") or ""
    if tool_name == "Edit":
        return tool_input.get("new_string", "") or ""
    if tool_name == "MultiEdit":
        all_edits = tool_input.get("edits", []) or []
        return NEWLINE_JOIN_SEPARATOR.join(_multiedit_new_strings(all_edits))
    return ""
