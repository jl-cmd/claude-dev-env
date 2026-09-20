"""Build the whole-repository inventory and dependency ledger from `git ls-files`.

The walk reads blobs from the git index, so the output does not depend on the
checkout's line endings. Ship lists are read only to reconcile the `shipped`
column; they never decide which paths are inventoried.

Run the builder with ``python -m tests.audit.build_inventory`` from the
repository root.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

from tests.audit.config.build_inventory_constants import (
    AGENTS_PREFIX,
    AGENT_KIND,
    ALL_BLOB_BATCH_ARGUMENTS,
    ALL_DEPENDENCY_COLUMNS,
    ALL_EXECUTABLE_SUFFIXES,
    ALL_INVENTORY_COLUMNS,
    ALL_JAVASCRIPT_SOURCE_SUFFIXES,
    ALL_LIST_FILES_ARGUMENTS,
    ALL_NAMING_SUBJECT_SUFFIXES,
    ALL_PACKAGE_KIND_BY_PREFIX,
    ALL_PROOF_CLASS_BY_KIND,
    ALL_PROOF_METHOD_BY_CLASS,
    ALL_PROSE_SOURCE_SUFFIXES,
    ALL_ROOT_DOC_BASENAMES,
    ALL_ROOT_MANIFEST_BASENAMES,
    ALL_SETTINGS_MANIFEST_SUFFIXES,
    ALL_TEST_DIRECTORY_MARKERS,
    ALL_TEST_MODULE_SUFFIXES,
    ALL_TEST_SUBJECT_SUFFIXES,
    ALL_TEXT_SUFFIXES,
    ARCHIVED_RULES_PREFIX,
    ARCHIVED_SKILLS_PREFIX,
    ARCHIVE_IN_SHIPPED_PATH_FLAG,
    ARCHIVE_ITEM_KIND,
    ARCHIVE_SUFFIX,
    ASCII_ENCODING,
    BLOB_SIZE_FIELD_INDEX,
    CHANGELOG_BASENAME,
    CHANGELOG_MARKER,
    CI_SUPPORT_KIND,
    CI_WORKFLOW_KIND,
    CLAUDE_HOME_PREFIX,
    CLAUDE_HOOKS_PREFIX,
    CLAUDE_PLUGIN_PREFIX,
    CODE_KINDS,
    CODEX_BASENAME_PREFIX,
    CODEX_PROJECTION_KIND,
    CODEX_RULES_PREFIX,
    COLUMN_SEPARATOR,
    CONFIG_PREFIX,
    CONFTEST_BASENAME,
    CONTENT_DIRECTORIES_DECLARATION,
    CONTEXT_LOADED_KINDS,
    CONTEXT_UNKNOWN_KINDS,
    COVERAGE_FAULT_MESSAGE,
    CURRENT_DIRECTORY_PREFIX,
    CURSOR_DIRECTORY_PREFIX,
    CURSOR_IGNORE_PATH,
    CURSOR_PROJECTION_KIND,
    CURSOR_SKILLS_PREFIX,
    DECODE_ERROR_POLICY,
    DEFAULT_DESTINATION_NAME,
    DEPENDENCY_TABLE_NAME,
    DIGEST_PREFIX_LENGTH,
    DOC_KIND,
    DOCS_PREFIX,
    EXACT_DUPLICATE_FLAG,
    FIELD_SEPARATOR,
    FLAG_DETAIL_SEPARATOR,
    GIT_HOOK_KIND,
    GIT_HOOKS_PREFIX,
    GITHUB_PREFIX,
    HOME_DIRECTORY_PREFIX,
    HOOK_CONSTANTS_SEGMENT,
    HOOK_MODULE_KIND,
    HOOK_SUPPORT_KIND,
    HOOK_UNREGISTERED_FLAG,
    HOOKS_MANIFEST_INNER_PATH,
    HOOKS_PREFIX,
    IMPORTED_NAME,
    IMPORTS_RELATION,
    INSTALLER_INNER_PATH,
    INSTALLS_RELATION,
    INSTRUCTION_BASENAMES,
    INSTRUCTION_FILE_KIND,
    INVENTORY_TABLE_NAME,
    INVOKES_RELATION,
    JAVASCRIPT_IMPORT,
    JAVASCRIPT_INDEX_TAIL,
    JAVASCRIPT_MODULE_SUFFIX,
    JAVASCRIPT_SUFFIX,
    LINE_SEPARATOR,
    MANIFEST_DIRECTORIES_KEY,
    MANIFEST_ROOT_FILES_KEY,
    MAXIMUM_BASENAME_CANDIDATES,
    MAXIMUM_LISTED_DUPLICATES,
    MAXIMUM_LISTED_IMPORTERS,
    MENTION_TOKEN,
    MINIMUM_DUPLICATE_GROUP_SIZE,
    MINIMUM_NAME_MENTION_LENGTH,
    MODULE_INITIALIZER_STEM,
    MODULE_INITIALIZER_TAIL,
    NAME_TOKEN,
    NAME_WORD_SEPARATOR,
    NAMED_COMPONENT_KINDS,
    NEWLINE_BYTE,
    NO_IMPORTER_PLACEHOLDER,
    NON_LIVE_KINDS,
    NUL_BYTE,
    NUL_SEPARATOR,
    NULL_BYTE_SCAN_LENGTH,
    PACKAGE_FILES_KEY,
    PACKAGE_MANIFEST_INNER_PATH,
    PACKAGE_ROOT,
    PARENT_DIRECTORY_PREFIX,
    PARENT_PREFIX_LENGTH,
    PATH_SEPARATOR,
    PROJECTS_RELATION,
    PYTHON_IMPORT,
    PYTHON_SUFFIX,
    QUOTED_ENTRY,
    REACHABILITY_RELATIONS,
    REFERENCES_RELATION,
    REGISTERS_RELATION,
    RELATIVE_PREFIX_LENGTH,
    REPOSITORY_ROOT_PARENT_INDEX,
    ROOT_CONFIG_KIND,
    SHARED_MODULE_KIND,
    SHARED_SKILLS_PREFIX,
    SHIP_NEGATION_MARKER,
    SHIPPED_NO,
    SHIPPED_UNKNOWN,
    SHIPPED_YES,
    SKILL_ARCHIVE_PREFIX,
    SKILL_KIND,
    SKILL_REGISTRY_BASENAME,
    SKILLS_PREFIX,
    SPACE_BYTE,
    SUCCESS_EXIT_CODE,
    SUMMARY_LIST_SEPARATOR,
    SURFACES_MANIFEST_INNER_PATH,
    SETTINGS_MANIFEST_KIND,
    SYMLINK_KIND,
    SYMLINK_MODE,
    SYMLINK_TARGET_MARKER,
    TEST_KIND,
    TEST_MODULE_PREFIX,
    TEST_SUBJECT_GONE_DETAIL,
    TEST_SUBJECT_GONE_FLAG,
    TEST_SUPPORT_SUFFIX,
    TESTS_RELATION,
    UBIQUITOUS_BASENAMES,
    UNREACHABLE_MODULE_FLAG,
    UTF8_ENCODING,
    WORD_SEPARATOR,
    WORKFLOWS_PREFIX,
)


@dataclass(frozen=True)
class TrackedFile:
    path: str
    mode: str
    blob_id: str
    content: bytes


@dataclass
class Component:
    component_id: str
    path: str
    kind: str
    all_files: list[TrackedFile] = field(default_factory=list)


@dataclass(frozen=True)
class ShipLists:
    package_files: tuple[str, ...]
    package_negations: tuple[str, ...]
    manifest_directories: tuple[str, ...]
    manifest_root_files: tuple[str, ...]
    content_directories: tuple[str, ...]


@dataclass(frozen=True)
class Edge:
    source_id: str
    relation: str
    target_id: str


@dataclass(frozen=True)
class Reachability:
    all_live_inbound: dict[str, set[str]]
    all_registered: set[str]
    all_outbound: dict[str, set[str]]


def run_git(
    repository_root: Path, all_arguments: tuple[str, ...], stdin_bytes: bytes | None
) -> bytes:
    """Run one git command inside a repository and return its standard output.

    Args:
        repository_root: Working tree the command runs against.
        all_arguments: Git subcommand and its arguments.
        stdin_bytes: Bytes fed to the command, or None for no input.

    Returns:
        The raw bytes the command wrote to standard output.
    """
    completed = subprocess.run(
        ["git", "-C", str(repository_root), *all_arguments],
        input=stdin_bytes,
        capture_output=True,
        check=True,
    )
    return completed.stdout


def read_index_entries(listing: str) -> list[tuple[str, str, str]]:
    """Parse a NUL-separated `git ls-files -s -z` listing.

    Args:
        listing: Decoded listing text from git.

    Returns:
        One path, mode, and blob identifier triple per tracked file.
    """
    all_entries: list[tuple[str, str, str]] = []
    for each_record in listing.split(NUL_SEPARATOR):
        if not each_record:
            continue
        metadata, entry_path = each_record.split(COLUMN_SEPARATOR, 1)
        entry_mode, entry_blob_id, _stage = metadata.split(FIELD_SEPARATOR)
        all_entries.append((entry_path, entry_mode, entry_blob_id))
    return all_entries


def split_blob_stream(
    blob_stream: bytes, all_entries: list[tuple[str, str, str]]
) -> list[TrackedFile]:
    """Slice a `git cat-file --batch` stream into one tracked file per entry.

    Args:
        blob_stream: Concatenated header and body bytes from git.
        all_entries: Index entries in the order their blobs were requested.

    Returns:
        One tracked file per index entry, in request order.
    """
    all_files: list[TrackedFile] = []
    cursor = 0
    for each_path, each_mode, each_blob_id in all_entries:
        header_end = blob_stream.index(NEWLINE_BYTE, cursor)
        header = blob_stream[cursor:header_end].split(SPACE_BYTE)
        size = int(header[BLOB_SIZE_FIELD_INDEX])
        body_start = header_end + 1
        all_files.append(
            TrackedFile(
                each_path,
                each_mode,
                each_blob_id,
                blob_stream[body_start : body_start + size],
            )
        )
        cursor = body_start + size + 1
    return all_files


def read_tracked_files(repository_root: Path) -> list[TrackedFile]:
    """Read every tracked path and its indexed blob content.

    Args:
        repository_root: Working tree to inventory.

    Returns:
        Every tracked file with its content, sorted by path.
    """
    listing = run_git(repository_root, ALL_LIST_FILES_ARGUMENTS, None).decode(
        UTF8_ENCODING
    )
    all_entries = read_index_entries(listing)
    request = "".join(
        f"{each_blob_id}{LINE_SEPARATOR}" for _path, _mode, each_blob_id in all_entries
    ).encode(ASCII_ENCODING)
    blob_stream = run_git(repository_root, ALL_BLOB_BATCH_ARGUMENTS, request)
    return sorted(
        split_blob_stream(blob_stream, all_entries),
        key=lambda each_file: each_file.path,
    )


def is_test_path(path: str) -> bool:
    """Report whether a repository path belongs to the test surface.

    Args:
        path: Repository-relative POSIX path.

    Returns:
        True when the path names a test module or sits under a test directory.
    """
    basename = posixpath.basename(path)
    if basename.startswith(TEST_MODULE_PREFIX) and basename.endswith(PYTHON_SUFFIX):
        return True
    if (
        basename.endswith(ALL_TEST_MODULE_SUFFIXES)
        or basename == CONFTEST_BASENAME
    ):
        return True
    if basename.endswith(TEST_SUPPORT_SUFFIX):
        return True
    return any(
        each_marker in f"{PATH_SEPARATOR}{path}"
        for each_marker in ALL_TEST_DIRECTORY_MARKERS
    )


def directory_group(path: str, prefix: str) -> str:
    """Return the first directory under a prefix as the component path.

    Args:
        path: Repository-relative POSIX path.
        prefix: Prefix whose immediate child groups the component.

    Returns:
        The prefix joined with the first path segment after it.
    """
    remainder = path[len(prefix) :]
    return prefix + remainder.split(PATH_SEPARATOR, 1)[0]


def package_prefix_kind(inner: str) -> str:
    """Look up the component kind for a package-relative path prefix.

    Args:
        inner: Package-relative POSIX path.

    Returns:
        The matching kind, or an empty string when no prefix matches.
    """
    for each_prefix, each_kind in ALL_PACKAGE_KIND_BY_PREFIX:
        if inner.startswith(each_prefix):
            return each_kind
    return ""


def classify_package_archive(path: str, inner: str) -> tuple[str, str] | None:
    """Classify a package path that sits inside an archive directory.

    Args:
        path: Repository-relative POSIX path.
        inner: Package-relative POSIX path.

    Returns:
        A kind and component path pair, or None when the path is not archived.
    """
    if inner.startswith(ARCHIVED_SKILLS_PREFIX):
        return ARCHIVE_ITEM_KIND, directory_group(
            path, PACKAGE_ROOT + ARCHIVED_SKILLS_PREFIX
        )
    if inner.startswith(ARCHIVED_RULES_PREFIX):
        return ARCHIVE_ITEM_KIND, path
    return None


def classify_package_agent_asset(path: str, inner: str) -> tuple[str, str] | None:
    """Classify a package path that ships a skill, agent, or shared module.

    Args:
        path: Repository-relative POSIX path.
        inner: Package-relative POSIX path.

    Returns:
        A kind and component path pair, or None when no agent asset matches.
    """
    if inner.startswith(SHARED_SKILLS_PREFIX):
        return SHARED_MODULE_KIND, path
    if inner.startswith(SKILLS_PREFIX):
        return SKILL_KIND, directory_group(path, PACKAGE_ROOT + SKILLS_PREFIX)
    if inner.startswith(AGENTS_PREFIX):
        return AGENT_KIND, path
    return None


def classify_package_hook(path: str, inner: str) -> tuple[str, str] | None:
    """Classify a package path that belongs to the hook surface.

    Args:
        path: Repository-relative POSIX path.
        inner: Package-relative POSIX path.

    Returns:
        A kind and component path pair, or None when the path is not a hook.
    """
    if inner == HOOKS_MANIFEST_INNER_PATH:
        return SETTINGS_MANIFEST_KIND, path
    if inner.startswith(GIT_HOOKS_PREFIX):
        return GIT_HOOK_KIND, path
    if not inner.startswith(HOOKS_PREFIX):
        return None
    is_entry_module = (
        inner.endswith(ALL_EXECUTABLE_SUFFIXES)
        and HOOK_CONSTANTS_SEGMENT not in f"{PATH_SEPARATOR}{inner}"
    )
    return (HOOK_MODULE_KIND if is_entry_module else HOOK_SUPPORT_KIND), path


def classify_package_path(path: str, inner: str) -> tuple[str, str]:
    """Classify a path that lives under the installable package root.

    Args:
        path: Repository-relative POSIX path.
        inner: Package-relative POSIX path.

    Returns:
        The component kind and the component path the file groups into.
    """
    basename = posixpath.basename(inner)
    archived = classify_package_archive(path, inner)
    if archived is not None:
        return archived
    if basename in INSTRUCTION_BASENAMES:
        return INSTRUCTION_FILE_KIND, path
    if is_test_path(inner):
        return TEST_KIND, path
    agent_asset = classify_package_agent_asset(path, inner)
    if agent_asset is not None:
        return agent_asset
    hook = classify_package_hook(path, inner)
    if hook is not None:
        return hook
    prefix_kind = package_prefix_kind(inner)
    if prefix_kind:
        return prefix_kind, path
    if basename.startswith(CODEX_BASENAME_PREFIX) or inner.startswith(
        CODEX_RULES_PREFIX
    ):
        return CODEX_PROJECTION_KIND, path
    if basename == CHANGELOG_BASENAME:
        return DOC_KIND, path
    if basename.endswith(ALL_SETTINGS_MANIFEST_SUFFIXES):
        return SETTINGS_MANIFEST_KIND, path
    return ROOT_CONFIG_KIND, path


def classify_archive_path(path: str) -> tuple[str, str] | None:
    """Classify a repository path that holds archived material.

    Args:
        path: Repository-relative POSIX path.

    Returns:
        A kind and component path pair, or None when nothing archived matches.
    """
    if path.startswith(SKILL_ARCHIVE_PREFIX):
        has_directory = PATH_SEPARATOR in path[len(SKILL_ARCHIVE_PREFIX) :]
        grouped = (
            directory_group(path, SKILL_ARCHIVE_PREFIX) if has_directory else path
        )
        return ARCHIVE_ITEM_KIND, grouped
    if posixpath.basename(path).endswith(ARCHIVE_SUFFIX):
        return ARCHIVE_ITEM_KIND, path
    return None


def classify_client_path(path: str, basename: str) -> tuple[str, str] | None:
    """Classify a path owned by an editor, a client, or continuous integration.

    Args:
        path: Repository-relative POSIX path.
        basename: Final path segment.

    Returns:
        A kind and component path pair, or None when no client surface matches.
    """
    if path.startswith(CURSOR_SKILLS_PREFIX) and PATH_SEPARATOR in path[
        len(CURSOR_SKILLS_PREFIX) :
    ]:
        return CURSOR_PROJECTION_KIND, directory_group(path, CURSOR_SKILLS_PREFIX)
    if path.startswith(CURSOR_DIRECTORY_PREFIX) or path == CURSOR_IGNORE_PATH:
        return CURSOR_PROJECTION_KIND, path
    if path.startswith(WORKFLOWS_PREFIX):
        return CI_WORKFLOW_KIND, path
    if path.startswith(GITHUB_PREFIX):
        return CI_SUPPORT_KIND, path
    if path.startswith(CLAUDE_HOOKS_PREFIX):
        is_entry_module = path.endswith(ALL_EXECUTABLE_SUFFIXES)
        return (HOOK_MODULE_KIND if is_entry_module else HOOK_SUPPORT_KIND), path
    if (
        path.startswith((CLAUDE_PLUGIN_PREFIX, CLAUDE_HOME_PREFIX))
        or basename in ALL_ROOT_MANIFEST_BASENAMES
    ):
        return SETTINGS_MANIFEST_KIND, path
    return None


def classify_path(tracked_file: TrackedFile) -> tuple[str, str]:
    """Classify one tracked file into a component kind and component path.

    Args:
        tracked_file: Tracked file with its index mode and content.

    Returns:
        The component kind and the component path the file groups into.
    """
    path = tracked_file.path
    basename = posixpath.basename(path)
    if tracked_file.mode == SYMLINK_MODE:
        return SYMLINK_KIND, path
    archived = classify_archive_path(path)
    if archived is not None:
        return archived
    if path.startswith(PACKAGE_ROOT):
        return classify_package_path(path, path[len(PACKAGE_ROOT) :])
    if basename in INSTRUCTION_BASENAMES:
        return INSTRUCTION_FILE_KIND, path
    if is_test_path(path):
        return TEST_KIND, path
    client = classify_client_path(path, basename)
    if client is not None:
        return client
    if path.startswith(DOCS_PREFIX) or basename in ALL_ROOT_DOC_BASENAMES:
        return DOC_KIND, path
    if path.startswith(CONFIG_PREFIX):
        return CI_SUPPORT_KIND, path
    return ROOT_CONFIG_KIND, path


def build_components(all_files: list[TrackedFile]) -> dict[str, Component]:
    """Group tracked files into components keyed by component identifier.

    Args:
        all_files: Every tracked file in the repository.

    Returns:
        One component per identifier, holding the files that group into it.
    """
    component_by_id: dict[str, Component] = {}
    for each_file in all_files:
        kind, component_path = classify_path(each_file)
        component_id = f"{kind}:{component_path}"
        if component_id not in component_by_id:
            component_by_id[component_id] = Component(
                component_id, component_path, kind
            )
        component_by_id[component_id].all_files.append(each_file)
    return component_by_id


def decode_text(tracked_file: TrackedFile) -> str:
    """Decode a tracked file when its suffix and content look textual.

    Args:
        tracked_file: Tracked file with its index mode and content.

    Returns:
        The decoded text, or an empty string for a binary or unknown suffix.
    """
    suffix = posixpath.splitext(tracked_file.path)[1].lower()
    if suffix not in ALL_TEXT_SUFFIXES:
        return ""
    if NUL_BYTE in tracked_file.content[:NULL_BYTE_SCAN_LENGTH]:
        return ""
    return tracked_file.content.decode(UTF8_ENCODING, errors=DECODE_ERROR_POLICY)


def find_tracked_json(all_files: list[TrackedFile], path: str) -> dict[str, object]:
    """Parse one tracked JSON document into a mapping.

    Args:
        all_files: Every tracked file in the repository.
        path: Repository-relative POSIX path of the document.

    Returns:
        The parsed mapping, or an empty mapping when it is absent or not a map.
    """
    for each_file in all_files:
        if each_file.path == path:
            parsed = json.loads(each_file.content.decode(UTF8_ENCODING))
            return parsed if isinstance(parsed, dict) else {}
    return {}


def string_entries(candidate: object) -> tuple[str, ...]:
    """Keep the string members of a parsed JSON list.

    Args:
        candidate: Parsed JSON member of unknown shape.

    Returns:
        Every string member, or an empty tuple when the member is not a list.
    """
    if not isinstance(candidate, list):
        return ()
    return tuple(each_entry for each_entry in candidate if isinstance(each_entry, str))


def installer_content_directories(all_files: list[TrackedFile]) -> tuple[str, ...]:
    """Read the content directory names the installer script declares.

    Args:
        all_files: Every tracked file in the repository.

    Returns:
        The declared directory names, or an empty tuple when none are declared.
    """
    installer_text = ""
    for each_file in all_files:
        if each_file.path == PACKAGE_ROOT + INSTALLER_INNER_PATH:
            installer_text = decode_text(each_file)
    declaration = CONTENT_DIRECTORIES_DECLARATION.search(installer_text)
    if not declaration:
        return ()
    return tuple(QUOTED_ENTRY.findall(declaration.group(1)))


def read_ship_lists(all_files: list[TrackedFile]) -> ShipLists:
    """Read the package, manifest, and installer ship lists.

    Args:
        all_files: Every tracked file in the repository.

    Returns:
        The three ship lists the shipped column reconciles against.
    """
    package = find_tracked_json(all_files, PACKAGE_ROOT + PACKAGE_MANIFEST_INNER_PATH)
    manifest = find_tracked_json(all_files, PACKAGE_ROOT + SURFACES_MANIFEST_INNER_PATH)
    all_package_entries = string_entries(package.get(PACKAGE_FILES_KEY))
    return ShipLists(
        package_files=tuple(
            each_entry
            for each_entry in all_package_entries
            if not each_entry.startswith(SHIP_NEGATION_MARKER)
        ),
        package_negations=tuple(
            each_entry[1:]
            for each_entry in all_package_entries
            if each_entry.startswith(SHIP_NEGATION_MARKER)
        ),
        manifest_directories=string_entries(manifest.get(MANIFEST_DIRECTORIES_KEY)),
        manifest_root_files=string_entries(manifest.get(MANIFEST_ROOT_FILES_KEY)),
        content_directories=installer_content_directories(all_files),
    )


def matches_ship_entry(inner_path: str, all_entries: tuple[str, ...]) -> bool:
    """Report whether a package-relative path falls under any ship list entry.

    Args:
        inner_path: Package-relative POSIX path.
        all_entries: Ship list entries, as files or directory prefixes.

    Returns:
        True when the path equals an entry or sits under an entry directory.
    """
    for each_entry in all_entries:
        directory = each_entry.rstrip(PATH_SEPARATOR) + PATH_SEPARATOR
        if inner_path == each_entry.rstrip(PATH_SEPARATOR) or inner_path.startswith(
            directory
        ):
            return True
    return False


def shipped_status(component: Component, ship_lists: ShipLists) -> str:
    """Decide whether a component ships with the installable package.

    Args:
        component: Component whose files are checked.
        ship_lists: Ship lists read from the repository.

    Returns:
        The shipped verdict as yes, no, or unknown.
    """
    if not ship_lists.package_files:
        return SHIPPED_UNKNOWN
    if not component.path.startswith(PACKAGE_ROOT):
        return SHIPPED_NO
    all_inner_paths = [
        each_file.path[len(PACKAGE_ROOT) :] for each_file in component.all_files
    ]
    all_verdicts = {
        matches_ship_entry(each_inner, ship_lists.package_files)
        for each_inner in all_inner_paths
    }
    if all_verdicts == {True}:
        return SHIPPED_YES
    return SHIPPED_NO if all_verdicts == {False} else SHIPPED_UNKNOWN


def context_status(component: Component, shipped: str) -> str:
    """Decide whether a component reaches the agent context.

    Args:
        component: Component whose kind decides the verdict.
        shipped: Shipped verdict for the same component.

    Returns:
        The context verdict as yes, no, or unknown.
    """
    if component.kind in CONTEXT_LOADED_KINDS:
        if component.kind == INSTRUCTION_FILE_KIND or shipped == SHIPPED_YES:
            return SHIPPED_YES
        return SHIPPED_UNKNOWN
    if component.kind in CONTEXT_UNKNOWN_KINDS:
        return SHIPPED_UNKNOWN
    return SHIPPED_NO


class MentionIndex:
    """Resolve a path-like token to the components whose files it names."""

    def __init__(self, component_by_id: dict[str, Component]) -> None:
        self.component_id_by_path: dict[str, str] = {}
        self.all_paths_by_basename: dict[str, list[str]] = defaultdict(list)
        self.component_id_by_name: dict[str, str] = {}
        for each_component in component_by_id.values():
            self._index_paths(each_component)
            self._index_name(each_component)

    def _index_paths(self, component: Component) -> None:
        for each_file in component.all_files:
            self.component_id_by_path[each_file.path] = component.component_id
            basename = posixpath.basename(each_file.path)
            self.all_paths_by_basename[basename].append(each_file.path)

    def _index_name(self, component: Component) -> None:
        if component.kind not in NAMED_COMPONENT_KINDS:
            return
        name = posixpath.splitext(posixpath.basename(component.path))[0]
        if len(name) >= MINIMUM_NAME_MENTION_LENGTH and NAME_WORD_SEPARATOR in name:
            self.component_id_by_name[name] = component.component_id

    def resolve_token(self, token: str, source_directory: str) -> set[str]:
        """Resolve one path-like token to the component identifiers it names.

        Args:
            token: Path-like token found in file text.
            source_directory: Directory of the file the token was found in.

        Returns:
            Every component identifier the token resolves to.
        """
        normalized = token.replace("\\", PATH_SEPARATOR).lstrip("@").lstrip(
            PATH_SEPARATOR
        )
        while normalized.startswith(
            (CURRENT_DIRECTORY_PREFIX, HOME_DIRECTORY_PREFIX)
        ):
            normalized = normalized[RELATIVE_PREFIX_LENGTH:]
        basename = posixpath.basename(normalized)
        all_candidates = self.all_paths_by_basename.get(basename)
        if not all_candidates:
            return set()
        nearby = self._resolve_nearby(normalized, source_directory)
        if nearby is not None:
            return nearby
        all_suffix_matches = self._suffix_matches(normalized, all_candidates)
        if all_suffix_matches:
            return all_suffix_matches
        if (
            basename in UBIQUITOUS_BASENAMES
            or len(all_candidates) > MAXIMUM_BASENAME_CANDIDATES
        ):
            return set()
        return {self.component_id_by_path[each_path] for each_path in all_candidates}

    def _resolve_nearby(self, normalized: str, source_directory: str) -> set[str] | None:
        if not normalized.startswith(
            PARENT_DIRECTORY_PREFIX
        ) and PATH_SEPARATOR in normalized:
            return None
        relative = posixpath.normpath(posixpath.join(source_directory, normalized))
        if relative in self.component_id_by_path:
            return {self.component_id_by_path[relative]}
        return None

    def _suffix_matches(self, normalized: str, all_candidates: list[str]) -> set[str]:
        stripped = normalized
        while stripped.startswith(PARENT_DIRECTORY_PREFIX):
            stripped = stripped[PARENT_PREFIX_LENGTH:]
        if PATH_SEPARATOR not in stripped:
            return set()
        return {
            self.component_id_by_path[each_path]
            for each_path in all_candidates
            if f"{PATH_SEPARATOR}{each_path}".endswith(
                f"{PATH_SEPARATOR}{stripped}"
            )
        }


def resolve_python_module(
    module: str, source_path: str, index: MentionIndex
) -> set[str]:
    """Resolve a dotted Python module name to tracked component identifiers.

    Args:
        module: Dotted module name taken from an import statement.
        source_path: Path of the file that holds the import.
        index: Mention index built over every component.

    Returns:
        Every component identifier the module name resolves to.
    """
    all_parts = [each_part for each_part in module.split(".") if each_part]
    if not all_parts:
        return set()
    all_found: set[str] = set()
    joined = PATH_SEPARATOR.join(all_parts)
    for each_tail in (joined + PYTHON_SUFFIX, joined + MODULE_INITIALIZER_TAIL):
        all_found |= module_tail_targets(each_tail, source_path, index)
    return all_found


def module_tail_targets(tail: str, source_path: str, index: MentionIndex) -> set[str]:
    """Resolve one candidate module path tail to component identifiers.

    Args:
        tail: Candidate path tail, such as a module file or package file.
        source_path: Path of the file that holds the import.
        index: Mention index built over every component.

    Returns:
        Every component identifier the tail resolves to.
    """
    basename = posixpath.basename(tail)
    all_matches = [
        each_path
        for each_path in index.all_paths_by_basename.get(basename, [])
        if f"{PATH_SEPARATOR}{each_path}".endswith(f"{PATH_SEPARATOR}{tail}")
    ]
    source_directory = posixpath.dirname(source_path)
    all_nearby = [
        each_path
        for each_path in all_matches
        if posixpath.dirname(each_path).startswith(source_directory)
    ]
    return {
        index.component_id_by_path[each_path]
        for each_path in all_nearby or all_matches
    }


def named_import_targets(
    from_module: str, imported_clause: str, source_path: str, index: MentionIndex
) -> set[str]:
    """Resolve each name in a `from ... import ...` clause to a submodule.

    Args:
        from_module: Dotted module the names are imported from.
        imported_clause: Raw text of the imported name list.
        source_path: Path of the file that holds the import.
        index: Mention index built over every component.

    Returns:
        Every component identifier the imported names resolve to.
    """
    all_targets: set[str] = set()
    for each_name in IMPORTED_NAME.findall(imported_clause):
        all_targets |= resolve_python_module(
            f"{from_module}.{each_name}", source_path, index
        )
    return all_targets


def import_match_targets(
    from_module: str, imported_clause: str, plain_modules: str, source_path: str, index: MentionIndex
) -> set[str]:
    """Resolve the module names captured by one Python import match.

    Args:
        from_module: Dotted module of a `from ... import ...` statement.
        imported_clause: Raw text of the imported name list.
        plain_modules: Comma-separated modules of a plain import statement.
        source_path: Path of the file that holds the import.
        index: Mention index built over every component.

    Returns:
        Every component identifier the import statement resolves to.
    """
    all_targets: set[str] = set()
    if from_module:
        all_targets |= resolve_python_module(from_module, source_path, index)
        all_targets |= named_import_targets(
            from_module, imported_clause, source_path, index
        )
    for each_module in plain_modules.split(FLAG_DETAIL_SEPARATOR):
        all_targets |= resolve_python_module(
            each_module.strip().split(FIELD_SEPARATOR)[0], source_path, index
        )
    return all_targets


def python_import_targets(text: str, source_path: str, index: MentionIndex) -> set[str]:
    """Resolve every Python import in a file to component identifiers.

    Args:
        text: Decoded file text.
        source_path: Path of the file the text came from.
        index: Mention index built over every component.

    Returns:
        Every component identifier the file's imports resolve to.
    """
    all_targets: set[str] = set()
    for each_match in PYTHON_IMPORT.finditer(text):
        from_module, imported_clause, plain_modules = each_match.groups()
        all_targets |= import_match_targets(
            from_module or "",
            imported_clause or "",
            plain_modules or "",
            source_path,
            index,
        )
    return all_targets


def specifier_targets(
    specifier: str, source_directory: str, index: MentionIndex
) -> set[str]:
    """Resolve one relative JavaScript specifier to component identifiers.

    Args:
        specifier: Relative specifier taken from an import or require call.
        source_directory: Directory of the file that holds the specifier.
        index: Mention index built over every component.

    Returns:
        Every component identifier the specifier resolves to.
    """
    resolved = posixpath.normpath(posixpath.join(source_directory, specifier))
    all_targets: set[str] = set()
    for each_candidate in (
        resolved,
        resolved + JAVASCRIPT_MODULE_SUFFIX,
        resolved + JAVASCRIPT_SUFFIX,
        resolved + JAVASCRIPT_INDEX_TAIL,
    ):
        if each_candidate in index.component_id_by_path:
            all_targets.add(index.component_id_by_path[each_candidate])
    return all_targets


def javascript_import_targets(
    text: str, source_path: str, index: MentionIndex
) -> set[str]:
    """Resolve every relative JavaScript import in a file.

    Args:
        text: Decoded file text.
        source_path: Path of the file the text came from.
        index: Mention index built over every component.

    Returns:
        Every component identifier the file's imports resolve to.
    """
    source_directory = posixpath.dirname(source_path)
    all_targets: set[str] = set()
    for each_specifier in JAVASCRIPT_IMPORT.findall(text):
        all_targets |= specifier_targets(each_specifier, source_directory, index)
    return all_targets


def is_registry(component: Component) -> bool:
    """Report whether a component registers other components.

    Args:
        component: Component to classify.

    Returns:
        True for a settings manifest or the shipped-skill registry script.
    """
    return component.kind == SETTINGS_MANIFEST_KIND or component.path.endswith(
        SKILL_REGISTRY_BASENAME
    )


def mention_relation(source: Component, source_path: str, target: Component) -> str:
    """Name the edge relation a mention creates between two components.

    Args:
        source: Component that holds the mention.
        source_path: Path of the mentioning file.
        target: Component the mention resolves to.

    Returns:
        The relation name for the mention edge.
    """
    if is_registry(source):
        return REGISTERS_RELATION
    if source.kind in {CODEX_PROJECTION_KIND, CURSOR_PROJECTION_KIND}:
        return PROJECTS_RELATION
    target_is_executable = target.path.endswith(ALL_EXECUTABLE_SUFFIXES)
    if target_is_executable and source_path.endswith(ALL_PROSE_SOURCE_SUFFIXES):
        return INVOKES_RELATION
    return REFERENCES_RELATION


def test_subject_stems(test_path: str) -> list[str]:
    """Derive the subject name a test module names in its filename.

    Args:
        test_path: Repository-relative POSIX path of a test module.

    Returns:
        The single subject stem, or an empty list for an unnamed test module.
    """
    basename = posixpath.basename(test_path)
    for each_suffix in ALL_TEST_SUBJECT_SUFFIXES:
        if basename.endswith(each_suffix):
            return [basename[: -len(each_suffix)]]
    if basename.startswith(TEST_MODULE_PREFIX) and basename.endswith(PYTHON_SUFFIX):
        return [basename[len(TEST_MODULE_PREFIX) : -len(PYTHON_SUFFIX)]]
    return []


def prefix_subjects(prefix: str, index: MentionIndex) -> set[str]:
    """Find non-test components whose basename matches a stem prefix.

    Args:
        prefix: Stem prefix without a file suffix.
        index: Mention index built over every component.

    Returns:
        Every non-test component identifier the prefix names.
    """
    all_subjects: set[str] = set()
    for each_extension in ALL_NAMING_SUBJECT_SUFFIXES:
        all_subjects |= {
            index.component_id_by_path[each_path]
            for each_path in index.all_paths_by_basename.get(
                prefix + each_extension, []
            )
            if not is_test_path(each_path)
        }
    return all_subjects


def stem_prefix_subjects(stem: str, index: MentionIndex) -> set[str]:
    """Find the subjects the longest matching prefix of a stem names.

    Args:
        stem: Subject stem taken from a test module filename.
        index: Mention index built over every component.

    Returns:
        The subjects of the longest prefix that names any, else an empty set.
    """
    all_words = stem.split(WORD_SEPARATOR)
    all_subjects: set[str] = set()
    for each_length in range(len(all_words), 0, -1):
        prefix = WORD_SEPARATOR.join(all_words[:each_length])
        all_subjects |= prefix_subjects(prefix, index)
        if all_subjects:
            return all_subjects
    return all_subjects


def naming_subjects(test_path: str, index: MentionIndex) -> set[str]:
    """Find the components a test module names through its filename.

    Args:
        test_path: Repository-relative POSIX path of a test module.
        index: Mention index built over every component.

    Returns:
        Every component identifier the test module names.
    """
    all_subjects: set[str] = set()
    for each_stem in test_subject_stems(test_path):
        all_subjects |= stem_prefix_subjects(each_stem, index)
        if all_subjects:
            return all_subjects
    return all_subjects


def symlink_edges(
    source_id: str, file_path: str, target_text: str, index: MentionIndex
) -> set[Edge]:
    """Build the projection edges a symlink creates into its target tree.

    Args:
        source_id: Component identifier of the symlink.
        file_path: Repository-relative POSIX path of the symlink.
        target_text: Symlink target as stored in the blob.
        index: Mention index built over every component.

    Returns:
        One projection edge per component under the symlink target.
    """
    target_directory = posixpath.normpath(
        posixpath.join(posixpath.dirname(file_path), target_text.strip())
    )
    return {
        Edge(source_id, PROJECTS_RELATION, each_target_id)
        for each_path, each_target_id in index.component_id_by_path.items()
        if each_path.startswith(target_directory + PATH_SEPARATOR)
    }


def import_targets(text: str, source_path: str, index: MentionIndex) -> set[str]:
    """Resolve the imports of one file, by language.

    Args:
        text: Decoded file text.
        source_path: Path of the file the text came from.
        index: Mention index built over every component.

    Returns:
        Every component identifier the file's imports resolve to.
    """
    if source_path.endswith(PYTHON_SUFFIX):
        return python_import_targets(text, source_path, index)
    if source_path.endswith(ALL_JAVASCRIPT_SOURCE_SUFFIXES):
        return javascript_import_targets(text, source_path, index)
    return set()


def mention_edges(
    component: Component,
    file_path: str,
    text: str,
    index: MentionIndex,
    component_by_id: dict[str, Component],
    all_import_targets: set[str],
) -> set[Edge]:
    """Build the edges the path-like tokens in a file create.

    Args:
        component: Component that holds the file.
        file_path: Repository-relative POSIX path of the file.
        text: Decoded file text.
        index: Mention index built over every component.
        component_by_id: Every component keyed by identifier.
        all_import_targets: Identifiers already covered by import edges.

    Returns:
        One mention edge per resolved token that is not already imported.
    """
    source_directory = posixpath.dirname(file_path)
    all_target_ids: set[str] = set()
    for each_token in set(MENTION_TOKEN.findall(text)):
        all_target_ids |= index.resolve_token(each_token, source_directory)
    return {
        Edge(
            component.component_id,
            mention_relation(component, file_path, component_by_id[each_target_id]),
            each_target_id,
        )
        for each_target_id in all_target_ids - all_import_targets
    }


def name_edges(
    component: Component,
    file_path: str,
    text: str,
    index: MentionIndex,
    component_by_id: dict[str, Component],
) -> set[Edge]:
    """Build the edges that bare component names in a file create.

    Args:
        component: Component that holds the file.
        file_path: Repository-relative POSIX path of the file.
        text: Decoded file text.
        index: Mention index built over every component.
        component_by_id: Every component keyed by identifier.

    Returns:
        One edge per named skill, agent, or command the text mentions.
    """
    all_names = set(NAME_TOKEN.findall(text)) & index.component_id_by_name.keys()
    return {
        Edge(
            component.component_id,
            mention_relation(
                component,
                file_path,
                component_by_id[index.component_id_by_name[each_name]],
            ),
            index.component_id_by_name[each_name],
        )
        for each_name in all_names
    }


def file_edges(
    component: Component,
    tracked_file: TrackedFile,
    index: MentionIndex,
    component_by_id: dict[str, Component],
) -> set[Edge]:
    """Build every outbound edge one tracked file creates.

    Args:
        component: Component that holds the file.
        tracked_file: Tracked file with its index mode and content.
        index: Mention index built over every component.
        component_by_id: Every component keyed by identifier.

    Returns:
        Every edge the file's symlink target, imports, and mentions create.
    """
    text = decode_text(tracked_file)
    if tracked_file.mode == SYMLINK_MODE:
        return symlink_edges(component.component_id, tracked_file.path, text, index)
    if not text:
        return set()
    all_import_targets = import_targets(text, tracked_file.path, index)
    all_edges = {
        Edge(component.component_id, IMPORTS_RELATION, each_target_id)
        for each_target_id in all_import_targets
    }
    all_edges |= mention_edges(
        component, tracked_file.path, text, index, component_by_id, all_import_targets
    )
    all_edges |= name_edges(
        component, tracked_file.path, text, index, component_by_id
    )
    if component.kind == TEST_KIND:
        all_edges |= {
            Edge(component.component_id, TESTS_RELATION, each_subject_id)
            for each_subject_id in naming_subjects(tracked_file.path, index)
        }
    return all_edges


def installer_edges(
    index: MentionIndex,
    component_by_id: dict[str, Component],
    ship_lists: ShipLists,
) -> set[Edge]:
    """Build the install edges from the installer script to shipped content.

    Args:
        index: Mention index built over every component.
        component_by_id: Every component keyed by identifier.
        ship_lists: Ship lists read from the repository.

    Returns:
        One install edge per component under a declared content directory.
    """
    installer_id = index.component_id_by_path.get(PACKAGE_ROOT + INSTALLER_INNER_PATH)
    if not installer_id:
        return set()
    return {
        Edge(installer_id, INSTALLS_RELATION, each_component.component_id)
        for each_component in component_by_id.values()
        if each_component.path.startswith(PACKAGE_ROOT)
        and matches_ship_entry(
            each_component.path[len(PACKAGE_ROOT) :], ship_lists.content_directories
        )
    }


def build_edges(
    component_by_id: dict[str, Component], ship_lists: ShipLists
) -> set[Edge]:
    """Build the dependency ledger for every component.

    Args:
        component_by_id: Every component keyed by identifier.
        ship_lists: Ship lists read from the repository.

    Returns:
        Every edge between two distinct components.
    """
    index = MentionIndex(component_by_id)
    all_edges: set[Edge] = set()
    for each_component in component_by_id.values():
        for each_file in each_component.all_files:
            all_edges |= file_edges(each_component, each_file, index, component_by_id)
    all_edges |= installer_edges(index, component_by_id, ship_lists)
    return {
        each_edge
        for each_edge in all_edges
        if each_edge.source_id != each_edge.target_id
    }


def count_lines(component: Component) -> int:
    """Count the lines across every file of a component.

    Args:
        component: Component whose files are counted.

    Returns:
        The line count, counting a trailing partial line as one line.
    """
    return sum(
        each_file.content.count(NEWLINE_BYTE)
        + (
            1
            if each_file.content and not each_file.content.endswith(NEWLINE_BYTE)
            else 0
        )
        for each_file in component.all_files
    )


def registrar_paths(
    all_edges: set[Edge], component_by_id: dict[str, Component]
) -> dict[str, set[str]]:
    """Collect the registering file paths for each registered component.

    Args:
        all_edges: Every edge in the dependency ledger.
        component_by_id: Every component keyed by identifier.

    Returns:
        The registrar paths keyed by registered component identifier.
    """
    all_registrars: dict[str, set[str]] = defaultdict(set)
    for each_edge in all_edges:
        if each_edge.relation == REGISTERS_RELATION:
            all_registrars[each_edge.target_id].add(
                component_by_id[each_edge.source_id].path
            )
    return all_registrars


def inventory_row(
    component_id: str,
    component: Component,
    all_registrars: dict[str, set[str]],
    ship_lists: ShipLists,
) -> tuple[str, ...]:
    """Build one inventory table row for a component.

    Args:
        component_id: Identifier of the component.
        component: Component the row describes.
        all_registrars: Registrar paths keyed by component identifier.
        ship_lists: Ship lists read from the repository.

    Returns:
        The row fields in inventory column order.
    """
    proof_class = ALL_PROOF_CLASS_BY_KIND[component.kind]
    shipped = shipped_status(component, ship_lists)
    registered_in = SUMMARY_LIST_SEPARATOR.join(sorted(all_registrars[component_id]))
    if component.kind == SYMLINK_KIND:
        target_text = component.all_files[0].content.decode(UTF8_ENCODING).strip()
        registered_in = SYMLINK_TARGET_MARKER + target_text
    return (
        component_id,
        component.path,
        component.kind,
        proof_class,
        shipped,
        context_status(component, shipped),
        registered_in,
        str(sum(len(each_file.content) for each_file in component.all_files)),
        str(count_lines(component)),
        ALL_PROOF_METHOD_BY_CLASS[proof_class],
        "",
    )


def inventory_rows(
    component_by_id: dict[str, Component], all_edges: set[Edge], ship_lists: ShipLists
) -> list[tuple[str, ...]]:
    """Build the inventory table rows in component identifier order.

    Args:
        component_by_id: Every component keyed by identifier.
        all_edges: Every edge in the dependency ledger.
        ship_lists: Ship lists read from the repository.

    Returns:
        One inventory row per component, sorted by identifier.
    """
    all_registrars = registrar_paths(all_edges, component_by_id)
    return [
        inventory_row(each_id, component_by_id[each_id], all_registrars, ship_lists)
        for each_id in sorted(component_by_id)
    ]


def is_live_source(component: Component) -> bool:
    """Report whether a component counts as a live reachability source.

    Args:
        component: Component to classify.

    Returns:
        True for a component outside the test and archive surfaces.
    """
    return (
        component.kind not in NON_LIVE_KINDS
        and CHANGELOG_MARKER not in component.path
    )


def edge_reachability(
    all_edges: set[Edge], component_by_id: dict[str, Component]
) -> Reachability:
    """Summarize inbound, outbound, and registration reach per component.

    Args:
        all_edges: Every edge in the dependency ledger.
        component_by_id: Every component keyed by identifier.

    Returns:
        The live inbound sources, registered targets, and outbound targets.
    """
    all_live_inbound: dict[str, set[str]] = defaultdict(set)
    all_registered: set[str] = set()
    all_outbound: dict[str, set[str]] = defaultdict(set)
    for each_edge in all_edges:
        all_outbound[each_edge.source_id].add(each_edge.target_id)
        is_live = each_edge.relation in REACHABILITY_RELATIONS and is_live_source(
            component_by_id[each_edge.source_id]
        )
        if not is_live:
            continue
        all_live_inbound[each_edge.target_id].add(each_edge.source_id)
        if each_edge.relation == REGISTERS_RELATION:
            all_registered.add(each_edge.target_id)
    return Reachability(all_live_inbound, all_registered, all_outbound)


def is_unreachable_module(
    component_id: str, component: Component, reachability: Reachability
) -> bool:
    """Report whether a code component has no live inbound edge.

    Args:
        component_id: Identifier of the component.
        component: Component to classify.
        reachability: Reach summary for the whole ledger.

    Returns:
        True when an executable code component has no live inbound edge.
    """
    return (
        component.kind in CODE_KINDS
        and component.path.endswith(ALL_EXECUTABLE_SUFFIXES)
        and not reachability.all_live_inbound[component_id]
        and MODULE_INITIALIZER_STEM not in component_id
    )


def is_unregistered_hook(
    component_id: str, component: Component, reachability: Reachability
) -> bool:
    """Report whether a hook module is missing from every registration file.

    Args:
        component_id: Identifier of the component.
        component: Component to classify.
        reachability: Reach summary for the whole ledger.

    Returns:
        True when a hook module carries no registration edge.
    """
    return (
        component.kind == HOOK_MODULE_KIND
        and component_id not in reachability.all_registered
        and MODULE_INITIALIZER_STEM not in component_id
    )


def has_lost_test_subject(
    component_id: str,
    component: Component,
    reachability: Reachability,
    component_by_id: dict[str, Component],
) -> bool:
    """Report whether a named test module resolves to no non-test component.

    Args:
        component_id: Identifier of the component.
        component: Component to classify.
        reachability: Reach summary for the whole ledger.
        component_by_id: Every component keyed by identifier.

    Returns:
        True when a named test module has no non-test outbound target.
    """
    if component.kind != TEST_KIND:
        return False
    if not test_subject_stems(component.path):
        return False
    return not any(
        component_by_id[each_target].kind != TEST_KIND
        for each_target in reachability.all_outbound[component_id]
    )


def component_flags(
    component_id: str,
    component: Component,
    reachability: Reachability,
    component_by_id: dict[str, Component],
    ship_lists: ShipLists,
) -> list[tuple[str, str, str]]:
    """Collect the removal flags one component earns.

    Args:
        component_id: Identifier of the component.
        component: Component to inspect.
        reachability: Reach summary for the whole ledger.
        component_by_id: Every component keyed by identifier.
        ship_lists: Ship lists read from the repository.

    Returns:
        One flag name, component identifier, and detail triple per finding.
    """
    shipped = shipped_status(component, ship_lists)
    all_flags: list[tuple[str, str, str]] = []
    if is_unreachable_module(component_id, component, reachability):
        detail = f"no inbound live edge; registered=no; shipped={shipped}"
        all_flags.append((UNREACHABLE_MODULE_FLAG, component_id, detail))
    if is_unregistered_hook(component_id, component, reachability):
        all_importers = (
            FLAG_DETAIL_SEPARATOR.join(
                sorted(reachability.all_live_inbound[component_id])[
                    :MAXIMUM_LISTED_IMPORTERS
                ]
            )
            or NO_IMPORTER_PLACEHOLDER
        )
        detail = (
            f"no hooks.json or settings registration; live inbound: {all_importers}"
        )
        all_flags.append((HOOK_UNREGISTERED_FLAG, component_id, detail))
    if component.kind == ARCHIVE_ITEM_KIND and shipped != SHIPPED_NO:
        detail = f"shipped={shipped} through package.json files"
        all_flags.append((ARCHIVE_IN_SHIPPED_PATH_FLAG, component_id, detail))
    if has_lost_test_subject(component_id, component, reachability, component_by_id):
        all_flags.append(
            (TEST_SUBJECT_GONE_FLAG, component_id, TEST_SUBJECT_GONE_DETAIL)
        )
    return all_flags


def record_blob_digests(
    component: Component, all_paths_by_digest: dict[str, list[str]]
) -> None:
    """Record each non-blank file of a component under its content digest.

    Args:
        component: Component whose files are digested.
        all_paths_by_digest: Accumulator keyed by content digest.
    """
    for each_file in component.all_files:
        if each_file.content.strip():
            digest = hashlib.sha256(each_file.content).hexdigest()
            all_paths_by_digest[digest].append(each_file.path)


def duplicate_flags(
    all_paths_by_digest: dict[str, list[str]]
) -> list[tuple[str, str, str]]:
    """Flag every content digest shared by more than one tracked file.

    Args:
        all_paths_by_digest: Tracked paths keyed by content digest.

    Returns:
        One duplicate flag triple per shared digest.
    """
    all_flags: list[tuple[str, str, str]] = []
    for each_digest, each_path_group in all_paths_by_digest.items():
        if len(each_path_group) < MINIMUM_DUPLICATE_GROUP_SIZE:
            continue
        listed = SUMMARY_LIST_SEPARATOR.join(
            each_path_group[1:MAXIMUM_LISTED_DUPLICATES]
        )
        detail = (
            f"sha256 {each_digest[:DIGEST_PREFIX_LENGTH]} "
            f"x{len(each_path_group)}: {listed}"
        )
        all_flags.append((EXACT_DUPLICATE_FLAG, each_path_group[0], detail))
    return all_flags


def removal_flags(
    component_by_id: dict[str, Component], all_edges: set[Edge], ship_lists: ShipLists
) -> list[tuple[str, str, str]]:
    """Collect every removal flag the inventory raises, in sorted order.

    Args:
        component_by_id: Every component keyed by identifier.
        all_edges: Every edge in the dependency ledger.
        ship_lists: Ship lists read from the repository.

    Returns:
        One flag name, subject, and detail triple per finding, sorted.
    """
    reachability = edge_reachability(all_edges, component_by_id)
    all_flags: list[tuple[str, str, str]] = []
    all_paths_by_digest: dict[str, list[str]] = defaultdict(list)
    for each_id, each_component in component_by_id.items():
        all_flags.extend(
            component_flags(
                each_id, each_component, reachability, component_by_id, ship_lists
            )
        )
        record_blob_digests(each_component, all_paths_by_digest)
    all_flags.extend(duplicate_flags(all_paths_by_digest))
    return sorted(all_flags)


def list_disagreements(
    all_package_entries: set[str], all_manifest_entries: set[str]
) -> list[str]:
    """Report each entry that only one of the two ship lists names.

    Args:
        all_package_entries: Entries from the package manifest files list.
        all_manifest_entries: Entries from the installable surfaces manifest.

    Returns:
        One sentence per entry missing from the other list.
    """
    all_mismatches = [
        f"package.json files lists '{each_entry}'; "
        "installable-surfaces manifest does not"
        for each_entry in sorted(all_package_entries - all_manifest_entries)
    ]
    all_mismatches += [
        f"installable-surfaces manifest lists '{each_entry}'; "
        "package.json files does not"
        for each_entry in sorted(all_manifest_entries - all_package_entries)
    ]
    return all_mismatches


def unbacked_entries(all_entries: set[str], all_inner_paths: list[str]) -> list[str]:
    """Report each ship list entry that no tracked file sits under.

    Args:
        all_entries: Every ship list entry across the three lists.
        all_inner_paths: Package-relative paths of every tracked package file.

    Returns:
        One sentence per entry with no tracked file beneath it.
    """
    return [
        f"ship list names '{each_entry}'; no tracked file sits under it"
        for each_entry in sorted(all_entries)
        if not matches_ship_entry(each_entry, tuple(all_inner_paths))
        and not any(
            each_inner == each_entry
            or each_inner.startswith(each_entry + PATH_SEPARATOR)
            for each_inner in all_inner_paths
        )
    ]


def unlisted_top_levels(
    all_package_entries: set[str], all_inner_paths: list[str]
) -> list[str]:
    """Report each tracked top-level directory the package list omits.

    Args:
        all_package_entries: Entries from the package manifest files list.
        all_inner_paths: Package-relative paths of every tracked package file.

    Returns:
        One sentence per top-level directory outside the package files list.
    """
    all_top_levels = {
        each_inner.split(PATH_SEPARATOR, 1)[0] for each_inner in all_inner_paths
    }
    return [
        f"tracked top-level '{each_top}' is outside package.json files"
        for each_top in sorted(all_top_levels)
        if not matches_ship_entry(each_top, tuple(all_package_entries))
        and not any(
            each_entry.startswith(each_top + PATH_SEPARATOR)
            for each_entry in all_package_entries
        )
    ]


def ship_list_mismatches(
    ship_lists: ShipLists, all_files: list[TrackedFile]
) -> list[str]:
    """Reconcile the ship lists against each other and against tracked files.

    Args:
        ship_lists: Ship lists read from the repository.
        all_files: Every tracked file in the repository.

    Returns:
        One sentence per mismatch, in reporting order.
    """
    all_package_entries = {
        each_entry.rstrip(PATH_SEPARATOR) for each_entry in ship_lists.package_files
    }
    all_manifest_entries = set(ship_lists.manifest_directories) | set(
        ship_lists.manifest_root_files
    )
    all_inner_paths = [
        each_file.path[len(PACKAGE_ROOT) :]
        for each_file in all_files
        if each_file.path.startswith(PACKAGE_ROOT)
    ]
    all_named_entries = (
        all_package_entries
        | all_manifest_entries
        | set(ship_lists.content_directories)
    )
    all_mismatches = list_disagreements(all_package_entries, all_manifest_entries)
    all_mismatches += unbacked_entries(all_named_entries, all_inner_paths)
    all_mismatches += unlisted_top_levels(all_package_entries, all_inner_paths)
    return all_mismatches


def render_table(
    all_columns: tuple[str, ...], all_rows: list[tuple[str, ...]]
) -> bytes:
    """Render a header and rows as a tab-separated table.

    Args:
        all_columns: Column names for the header line.
        all_rows: Row fields in column order.

    Returns:
        The encoded table, with a trailing newline.
    """
    all_lines = [COLUMN_SEPARATOR.join(all_columns)] + [
        COLUMN_SEPARATOR.join(each_row) for each_row in all_rows
    ]
    return (LINE_SEPARATOR.join(all_lines) + LINE_SEPARATOR).encode(UTF8_ENCODING)


def verify_coverage(
    component_by_id: dict[str, Component], all_files: list[TrackedFile]
) -> None:
    """Check that every tracked file landed in exactly one component.

    Args:
        component_by_id: Every component keyed by identifier.
        all_files: Every tracked file in the repository.

    Raises:
        SystemExit: When the component files and the tracked paths differ.
    """
    all_mapped_paths = [
        each_file.path
        for each_component in component_by_id.values()
        for each_file in each_component.all_files
    ]
    if sorted(all_mapped_paths) != [each_file.path for each_file in all_files]:
        raise SystemExit(COVERAGE_FAULT_MESSAGE)


def write_tables(
    destination_directory: Path,
    component_by_id: dict[str, Component],
    all_edges: set[Edge],
    ship_lists: ShipLists,
) -> None:
    """Write the inventory and dependency tables into a directory.

    Args:
        destination_directory: Directory the tables are written into.
        component_by_id: Every component keyed by identifier.
        all_edges: Every edge in the dependency ledger.
        ship_lists: Ship lists read from the repository.
    """
    destination_directory.mkdir(parents=True, exist_ok=True)
    (destination_directory / INVENTORY_TABLE_NAME).write_bytes(
        render_table(
            ALL_INVENTORY_COLUMNS,
            inventory_rows(component_by_id, all_edges, ship_lists),
        )
    )
    all_edge_rows = sorted(
        (each_edge.source_id, each_edge.relation, each_edge.target_id)
        for each_edge in all_edges
    )
    (destination_directory / DEPENDENCY_TABLE_NAME).write_bytes(
        render_table(ALL_DEPENDENCY_COLUMNS, all_edge_rows)
    )


def report_lines(
    component_by_id: dict[str, Component],
    all_edges: set[Edge],
    ship_lists: ShipLists,
    all_files: list[TrackedFile],
) -> list[str]:
    """Build the counts, ship list mismatches, and removal flags report.

    Args:
        component_by_id: Every component keyed by identifier.
        all_edges: Every edge in the dependency ledger.
        ship_lists: Ship lists read from the repository.
        all_files: Every tracked file in the repository.

    Returns:
        One report line per count, mismatch, and removal flag.
    """
    all_report_lines = [
        f"files{COLUMN_SEPARATOR}{len(all_files)}",
        f"components{COLUMN_SEPARATOR}{len(component_by_id)}",
        f"edges{COLUMN_SEPARATOR}{len(all_edges)}",
    ]
    all_report_lines += [
        f"mismatch{COLUMN_SEPARATOR}{each_line}"
        for each_line in ship_list_mismatches(ship_lists, all_files)
    ]
    all_report_lines += [
        COLUMN_SEPARATOR.join(each_flag)
        for each_flag in removal_flags(component_by_id, all_edges, ship_lists)
    ]
    return all_report_lines


def build(repository_root: Path, destination_directory: Path) -> list[str]:
    """Build the inventory tables and return the run report.

    Args:
        repository_root: Working tree to inventory.
        destination_directory: Directory the tables are written into.

    Returns:
        One report line per count, mismatch, and removal flag.
    """
    all_files = read_tracked_files(repository_root)
    component_by_id = build_components(all_files)
    ship_lists = read_ship_lists(all_files)
    all_edges = build_edges(component_by_id, ship_lists)
    verify_coverage(component_by_id, all_files)
    write_tables(destination_directory, component_by_id, all_edges, ship_lists)
    return report_lines(component_by_id, all_edges, ship_lists, all_files)


def main(stream: TextIO = sys.stdout) -> int:
    """Parse the command line, build the tables, and print the report.

    Args:
        stream: Text stream the report lines are written to.

    Returns:
        The process exit code.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    default_root = Path(__file__).resolve().parents[REPOSITORY_ROOT_PARENT_INDEX]
    parser.add_argument("--repository-root", type=Path, default=default_root)
    parser.add_argument(
        "--output-directory",
        dest="destination_directory",
        type=Path,
        default=Path(__file__).resolve().parent / DEFAULT_DESTINATION_NAME,
    )
    arguments = parser.parse_args()
    sys.stdout.reconfigure(encoding=UTF8_ENCODING)
    for each_line in build(
        arguments.repository_root, arguments.destination_directory
    ):
        stream.write(f"{each_line}{LINE_SEPARATOR}")
    return SUCCESS_EXIT_CODE


if __name__ == "__main__":
    raise SystemExit(main())
