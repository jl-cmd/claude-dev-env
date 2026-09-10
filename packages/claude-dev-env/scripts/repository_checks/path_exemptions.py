"""Load frozen-file path exceptions owned by a repository."""

from __future__ import annotations

from pathlib import Path

from repository_checks.config.policy_document import (
    PATH_EXEMPTION_SUBJECT,
    PATH_EXEMPTIONS_FIELD,
)
from repository_checks.policy_document import (
    PolicyConfigurationRunFatal,
    entry_path_and_digest,
    read_policy_entries,
)


def load_path_exemptions(repository_root: Path) -> frozenset[tuple[str, str]]:
    """Read validated frozen-file path exceptions.

    Args:
        repository_root: Repository containing the optional policy configuration.
    Returns:
        Exact path and recorded file-content digest identities.
    Raises:
        ValueError: Configuration contains invalid JSON or schema fields.
        OSError: Configuration cannot be read.
    """
    exemptions: set[tuple[str, str]] = set()
    for each_entry in read_policy_entries(repository_root, PATH_EXEMPTIONS_FIELD):
        identity = entry_path_and_digest(each_entry, PATH_EXEMPTION_SUBJECT)
        if identity in exemptions:
            raise PolicyConfigurationRunFatal("Duplicate repository path exemption")
        exemptions.add(identity)
    return frozenset(exemptions)
