"""Repository public-email exception schema."""

import re

CONFIG_RELATIVE_PATH = "config/repository-policy.json"
DIGEST_PATTERN = re.compile(r"[0-9a-f]{64}")
FORBIDDEN_PATH_CHARACTERS = frozenset("\\:*?[]")
ALL_ENTRY_FIELDS = frozenset({"path", "sha256", "reason"})
ALL_FORBIDDEN_PATH_SEGMENTS = frozenset({"", ".", ".."})
FIRST_PRINTABLE_CODEPOINT = 32
