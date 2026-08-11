"""Specifications that LLM review docs match hook-enforced CODE_RULES exemptions."""

from __future__ import annotations

from pathlib import Path


def _repository_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _bugbot_text() -> str:
    bugbot_path = _repository_root() / ".cursor" / "BUGBOT.md"
    return bugbot_path.read_text(encoding="utf-8")


def _workflow_registry_bullet(document_text: str) -> str:
    workflow_label = "Workflow registries:"
    workflow_bullet_start = document_text.find(workflow_label)
    assert workflow_bullet_start != -1, (
        f"{workflow_label!r} not found in document "
        f"(first 200 chars: {document_text[:200]!r})"
    )
    newline_after_bullet = document_text.find("\n", workflow_bullet_start)
    if newline_after_bullet == -1:
        return document_text[workflow_bullet_start:]
    return document_text[workflow_bullet_start:newline_after_bullet]


def _assert_workflow_registry_describes_substring_match(workflow_bullet: str) -> None:
    lower_bullet = workflow_bullet.lower()
    assert "substring" in lower_bullet, (
        "Workflow registry exemption must describe path substring matching, "
        f"got: {workflow_bullet!r}"
    )
    assert any(
        each_phrase in lower_bullet
        for each_phrase in (
            "contains any of these substrings",
            "contains the substring",
            "appears as a substring",
            "as a substring",
        )
    ), (
        "Workflow registry exemption must use substring-match language "
        f"(not basename-only), got: {workflow_bullet!r}"
    )
    assert "/workflow/" in workflow_bullet
    assert "/states.py" in workflow_bullet
    assert "/modules.py" in workflow_bullet
    assert "_tab.py" in workflow_bullet
    assert "basename" not in lower_bullet


def test_bugbot_documents_upper_snake_exemptions_matching_hook() -> None:
    """code_rules_enforcer exempts migrations, workflow registries, and tests."""
    text = _bugbot_text()
    assert "/migrations/" in text
    assert "_tab.py" in text
    assert "/states.py" in text
    assert "/modules.py" in text
    assert "/workflow/" in text
    assert "conftest" in text
    assert "/tests/" in text


def test_bugbot_workflow_registry_phrasing_describes_substring_match() -> None:
    """BUGBOT phrasing must describe substring matching (hook behavior), not basename-only matching."""
    workflow_bullet = _workflow_registry_bullet(_bugbot_text())
    _assert_workflow_registry_describes_substring_match(workflow_bullet)


def test_bugbot_file_length_matches_hook_advisory_behavior() -> None:
    """Hook uses stderr advisories at 400 and 1000 lines; it does not block on length."""
    text = _bugbot_text()
    lower = text.lower()
    assert "400" in text
    assert "1000" in text
    assert "advisory" in lower
    assert "stderr" in lower
    assert "hard limit" not in lower
