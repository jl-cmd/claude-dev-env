"""Output-shape constants for the verified-commit gate's deny payload.

Shared by ``verified_commit_gate.py`` and its ``verified_commit_gate_parts``
package so the PreToolUse event name, the deny decision string, the hook's
own module name for block logging, and the regex-alternation join separator
live in one place.
"""

from __future__ import annotations

PRE_TOOL_USE_HOOK_EVENT_NAME = "PreToolUse"
DENY_PERMISSION_DECISION = "deny"
GATE_HOOK_MODULE_NAME = "verified_commit_gate.py"
REGEX_ALTERNATION_SEPARATOR = "|"
