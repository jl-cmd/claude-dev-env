"""Tests that shipped instruction surfaces carry the comment and word policies."""

from __future__ import annotations

from pathlib import Path

_PACKAGE_ROOT = Path(__file__).resolve().parents[2]


def _comment_policy_phrases() -> tuple[str, ...]:
    return (
        "when a change touches code that an existing comment describes or is attached to",
        "leave comments tied to untouched code unchanged",
        "keep comment cleanup inside the requested task",
        "production and tests follow one rule",
        "changed directive, todo, fixme, hack, xxx, and type-ignore comments are removed rather than added or justified",
    )


def _comment_policy_surfaces(package_root: Path) -> tuple[Path, ...]:
    return (
        package_root.parent.parent / "AGENTS.md",
        package_root / "AGENTS.md",
        package_root / "docs" / "CODE_RULES.md",
        package_root / "system-prompts" / "software-engineer.xml",
        package_root / ".agents" / "agents-archived" / "clean-coder.md",
        package_root / ".agents" / "agents-archived" / "code-quality-agent.md",
        package_root / "audit-rubrics-archived" / "category_rubrics" / "category-j-code-rules-compliance.md",
        package_root / "audit-rubrics-archived" / "prompts" / "category-j-code-rules-compliance.md",
        package_root / "audit-rubrics-archived" / "category_rubrics" / "category-l-behavior-equivalence.md",
        package_root / "audit-rubrics-archived" / "prompts" / "category-l-behavior-equivalence.md",
        package_root / ".agents" / "skills" / "grok-spawn" / "reference" / "worker-briefs.md",
        package_root.parent.parent / ".github" / "copilot-instructions.md",
    )


def _worker_policy_phrases() -> tuple[str, ...]:
    return (
        "do not add code comments.",
        "preserve existing comments.",
        "docstrings remain allowed.",
    )


def _worker_policy_surfaces(package_root: Path) -> tuple[Path, ...]:
    return (
        package_root.parent.parent / "AGENTS.md",
        package_root / "AGENTS.md",
        package_root / "docs" / "CODE_RULES.md",
        package_root / "system-prompts" / "software-engineer.xml",
        package_root / ".agents" / "agents-archived" / "clean-coder.md",
        package_root / ".agents" / "skills" / "grok-spawn" / "reference" / "worker-briefs.md",
        package_root.parent.parent / ".github" / "copilot-instructions.md",
    )


def _banned_word_real_phrases() -> tuple[str, ...]:
    return (
        "banned word: real",
        "never write real, really, or real-world",
        "this ban has no exception",
        "swapping in actual, actually, genuine, or true is the same move",
    )


def _banned_word_real_surfaces(package_root: Path) -> tuple[Path, ...]:
    return (
        package_root.parent.parent / "AGENTS.md",
        package_root / "AGENTS.md",
    )


def test_banned_word_real_reaches_installed_instruction_surfaces() -> None:
    all_expected_phrases = _banned_word_real_phrases()

    for each_surface_path in _banned_word_real_surfaces(_PACKAGE_ROOT):
        surface_text = each_surface_path.read_text(encoding="utf-8").lower()
        for each_phrase in all_expected_phrases:
            assert each_phrase in surface_text, each_surface_path


def test_comment_guidance_reaches_installed_instruction_surfaces() -> None:
    expected_phrases = _comment_policy_phrases()
    all_surface_paths = _comment_policy_surfaces(_PACKAGE_ROOT)

    for each_surface_path in all_surface_paths:
        surface_text = each_surface_path.read_text(encoding="utf-8").lower()
        for each_phrase in expected_phrases:
            assert each_phrase in surface_text, each_surface_path
    for each_surface_path in _worker_policy_surfaces(_PACKAGE_ROOT):
        surface_text = each_surface_path.read_text(encoding="utf-8").lower()
        for each_phrase in _worker_policy_phrases():
            assert each_phrase in surface_text, each_surface_path


def _category_l_policy_texts() -> tuple[str, str, str]:
    category_l_rubric = (
        _PACKAGE_ROOT
        / "audit-rubrics-archived"
        / "category_rubrics"
        / "category-l-behavior-equivalence.md"
    )
    category_l_prompt = (
        _PACKAGE_ROOT
        / "audit-rubrics-archived"
        / "prompts"
        / "category-l-behavior-equivalence.md"
    )
    audit_categories = _PACKAGE_ROOT / "audit-rubrics-archived" / "audit-categories.json"
    return tuple(
        each_path.read_text(encoding="utf-8").lower()
        for each_path in (category_l_rubric, category_l_prompt, audit_categories)
    )


def _comment_policy_summary_texts() -> tuple[str, str, str]:
    clean_coder = _PACKAGE_ROOT / ".agents" / "agents-archived" / "clean-coder.md"
    category_j = (
        _PACKAGE_ROOT
        / "audit-rubrics-archived"
        / "category_rubrics"
        / "category-j-code-rules-compliance.md"
    )
    code_quality = _PACKAGE_ROOT / ".agents" / "agents-archived" / "code-quality-agent.md"
    return tuple(
        each_path.read_text(encoding="utf-8").lower()
        for each_path in (clean_coder, category_j, code_quality)
    )


def test_comment_policy_uses_changed_comment_names_and_type_directives() -> None:
    category_l_rubric, category_l_prompt, audit_categories = _category_l_policy_texts()
    clean_coder, category_j, code_quality = _comment_policy_summary_texts()
    assert "| l7 | changed-comment handling" in category_l_rubric
    assert "**l7. changed-comment handling**" in category_l_prompt
    assert '"axis_name": "changed-comment handling"' in audit_categories
    assert "no type-ignore directives" in clean_coder
    assert "no `# type: ignore` directives" in category_j
    assert "production and test code" in code_quality


def test_comment_policy_removes_directive_justification_guidance() -> None:
    react_patterns = (
        _PACKAGE_ROOT / "docs" / "REACT_PATTERNS.md"
    ).read_text(encoding="utf-8").lower()
    category_e_prompt = (
        _PACKAGE_ROOT
        / "audit-rubrics-archived"
        / "prompts"
        / "category-e-dead-code.md"
    ).read_text(encoding="utf-8").lower()

    assert "resolve `@ts-ignore` and `@ts-expect-error`" in react_patterns
    assert "without clear justification" not in react_patterns
    assert "changed `# noqa` directives are removed or resolved" in category_e_prompt
    assert "every `# noqa` on an import line must be justified" not in category_e_prompt

