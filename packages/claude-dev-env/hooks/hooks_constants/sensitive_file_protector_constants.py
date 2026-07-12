"""Constants for the ``sensitive_file_protector`` PreToolUse hook.

The hook denies a Write or Edit whose target basename names a live secret or a
lock file, and steps aside for a placeholders-only committed template.
"""

from __future__ import annotations

ALL_SENSITIVE_PATTERNS = (
    ".env",
    ".env.*",
    "*.env",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "credentials.json",
    "secrets.json",
    "id_rsa",
    "id_ed25519",
    "package-lock.json",
    "yarn.lock",
    "Pipfile.lock",
    "poetry.lock",
    "pnpm-lock.yaml",
    "composer.lock",
)

ALL_TEMPLATE_SUFFIXES = (".example", ".sample", ".template")

ALL_WRITE_EDIT_TOOLS = ("Write", "Edit")

HOOK_SCRIPT_NAME = "sensitive_file_protector.py"

HOOK_EVENT_NAME = "PreToolUse"

DENY_DECISION = "deny"

DENY_REASON_TEMPLATE = (
    "BLOCKED: Sensitive file '{filename}' (pattern: '{matched_pattern}'). "
    "Edit manually outside Claude Code."
)
