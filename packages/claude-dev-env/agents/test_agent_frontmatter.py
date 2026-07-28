"""Behavior tests for agent-definition YAML frontmatter.

Every agent `.md` in this directory opens with a frontmatter block the Claude
Code subagent loader reads. The loader accepts a fixed key set; an unrecognized
top-level key breaks the spawn — the subagent starts with a broken definition,
idles, and dies without a report::

    ok:   name / description / tools / color
    flag: effort            <- unrecognized, subagent dies delivering nothing

An agent definition carries no `model` key at all — the caller supplies the
model on every spawn, so no agent definition names one, concrete or
`inherit`::

    ok:   <no model key at all>
    flag: model: inherit    <- caller can no longer choose the model
    flag: model: opus       <- pinned concrete model, caller can't override

Every block must also load through `yaml.safe_load`. An unquoted colon inside
a plain scalar reads as a mapping key and makes the whole block unloadable::

    ok:   description: ... constraints. Examples are below.
    flag: description: ... constraints. Examples:   <- block no longer loads

Frontmatter parsing is self-contained here (stdlib only): the block is the
text between the file's opening and closing `---` fence lines, and top-level
keys are read with a line scan so an agent whose `description` embeds
informal `<example>` prose is not mistaken for one carrying extra keys.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import pytest
import yaml

ACCEPTED_FRONTMATTER_KEYS = frozenset({"name", "description", "tools", "color"})
CODE_VERIFIER_AGENT_NAME = "code-verifier"
EXEMPT_MARKDOWN_FILENAME = "CLAUDE.md"
FRONTMATTER_FENCE_LINE = "---"
MODEL_KEY_NAME = "model"
TOP_LEVEL_KEY_PATTERN = re.compile(r"^([a-z][a-z0-9_]*):", re.MULTILINE)


def _extract_frontmatter_block(markdown_text: str) -> str | None:
    """Return the YAML text between the file's opening and closing --- fences.

    Args:
        markdown_text: The full text of an agent definition markdown file.

    Returns:
        The frontmatter text (the lines strictly between the two fence
        lines), or None when the file does not open with a --- fence line or
        never closes one.
    """
    all_lines = markdown_text.splitlines()
    if not all_lines or all_lines[0].strip() != FRONTMATTER_FENCE_LINE:
        return None
    for each_line_index in range(1, len(all_lines)):
        if all_lines[each_line_index].strip() == FRONTMATTER_FENCE_LINE:
            return "\n".join(all_lines[1:each_line_index])
    return None


@cache
def _agent_definition_paths() -> tuple[Path, ...]:
    agents_directory = Path(__file__).parent
    all_markdown_files = sorted(agents_directory.glob("*.md"))
    return tuple(
        each_markdown_file
        for each_markdown_file in all_markdown_files
        if each_markdown_file.name != EXEMPT_MARKDOWN_FILENAME
        and _extract_frontmatter_block(each_markdown_file.read_text(encoding="utf-8"))
        is not None
    )


def _frontmatter_block(agent_definition_path: Path) -> str:
    frontmatter_block = _extract_frontmatter_block(
        agent_definition_path.read_text(encoding="utf-8")
    )
    assert frontmatter_block is not None
    return frontmatter_block


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


@pytest.mark.parametrize(
    "agent_definition_path",
    _agent_definition_paths(),
    ids=lambda each_path: each_path.name,
)
def test_agent_frontmatter_loads_as_a_yaml_mapping(
    agent_definition_path: Path,
) -> None:
    frontmatter_block = _frontmatter_block(agent_definition_path)
    try:
        parsed_frontmatter = yaml.safe_load(frontmatter_block)
    except yaml.YAMLError as yaml_error:
        pytest.fail(
            f"{agent_definition_path.name} frontmatter is not loadable YAML, so "
            f"the subagent loader cannot read the definition: {yaml_error}"
        )
    assert isinstance(parsed_frontmatter, dict), (
        f"{agent_definition_path.name} frontmatter loads as "
        f"{type(parsed_frontmatter).__name__} rather than a key/value mapping"
    )
    unaccepted_keys = set(parsed_frontmatter) - ACCEPTED_FRONTMATTER_KEYS
    assert not unaccepted_keys, (
        f"{agent_definition_path.name} loads frontmatter keys the subagent "
        f"loader does not accept: {sorted(unaccepted_keys)}"
    )


def test_code_verifier_frontmatter_names_the_agent() -> None:
    agents_directory = Path(__file__).parent
    code_verifier_block = _frontmatter_block(
        agents_directory / f"{CODE_VERIFIER_AGENT_NAME}.md"
    )
    parsed_frontmatter = yaml.safe_load(code_verifier_block)
    assert parsed_frontmatter["name"] == CODE_VERIFIER_AGENT_NAME


@pytest.mark.parametrize(
    "agent_definition_path",
    _agent_definition_paths(),
    ids=lambda each_path: each_path.name,
)
def test_agent_frontmatter_carries_no_model_key(
    agent_definition_path: Path,
) -> None:
    frontmatter_block = _frontmatter_block(agent_definition_path)
    declared_keys = _top_level_keys(frontmatter_block)
    assert MODEL_KEY_NAME not in declared_keys, (
        f"{agent_definition_path.name} carries a model: key in frontmatter; "
        "the caller supplies the model on every spawn, so agent definitions "
        "carry no model key at all, not even model: inherit"
    )
