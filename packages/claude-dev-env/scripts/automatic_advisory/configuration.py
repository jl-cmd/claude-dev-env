from __future__ import annotations

import json
import math
from collections.abc import Mapping
from pathlib import Path, PurePosixPath

from pr_verification.config.constants import GITHUB_API_URL, REPOSITORY_SLUG_PATTERN
from pr_verification.model import RepositorySettings

from .config.constants import (
    DEFAULT_CLONE_URL_SUFFIX,
    REGISTRATION_BASE_REF_KEY,
    REGISTRATION_CHECKOUT_KEY,
    REGISTRATION_MANIFEST_KEY,
    REGISTRATION_PULL_REQUEST_KEY,
    REGISTRATION_REMOTE_KEY,
    REGISTRATION_REPORT_KEY,
    REGISTRATION_REPOSITORY_KEY,
    REGISTRATION_STATE_KEY,
    SETTINGS_API_URL_KEY,
    SETTINGS_APP_ID_KEY,
    SETTINGS_CHILD_TIMEOUT_SECONDS_KEY,
    SETTINGS_INSTALLATION_ID_KEY,
    SETTINGS_POLL_SECONDS_KEY,
    SETTINGS_REGISTRATIONS_KEY,
    SETTINGS_SIGNING_FILE_FIELD,
    SETTINGS_VERSION,
    SETTINGS_VERSION_KEY,
)
from .config.timing import DEFAULT_CHILD_TIMEOUT_SECONDS, DEFAULT_POLL_SECONDS
from .model import AdvisoryRegistration, AdvisorySettings


class AdvisoryConfigurationError(ValueError):
    """Raised when automatic advisory settings are invalid."""


def load_advisory_settings(settings_path: Path) -> AdvisorySettings:
    """Load and validate the explicit automatic advisory registrations.

    Args:
        settings_path: JSON file containing the advisory settings.

    Returns:
        Validated settings for the registered checkout and pull request pairs.

    Raises:
        AdvisoryConfigurationError: If the file or any registration is invalid.
    """
    try:
        parsed_settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AdvisoryConfigurationError(str(error)) from error
    all_settings = _require_mapping(parsed_settings)
    _require_version(all_settings)
    return _build_settings(all_settings)


def _build_settings(all_settings: Mapping[str, object]) -> AdvisorySettings:
    registrations = _load_registrations(all_settings)
    return AdvisorySettings(
        _load_api_url(all_settings),
        _require_positive_integer(all_settings, SETTINGS_APP_ID_KEY),
        _require_positive_integer(all_settings, SETTINGS_INSTALLATION_ID_KEY),
        _require_absolute_path(all_settings, SETTINGS_SIGNING_FILE_FIELD),
        _load_positive_number(
            all_settings,
            SETTINGS_POLL_SECONDS_KEY,
            DEFAULT_POLL_SECONDS,
        ),
        _load_positive_number(
            all_settings,
            SETTINGS_CHILD_TIMEOUT_SECONDS_KEY,
            DEFAULT_CHILD_TIMEOUT_SECONDS,
        ),
        registrations,
    )


def _load_registrations(
    all_settings: Mapping[str, object],
) -> tuple[AdvisoryRegistration, ...]:
    raw_registrations = all_settings.get(SETTINGS_REGISTRATIONS_KEY)
    if not isinstance(raw_registrations, list) or not raw_registrations:
        raise AdvisoryConfigurationError("registrations must be a non-empty array")
    all_registrations = tuple(
        _load_registration(each_registration) for each_registration in raw_registrations
    )
    all_repositories = tuple(
        each_registration.repository.slug for each_registration in all_registrations
    )
    if len(set(all_repositories)) != len(all_repositories):
        raise AdvisoryConfigurationError(
            "each repository can have only one automatic advisory registration"
        )
    return all_registrations


def _load_registration(raw_registration: object) -> AdvisoryRegistration:
    registration = _require_mapping(raw_registration)
    repository_slug = _require_text(registration, REGISTRATION_REPOSITORY_KEY)
    if REPOSITORY_SLUG_PATTERN.fullmatch(repository_slug) is None:
        raise AdvisoryConfigurationError("repository must use owner/name")
    pull_request_number = _require_positive_integer(
        registration, REGISTRATION_PULL_REQUEST_KEY
    )
    checkout_path = _require_absolute_path(registration, REGISTRATION_CHECKOUT_KEY)
    manifest_path = _require_relative_manifest(registration)
    report_path = _require_absolute_path(registration, REGISTRATION_REPORT_KEY)
    state_path = _require_absolute_path(registration, REGISTRATION_STATE_KEY)
    return AdvisoryRegistration(
        RepositorySettings(repository_slug, repository_slug + DEFAULT_CLONE_URL_SUFFIX),
        pull_request_number,
        checkout_path,
        manifest_path,
        report_path,
        state_path,
        _require_text(registration, REGISTRATION_BASE_REF_KEY),
        _require_text(registration, REGISTRATION_REMOTE_KEY),
    )


def _load_api_url(all_settings: Mapping[str, object]) -> str:
    return _require_text_or_default(
        all_settings, SETTINGS_API_URL_KEY, GITHUB_API_URL
    ).rstrip("/")


def _load_positive_number(
    all_settings: Mapping[str, object],
    field_name: str,
    default_seconds: float,
) -> float:
    raw_number = all_settings.get(field_name, default_seconds)
    if isinstance(raw_number, bool) or not isinstance(raw_number, (float, int)):
        raise AdvisoryConfigurationError(f"{field_name} must be positive")
    if raw_number <= 0 or not math.isfinite(raw_number):
        raise AdvisoryConfigurationError(f"{field_name} must be positive")
    return float(raw_number)


def _require_mapping(raw_payload: object) -> Mapping[str, object]:
    if not isinstance(raw_payload, Mapping):
        raise AdvisoryConfigurationError("settings must be an object")
    return raw_payload


def _require_version(all_settings: Mapping[str, object]) -> None:
    if all_settings.get(SETTINGS_VERSION_KEY) != SETTINGS_VERSION:
        raise AdvisoryConfigurationError("settings version is unsupported")


def _require_text(all_settings: Mapping[str, object], field_name: str) -> str:
    field_text = all_settings.get(field_name)
    if not isinstance(field_text, str) or not field_text.strip():
        raise AdvisoryConfigurationError(f"{field_name} must be a non-empty string")
    return field_text


def _require_text_or_default(
    all_settings: Mapping[str, object],
    field_name: str,
    default_text: str,
) -> str:
    field_text = all_settings.get(field_name, default_text)
    if not isinstance(field_text, str) or not field_text.strip():
        raise AdvisoryConfigurationError(f"{field_name} must be a non-empty string")
    return field_text


def _require_positive_integer(
    all_settings: Mapping[str, object], field_name: str
) -> int:
    field_number = all_settings.get(field_name)
    if isinstance(field_number, bool) or not isinstance(field_number, int):
        raise AdvisoryConfigurationError(f"{field_name} must be positive")
    if field_number < 1:
        raise AdvisoryConfigurationError(f"{field_name} must be positive")
    return field_number


def _require_absolute_path(all_settings: Mapping[str, object], field_name: str) -> Path:
    configured_path = Path(_require_text(all_settings, field_name))
    if not configured_path.is_absolute():
        raise AdvisoryConfigurationError(f"{field_name} must be absolute")
    return configured_path.resolve()


def _require_relative_manifest(
    all_settings: Mapping[str, object],
) -> PurePosixPath:
    manifest_text = _require_text(all_settings, REGISTRATION_MANIFEST_KEY)
    manifest_path = PurePosixPath(manifest_text.replace("\\", "/"))
    if manifest_path.is_absolute() or ".." in manifest_path.parts:
        raise AdvisoryConfigurationError("manifest must stay inside checkout")
    return manifest_path
