"""Contract tests for the PR description writer voice."""

from pathlib import Path


AGENT_DIRECTORY = Path(__file__).parent
AGENT_PATH = AGENT_DIRECTORY / "pr-description-writer.md"
VOICE_REFERENCE_PATH = AGENT_DIRECTORY / "reference" / "pr-description-illustrative-voice.md"
VERIFICATION_REFERENCE_PATH = AGENT_DIRECTORY / "reference" / "pr-description-verification.md"


def test_pr_description_writer_uses_repo_owned_progressive_samples() -> None:
    agent_text = AGENT_PATH.read_text(encoding="utf-8")

    assert "reference/pr-description-illustrative-voice.md" in agent_text
    assert "reference/pr-description-verification.md" in agent_text
    assert "only when needed" in agent_text
    assert "PR #2562" not in agent_text
    assert "PR #1150" not in agent_text


def test_voice_reference_keeps_the_plain_illustrative_shape() -> None:
    reference_text = VOICE_REFERENCE_PATH.read_text(encoding="utf-8")

    for required_text in (
        "Before:",
        "After:",
        "finder’s name tag",
        "found it",
        "missing",
        "duplicated",
        "Why",
        "Verification",
    ):
        assert required_text in reference_text


def test_verification_leads_with_a_human_visible_check() -> None:
    agent_text = AGENT_PATH.read_text(encoding="utf-8")
    reference_text = VERIFICATION_REFERENCE_PATH.read_text(encoding="utf-8")

    for visible_action in ("open", "see", "click", "compare", "try"):
        assert visible_action in agent_text
        assert visible_action in reference_text
    assert "Tests: focused checks pass." in reference_text
    assert "Machine checks can support the claim." in reference_text
