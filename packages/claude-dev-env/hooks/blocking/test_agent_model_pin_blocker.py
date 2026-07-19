"""Tests for the agent_model_pin_blocker PreToolUse hook."""

import sys
from pathlib import Path

import pytest
import yaml

try:
    from agent_model_pin_blocker import (
        evaluate,
        frontmatter_pins_concrete_model,
        is_agent_definition_path,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from agent_model_pin_blocker import (
        evaluate,
        frontmatter_pins_concrete_model,
        is_agent_definition_path,
    )

PACKAGE_AGENT_PATH = "packages/claude-dev-env/agents/clean-coder.md"
INSTALLED_AGENT_PATH = "/home/user/.claude/agents/clean-coder.md"
WINDOWS_AGENT_PATH = r"C:\repo\packages\claude-dev-env\agents\clean-coder.md"
NON_AGENT_PATH = "packages/claude-dev-env/docs/notes.md"
UNTERMINATED_QUOTE_BLOCK = "name: sample\nmodel: 'inherit\n"


def _write_payload(file_path: str, content: str) -> dict[str, object]:
    return {
        "tool_name": "Write",
        "tool_input": {"file_path": file_path, "content": content},
    }


def _pinned_agent_file(model_line: str) -> str:
    return f"---\nname: sample\n{model_line}\n---\n\nBody text.\n"


@pytest.mark.parametrize(
    ("frontmatter_block", "expected_pin_verdict"),
    [
        ("name: sample\nmodel: opus\n", True),
        ("name: sample\nmodel: inherit\nmodel: opus\n", True),
        ("name: sample\nmodel: opus\nmodel: inherit\n", False),
        ("name: sample\nmodel:\n", False),
        ("name: sample\nmodel: inherit\n", False),
        ('name: sample\nmodel: "inherit"\n', False),
        ('name: sample\nmodel: "inherit "\n', False),
        ("name: sample\nmodel: Inherit\n", False),
        ("name: sample\nmodel: inherit  # loader default\n", False),
        ("name: sample\ncolor: green\n", False),
    ],
    ids=[
        "bare-alias-pin",
        "inherit-then-opus-last-pins",
        "opus-then-inherit-not-a-pin",
        "bare-model-key-none",
        "inherit",
        "quoted-inherit",
        "quoted-inherit-trailing-space",
        "title-case-inherit",
        "commented-inherit",
        "no-model-key",
    ],
)
def test_pin_detector_flags_every_concrete_value(
    frontmatter_block: str, expected_pin_verdict: bool
) -> None:
    assert frontmatter_pins_concrete_model(frontmatter_block) is expected_pin_verdict


DESCRIPTION_WITH_COLONS_BLOCK = (
    "name: sample\n"
    "description: Use this agent when needed. Examples:\n"
    "\n"
    "  <example>\n"
    '  Context: User wants a report\n'
    '  user: "Research this topic"\n'
    "  </example>\n"
)


def test_pin_detector_ignores_colon_laden_description_without_model() -> None:
    assert frontmatter_pins_concrete_model(DESCRIPTION_WITH_COLONS_BLOCK) is False


def test_pin_detector_flags_model_beside_colon_laden_description() -> None:
    block_with_pin = DESCRIPTION_WITH_COLONS_BLOCK + "model: opus\n"
    assert frontmatter_pins_concrete_model(block_with_pin) is True


def test_pin_detector_raises_on_unterminated_quote() -> None:
    with pytest.raises(yaml.YAMLError):
        frontmatter_pins_concrete_model(UNTERMINATED_QUOTE_BLOCK)


def test_evaluate_allows_unterminated_quote_fragment() -> None:
    payload = _write_payload(PACKAGE_AGENT_PATH, f"---\n{UNTERMINATED_QUOTE_BLOCK}---\n\nBody.\n")
    assert evaluate(payload) is None


@pytest.mark.parametrize(
    "agent_file_path",
    [PACKAGE_AGENT_PATH, INSTALLED_AGENT_PATH, WINDOWS_AGENT_PATH],
)
def test_evaluate_denies_pinned_model_on_agent_write(agent_file_path: str) -> None:
    payload = _write_payload(agent_file_path, _pinned_agent_file("model: opus"))
    deny_reason = evaluate(payload)
    assert deny_reason is not None
    assert agent_file_path in deny_reason


def test_evaluate_allows_inherit_model_on_agent_write() -> None:
    payload = _write_payload(PACKAGE_AGENT_PATH, _pinned_agent_file("model: inherit"))
    assert evaluate(payload) is None


def test_evaluate_allows_agent_write_without_model_key() -> None:
    payload = _write_payload(PACKAGE_AGENT_PATH, "---\nname: sample\ncolor: green\n---\n\nBody.\n")
    assert evaluate(payload) is None


def test_evaluate_ignores_column_zero_model_line_in_body() -> None:
    content = (
        "---\nname: sample\ncolor: green\n---\n\n"
        "Body prose about configuration.\nmodel: opus\nMore prose.\n"
    )
    payload = _write_payload(PACKAGE_AGENT_PATH, content)
    assert evaluate(payload) is None


def test_evaluate_ignores_non_agent_markdown() -> None:
    payload = _write_payload(NON_AGENT_PATH, _pinned_agent_file("model: opus"))
    assert evaluate(payload) is None


def test_evaluate_ignores_non_write_tool() -> None:
    payload = {
        "tool_name": "Read",
        "tool_input": {"file_path": PACKAGE_AGENT_PATH},
    }
    assert evaluate(payload) is None


def test_evaluate_denies_pinned_model_on_multiedit() -> None:
    payload = {
        "tool_name": "MultiEdit",
        "tool_input": {
            "file_path": PACKAGE_AGENT_PATH,
            "edits": [{"old_string": "x", "new_string": _pinned_agent_file("model: haiku")}],
        },
    }
    deny_reason = evaluate(payload)
    assert deny_reason is not None
    assert PACKAGE_AGENT_PATH in deny_reason


def test_is_agent_definition_path_discriminates_markdown_from_other() -> None:
    assert is_agent_definition_path(PACKAGE_AGENT_PATH) is True
    assert (
        is_agent_definition_path("packages/claude-dev-env/agents/clean-coder.py")
        is False
    )
