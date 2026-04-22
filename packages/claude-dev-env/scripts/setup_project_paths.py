#!/usr/bin/env python3
"""One-time bootstrap: discover git repos via es.exe and write ~/.claude/project-paths.json.

Invokes Everything's command-line binary (es.exe) with a folders-only query to
locate ``.git`` directories across all indexed locations, applies final-segment
and exclusion filters, presents the discovered mapping to the user, and writes the
approved entries to the per-user config file. Never hardcodes scan roots —
discovery runs against whatever es.exe returns on the local machine.
"""

from __future__ import annotations

import datetime
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

_hooks_dir = Path(__file__).resolve().parent.parent / "hooks"
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

from config.project_paths_reader import registry_file_path
from config.setup_project_paths_constants import (
    ABORTED_NOTHING_WRITTEN_MESSAGE,
    CONFIRMATION_PROMPT_TEXT,
    ES_EXE_BINARY_NAME,
    ES_EXE_FOLDERS_ONLY_QUERY_ARGUMENTS,
    EXCLUDED_PATH_SEGMENTS,
    GIT_DIRECTORY_SEGMENT_NAME,
    JSON_INDENT_SPACES,
    META_KEY,
    STDERR_TRUNCATION_LENGTH,
    SUPPORTED_SCHEMA_VERSION,
    UTF8_ENCODING,
    WROTE_ENTRIES_STATUS_TEMPLATE,
)


class SchemaMismatchError(Exception):
    """Raised when the on-disk config declares a schema newer than this script supports."""


class RegistryReadError(Exception):
    """Raised when an existing registry file is unreadable or corrupt."""


class EverythingScanError(Exception):
    """Raised when es.exe returns a non-zero exit code during the folder scan."""


def _split_path_segments(path_string: str) -> list[str]:
    normalized = path_string.replace("\\", "/")
    return [each_segment for each_segment in normalized.split("/") if each_segment]


def _final_segment(path_string: str) -> str:
    all_segments = _split_path_segments(path_string)
    if not all_segments:
        return ""
    return all_segments[-1]


def _parent_of_git_directory(git_directory_path: str) -> str:
    normalized = git_directory_path.replace("\\", "/").rstrip("/")
    last_slash_index = normalized.rfind("/")
    if last_slash_index < 0:
        return ""
    original_separator_kind = "\\" if "\\" in git_directory_path else "/"
    parent_with_forward_slashes = normalized[:last_slash_index]
    if original_separator_kind == "\\":
        return parent_with_forward_slashes.replace("/", "\\")
    return parent_with_forward_slashes


def filter_to_git_roots(all_es_exe_paths: list[str]) -> list[str]:
    """Return repo-root paths for only those entries whose final segment is exactly ``.git``.

    Rejects siblings like ``.gitignore``, ``.github``, ``.gitattributes`` that
    share the ``.git`` prefix but are not the canonical git metadata directory.
    """
    all_repo_roots: list[str] = []
    for each_es_path in all_es_exe_paths:
        if _final_segment(each_es_path).lower() != GIT_DIRECTORY_SEGMENT_NAME:
            continue
        parent_repo_root = _parent_of_git_directory(each_es_path)
        if parent_repo_root:
            all_repo_roots.append(parent_repo_root)
    return all_repo_roots


def apply_exclusion_filter(all_candidate_paths: list[str]) -> list[str]:
    """Drop paths whose any whole segment matches an excluded name (case-insensitive).

    Whole-segment matching preserves legitimate names that merely contain an
    excluded substring (for example ``template`` is retained even though
    ``temp`` is excluded).
    """
    all_retained_paths: list[str] = []
    for each_candidate_path in all_candidate_paths:
        all_lowercased_segments = [
            each_segment.lower()
            for each_segment in _split_path_segments(each_candidate_path)
        ]
        is_excluded = any(
            each_segment in EXCLUDED_PATH_SEGMENTS
            for each_segment in all_lowercased_segments
        )
        if not is_excluded:
            all_retained_paths.append(each_candidate_path)
    return all_retained_paths


def _current_iso_timestamp_utc() -> str:
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    formatted = now_utc.strftime("%Y-%m-%dT%H:%M:%S")
    iso_utc_suffix = "Z"
    return formatted + iso_utc_suffix


def merge_registries(
    existing_registry: dict,
    new_path_by_name: dict[str, str],
) -> dict:
    """Merge newly discovered entries into the existing registry.

    Pre-existing entries not in the new set are preserved. On name collisions
    the newly discovered entry wins. The ``_meta.last_scan`` timestamp is
    refreshed to the current UTC time.
    """
    merged_registry: dict = {
        each_key: each_value
        for each_key, each_value in existing_registry.items()
        if each_key != META_KEY
    }
    for each_name, each_path in new_path_by_name.items():
        merged_registry[each_name] = each_path
    merged_registry[META_KEY] = {
        "schema_version": SUPPORTED_SCHEMA_VERSION,
        "last_scan": _current_iso_timestamp_utc(),
    }
    return merged_registry


def _read_existing_registry(target_file: Path) -> dict:
    if not target_file.is_file():
        return {}
    try:
        raw_text = target_file.read_text(encoding=UTF8_ENCODING)
    except OSError as read_error:
        raise RegistryReadError(
            f"Cannot read registry at {target_file}: {read_error}"
        ) from read_error
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as decode_error:
        raise RegistryReadError(
            f"Malformed JSON in registry at {target_file}: {decode_error}"
        ) from decode_error
    if not isinstance(parsed, dict):
        raise RegistryReadError(
            f"Registry at {target_file} is not a JSON object."
        )
    return parsed


def _verify_schema_version_is_supported(existing_registry: dict) -> None:
    existing_meta = existing_registry.get(META_KEY)
    if not isinstance(existing_meta, dict):
        return
    existing_schema_version = existing_meta.get("schema_version")
    if not isinstance(existing_schema_version, int):
        return
    if existing_schema_version > SUPPORTED_SCHEMA_VERSION:
        raise SchemaMismatchError(
            f"On-disk schema_version {existing_schema_version} exceeds supported "
            f"version {SUPPORTED_SCHEMA_VERSION}; refusing to overwrite."
        )


def write_registry_atomically(registry_to_write: dict, target_file: Path) -> None:
    """Serialize registry to a temp sibling and rename into place atomically.

    Caller is responsible for reading the existing registry, verifying the
    schema version, and merging before calling this function. This function
    performs no file reads and no schema checks.
    """
    target_file.parent.mkdir(parents=True, exist_ok=True)
    temp_suffix = ".tmp"
    temp_sibling_path = target_file.with_suffix(target_file.suffix + temp_suffix)
    serialized_text = json.dumps(registry_to_write, indent=JSON_INDENT_SPACES, sort_keys=True)
    try:
        temp_sibling_path.write_text(serialized_text, encoding=UTF8_ENCODING)
        os.replace(temp_sibling_path, target_file)
    finally:
        if temp_sibling_path.exists():
            try:
                temp_sibling_path.unlink()
            except OSError:
                pass


def _everything_binary_is_available() -> bool:
    return shutil.which(ES_EXE_BINARY_NAME) is not None


def _run_es_exe_folders_query() -> list[str]:
    completion = subprocess.run(
        [ES_EXE_BINARY_NAME, *ES_EXE_FOLDERS_ONLY_QUERY_ARGUMENTS],
        capture_output=True,
        text=True,
        encoding=UTF8_ENCODING,
        check=False,
    )
    if completion.returncode != 0:
        truncated_stderr = completion.stderr[:STDERR_TRUNCATION_LENGTH].strip()
        raise EverythingScanError(
            f"es.exe exited with code {completion.returncode}: {truncated_stderr}"
        )
    return [line.strip() for line in completion.stdout.splitlines() if line.strip()]


def discover_repo_roots_via_everything() -> list[str]:
    """Run es.exe, filter to genuine git roots, deduplicate, and sort."""
    all_raw_paths = _run_es_exe_folders_query()
    all_git_roots = filter_to_git_roots(all_raw_paths)
    all_included = apply_exclusion_filter(all_git_roots)
    return sorted(set(all_included))


def _default_user_config_path() -> Path:
    return registry_file_path()


def _prompt_for_affirmative(prompt_text: str) -> bool:
    affirmative_values = frozenset({"yes", "y"})
    user_response = input(prompt_text).strip().lower()
    return user_response in affirmative_values


def _leaf_name_of(repo_root_path: str) -> str:
    leaf = _final_segment(repo_root_path)
    return leaf if leaf else repo_root_path


def _load_and_validate_registry(save_path: Path) -> dict:
    """Read and validate the existing registry, exiting on fatal errors."""
    try:
        existing_registry = _read_existing_registry(save_path)
    except RegistryReadError as registry_error:
        print(
            f"Existing registry at {save_path} is unreadable: {registry_error}. "
            "Refusing to overwrite. Fix or remove the file manually and re-run.",
            file=sys.stderr,
        )
        raise SystemExit(1) from registry_error
    try:
        _verify_schema_version_is_supported(existing_registry)
    except SchemaMismatchError as schema_error:
        print(
            f"Existing registry at {save_path} cannot be overwritten: {schema_error}. "
            "Upgrade this script before re-running.",
            file=sys.stderr,
        )
        raise SystemExit(1) from schema_error
    return existing_registry


def _display_proposed_mapping(
    path_by_name: dict[str, str], save_path: Path
) -> None:
    """Print the proposed name-to-path mapping for user review."""
    print(f"Proposed mapping (save target: {save_path}):")
    for each_name, each_path in sorted(path_by_name.items()):
        print(f"  {each_name} -> {each_path}")
    print()


def prompt_and_write(
    path_by_name: dict[str, str],
    save_path: Path,
) -> None:
    """Present the mapping to the user and write it only on explicit approval.

    Reads and validates the existing registry BEFORE prompting so the user
    learns of any schema or read error early. Declining writes nothing.
    """
    existing_registry = _load_and_validate_registry(save_path)
    _display_proposed_mapping(path_by_name, save_path)
    if not _prompt_for_affirmative(CONFIRMATION_PROMPT_TEXT):
        print(ABORTED_NOTHING_WRITTEN_MESSAGE)
        return
    merged = merge_registries(existing_registry, path_by_name)
    write_registry_atomically(merged, save_path)
    print(WROTE_ENTRIES_STATUS_TEMPLATE.format(entry_count=len(path_by_name), save_path=save_path))


def _build_path_by_name_from_roots(all_repo_roots: list[str]) -> dict[str, str]:
    path_by_name: dict[str, str] = {}
    for each_repo_root in sorted(all_repo_roots):
        each_leaf_name = _leaf_name_of(each_repo_root)
        if each_leaf_name in path_by_name:
            kept_path = path_by_name[each_leaf_name]
            print(
                f"Duplicate leaf name '{each_leaf_name}' — keeping {kept_path}, "
                f"skipping {each_repo_root}. Edit {registry_file_path()} "
                "after generation to disambiguate."
            )
            continue
        path_by_name[each_leaf_name] = each_repo_root
    return path_by_name


def main() -> int:
    if not _everything_binary_is_available():
        print(
            f"ERROR: {ES_EXE_BINARY_NAME} not found on PATH. Install Everything "
            "and ensure its command-line binary is available before running this script.",
            file=sys.stderr,
        )
        return 1
    print(
        f"Running Everything folder scan for {GIT_DIRECTORY_SEGMENT_NAME} directories..."
    )
    try:
        all_repo_roots = discover_repo_roots_via_everything()
    except EverythingScanError as scan_error:
        print(
            f"Everything scan failed: {scan_error}. "
            "Ensure the Everything service is running and try again.",
            file=sys.stderr,
        )
        raise SystemExit(1) from scan_error
    if not all_repo_roots:
        print("No candidate git repositories found via es.exe.")
        return 0
    print(f"Found {len(all_repo_roots)} candidate repositories.")
    path_by_name = _build_path_by_name_from_roots(all_repo_roots)
    save_path = _default_user_config_path()
    prompt_and_write(path_by_name=path_by_name, save_path=save_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
