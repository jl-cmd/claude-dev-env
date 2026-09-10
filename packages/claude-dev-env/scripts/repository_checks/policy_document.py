"""Read and validate the repository policy document."""

from __future__ import annotations

import json
from pathlib import Path

from repository_checks.config.policy_document import (
    ALL_DOCUMENT_FIELDS,
    ALL_ENTRY_FIELDS,
    ALL_EXEMPTION_FIELDS,
    ALL_FORBIDDEN_PATH_SEGMENTS,
    CONFIG_RELATIVE_PATH,
    DIGEST_PATTERN,
    FIRST_PRINTABLE_CODEPOINT,
    FORBIDDEN_PATH_CHARACTERS,
    SUPPORTED_DOCUMENT_VERSION,
    VERSION_FIELD,
)


class PolicyConfigurationRunFatal(ValueError):
    """Reject the entire policy run when exception configuration is invalid."""


def read_policy_entries(repository_root: Path, field_name: str) -> list[object]:
    """Read one exception list from the validated policy document.

    Args:
        repository_root: Repository containing the optional policy configuration.
        field_name: Top-level document field holding the exception list.

    Returns:
        Raw entries recorded under the requested field.

    Raises:
        ValueError: Configuration contains invalid JSON or schema fields.
        OSError: Configuration cannot be read.
    """
    config_path = repository_root / CONFIG_RELATIVE_PATH
    if not config_path.exists() and not config_path.is_symlink():
        return []
    if not config_path.resolve().is_relative_to(repository_root.resolve()):
        raise ValueError(
            "Repository policy configuration must remain inside the repository"
        )
    document = json.loads(
        config_path.read_text(encoding="utf-8"), object_pairs_hook=_unique_fields
    )
    _require_valid_document(document)
    return document.get(field_name, [])


def entry_path_and_digest(entry: object, subject: str) -> tuple[str, str]:
    """Return the validated path and digest of one exception entry.

    Args:
        entry: Raw entry read from the policy document.
        subject: Exception family named in each rejection message.

    Returns:
        Repository-relative path and its recorded sha256 digest.

    Raises:
        ValueError: The entry omits a field or carries an invalid value.
    """
    if not isinstance(entry, dict) or set(entry) != ALL_ENTRY_FIELDS:
        raise ValueError(f"{subject}s require path, sha256, and reason")
    relative_path, digest, reason = entry["path"], entry["sha256"], entry["reason"]
    if not isinstance(relative_path, str) or not relative_path:
        raise ValueError(f"{subject} path must name one repository file")
    if _is_nonliteral_relative_path(relative_path):
        raise ValueError(f"{subject} path must be a literal relative file path")
    if not isinstance(digest, str) or DIGEST_PATTERN.fullmatch(digest) is None:
        raise ValueError(f"{subject} sha256 must contain 64 lowercase hex digits")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError(f"{subject} reason must explain why the exception is owned")
    return relative_path, digest


def _require_valid_document(document: object) -> None:
    if (
        not isinstance(document, dict)
        or not set(document) <= ALL_DOCUMENT_FIELDS
        or VERSION_FIELD not in document
        or type(document[VERSION_FIELD]) is not int
        or document[VERSION_FIELD] != SUPPORTED_DOCUMENT_VERSION
        or not _has_only_list_exemption_fields(document)
    ):
        raise ValueError("Invalid repository policy configuration schema")


def _has_only_list_exemption_fields(all_document_fields: dict[str, object]) -> bool:
    return all(
        isinstance(all_document_fields[each_field], list)
        for each_field in ALL_EXEMPTION_FIELDS
        if each_field in all_document_fields
    )


def _is_nonliteral_relative_path(relative_path: str) -> bool:
    return (
        any(character in FORBIDDEN_PATH_CHARACTERS for character in relative_path)
        or any(
            segment in ALL_FORBIDDEN_PATH_SEGMENTS
            for segment in relative_path.split("/")
        )
        or any(
            ord(character) < FIRST_PRINTABLE_CODEPOINT for character in relative_path
        )
    )


def _unique_fields(all_pairs: list[tuple[str, object]]) -> dict[str, object]:
    fields: dict[str, object] = {}
    for each_key, each_content in all_pairs:
        if each_key in fields:
            raise PolicyConfigurationRunFatal("Duplicate repository policy field")
        fields[each_key] = each_content
    return fields
