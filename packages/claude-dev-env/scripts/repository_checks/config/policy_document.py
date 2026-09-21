"""Repository policy document and exception-entry schema."""

import re
from typing import NamedTuple

CONFIG_RELATIVE_PATH = "config/repository-policy.json"
DIGEST_PATTERN = re.compile(r"[0-9a-f]{64}")
FORBIDDEN_PATH_CHARACTERS = frozenset("\\:*?[]")
ALL_ENTRY_FIELDS = frozenset({"path", "sha256", "reason"})
ALL_FORBIDDEN_PATH_SEGMENTS = frozenset({"", ".", ".."})
FIRST_PRINTABLE_CODEPOINT = 32
VERSION_FIELD = "version"
SUPPORTED_DOCUMENT_VERSION = 1
EMAIL_EXEMPTIONS_FIELD = "email_exemptions"
PRIVATE_IP_EXEMPTIONS_FIELD = "private_ip_exemptions"
PATH_EXEMPTIONS_FIELD = "path_exemptions"
ALL_EXEMPTION_FIELDS = frozenset(
    {EMAIL_EXEMPTIONS_FIELD, PRIVATE_IP_EXEMPTIONS_FIELD, PATH_EXEMPTIONS_FIELD}
)
ALL_DOCUMENT_FIELDS = ALL_EXEMPTION_FIELDS | {VERSION_FIELD}
EMAIL_EXEMPTION_SUBJECT = "Email exemption"
PRIVATE_IP_EXEMPTION_SUBJECT = "Private IP exemption"
PATH_EXEMPTION_SUBJECT = "Path exemption"
EMAIL_CATEGORY = "email"
PRIVATE_IP_CATEGORY = "private-ip"


class MatchExemptionFamily(NamedTuple):
    """One scanner category cleared by a committed path and match digest."""

    field_name: str
    category: str
    subject: str


EMAIL_EXEMPTION_FAMILY = MatchExemptionFamily(
    EMAIL_EXEMPTIONS_FIELD, EMAIL_CATEGORY, EMAIL_EXEMPTION_SUBJECT
)
PRIVATE_IP_EXEMPTION_FAMILY = MatchExemptionFamily(
    PRIVATE_IP_EXEMPTIONS_FIELD, PRIVATE_IP_CATEGORY, PRIVATE_IP_EXEMPTION_SUBJECT
)
ALL_MATCH_EXEMPTION_FAMILIES = (
    EMAIL_EXEMPTION_FAMILY,
    PRIVATE_IP_EXEMPTION_FAMILY,
)
