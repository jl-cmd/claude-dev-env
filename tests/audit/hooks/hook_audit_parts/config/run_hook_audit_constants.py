"""Paths, table columns, and default case rows the hook audit run reads."""

from __future__ import annotations

from pathlib import Path

HOOKS_AUDIT_DIRECTORY = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = HOOKS_AUDIT_DIRECTORY.parents[2]
DEFAULT_PLUGIN_ROOT = REPOSITORY_ROOT / "packages" / "claude-dev-env"
EVIDENCE_DIRECTORY = REPOSITORY_ROOT / "tests" / "audit" / "data"
DEFAULT_CASES_FILE_NAME = "hook_cases.json"
HOOKS_REGISTRATION_RELATIVE_PATH = Path("hooks") / "hooks.json"
SCRATCH_PREFIX = "hook-audit-"
STDERR_HEAD_CHARACTERS = 200
REASON_SEPARATOR = "; "
COLUMN_TEXT_SEPARATOR = " | "
TABLE_DELIMITER = "\t"
TABLE_LINE_TERMINATOR = "\n"
UTF8_ENCODING = "utf-8"
ALL_DEFAULT_CASES: list[dict[str, object]] = [
    {"kind": "malformed", "expect": {}},
    {
        "kind": "non_matching",
        "event": "PreToolUse",
        "payload": {
            "tool_name": "Read",
            "tool_input": {"file_path": "{sandbox}/notes.txt"},
        },
        "expect": {"outcome": "silent"},
    },
]
ALL_CASE_RUN_COLUMNS = [
    "hook_id",
    "kind",
    "hosted_hook",
    "matcher_hit",
    "expected",
    "observed",
    "pass",
    "exit_code",
    "wall_ms",
    "injected_characters",
    "effect_failures",
    "claim_chain",
    "stderr_head",
]
ALL_VERDICT_COLUMNS = [
    "hook_id",
    "event",
    "matcher",
    "claim",
    "component_class",
    "mechanism_verdict",
    "prohibited_result",
    "near_neighbor_result",
    "malformed_result",
    "non_matching_result",
    "redundancy_result",
    "median_wall_ms",
    "injected_characters",
    "reasons",
]
