"""Load exact public-email exceptions owned by a repository."""

from __future__ import annotations

import json
from pathlib import Path

from repository_checks.config.email_exemptions import (
    ALL_ENTRY_FIELDS,
    ALL_FORBIDDEN_PATH_SEGMENTS,
    CONFIG_RELATIVE_PATH,
    DIGEST_PATTERN,
    FIRST_PRINTABLE_CODEPOINT,
    FORBIDDEN_PATH_CHARACTERS,
)


class PolicyConfigurationRunFatal(ValueError):
    """Reject the entire policy run when exception configuration is invalid."""


def load_email_exemptions(repository_root: Path) -> frozenset[tuple[str, str, str]]:
    """Read validated email exceptions.

    Args:
        repository_root: Repository containing the optional policy configuration.
    Returns:
        Exact path, email category, and digest identities.
    Raises:
        ValueError: Configuration contains invalid JSON or schema fields.
        OSError: Configuration cannot be read.
    """
    exemptions: set[tuple[str, str, str]] = set()
    for each_entry in _read_entries(repository_root):
        identity = _entry_identity(each_entry)
        if identity in exemptions:
            raise PolicyConfigurationRunFatal("Duplicate repository email exemption")
        exemptions.add(identity)
    return frozenset(exemptions)


def _read_entries(repository_root: Path) -> list[object]:
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
    if (
        not isinstance(document, dict)
        or set(document) != {"version", "email_exemptions"}
        or type(document["version"]) is not int
        or document["version"] != 1
        or not isinstance(document["email_exemptions"], list)
    ):
        raise ValueError("Invalid repository policy configuration schema")
    return document["email_exemptions"]


def _unique_fields(all_pairs: list[tuple[str, object]]) -> dict[str, object]:
    fields: dict[str, object] = {}
    for each_key, each_content in all_pairs:
        if each_key in fields:
            raise PolicyConfigurationRunFatal("Duplicate repository policy field")
        fields[each_key] = each_content
    return fields


def _entry_identity(entry: object) -> tuple[str, str, str]:
    if not isinstance(entry, dict) or set(entry) != ALL_ENTRY_FIELDS:
        raise ValueError("Email exemptions require path, sha256, and reason")
    relative_path, digest, reason = entry["path"], entry["sha256"], entry["reason"]
    if not isinstance(relative_path, str) or not relative_path:
        raise ValueError("Email exemption path must name one repository file")
    if (
        any(character in FORBIDDEN_PATH_CHARACTERS for character in relative_path)
        or any(
            segment in ALL_FORBIDDEN_PATH_SEGMENTS
            for segment in relative_path.split("/")
        )
        or any(
            ord(character) < FIRST_PRINTABLE_CODEPOINT for character in relative_path
        )
    ):
        raise ValueError("Email exemption path must be a literal relative file path")
    if not isinstance(digest, str) or DIGEST_PATTERN.fullmatch(digest) is None:
        raise ValueError("Email exemption sha256 must contain 64 lowercase hex digits")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError(
            "Email exemption reason must explain its public contact purpose"
        )
    return relative_path, "email", digest
