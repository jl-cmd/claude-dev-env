"""Load the scanner matches a repository owns through its policy document."""

from __future__ import annotations

from pathlib import Path

from repository_checks.config.policy_document import (
    ALL_MATCH_EXEMPTION_FAMILIES,
    MatchExemptionFamily,
)
from repository_checks.policy_document import (
    PolicyConfigurationRunFatal,
    entry_path_and_digest,
    read_policy_entries,
)


def load_match_exemptions(
    repository_root: Path, family: MatchExemptionFamily
) -> frozenset[tuple[str, str, str]]:
    """Read one family of matches the repository owns.

    ::

        the email family over a document owning one address
        ok:   {("contacts.py", "email", "<digest of the address>")}
        flag: the private-IP list read through the email family

    Args:
        repository_root: Repository containing the optional policy configuration.
        family: Document field, scanner category, and rejection subject to read.
    Returns:
        Exact path, scanner category, and digest identities.
    Raises:
        ValueError: Configuration contains invalid JSON or schema fields.
        OSError: Configuration cannot be read.
    """
    exemptions: set[tuple[str, str, str]] = set()
    for each_entry in read_policy_entries(repository_root, family.field_name):
        relative_path, digest = entry_path_and_digest(each_entry, family.subject)
        identity = (relative_path, family.category, digest)
        if identity in exemptions:
            raise PolicyConfigurationRunFatal(
                f"Duplicate repository {family.subject.lower()}"
            )
        exemptions.add(identity)
    return frozenset(exemptions)


def load_all_match_exemptions(
    repository_root: Path,
) -> frozenset[tuple[str, str, str]]:
    """Read every family of matches the repository owns.

    Args:
        repository_root: Repository containing the optional policy configuration.
    Returns:
        Exact path, scanner category, and digest identities across all families.
    Raises:
        ValueError: Configuration contains invalid JSON or schema fields.
        OSError: Configuration cannot be read.
    """
    return frozenset().union(
        *(
            load_match_exemptions(repository_root, each_family)
            for each_family in ALL_MATCH_EXEMPTION_FAMILIES
        )
    )
