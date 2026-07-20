"""Directory-segment names that anchor validator temp-path staging.

``validate_proposed_file`` keeps the target's path from the first segment named
here, so the staged copy matches the real path's exemptions. Segment names are
derived from the authoritative path-exemption pattern sets and CLI markers,
then unioned with the config-directory allowlist.
"""

from __future__ import annotations

from collections.abc import Iterable

from hooks_constants.code_rules_enforcer_constants import ALL_CLI_FILE_PATH_MARKERS
from hooks_constants.code_rules_path_utils_constants import ALL_CONFIG_DIRECTORY_NAMES

from ..exempt_paths import (
    HOOK_INFRASTRUCTURE_PATTERNS,
    MIGRATION_PATH_PATTERNS,
    TEST_PATH_PATTERNS,
    WORKFLOW_REGISTRY_PATTERNS,
)

POSIX_DIRECTORY_SEPARATOR = "/"
WINDOWS_DIRECTORY_SEPARATOR = "\\"

ALL_AUTHORITATIVE_DIRECTORY_PATH_PATTERN_SETS: tuple[Iterable[str], ...] = (
    TEST_PATH_PATTERNS,
    WORKFLOW_REGISTRY_PATTERNS,
    MIGRATION_PATH_PATTERNS,
    HOOK_INFRASTRUCTURE_PATTERNS,
    ALL_CLI_FILE_PATH_MARKERS,
)


def is_filename_like_path_segment(path_segment: str) -> bool:
    """Return True when *path_segment* looks like a file name, not a directory.

    ::

        is_filename_like_path_segment("states.py")  # True
        is_filename_like_path_segment(".claude")    # False
        is_filename_like_path_segment("tests")      # False

    A leading-dot name is treated as a directory (``.claude``). Any other
    segment that contains a dot is treated as a filename (``states.py``).

    Args:
        path_segment: One path component with no separators.

    Returns:
        True when the segment should be ignored as a directory token.
    """
    if path_segment.startswith("."):
        return False
    return "." in path_segment


def all_directory_segments_in_path_pattern(path_pattern: str) -> list[str]:
    """Return lowercased directory tokens from one path-exemption pattern.

    ::

        all_directory_segments_in_path_pattern("/.claude/hooks/")
        # ['.claude', 'hooks']

        all_directory_segments_in_path_pattern("/tests.py")
        # []

        all_directory_segments_in_path_pattern("conftest")
        # []

    Separators normalize to POSIX. Filename-like segments and empty splits
    are dropped so only directory tokens remain.

    Args:
        path_pattern: One entry from an exemption or CLI marker pattern set.

    Returns:
        Lowercased directory segment names in path order.
    """
    normalized_pattern = path_pattern.replace(
        WINDOWS_DIRECTORY_SEPARATOR, POSIX_DIRECTORY_SEPARATOR
    )
    if POSIX_DIRECTORY_SEPARATOR not in normalized_pattern:
        return []
    all_directory_segments: list[str] = []
    for each_segment in normalized_pattern.split(POSIX_DIRECTORY_SEPARATOR):
        if not each_segment:
            continue
        if is_filename_like_path_segment(each_segment):
            continue
        all_directory_segments.append(each_segment.lower())
    return all_directory_segments


def directory_segment_names_from_path_patterns(
    all_path_patterns: Iterable[str],
) -> frozenset[str]:
    """Collect unique directory segment names from path-exemption patterns.

    ::

        directory_segment_names_from_path_patterns({"/tests/", "\\workflow\\", "/cli.py"})
        # frozenset({'tests', 'workflow'})

    Basename markers without a directory token contribute nothing. Adding a
    new ``/foo/`` pattern to an authoritative set surfaces ``foo`` here
    automatically.

    Args:
        all_path_patterns: Path substrings used by exemption or CLI checks.

    Returns:
        Lowercased directory segment names present in the patterns.
    """
    all_segment_names: set[str] = set()
    for each_pattern in all_path_patterns:
        all_segment_names.update(all_directory_segments_in_path_pattern(each_pattern))
    return frozenset(all_segment_names)


def substring_patterns_from_path_patterns(
    all_path_patterns: Iterable[str],
) -> frozenset[str]:
    """Collect separator-free substring patterns from path-exemption patterns.

    ::

        substring_patterns_from_path_patterns({"test_", "/tests/", "conftest"})
        # frozenset({'test_', 'conftest'})

    ``is_test_file`` and its siblings match these fragments anywhere in a path,
    including inside a directory segment name such as ``pkg/test_helpers/``.
    Patterns carrying a separator are directory tokens handled by
    ``directory_segment_names_from_path_patterns`` and are skipped here.

    Args:
        all_path_patterns: Path substrings used by exemption or CLI checks.

    Returns:
        Lowercased separator-free substring patterns.
    """
    all_substring_patterns: set[str] = set()
    for each_pattern in all_path_patterns:
        if (
            POSIX_DIRECTORY_SEPARATOR in each_pattern
            or WINDOWS_DIRECTORY_SEPARATOR in each_pattern
        ):
            continue
        all_substring_patterns.add(each_pattern.lower())
    return frozenset(all_substring_patterns)


ALL_DIRECTORY_SEGMENTS_FROM_PATH_PATTERNS: frozenset[str] = frozenset().union(
    *(
        directory_segment_names_from_path_patterns(each_pattern_set)
        for each_pattern_set in ALL_AUTHORITATIVE_DIRECTORY_PATH_PATTERN_SETS
    )
)

ALL_DIRECTORY_EXEMPTION_SEGMENT_NAMES: frozenset[str] = (
    ALL_CONFIG_DIRECTORY_NAMES | ALL_DIRECTORY_SEGMENTS_FROM_PATH_PATTERNS
)

ALL_DIRECTORY_EXEMPTION_SUBSTRING_PATTERNS: frozenset[str] = frozenset().union(
    *(
        substring_patterns_from_path_patterns(each_pattern_set)
        for each_pattern_set in ALL_AUTHORITATIVE_DIRECTORY_PATH_PATTERN_SETS
    )
)
