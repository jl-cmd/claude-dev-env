"""Specifications for holding a merge policy document to its branch ruleset."""

from __future__ import annotations

import json
from pathlib import Path

from merge_gate_checks import (
    main,
    missing_contexts,
    parse_declared_contexts,
    ruleset_contexts,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
POLICY_DOCUMENT_PATH = REPOSITORY_ROOT / "docs" / "merge-policy.md"
RULESET_SNAPSHOT_PATH = REPOSITORY_ROOT / "docs" / "merge-policy-ruleset.json"
INSTRUCTION_PAIRS_CONTEXT = "instruction-pairs / instruction-pairs"
UTF8_ENCODING = "utf-8"


def _ruleset_with_contexts(*all_contexts: str) -> list[dict[str, object]]:
    return [
        {"type": "deletion"},
        {
            "type": "required_status_checks",
            "parameters": {
                "required_status_checks": [
                    {"context": each_context, "integration_id": 15368}
                    for each_context in all_contexts
                ]
            },
        },
    ]


def should_read_the_contexts_the_fenced_block_declares() -> None:
    document_text = (
        "# Merge policy\n\n"
        "```required-status-checks\n"
        f"{INSTRUCTION_PAIRS_CONTEXT}\n"
        "```\n\n"
        "```\n"
        "python merge_gate_checks.py --refresh\n"
        "```\n"
    )

    assert parse_declared_contexts(document_text) == [INSTRUCTION_PAIRS_CONTEXT]


def should_ignore_a_document_with_no_declaration_block() -> None:
    assert parse_declared_contexts("# Merge policy\n\nNo block here.\n") == []


def should_read_every_context_the_ruleset_requires() -> None:
    payload = _ruleset_with_contexts(INSTRUCTION_PAIRS_CONTEXT, "Ruff")

    assert ruleset_contexts(payload) == {INSTRUCTION_PAIRS_CONTEXT, "Ruff"}


def should_report_a_check_the_ruleset_stopped_requiring() -> None:
    document_text = f"```required-status-checks\n{INSTRUCTION_PAIRS_CONTEXT}\n```\n"

    assert missing_contexts(document_text, _ruleset_with_contexts("Ruff")) == [
        INSTRUCTION_PAIRS_CONTEXT
    ]


def should_find_every_check_the_checked_in_policy_names() -> None:
    document_text = POLICY_DOCUMENT_PATH.read_text(encoding=UTF8_ENCODING)
    ruleset_payload = json.loads(
        RULESET_SNAPSHOT_PATH.read_text(encoding=UTF8_ENCODING)
    )

    assert parse_declared_contexts(document_text)
    assert missing_contexts(document_text, ruleset_payload) == []


def should_exit_non_zero_when_a_named_check_left_the_ruleset(tmp_path: Path) -> None:
    document_path = tmp_path / "merge-policy.md"
    document_path.write_text(
        f"```required-status-checks\n{INSTRUCTION_PAIRS_CONTEXT}\n```\n",
        encoding=UTF8_ENCODING,
    )
    ruleset_path = tmp_path / "merge-policy-ruleset.json"
    ruleset_path.write_text(
        json.dumps(_ruleset_with_contexts("Ruff")), encoding=UTF8_ENCODING
    )

    exit_code = main(["--document", str(document_path), "--ruleset", str(ruleset_path)])

    assert exit_code == 1
