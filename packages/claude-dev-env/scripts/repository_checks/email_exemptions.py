"""Load exact public-email exceptions owned by a repository."""

from __future__ import annotations

from pathlib import Path

from repository_checks.config.policy_document import (
    EMAIL_CATEGORY,
    EMAIL_EXEMPTION_SUBJECT,
    EMAIL_EXEMPTIONS_FIELD,
)
from repository_checks.policy_document import (
    PolicyConfigurationRunFatal,
    entry_path_and_digest,
    read_policy_entries,
)


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
    for each_entry in read_policy_entries(repository_root, EMAIL_EXEMPTIONS_FIELD):
        relative_path, digest = entry_path_and_digest(
            each_entry, EMAIL_EXEMPTION_SUBJECT
        )
        identity = (relative_path, EMAIL_CATEGORY, digest)
        if identity in exemptions:
            raise PolicyConfigurationRunFatal("Duplicate repository email exemption")
        exemptions.add(identity)
    return frozenset(exemptions)
