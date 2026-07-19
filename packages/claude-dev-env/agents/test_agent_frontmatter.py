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

`frontmatter_pins_concrete_model` is the write-time hook's shared pin detector;
importing it here reads a pin the same way the hook does. Its exhaustive value
truth table lives beside it in
`hooks_constants/test_agent_model_pin_detection.py`.

Top-level keys are read with a line scan so an agent whose `description`
embeds informal `<example>` prose is not mistaken for one carrying extra
keys.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import pytest
import yaml

from hooks_constants.agent_model_pin_detection import frontmatter_pins_concrete_model

ACCEPTED_FRONTMATTER_KEYS = frozenset(
    {"name", "description", "tools", "model", "color"}
)
FRONTMATTER_FENCE = "---"
FRONTMATTER_SEGMENT_COUNT = 3
CODE_VERIFIER_AGENT_NAME = "code-verifier"
TOP_LEVEL_KEY_PATTERN = re.compile(r"^([a-z][a-z0-9_]*):", re.MULTILINE)


@cache
def _agent_definition_paths() -> tuple[Path, ...]:
    agents_directory = Path(__file__).parent
    all_markdown_files = sorted(agents_directory.glob("*.md"))
    return tuple(
        each_markdown_file
        for each_markdown_file in all_markdown_files
        if each_markdown_file.read_text(encoding="utf-8").startswith(FRONTMATTER_FENCE)
    )


def _frontmatter_block(agent_definition_path: Path) -> str:
    agent_text = agent_definition_path.read_text(encoding="utf-8")
    fence_segments = agent_text.split(FRONTMATTER_FENCE, FRONTMATTER_SEGMENT_COUNT - 1)
    return fence_segments[1]


def _top_level_keys(frontmatter_block: str) -> set[str]:
    return set(TOP_LEVEL_KEY_PATTERN.findall(frontmatter_block))


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
    "agent_definition_path",
    _agent_definition_paths(),
    ids=lambda each_path: each_path.name,
)
def test_agent_frontmatter_carries_no_pinned_model(
    agent_definition_path: Path,
) -> None:
    frontmatter_block = _frontmatter_block(agent_definition_path)
    assert not frontmatter_pins_concrete_model(frontmatter_block), (
        f"{agent_definition_path.name} pins a concrete model in frontmatter; "
        "the caller supplies the model on every spawn, so agent definitions "
        "carry no model: line or only model: inherit"
    )
