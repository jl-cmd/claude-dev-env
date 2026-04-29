"""Specifications that LLM review docs match hook-enforced CODE_RULES exemptions."""

from pathlib import Path


def _repository_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _bugbot_text() -> str:
    bugbot_path = _repository_root() / ".cursor" / "BUGBOT.md"
    return bugbot_path.read_text(encoding="utf-8")


def _agents_instructions_text() -> str:
    agents_path = _repository_root() / "AGENTS.md"
    return agents_path.read_text(encoding="utf-8")


def _agents_instructions_part1_text() -> str:
    text = _agents_instructions_text()
    part2_marker = "\n## Part 2"
    if part2_marker in text:
        return text.split(part2_marker, maxsplit=1)[0]
    return text


def _copilot_instructions_part1_text() -> str:
    text = _copilot_instructions_text()
    part_marker = "\n## Part 2"
    if part_marker in text:
        return text.split(part_marker, maxsplit=1)[0]
    return text


def _slice_named_section(
    document_text: str, section_heading: str, section_end_marker: str
) -> str:
    start_offset = document_text.find(section_heading)
    assert start_offset != -1, (
        f"Section heading {section_heading!r} not found in document "
        f"(first 200 chars: {document_text[:200]!r})"
    )
    after_start = document_text[start_offset:]
    end_offset = after_start.find(section_end_marker)
    if end_offset == -1:
        return after_start
    return after_start[:end_offset]


def _magic_values_configuration_section(document_text: str) -> str:
    return _slice_named_section(
        document_text,
        section_heading="### Magic values & configuration",
        section_end_marker="\n### Types",
    )


def _structure_section(document_text: str) -> str:
    return _slice_named_section(document_text, section_heading="### Structure", section_end_marker="\n### ")


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
    text = _bugbot_text()
    assert "contains the substring" in text
    workflow_bullet_start = text.find("Workflow registries:")
    assert workflow_bullet_start != -1
    newline_after_bullet = text.find("\n", workflow_bullet_start)
    workflow_bullet = text[workflow_bullet_start:newline_after_bullet]
    assert "contains the substring" in workflow_bullet
    assert "/workflow/" in workflow_bullet
    assert "/states.py" in workflow_bullet
    assert "/modules.py" in workflow_bullet
    assert "_tab.py" in workflow_bullet
    assert "basename" not in workflow_bullet.lower()


def test_bugbot_file_length_matches_hook_advisory_behavior() -> None:
    """Hook uses stderr advisories at 400 and 1000 lines; it does not block on length."""
    text = _bugbot_text()
    lower = text.lower()
    assert "400" in text
    assert "1000" in text
    assert "advisory" in lower
    assert "stderr" in lower
    assert "hard limit" not in lower


def test_agents_instructions_upper_snake_path_exemptions() -> None:
    """AGENTS Part 1 (static rubric) documents UPPER_SNAKE path exemptions without naming implementation files."""
    text = _agents_instructions_part1_text()
    lower = text.lower()
    assert "/migrations/" in text
    assert "/workflow/" in text
    assert "_tab.py" in text
    assert "/states.py" in text
    assert "/modules.py" in text
    assert "test_" in text
    assert "conftest" in text
    assert "/tests/" in text
    magic_values_section_lower = _magic_values_configuration_section(text).lower()
    assert "hook" not in magic_values_section_lower
    assert "code_rules_enforcer" not in magic_values_section_lower


def test_agents_instructions_file_length_is_advisory_signal() -> None:
    """AGENTS Part 1 (static rubric) describes length as an advisory signal emitted to stderr."""
    text = _agents_instructions_part1_text()
    lower = text.lower()
    assert "400" in text
    assert "1000" in text
    assert "advisory" in lower
    assert "stderr" in lower
    assert "hard limit" not in lower
    assert "hard gate" not in lower
    structure_section_lower = _structure_section(text).lower()
    assert "code_rules_enforcer" not in structure_section_lower
    assert "hook" not in structure_section_lower


def test_agents_workflow_registry_phrasing_describes_substring_match() -> None:
    """Workflow exemption must describe path substring matching, not basename-only matching."""
    text = _agents_instructions_text()
    workflow_label = "Workflow registries:"
    workflow_bullet_start = text.index(workflow_label)
    newline_after_bullet = text.index("\n", workflow_bullet_start)
    workflow_bullet = text[workflow_bullet_start:newline_after_bullet]
    lower_bullet = workflow_bullet.lower()
    assert "substring" in lower_bullet
    assert "/workflow/" in workflow_bullet
    assert "/states.py" in workflow_bullet
    assert "/modules.py" in workflow_bullet
    assert "_tab.py" in workflow_bullet
    assert "basename" not in lower_bullet
