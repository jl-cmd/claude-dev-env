"""Load exact-value scanner exceptions owned by a repository."""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from repository_checks.config.policy_document import (
    EMAIL_CATEGORY,
    EMAIL_EXEMPTION_SUBJECT,
    EMAIL_EXEMPTIONS_FIELD,
    PRIVATE_IP_CATEGORY,
    PRIVATE_IP_EXEMPTION_SUBJECT,
    PRIVATE_IP_EXEMPTIONS_FIELD,
)
from repository_checks.policy_document import (
    PolicyConfigurationRunFatal,
    entry_path_and_digest,
    read_policy_entries,
)


class ExactValueExemptionFamily(NamedTuple):
    """One scanner category cleared by a committed path and value digest."""

    field_name: str
    category: str
    subject: str


EMAIL_EXEMPTION_FAMILY = ExactValueExemptionFamily(
    EMAIL_EXEMPTIONS_FIELD, EMAIL_CATEGORY, EMAIL_EXEMPTION_SUBJECT
)
PRIVATE_IP_EXEMPTION_FAMILY = ExactValueExemptionFamily(
    PRIVATE_IP_EXEMPTIONS_FIELD, PRIVATE_IP_CATEGORY, PRIVATE_IP_EXEMPTION_SUBJECT
)
ALL_EXACT_VALUE_EXEMPTION_FAMILIES = (
    EMAIL_EXEMPTION_FAMILY,
    PRIVATE_IP_EXEMPTION_FAMILY,
)


def load_exact_value_exemptions(
    repository_root: Path, family: ExactValueExemptionFamily
) -> frozenset[tuple[str, str, str]]:
    """Read one family of validated exact-value exceptions.

    ::

        load_exact_value_exemptions(root, EMAIL_EXEMPTION_FAMILY)
        ok:   {("contacts.py", "email", "<digest of the address>")}
        flag: reading the private-IP list through the email family

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


def load_all_exact_value_exemptions(
    repository_root: Path,
) -> frozenset[tuple[str, str, str]]:
    """Read every family of validated exact-value exceptions.

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
            load_exact_value_exemptions(repository_root, each_family)
            for each_family in ALL_EXACT_VALUE_EXEMPTION_FAMILIES
        )
    )
