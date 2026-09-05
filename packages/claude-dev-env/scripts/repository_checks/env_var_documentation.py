"""Environment-variable documentation checks for committed trees."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from pathlib import Path
from types import ModuleType

from policy_lint.config.constants import PATH_SEPARATOR, UTF8_ENCODING

from repository_checks.config.constants import (
    CHECK_ID_ENV_VAR_DOCUMENTATION,
    ENV_VAR_DRIFT_CONSTANTS_MODULE_NAME,
    ENV_VAR_DRIFT_MODULE_NAME,
    WINDOWS_PATH_SEPARATOR,
)
from repository_checks.hook_modules import load_hooks_module
from repository_checks.models import RepositoryFinding


def collect_env_var_documentation_findings(
    repository_root: Path, all_tracked_paths: Sequence[str]
) -> list[RepositoryFinding]:
    """Return drifted environment-variable rows in tracked documentation.

    Args:
        repository_root: Git repository root.
        all_tracked_paths: Repository-relative tracked paths.

    Returns:
        Findings for documentation rows whose code reference has drifted.
    """
    drift_module = load_hooks_module(ENV_VAR_DRIFT_MODULE_NAME)
    drift_constants = load_hooks_module(ENV_VAR_DRIFT_CONSTANTS_MODULE_NAME)
    all_findings: list[RepositoryFinding] = []
    for each_relative_path in all_tracked_paths:
        all_findings.extend(
            find_documentation_findings_for_path(
                repository_root,
                each_relative_path,
                drift_module,
                drift_constants,
            )
        )
    return all_findings


def find_documentation_findings_for_path(
    repository_root: Path,
    relative_path: str,
    drift_module: ModuleType,
    drift_constants: ModuleType,
) -> list[RepositoryFinding]:
    """Return documentation rows whose code file does not read the variable.

    Args:
        repository_root: Git repository root.
        relative_path: Repository-relative documentation path.
        drift_module: Existing documentation detector module.
        drift_constants: Existing detector constants module.

    Returns:
        Findings for drifted documentation rows.
    """
    if not drift_module.is_markdown_file(relative_path):
        return []
    absolute_path = repository_root / relative_path
    if not absolute_path.is_file():
        return []
    return _find_documentation_file_findings(
        repository_root,
        relative_path,
        absolute_path,
        drift_module,
        drift_constants,
    )


def _find_documentation_file_findings(
    repository_root: Path,
    relative_path: str,
    absolute_path: Path,
    drift_module: ModuleType,
    drift_constants: ModuleType,
) -> list[RepositoryFinding]:
    content = absolute_path.read_text(encoding=UTF8_ENCODING)
    _require_readable_code_files(
        content,
        repository_root,
        drift_module,
        drift_constants,
    )
    all_drift_rows = drift_module.find_drift_rows(content, absolute_path.parent)
    return _build_findings(relative_path, all_drift_rows)


def _build_findings(
    relative_path: str, all_drift_rows: Sequence[str]
) -> list[RepositoryFinding]:
    return [
        RepositoryFinding(
            CHECK_ID_ENV_VAR_DOCUMENTATION,
            relative_path.replace(WINDOWS_PATH_SEPARATOR, PATH_SEPARATOR),
            each_drift_row,
        )
        for each_drift_row in all_drift_rows
    ]


def _require_readable_code_files(
    content: str,
    repository_root: Path,
    drift_module: ModuleType,
    drift_constants: ModuleType,
) -> None:
    resolved_repository_root = repository_root.resolve(strict=True)
    for each_code_reference in _iter_env_var_code_references(
        content,
        drift_module,
        drift_constants,
    ):
        maybe_code_file = _resolve_code_file(
            repository_root,
            each_code_reference,
            drift_constants,
        )
        if maybe_code_file is None:
            continue
        resolved_code_file = _resolve_inside_repository(
            resolved_repository_root,
            maybe_code_file,
        )
        resolved_code_file.read_text(encoding=UTF8_ENCODING)


def _iter_env_var_code_references(
    content: str,
    drift_module: ModuleType,
    drift_constants: ModuleType,
) -> Iterator[str]:
    is_inside_code_fence = False
    for each_line in content.splitlines():
        if drift_constants.CODE_FENCE_PATTERN.match(each_line) is not None:
            is_inside_code_fence = not is_inside_code_fence
            continue
        if is_inside_code_fence:
            continue
        if drift_constants.TABLE_ROW_PATTERN.match(each_line) is None:
            continue
        maybe_code_reference = _code_reference_for_env_var_row(
            each_line,
            drift_module,
            drift_constants,
        )
        if maybe_code_reference is not None:
            yield maybe_code_reference


def _code_reference_for_env_var_row(
    table_line: str,
    drift_module: ModuleType,
    drift_constants: ModuleType,
) -> str | None:
    all_cells = drift_module._row_cells(table_line)
    if len(all_cells) < drift_constants.MINIMUM_ENV_VAR_ROW_CELL_COUNT:
        return None
    if drift_module._is_separator_row(all_cells):
        return None
    if drift_module._env_var_name_in_cell(all_cells[0]) is None:
        return None
    for each_cell in all_cells[1:]:
        maybe_code_reference = drift_module._code_file_reference_in_cell(each_cell)
        if maybe_code_reference is not None:
            return maybe_code_reference
    return None


def _resolve_inside_repository(
    resolved_repository_root: Path,
    candidate_path: Path,
) -> Path:
    resolved_candidate_path = candidate_path.resolve(strict=True)
    try:
        resolved_candidate_path.relative_to(resolved_repository_root)
    except ValueError as e:
        raise OSError(candidate_path) from e
    return resolved_candidate_path


def _resolve_code_file(
    repository_root: Path,
    code_reference: str,
    drift_constants: ModuleType,
) -> Path | None:
    normalized_reference = code_reference.replace(
        WINDOWS_PATH_SEPARATOR, PATH_SEPARATOR
    ).lstrip(PATH_SEPARATOR)
    direct_path = repository_root / normalized_reference
    if direct_path.is_file():
        return direct_path
    reference_basename = Path(normalized_reference).name
    if not reference_basename:
        return None
    return _find_suffix_match(
        repository_root,
        normalized_reference,
        reference_basename,
        drift_constants,
    )


def _find_suffix_match(
    repository_root: Path,
    normalized_reference: str,
    reference_basename: str,
    drift_constants: ModuleType,
) -> Path | None:
    suffix_marker = PATH_SEPARATOR + normalized_reference
    scanned_count = 0
    for each_match in repository_root.rglob(reference_basename):
        if _is_under_noise_directory(repository_root, each_match, drift_constants):
            continue
        scanned_count += 1
        if scanned_count > drift_constants.MAX_SUBTREE_FILES_SCANNED:
            return None
        if not each_match.is_file():
            continue
        match_text = PATH_SEPARATOR + each_match.as_posix()
        if match_text.endswith(suffix_marker):
            return each_match
    return None


def _is_under_noise_directory(
    repository_root: Path,
    candidate_path: Path,
    drift_constants: ModuleType,
) -> bool:
    all_relative_segments = candidate_path.relative_to(repository_root).parts
    return any(
        each_segment in drift_constants.ALL_NOISE_DIRECTORY_NAMES
        for each_segment in all_relative_segments
    )
