"""Tests for the shared agent-model-pin detection helpers."""

import pytest
import yaml

from hooks_constants.agent_model_pin_detection import (
    extract_frontmatter_block,
    frontmatter_pins_concrete_model,
    is_agent_definition_path,
    raw_last_model_line_pins,
)

PACKAGE_AGENT_PATH = "packages/claude-dev-env/agents/clean-coder.md"
INSTALLED_AGENT_PATH = "/home/user/.claude/agents/clean-coder.md"
WINDOWS_AGENT_PATH = r"C:\Repo\Packages\Claude-Dev-Env\Agents\Clean-Coder.md"


@pytest.mark.parametrize(
    ("frontmatter_block", "expected_pin_verdict"),
    [
        ("name: sample\nmodel: opus\n", True),
        ("name: sample\nmodel: inherit\nmodel: opus\n", True),
        ("name: sample\nmodel: opus\nmodel: inherit\n", False),
        ("name: sample\nmodel: inherit#opus\n", True),
        ('name: sample\nmodel: "inherit # not a comment"\n', True),
        ("name: sample\nmodel:\n", False),
        ("name: sample\nmodel: inherit\n", False),
        ('name: sample\nmodel: "inherit"\n', False),
        ('name: sample\nmodel: "inherit "\n', False),
        ('name: sample\nmodel: "inherit"  # quoted then comment\n', False),
        ("name: sample\nmodel: Inherit\n", False),
        ("name: sample\nmodel: inherit  # loader default\n", False),
        ("name: sample\ncolor: green\n", False),
    ],
    ids=[
        "bare-alias-pin",
        "duplicate-key-opus-last-pins",
        "duplicate-key-inherit-last-not-a-pin",
        "hash-embedded-pin",
        "quoted-value-with-hash-pin",
        "bare-model-key-none",
        "inherit",
        "quoted-inherit",
        "quoted-inherit-trailing-space",
        "quoted-inherit-then-comment",
        "title-case-inherit",
        "commented-inherit",
        "no-model-key",
    ],
)
def test_pin_detector_flags_every_concrete_value(
    frontmatter_block: str, expected_pin_verdict: bool
) -> None:
    assert frontmatter_pins_concrete_model(frontmatter_block) is expected_pin_verdict


def test_pin_detector_raises_on_unterminated_quote() -> None:
    with pytest.raises(yaml.YAMLError):
        frontmatter_pins_concrete_model("name: sample\nmodel: 'inherit\n")


@pytest.mark.parametrize(
    ("frontmatter_block", "expected_pin_verdict"),
    [
        ("name: sample\nmodel: 'opus\n", True),
        ("name: sample\nmodel: 'inherit\n", False),
        ('name: sample\nmodel: "sonn\n', True),
        ("name: sample\nmodel:\n", False),
        ("name: sample\ncolor: green\n", False),
    ],
    ids=[
        "unterminated-opus-pins",
        "unterminated-inherit-allows",
        "unterminated-partial-model-pins",
        "bare-model-none",
        "no-model-key",
    ],
)
def test_raw_fallback_reads_the_last_model_line(
    frontmatter_block: str, expected_pin_verdict: bool
) -> None:
    assert raw_last_model_line_pins(frontmatter_block) is expected_pin_verdict


def test_extract_frontmatter_block_returns_text_between_fences() -> None:
    file_content = "---\nname: sample\nmodel: inherit\n---\n\nBody.\n"
    assert extract_frontmatter_block(file_content) == "name: sample\nmodel: inherit"


def test_extract_frontmatter_block_ignores_mid_line_fence_in_description() -> None:
    file_content = (
        "---\nname: sample\ndescription: use a --- separator in output\nmodel: opus\n---\n\nBody.\n"
    )
    block = extract_frontmatter_block(file_content)
    assert block is not None
    assert frontmatter_pins_concrete_model(block) is True


def test_extract_frontmatter_block_returns_none_without_opening_fence() -> None:
    assert extract_frontmatter_block("# agents\n\nSome docs.\n") is None


@pytest.mark.parametrize(
    "agent_file_path",
    [PACKAGE_AGENT_PATH, INSTALLED_AGENT_PATH, WINDOWS_AGENT_PATH],
)
def test_is_agent_definition_path_accepts_agent_markdown(agent_file_path: str) -> None:
    assert is_agent_definition_path(agent_file_path) is True


@pytest.mark.parametrize(
    "non_agent_path",
    [
        "packages/claude-dev-env/agents/clean-coder.py",
        "packages/claude-dev-env/agents/CLAUDE.md",
        "packages/claude-dev-env/agents/README.md",
        "packages/claude-dev-env/docs/notes.md",
    ],
)
def test_is_agent_definition_path_rejects_non_agent_files(non_agent_path: str) -> None:
    assert is_agent_definition_path(non_agent_path) is False
