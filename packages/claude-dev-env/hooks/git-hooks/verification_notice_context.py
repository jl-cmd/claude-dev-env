"""Load repository context used by the native Git verification notice."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from git_hooks_constants import (
    GIT_COMMAND_TIMEOUT_SECONDS,
    GIT_EXECUTABLE_NAME,
    GIT_OUTPUT_DECODE_ERRORS_POLICY,
    GIT_OUTPUT_ENCODING_NAME,
)
from git_hooks_constants.verification_notice_constants import (
    ALL_GIT_ABSOLUTE_DIRECTORY_QUERY,
    ALL_GIT_HEAD_QUERY,
    ALL_GIT_REMOTE_URL_QUERY,
    ALL_GIT_REPOSITORY_ROOT_QUERY,
    GIT_COMMAND_SUCCESS_EXIT_CODE,
    GIT_DIRECTORY_NAME,
    JSON_ENCODING,
    LOCAL_VERIFICATION_DIRECTORY_NAME,
    MANIFEST_DIRECTORY_NAME,
    MANIFEST_FILE_NAME,
    MINIMUM_REMOTE_PART_COUNT,
    OWNER_PART_INDEX,
    REPORT_FILE_NAME,
    REPOSITORY_PART_INDEX,
    SELECTED_MANIFEST_PATH_FIELD,
    SELECTION_FIELD,
    TARGET_REPOSITORY_REMOTE,
)
from local_verification.manifest import ManifestRunFatal, load_manifest


@dataclass(frozen=True)
class VerificationNoticeContext:
    event: str
    repository_remote: str
    repository_root: Path
    current_head: str | None
    manifest_path: Path | None
    manifest_is_available: bool
    git_directory: Path | None
    report_is_present: bool
    all_report_fields: Mapping[str, object] | None


def normalize_repository_remote(remote_url: str) -> str | None:
    """Return an owner/repository slug from common Git remote URL forms.

    Args:
        remote_url: Git remote URL to normalize.

    Returns:
        The normalized owner/repository slug, or None for an invalid URL.
    """
    stripped_remote_url = remote_url.strip().rstrip("/")
    if not stripped_remote_url:
        return None
    remote_path = _extract_remote_path(stripped_remote_url)
    all_remote_parts = [each_part for each_part in remote_path.split("/") if each_part]
    if len(all_remote_parts) < MINIMUM_REMOTE_PART_COUNT:
        return None
    repository_name = all_remote_parts[REPOSITORY_PART_INDEX].removesuffix(GIT_DIRECTORY_NAME)
    owner_name = all_remote_parts[OWNER_PART_INDEX]
    if not owner_name or not repository_name:
        return None
    return f"{owner_name}/{repository_name}".casefold()


def _load_notice_context(
    event: str, repository_path: Path
) -> VerificationNoticeContext | None:
    repository_identity = _load_repository_identity(repository_path)
    if repository_identity is None:
        return None
    repository_root, current_head, git_directory_text = repository_identity
    normalized_remote = normalize_repository_remote(
        _run_git_query(repository_root, ALL_GIT_REMOTE_URL_QUERY, False) or ""
    )
    if normalized_remote != TARGET_REPOSITORY_REMOTE or current_head is None:
        return None
    if not git_directory_text:
        return None
    git_directory = _resolve_common_directory(repository_root, git_directory_text)
    all_report_fields, report_is_present = _load_repository_report(git_directory)
    manifest_path, manifest_is_available = _load_manifest_context(
        repository_root, git_directory, all_report_fields
    )
    return VerificationNoticeContext(
        event=event,
        repository_remote=normalized_remote,
        repository_root=repository_root,
        current_head=current_head,
        manifest_path=manifest_path,
        manifest_is_available=manifest_is_available,
        git_directory=git_directory,
        report_is_present=report_is_present,
        all_report_fields=all_report_fields,
    )


def _load_manifest_context(
    repository_root: Path,
    git_directory: Path,
    all_report_fields: Mapping[str, object] | None,
) -> tuple[Path | None, bool]:
    manifest_path = _resolve_selected_manifest_path(
        repository_root, git_directory, all_report_fields
    )
    return manifest_path, _manifest_is_available(manifest_path)


def _load_repository_report(
    git_directory: Path,
) -> tuple[Mapping[str, object] | None, bool]:
    report_path = git_directory / LOCAL_VERIFICATION_DIRECTORY_NAME / REPORT_FILE_NAME
    return _load_json_mapping(report_path), report_path.is_file()


def _resolve_selected_manifest_path(
    repository_root: Path,
    git_directory: Path,
    all_report_fields: Mapping[str, object] | None,
) -> Path | None:
    selected_path_text = _read_selected_manifest_path(all_report_fields)
    if selected_path_text is None:
        if all_report_fields is not None:
            return None
        return repository_root / MANIFEST_DIRECTORY_NAME / MANIFEST_FILE_NAME
    selected_path = Path(selected_path_text)
    if not selected_path.is_absolute():
        selected_path = repository_root / selected_path
    resolved_path = selected_path.resolve()
    if _is_inside_repository(resolved_path, repository_root):
        return resolved_path
    metadata_directory = git_directory / LOCAL_VERIFICATION_DIRECTORY_NAME
    if _is_inside_repository(resolved_path, metadata_directory):
        return resolved_path
    return None


def _read_selected_manifest_path(
    all_report_fields: Mapping[str, object] | None,
) -> str | None:
    if all_report_fields is None:
        return None
    selection_record = all_report_fields.get(SELECTION_FIELD)
    if not isinstance(selection_record, Mapping):
        return None
    selected_path_text = selection_record.get(SELECTED_MANIFEST_PATH_FIELD)
    if not isinstance(selected_path_text, str) or not selected_path_text.strip():
        return None
    return selected_path_text


def _is_inside_repository(candidate_path: Path, repository_root: Path) -> bool:
    try:
        candidate_path.relative_to(repository_root)
    except ValueError:
        return False
    return True


def _load_repository_identity(
    repository_path: Path,
) -> tuple[Path, str | None, str | None] | None:
    if not repository_path.is_dir():
        return None
    repository_root_text = _run_git_query(
        repository_path,
        ALL_GIT_REPOSITORY_ROOT_QUERY,
        False,
    )
    if repository_root_text is None:
        return None
    repository_root = Path(repository_root_text).resolve()
    return (
        repository_root,
        _run_git_query(repository_root, ALL_GIT_HEAD_QUERY, False),
        _run_git_query(repository_root, ALL_GIT_ABSOLUTE_DIRECTORY_QUERY, False),
    )


def _run_git_query(
    repository_root: Path,
    all_git_arguments: tuple[str, ...],
    should_allow_empty: bool,
) -> str | None:
    try:
        completed_process = subprocess.run(
            [GIT_EXECUTABLE_NAME, *all_git_arguments],
            cwd=repository_root,
            check=False,
            capture_output=True,
            text=True,
            encoding=GIT_OUTPUT_ENCODING_NAME,
            errors=GIT_OUTPUT_DECODE_ERRORS_POLICY,
            timeout=GIT_COMMAND_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return None
    if completed_process.returncode != GIT_COMMAND_SUCCESS_EXIT_CODE:
        return None
    stripped_stdout = completed_process.stdout.strip()
    if stripped_stdout or should_allow_empty:
        return stripped_stdout
    return None


def _extract_remote_path(remote_url: str) -> str:
    if "://" in remote_url:
        return urlsplit(remote_url).path
    if "@" in remote_url and ":" in remote_url:
        return remote_url.rsplit(":", 1)[1]
    return remote_url


def _resolve_common_directory(
    repository_root: Path,
    common_directory_text: str,
) -> Path:
    common_directory_path = Path(common_directory_text)
    if common_directory_path.is_absolute():
        return common_directory_path.resolve()
    return (repository_root / common_directory_path).resolve()


def _load_json_mapping(json_path: Path) -> Mapping[str, object] | None:
    if not json_path.is_file():
        return None
    try:
        parsed_json: object = json.loads(json_path.read_text(encoding=JSON_ENCODING))
    except (OSError, UnicodeError, ValueError):
        return None
    if not isinstance(parsed_json, Mapping):
        return None
    return parsed_json


def _manifest_is_available(manifest_path: Path | None) -> bool:
    if manifest_path is None:
        return False
    try:
        load_manifest(manifest_path)
    except (ManifestRunFatal, OSError, UnicodeError, ValueError):
        return False
    return True
