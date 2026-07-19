"""Tests for the shared agent-model-pin detection helpers.

The hand-written scan reads YAML scalar semantics without a YAML library.
test_hand_parser_agrees_with_yaml_oracle pins it to yaml.safe_load over the
well-formed matrix, so any scalar-semantics divergence fails here rather than
shipping. The over-catch cases (yaml raises or returns a non-mapping) and the
malformed cases sit in their own contract tests, since the library refuses to
parse them the same way.
"""

import pytest
import yaml

from hooks_constants.agent_model_pin_detection import (
    extract_frontmatter_block,
    frontmatter_pins_concrete_model,
    is_agent_definition_path,
    pinned_model_value,
    pinned_or_malformed,
)

PACKAGE_AGENT_PATH = "packages/claude-dev-env/agents/clean-coder.md"
INSTALLED_AGENT_PATH = "/home/user/.claude/agents/clean-coder.md"
WINDOWS_AGENT_PATH = r"C:\Repo\Packages\Claude-Dev-Env\Agents\Clean-Coder.md"

YAML_CLEAN_BLOCKS = [
    "name: sample\nmodel: opus\n",
    "name: sample\nmodel: inherit\n",
    "name: sample\nmodel:\n",
    'name: sample\nmodel: "inherit"\n',
    "name: sample\nmodel: 'inherit'\n",
    'name: sample\nmodel: "inherit "\n',
    'name: sample\nmodel: "inherit"  # trailing comment\n',
    "name: sample\nmodel: Inherit\n",
    "name: sample\nmodel: inherit  # loader default\n",
    "name: sample\nmodel: inherit#opus\n",
    'name: sample\nmodel: "inherit # not a comment"\n',
    "name: sample\nmodel: opus\nmodel: inherit\n",
    "name: sample\nmodel: inherit\nmodel: opus\n",
    "name: sample\nmodel : opus\n",
    "name: sample\nmodel : inherit\n",
    "name: sample\nmodel: null\n",
    "name: sample\nmodel: Null\n",
    "name: sample\nmodel: NULL\n",
    "name: sample\nmodel: ~\n",
    "name: sample\nmodel: \xa0\n",
    "name: sample\ncolor: green\n",
]


def _yaml_oracle_pins(frontmatter_block: str) -> bool:
    parsed_frontmatter = yaml.safe_load(frontmatter_block)
    assert isinstance(parsed_frontmatter, dict)
    declared_model = parsed_frontmatter.get("model")
    if declared_model is None:
        return False
    return str(declared_model).strip().lower() != "inherit"


@pytest.mark.parametrize("frontmatter_block", YAML_CLEAN_BLOCKS)
def test_hand_parser_agrees_with_yaml_oracle(frontmatter_block: str) -> None:
    assert (
        frontmatter_pins_concrete_model(frontmatter_block)
        is _yaml_oracle_pins(frontmatter_block)
    )


@pytest.mark.parametrize(
    ("frontmatter_block", "expected_pin_verdict"),
    [
        ("name: sample\nmodel:opus\n", True),
        ("name: sample\nmodel:inherit\n", False),
    ],
    ids=["no-space-opus-pins", "no-space-inherit-allows"],
)
def test_hand_parser_over_catches_no_space_colon(
    frontmatter_block: str, expected_pin_verdict: bool
) -> None:
    assert frontmatter_pins_concrete_model(frontmatter_block) is expected_pin_verdict


@pytest.mark.parametrize(
    "frontmatter_block",
    [
        "name: sample\nmodel: 'opus\n",
        'name: sample\nmodel: "opus\n',
        'name: sample\nmodel: "inherit"opus\n',
        "name: sample\nmodel: \"inherit'\n",
        "name: sample\nmodel: 'inherit'' opus-4'\n",
        "name: sample\nmodel: |\n",
        "name: sample\nmodel: >\n",
    ],
    ids=[
        "unterminated-single",
        "unterminated-double",
        "content-after-close-quote",
        "mismatched-quote",
        "escaped-quote-then-content",
        "block-scalar-literal",
        "block-scalar-folded",
    ],
)
def test_malformed_model_line_is_flagged(frontmatter_block: str) -> None:
    pinned_value, is_malformed = pinned_or_malformed(frontmatter_block)
    assert is_malformed is True
    assert pinned_value is None


@pytest.mark.parametrize(
    ("frontmatter_block", "expected"),
    [
        ("name: sample\nmodel: opus\n", ("opus", False)),
        ("name: sample\nmodel: inherit\n", (None, False)),
        ("name: sample\nmodel: null\n", (None, False)),
        ("name: sample\nmodel:\n", (None, False)),
        ("name: sample\ncolor: green\n", (None, False)),
        ("name: sample\nmodel: |\n", (None, True)),
    ],
    ids=["concrete", "inherit", "null", "bare", "no-model", "malformed"],
)
def test_pinned_or_malformed_classifies_the_last_line(
    frontmatter_block: str, expected: tuple[str | None, bool]
) -> None:
    assert pinned_or_malformed(frontmatter_block) == expected


@pytest.mark.parametrize(
    ("frontmatter_block", "expected_value"),
    [
        ("name: sample\nmodel: opus\n", "opus"),
        ("name: sample\nmodel:opus\n", "opus"),
        ("name: sample\nmodel : haiku\n", "haiku"),
        ("name: sample\nmodel: inherit\n", None),
        ("name: sample\nmodel: 'opus\n", None),
        ("name: sample\nmodel:\n", None),
    ],
    ids=["opus", "no-space-opus", "space-before-haiku", "inherit", "malformed", "bare"],
)
def test_pinned_model_value_returns_the_value(
    frontmatter_block: str, expected_value: str | None
) -> None:
    assert pinned_model_value(frontmatter_block) == expected_value


def test_extract_returns_text_between_fences() -> None:
    file_content = "---\nname: sample\nmodel: inherit\n---\n\nBody.\n"
    assert extract_frontmatter_block(file_content) == "name: sample\nmodel: inherit"


def test_extract_ignores_mid_line_fence_in_description() -> None:
    file_content = (
        "---\nname: sample\ndescription: use a --- separator\nmodel: opus\n---\n"
    )
    block = extract_frontmatter_block(file_content)
    assert block is not None
    assert frontmatter_pins_concrete_model(block) is True


def test_extract_skips_byte_order_mark() -> None:
    block = extract_frontmatter_block(
        "\ufeff---\nname: sample\nmodel: opus\n---\n\nBody.\n"
    )
    assert block is not None
    assert frontmatter_pins_concrete_model(block) is True


def test_extract_skips_leading_blank_lines() -> None:
    block = extract_frontmatter_block(
        "\n\n---\nname: sample\nmodel: opus\n---\n\nBody.\n"
    )
    assert block is not None
    assert frontmatter_pins_concrete_model(block) is True


def test_extract_none_without_opening_fence() -> None:
    assert extract_frontmatter_block("# agents\n\nSome docs.\n") is None


def test_extract_none_when_body_precedes_fence() -> None:
    assert extract_frontmatter_block("# doc\n---\nmodel: opus\n---\n") is None


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
