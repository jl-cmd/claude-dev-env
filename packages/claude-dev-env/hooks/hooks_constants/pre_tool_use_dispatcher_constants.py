"""Constants for the PreToolUse dispatcher that hosts Write/Edit/MultiEdit hooks.

Holds the ordered hosted-hook list with per-hook applicable-tool sets, the
special exit codes, the deny decision string, and the hook-event name. The
dispatcher imports each of these by name.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "DENY_DECISION",
    "ALLOW_DECISION",
    "HOOK_EVENT_NAME",
    "BLOCKING_CRASH_EXIT_CODE",
    "EXIT_CODE_TWO_DENY_REASON",
    "BLOCKING_CRASH_DENY_REASON",
    "WRITE_TOOL_NAME",
    "EDIT_TOOL_NAME",
    "MULTI_EDIT_TOOL_NAME",
    "ALL_WRITE_AND_EDIT_TOOL_NAMES",
    "ALL_WRITE_EDIT_MULTI_EDIT_TOOL_NAMES",
    "STATE_DESCRIPTION_BLOCKER_MODULE_NAME",
    "PLAIN_LANGUAGE_BLOCKER_MODULE_NAME",
    "HostedHookEntry",
    "ALL_HOSTED_HOOK_ENTRIES",
]

DENY_DECISION = "deny"
ALLOW_DECISION = "allow"
HOOK_EVENT_NAME = "PreToolUse"
BLOCKING_CRASH_EXIT_CODE = 2
EXIT_CODE_TWO_DENY_REASON = "[dispatcher] hook denied via exit code 2 — write blocked"
BLOCKING_CRASH_DENY_REASON = "[dispatcher] hook crash in blocking hook — write blocked for safety"

WRITE_TOOL_NAME = "Write"
EDIT_TOOL_NAME = "Edit"
MULTI_EDIT_TOOL_NAME = "MultiEdit"

ALL_WRITE_AND_EDIT_TOOL_NAMES: frozenset[str] = frozenset({WRITE_TOOL_NAME, EDIT_TOOL_NAME})
ALL_WRITE_EDIT_MULTI_EDIT_TOOL_NAMES: frozenset[str] = frozenset(
    {WRITE_TOOL_NAME, EDIT_TOOL_NAME, MULTI_EDIT_TOOL_NAME}
)


STATE_DESCRIPTION_BLOCKER_MODULE_NAME = "state_description_blocker"
PLAIN_LANGUAGE_BLOCKER_MODULE_NAME = "plain_language_blocker"


@dataclass(frozen=True)
class HostedHookEntry:
    """A single hosted hook with its applicable-tools constraint and blocking flag.

    Attributes:
        script_relative_path: Hook path relative to the hooks/ directory.
        applicable_tool_names: Tool names this hook applies to. The dispatcher
            skips the hook when the payload's tool is not in this set.
        is_blocking: True when a crash surfaces a blocking signal; False when the
            hook is advisory and a crash stays silent.
        native_module_name: The importable module name whose evaluate function
            the dispatcher calls in-process for this hook, or None when the hook
            runs via runpy under __main__. The named module exposes a function
            named `evaluate` taking the payload dict and returning a deny-reason
            string or None.
    """

    script_relative_path: str
    applicable_tool_names: frozenset[str]
    is_blocking: bool = field(default=True)
    native_module_name: str | None = field(default=None)


ALL_HOSTED_HOOK_ENTRIES: tuple[HostedHookEntry, ...] = (
    HostedHookEntry(
        script_relative_path="blocking/write_existing_file_blocker.py",
        applicable_tool_names=ALL_WRITE_AND_EDIT_TOOL_NAMES,
    ),
    HostedHookEntry(
        script_relative_path="blocking/sensitive_file_protector.py",
        applicable_tool_names=ALL_WRITE_AND_EDIT_TOOL_NAMES,
    ),
    HostedHookEntry(
        script_relative_path="validation/hook_format_validator.py",
        applicable_tool_names=ALL_WRITE_AND_EDIT_TOOL_NAMES,
    ),
    HostedHookEntry(
        script_relative_path="blocking/code_rules_enforcer.py",
        applicable_tool_names=ALL_WRITE_AND_EDIT_TOOL_NAMES,
    ),
    HostedHookEntry(
        script_relative_path="blocking/tdd_enforcer.py",
        applicable_tool_names=ALL_WRITE_AND_EDIT_TOOL_NAMES,
    ),
    HostedHookEntry(
        script_relative_path="blocking/windows_rmtree_blocker.py",
        applicable_tool_names=ALL_WRITE_AND_EDIT_TOOL_NAMES,
    ),
    HostedHookEntry(
        script_relative_path="blocking/duplicate_rmtree_helper_blocker.py",
        applicable_tool_names=ALL_WRITE_AND_EDIT_TOOL_NAMES,
    ),
    HostedHookEntry(
        script_relative_path="blocking/state_description_blocker.py",
        applicable_tool_names=ALL_WRITE_AND_EDIT_TOOL_NAMES,
        native_module_name=STATE_DESCRIPTION_BLOCKER_MODULE_NAME,
    ),
    HostedHookEntry(
        script_relative_path="blocking/stale_comment_reference_blocker.py",
        applicable_tool_names=frozenset({EDIT_TOOL_NAME}),
    ),
    HostedHookEntry(
        script_relative_path="blocking/subprocess_budget_completeness.py",
        applicable_tool_names=ALL_WRITE_AND_EDIT_TOOL_NAMES,
    ),
    HostedHookEntry(
        script_relative_path="blocking/hook_prose_detector_consistency.py",
        applicable_tool_names=ALL_WRITE_AND_EDIT_TOOL_NAMES,
    ),
    HostedHookEntry(
        script_relative_path="blocking/verified_commit_message_accuracy_blocker.py",
        applicable_tool_names=ALL_WRITE_AND_EDIT_TOOL_NAMES,
    ),
    HostedHookEntry(
        script_relative_path="blocking/workflow_substitution_slot_blocker.py",
        applicable_tool_names=ALL_WRITE_EDIT_MULTI_EDIT_TOOL_NAMES,
    ),
    HostedHookEntry(
        script_relative_path="blocking/claude_md_orphan_file_blocker.py",
        applicable_tool_names=ALL_WRITE_EDIT_MULTI_EDIT_TOOL_NAMES,
    ),
    HostedHookEntry(
        script_relative_path="blocking/package_inventory_stale_blocker.py",
        applicable_tool_names=ALL_WRITE_EDIT_MULTI_EDIT_TOOL_NAMES,
    ),
    HostedHookEntry(
        script_relative_path="blocking/env_var_table_code_drift_blocker.py",
        applicable_tool_names=ALL_WRITE_EDIT_MULTI_EDIT_TOOL_NAMES,
    ),
    HostedHookEntry(
        script_relative_path="blocking/pytest_testpaths_orphan_blocker.py",
        applicable_tool_names=ALL_WRITE_EDIT_MULTI_EDIT_TOOL_NAMES,
    ),
    HostedHookEntry(
        script_relative_path="blocking/open_questions_in_plans_blocker.py",
        applicable_tool_names=ALL_WRITE_EDIT_MULTI_EDIT_TOOL_NAMES,
    ),
    HostedHookEntry(
        script_relative_path="blocking/docstring_rule_gate_count_blocker.py",
        applicable_tool_names=ALL_WRITE_EDIT_MULTI_EDIT_TOOL_NAMES,
    ),
    HostedHookEntry(
        script_relative_path="blocking/plain_language_blocker.py",
        applicable_tool_names=ALL_WRITE_EDIT_MULTI_EDIT_TOOL_NAMES,
        native_module_name=PLAIN_LANGUAGE_BLOCKER_MODULE_NAME,
    ),
)
