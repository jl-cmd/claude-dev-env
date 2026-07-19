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

`frontmatter_pins_concrete_model` is the write-time hook's shared pin detector,
imported here so the test and the hook read a pinned model the same way. It
parses the block with `yaml.safe_load`, so a duplicate `model` key follows
last-wins, a bare `model:` is None (not a pin), and an unterminated quote
raises `yaml.YAMLError`.

Top-level keys are read with a line scan so an agent whose `description`
embeds informal `<example>` prose is not mistaken for one carrying extra
keys.
"""

from __future__ import annotations

import re
import sys
from functools import cache
from pathlib import Path

import pytest
import yaml

try:
    from agent_model_pin_blocker import frontmatter_pins_concrete_model
except ModuleNotFoundError:
    _HOOKS_ROOT = Path(__file__).resolve().parent.parent / "hooks"
    sys.path.insert(0, str(_HOOKS_ROOT / "blocking"))
    sys.path.insert(0, str(_HOOKS_ROOT))
    from agent_model_pin_blocker import frontmatter_pins_concrete_model

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
    ("synthetic_frontmatter_block", "expected_pin_verdict"),
    [
        ("name: sample\nmodel: opus\n", True),
        ("name: sample\nmodel: inherit\nmodel: opus\n", True),
        ("name: sample\nmodel: opus\nmodel: inherit\n", False),
        ("name: sample\nmodel: inherit#opus\n", True),
        ('name: sample\nmodel: "inherit # not a comment"\n', True),
        ("name: sample\nmodel: inherit\n", False),
        ("name: sample\nmodel:\n", False),
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
        "inherit",
        "bare-model-key-none",
        "quoted-inherit",
        "quoted-inherit-trailing-space",
        "quoted-inherit-then-comment",
        "title-case-inherit",
        "commented-inherit",
        "no-model-key",
    ],
)
def test_pinned_model_detection_flags_every_concrete_value(
    synthetic_frontmatter_block: str, expected_pin_verdict: bool
) -> None:
    assert (
        frontmatter_pins_concrete_model(synthetic_frontmatter_block)
        is expected_pin_verdict
    )


def test_pinned_model_detection_raises_on_unterminated_quote() -> None:
    with pytest.raises(yaml.YAMLError):
        frontmatter_pins_concrete_model("name: sample\nmodel: 'inherit\n")


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
