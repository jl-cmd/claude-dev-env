"""Behavior tests for agent-definition YAML frontmatter.

Every agent `.md` in this directory opens with a frontmatter block the Claude
Code subagent loader reads. The loader accepts a fixed key set; an unrecognized
top-level key breaks the spawn — the subagent starts with a broken definition,
idles, and dies without a report::

    ok:   name / description / tools / model / color
    flag: effort            <- unrecognized, subagent dies delivering nothing

The accepted set is the one `agents/CLAUDE.md` documents (name, description,
tools, color) plus the optional `model` key, which every agent either omits
or sets to `inherit` — the orchestrator supplies a concrete model on every
spawn, so no agent definition pins one::

    ok:   model: inherit
    ok:   <no model key at all>
    flag: model: opus       <- pinned concrete model, caller can't override

Top-level keys are read with a line scan so an agent whose `description`
embeds informal `<example>` prose is not mistaken for one carrying extra
keys.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ACCEPTED_FRONTMATTER_KEYS = frozenset(
    {"name", "description", "tools", "model", "color"}
)
MODEL_KEY_PATTERN = re.compile(r"^model:(?P<declared_value>.*)$", re.MULTILINE)
INHERIT_MODEL_VALUE = "inherit"
MODEL_VALUE_QUOTE_CHARACTERS = "'\""
FRONTMATTER_FENCE = "---"
FRONTMATTER_SEGMENT_COUNT = 3
CODE_VERIFIER_AGENT_NAME = "code-verifier"
TOP_LEVEL_KEY_PATTERN = re.compile(r"^([a-z][a-z0-9_]*):", re.MULTILINE)


def _agent_definition_paths() -> list[Path]:
    agents_directory = Path(__file__).parent
    all_markdown_files = sorted(agents_directory.glob("*.md"))
    return [
        each_markdown_file
        for each_markdown_file in all_markdown_files
        if each_markdown_file.read_text(encoding="utf-8").startswith(FRONTMATTER_FENCE)
    ]


def _frontmatter_block(agent_definition_path: Path) -> str:
    agent_text = agent_definition_path.read_text(encoding="utf-8")
    fence_segments = agent_text.split(FRONTMATTER_FENCE, FRONTMATTER_SEGMENT_COUNT - 1)
    return fence_segments[1]


def _top_level_keys(frontmatter_block: str) -> set[str]:
    return set(TOP_LEVEL_KEY_PATTERN.findall(frontmatter_block))


def _declared_model_value(frontmatter_block: str) -> str | None:
    model_line_match = MODEL_KEY_PATTERN.search(frontmatter_block)
    if model_line_match is None:
        return None
    raw_declared_value = model_line_match.group("declared_value").strip()
    return raw_declared_value.strip(MODEL_VALUE_QUOTE_CHARACTERS).lower()


def _pins_concrete_model(frontmatter_block: str) -> bool:
    declared_model_value = _declared_model_value(frontmatter_block)
    if declared_model_value is None:
        return False
    return declared_model_value != INHERIT_MODEL_VALUE


@pytest.mark.parametrize(
    "agent_definition_path",
    _agent_definition_paths(),
    ids=lambda each_path: each_path.name,
)
def test_agent_frontmatter_uses_only_accepted_keys(
    agent_definition_path: Path,
) -> None:
    declared_keys = _top_level_keys(_frontmatter_block(agent_definition_path))
    unaccepted_keys = declared_keys - ACCEPTED_FRONTMATTER_KEYS
    assert not unaccepted_keys, (
        f"{agent_definition_path.name} carries frontmatter keys the subagent "
        f"loader does not accept: {sorted(unaccepted_keys)}"
    )


def test_code_verifier_frontmatter_parses_and_names_the_agent() -> None:
    agents_directory = Path(__file__).parent
    code_verifier_block = _frontmatter_block(
        agents_directory / f"{CODE_VERIFIER_AGENT_NAME}.md"
    )
    parsed_frontmatter = yaml.safe_load(code_verifier_block)
    assert parsed_frontmatter["name"] == CODE_VERIFIER_AGENT_NAME
    assert set(parsed_frontmatter) <= ACCEPTED_FRONTMATTER_KEYS


@pytest.mark.parametrize(
    ("synthetic_frontmatter_block", "expected_pin_verdict"),
    [
        ("name: sample\nmodel: opus\n", True),
        ('name: sample\nmodel: "opus"\n', True),
        ("name: sample\nmodel: Opus\n", True),
        ("name: sample\nmodel: opus-4-5\n", True),
        ("name: sample\nmodel: gpt-4\n", True),
        ("name: sample\nmodel: third-party\n", True),
        ("name: sample\nmodel: claude-sonnet-4-5\n", True),
        ("name: sample\nmodel: inherit\n", False),
        ('name: sample\nmodel: "inherit"\n', False),
        ("name: sample\nmodel: Inherit\n", False),
        ("name: sample\ncolor: green\n", False),
    ],
    ids=[
        "bare-alias",
        "quoted-alias",
        "title-case-alias",
        "versioned-alias",
        "foreign-model",
        "third-party-alias",
        "full-model-id",
        "inherit",
        "quoted-inherit",
        "title-case-inherit",
        "no-model-key",
    ],
)
def test_pinned_model_detection_flags_every_concrete_value(
    synthetic_frontmatter_block: str, expected_pin_verdict: bool
) -> None:
    assert _pins_concrete_model(synthetic_frontmatter_block) is expected_pin_verdict


@pytest.mark.parametrize(
    "agent_definition_path",
    _agent_definition_paths(),
    ids=lambda each_path: each_path.name,
)
def test_agent_frontmatter_carries_no_pinned_model(
    agent_definition_path: Path,
) -> None:
    frontmatter_block = _frontmatter_block(agent_definition_path)
    assert not _pins_concrete_model(frontmatter_block), (
        f"{agent_definition_path.name} pins a concrete model in frontmatter; "
        "the caller supplies the model on every spawn, so agent definitions "
        "carry no model: line or only model: inherit"
    )
