"""Contract tests for the PR description writer voice."""

from pathlib import Path


AGENT_PATH = Path(__file__).parent / "pr-description-writer.md"


def test_pr_description_writer_requires_plain_illustrative_voice() -> None:
    agent_text = AGENT_PATH.read_text(encoding="utf-8")

    for required_text in (
        "PR #2562",
        "PR #1150",
        "Explain the change so a kid could picture it.",
        "Before / After",
        "operation id",
        "finder’s name tag",
        "found it",
        "missing",
        "duplicated",
    ):
        assert required_text in agent_text


def test_pr_description_writer_requires_visible_pr_shape() -> None:
    agent_text = AGENT_PATH.read_text(encoding="utf-8")

    for required_heading in (
        "### What this adds",
        "### Why",
        "### Verification",
    ):
        assert required_heading in agent_text
