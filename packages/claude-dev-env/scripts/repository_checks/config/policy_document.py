"""Repository policy document and exception-entry schema."""

import re

CONFIG_RELATIVE_PATH = "config/repository-policy.json"
DIGEST_PATTERN = re.compile(r"[0-9a-f]{64}")
FORBIDDEN_PATH_CHARACTERS = frozenset("\\:*?[]")
ALL_ENTRY_FIELDS = frozenset({"path", "sha256", "reason"})
ALL_FORBIDDEN_PATH_SEGMENTS = frozenset({"", ".", ".."})
FIRST_PRINTABLE_CODEPOINT = 32
VERSION_FIELD = "version"
SUPPORTED_DOCUMENT_VERSION = 1
EMAIL_EXEMPTIONS_FIELD = "email_exemptions"
PATH_EXEMPTIONS_FIELD = "path_exemptions"
ALL_EXEMPTION_FIELDS = frozenset({EMAIL_EXEMPTIONS_FIELD, PATH_EXEMPTIONS_FIELD})
ALL_DOCUMENT_FIELDS = ALL_EXEMPTION_FIELDS | {VERSION_FIELD}
EMAIL_EXEMPTION_SUBJECT = "Email exemption"
PATH_EXEMPTION_SUBJECT = "Path exemption"
EMAIL_CATEGORY = "email"
