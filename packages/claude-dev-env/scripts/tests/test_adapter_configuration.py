"""Incremental migration tests for the hook-configuration lint rule."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from policy_lint import adapters
from policy_lint.model import Document


def _hook_document(all_commands: list[str], prior_text: str) -> Document:
    current_text = json.dumps(
        {
            "hooks": {
                "PreToolUse": [
                    {
                        "hooks": [
                            {"command": each_command} for each_command in all_commands
                        ]
                    }
                ]
            }
        }
    )
    return replace(
        Document.from_text("hooks/hooks.json", current_text),
        prior_text=prior_text,
    )


def test_incremental_blocker_removal_is_clean(tmp_path: Path) -> None:
    prior_text = _hook_document(
        ["hooks/blocking/first.py", "hooks/blocking/second.py"],
        '{"hooks": {}}',
    ).text
    current_document = _hook_document(
        ["hooks/blocking/second.py"],
        prior_text,
    )
    assert adapters.hook_configuration_diagnostics(current_document, tmp_path) == ()


def test_new_blocker_in_staged_change_is_rejected(tmp_path: Path) -> None:
    current_document = _hook_document(
        ["hooks/blocking/new.py"],
        '{"hooks": {}}',
    )
    all_diagnostics = adapters.hook_configuration_diagnostics(
        current_document, tmp_path
    )
    assert len(all_diagnostics) == 1
    assert all_diagnostics[0].rule_id == "hook-configuration"
