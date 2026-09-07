from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from pathlib import Path, PurePosixPath, PureWindowsPath

from .config import (
    ALL_MANIFEST_DIGEST_SEPARATORS,
    CHECK_ARGUMENTS_KEY,
    CHECK_DIRECTORY_KEY,
    CHECK_ID_KEY,
    CHECK_MINIMUM_TESTS_KEY,
    CHECK_TIMEOUT_KEY,
    EXCLUSION_REASON_KEY,
    EXCLUSION_SELECTOR_KEY,
    MANIFEST_CHECKS_KEY,
    MANIFEST_DIGEST_ALGORITHM,
    MANIFEST_EXCLUSIONS_KEY,
    MANIFEST_VERSION,
    MANIFEST_VERSION_KEY,
    UTF8_ENCODING,
)
from .model import CheckSpec, ExclusionSpec, VerificationManifest


class ManifestRunFatal(ValueError):
    """Raised when a verification manifest does not follow version 1."""


def compute_manifest_digest(manifest: VerificationManifest) -> str:
    """Return a stable digest for the validated manifest structure.

    Args:
        manifest: Validated required-check manifest.

    Returns:
        A SHA-256 digest that covers every executed manifest field.
    """
    canonical_manifest = json.dumps(
        _manifest_mapping(manifest),
        sort_keys=True,
        separators=ALL_MANIFEST_DIGEST_SEPARATORS,
    )
    return hashlib.new(
        MANIFEST_DIGEST_ALGORITHM, canonical_manifest.encode(UTF8_ENCODING)
    ).hexdigest()


def _manifest_mapping(manifest: VerificationManifest) -> dict[str, object]:
    all_check_mappings = [
        {
            CHECK_ID_KEY: each_check.check_id,
            CHECK_ARGUMENTS_KEY: list(each_check.command_arguments),
            CHECK_DIRECTORY_KEY: each_check.cwd,
            CHECK_TIMEOUT_KEY: each_check.timeout_seconds,
            CHECK_MINIMUM_TESTS_KEY: each_check.minimum_tests,
        }
        for each_check in manifest.checks
    ]
    all_exclusion_mappings = [
        {
            EXCLUSION_SELECTOR_KEY: each_exclusion.selector,
            EXCLUSION_REASON_KEY: each_exclusion.reason,
        }
        for each_exclusion in manifest.exclusions
    ]
    return {
        MANIFEST_VERSION_KEY: manifest.version,
        MANIFEST_CHECKS_KEY: all_check_mappings,
        MANIFEST_EXCLUSIONS_KEY: all_exclusion_mappings,
    }


def load_manifest(manifest_path: Path) -> VerificationManifest:
    """Read and validate a required-check manifest.

    Args:
        manifest_path: JSON file containing the required checks.

    Returns:
        The validated manifest.

    Raises:
        ManifestRunFatal: If the file cannot describe a valid manifest.
        OSError: If the file cannot be read.
    """
    try:
        parsed_manifest: object = json.loads(
            manifest_path.read_text(encoding=UTF8_ENCODING)
        )
    except json.JSONDecodeError as error:
        raise ManifestRunFatal(f"Manifest is not valid JSON: {error}") from error
    manifest_mapping = _require_mapping(parsed_manifest, "manifest")
    manifest_version = _require_integer(manifest_mapping, "version", "manifest")
    if manifest_version != MANIFEST_VERSION:
        raise ManifestRunFatal(f"Manifest version must be {MANIFEST_VERSION}")
    all_checks = _load_checks(manifest_mapping.get("checks"))
    all_exclusions = _load_exclusions(manifest_mapping.get("exclusions", []))
    return VerificationManifest(
        manifest_version, tuple(all_checks), tuple(all_exclusions)
    )


def _load_checks(raw_checks: object) -> list[CheckSpec]:
    if not isinstance(raw_checks, list) or not raw_checks:
        raise ManifestRunFatal("Manifest checks must be a non-empty array")
    all_checks: list[CheckSpec] = []
    all_check_ids: set[str] = set()
    for each_index, each_raw_check in enumerate(raw_checks):
        all_check_fields = _require_mapping(each_raw_check, f"checks[{each_index}]")
        check_spec = _load_check(all_check_fields, each_index)
        if check_spec.check_id in all_check_ids:
            raise ManifestRunFatal("Check ids must be unique")
        all_check_ids.add(check_spec.check_id)
        all_checks.append(check_spec)
    return all_checks


def _load_check(all_check_fields: Mapping[str, object], check_index: int) -> CheckSpec:
    location = f"checks[{check_index}]"
    check_id = _require_text(all_check_fields, "id", location)
    all_command_arguments = _load_command_arguments(
        all_check_fields.get("argv"), location
    )
    cwd = _load_relative_directory(all_check_fields.get("cwd"), location)
    timeout_seconds = _load_timeout(all_check_fields.get("timeout_seconds"), location)
    minimum_tests = _load_minimum_tests(all_check_fields.get("minimum_tests"), location)
    return CheckSpec(
        check_id, all_command_arguments, cwd, timeout_seconds, minimum_tests
    )


def _load_command_arguments(raw_arguments: object, location: str) -> tuple[str, ...]:
    if not isinstance(raw_arguments, list) or not raw_arguments:
        raise ManifestRunFatal(f"{location}.argv must be a non-empty array")
    if any(
        not isinstance(each_argument, str) or not each_argument
        for each_argument in raw_arguments
    ):
        raise ManifestRunFatal(f"{location}.argv must contain non-empty strings")
    return tuple(raw_arguments)


def _load_exclusions(raw_exclusions: object) -> list[ExclusionSpec]:
    if not isinstance(raw_exclusions, list):
        raise ManifestRunFatal("Manifest exclusions must be an array")
    all_exclusions: list[ExclusionSpec] = []
    for each_index, each_raw_exclusion in enumerate(raw_exclusions):
        all_exclusion_fields = _require_mapping(
            each_raw_exclusion, f"exclusions[{each_index}]"
        )
        location = f"exclusions[{each_index}]"
        selector = _require_text(all_exclusion_fields, "selector", location)
        reason = _require_text(all_exclusion_fields, "reason", location)
        all_exclusions.append(ExclusionSpec(selector, reason))
    return all_exclusions


def _load_relative_directory(raw_directory: object, location: str) -> str:
    if not isinstance(raw_directory, str) or not raw_directory:
        raise ManifestRunFatal(f"{location}.cwd must be a repo-relative directory")
    return _validate_relative_directory(raw_directory, location)


def _validate_relative_directory(directory_text: str, location: str) -> str:
    normalized_directory = directory_text.replace("\\", "/")
    directory_path = PurePosixPath(normalized_directory)
    if (
        directory_path.is_absolute()
        or normalized_directory.startswith("/")
        or PureWindowsPath(normalized_directory).drive
        or any(each_part == ".." for each_part in directory_path.parts)
    ):
        raise ManifestRunFatal(f"{location}.cwd must stay inside the repository")
    return directory_path.as_posix()


def _load_timeout(raw_timeout: object, location: str) -> float:
    if isinstance(raw_timeout, bool) or not isinstance(raw_timeout, (int, float)):
        raise ManifestRunFatal(f"{location}.timeout_seconds must be positive")
    timeout_seconds = float(raw_timeout)
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ManifestRunFatal(f"{location}.timeout_seconds must be positive")
    return timeout_seconds


def _load_minimum_tests(raw_minimum: object, location: str) -> int | None:
    if raw_minimum is None:
        return None
    if (
        isinstance(raw_minimum, bool)
        or not isinstance(raw_minimum, int)
        or raw_minimum < 0
    ):
        raise ManifestRunFatal(
            f"{location}.minimum_tests must be a non-negative integer"
        )
    return raw_minimum


def _require_mapping(candidate: object, location: str) -> Mapping[str, object]:
    if not isinstance(candidate, Mapping):
        raise ManifestRunFatal(f"{location} must be an object")
    return candidate


def _require_text(
    all_fields: Mapping[str, object], field_name: str, location: str
) -> str:
    field_text = all_fields.get(field_name)
    if not isinstance(field_text, str) or not field_text.strip():
        raise ManifestRunFatal(f"{location}.{field_name} must be a non-empty string")
    return field_text


def _require_integer(
    all_fields: Mapping[str, object], field_name: str, location: str
) -> int:
    field_number = all_fields.get(field_name)
    if isinstance(field_number, bool) or not isinstance(field_number, int):
        raise ManifestRunFatal(f"{location}.{field_name} must be an integer")
    return field_number
