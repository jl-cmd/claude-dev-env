"""Source-contract tests for the packaged ELI5 leaf skill."""

from __future__ import annotations

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = REPOSITORY_ROOT / "packages" / "claude-dev-env" / ".agents" / "skills" / "eli5" / "SKILL.md"
INSTALLER_PATH = REPOSITORY_ROOT / "packages" / "claude-dev-env" / "bin" / "install.mjs"
README_PATH = REPOSITORY_ROOT / "README.md"


def _read(file_path: Path) -> str:
    return file_path.read_text(encoding="utf-8")


def test_eli5_skill_keeps_metadata_and_trigger_contract() -> None:
    skill_text = _read(SKILL_PATH)

    assert skill_text.startswith("---\nname: eli5\n")
    for each_trigger in (
        "ELI5",
        "explain like I am 5",
        "explain this simply",
        "beginner explanation",
        "every user-facing response",
    ):
        assert each_trigger in skill_text


def test_eli5_skill_owns_the_leaf_presentation_envelope() -> None:
    skill_text = _read(SKILL_PATH)
    lowered_skill_text = skill_text.lower()
    normalized_skill_text = " ".join(lowered_skill_text.split())

    assert "Avoid all negative prose." in skill_text.splitlines()
    for each_requirement in (
        "beginner framing",
        "large visuals",
        "minimal text",
        "one stable self-contained HTML artifact",
        "update-in-place continuity",
        "sharing",
        "~/.claude/rules/asd-ste100-language.md",
        "ELI5 is a leaf skill",
        "zero presentation sub-skills",
    ):
        assert each_requirement.lower() in normalized_skill_text


def test_eli5_skill_has_the_three_step_artifact_process() -> None:
    skill_text = _read(SKILL_PATH)

    assert "locate the current HTML artifact or create the first one." in skill_text
    assert "add the current explanation to that artifact." in skill_text
    assert "share the updated artifact with the user." in skill_text
    assert "reference/task-seeds.md" in skill_text


def test_core_install_and_readme_use_eli5_presentation() -> None:
    installer_text = _read(INSTALLER_PATH)
    readme_text = _read(README_PATH)

    assert "'eli5'" in installer_text
    assert "### Skills (27)" in readme_text
    assert "| `eli5` |" in readme_text
