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

Two parsers read these files, and a block that satisfies one can still be
unreadable by the other. `scripts/codex_compat_materializer.py` reads the
block line by line, so every field fits on the line that names it::

    ok:   description: "Use this agent ... Examples:\\n\\n  <example> ..."
    flag: description: |        <- the line scan cannot follow the block scalar

That reader also counts fence lines across the whole file, so a bare `---`
anywhere in the body reads as a second frontmatter fence::

    ok:   ```yaml ... ``` example blocks in the body
    flag: a `---` line inside a body example  <- counted as a fence

That reader also cannot express an empty `tools: []` list, which is a defect
in the reader rather than in the one definition that declares it, so that
definition is named in `_codex_materializable_paths` and covered by every
other check here.

Each definition also has to carry a `name` and a `description` bound to a
non-empty string, and a `name` equal to its file stem — a mapping that loads
but binds `description` to nothing, or names an agent the file does not,
registers a subagent the caller cannot spawn::

    ok:   docs-agent.md  -> name: docs-agent
    flag: docs-agent.md  -> name: doc-manager   <- wrong spawn id
    flag: description:                          <- loads as None, loader needs text

Every check above is parametrized over the definitions that yield a
frontmatter block, so a file that yields none would drop out of all of them
and leave the suite green while unreadable. The block is what the fence lines
delimit, so the file that opens no fence or never closes one is exactly the
broken file these checks exist to catch::

    ok:   docs-agent.md  -> ---  name/description  ---   <- block found
    flag: docs-agent.md  -> ---  name/description        <- no closing fence,
                                                            silently uncovered

`test_every_agent_definition_yields_a_frontmatter_block` holds that floor: it
walks the same directory the parametrized checks draw from and fails on any
definition missing from them.

Frontmatter parsing is self-contained here (stdlib only): the block is the
text between the file's opening and closing `---` fence lines, and top-level
keys are read with a line scan so an agent whose `description` embeds
informal `<example>` prose is not mistaken for one carrying extra keys.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from functools import cache
from pathlib import Path
from types import ModuleType

import pytest
import yaml

ACCEPTED_FRONTMATTER_KEYS = frozenset({"name", "description", "tools", "color"})
EMPTY_TOOLS_LIST_FILENAME = "code-advisor.md"
EXEMPT_MARKDOWN_FILENAME = "CLAUDE.md"
FRONTMATTER_FENCE_LINE = "---"
MATERIALIZER_MODULE_NAME = "codex_compat_materializer"
MATERIALIZER_MODULE_PATH = (
    Path(__file__).resolve().parent.parent / "scripts" / f"{MATERIALIZER_MODULE_NAME}.py"
)
MODEL_KEY_NAME = "model"
RENAMED_AGENT_NAME = "an-agent-name-no-file-carries"
REQUIRED_FRONTMATTER_FIELDS = ("name", "description")
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
def _agent_definition_candidate_paths() -> tuple[Path, ...]:
    """Return every markdown file in this directory that must be a definition.

    This is the floor the parametrized checks are measured against: each of
    these files is expected to yield a frontmatter block, so one that does not
    is a broken definition rather than a file to pass over.

    Returns:
        Every `*.md` path in this directory except the exempt one, sorted.
    """
    agents_directory = Path(__file__).parent
    return tuple(
        each_markdown_file
        for each_markdown_file in sorted(agents_directory.glob("*.md"))
        if each_markdown_file.name != EXEMPT_MARKDOWN_FILENAME
    )


@cache
def _agent_definition_paths() -> tuple[Path, ...]:
    return tuple(
        each_markdown_file
        for each_markdown_file in _agent_definition_candidate_paths()
        if _extract_frontmatter_block(each_markdown_file.read_text(encoding="utf-8"))
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


@cache
def _codex_materializable_paths() -> tuple[Path, ...]:
    """Return the definitions the Codex materializer is expected to read.

    `code-advisor.md` declares `tools: []`, and its body states the agent has
    zero tools, so the empty list is the field saying what the author meant.
    The materializer's list parser raises on an empty list, so it cannot
    express a correct declaration::

        tools: Read, Bash  -> ok:   parsed
        tools: []          -> flag: MaterializerError, though the file is right

    The gap belongs to that parser, so the definition stays as written and only
    this one check steps around it. The YAML-load, required-field, accepted-key,
    model-ban, and name checks all still cover the file.

    Returns:
        Every agent definition path except the one whose correct frontmatter
        the materializer's list parser cannot express.
    """
    return tuple(
        each_path
        for each_path in _agent_definition_paths()
        if each_path.name != EMPTY_TOOLS_LIST_FILENAME
    )


@cache
def _codex_materializer_module() -> ModuleType:
    """Load the package's own line-oriented frontmatter parser from disk.

    Returns:
        The imported `codex_compat_materializer` module.
    """
    module_specification = importlib.util.spec_from_file_location(
        MATERIALIZER_MODULE_NAME, MATERIALIZER_MODULE_PATH
    )
    assert module_specification is not None, (
        f"no import specification for {MATERIALIZER_MODULE_PATH}"
    )
    assert module_specification.loader is not None, (
        f"no import loader for {MATERIALIZER_MODULE_PATH}"
    )
    materializer_module = importlib.util.module_from_spec(module_specification)
    sys.modules.setdefault(MATERIALIZER_MODULE_NAME, materializer_module)
    module_specification.loader.exec_module(materializer_module)
    return materializer_module


def _required_field_problem(parsed_frontmatter: object) -> str | None:
    """Describe what stops the loader using this frontmatter, or None.

    The loader needs text for every required field, so a field that loads as
    nothing or as a nested mapping is a problem even though the block itself
    is valid YAML::

        description: Use this agent ...  -> ok:   None
        description:                     -> flag: bound to NoneType
        description:                     -> flag: bound to dict
          nested: value

    Args:
        parsed_frontmatter: Value `yaml.safe_load` produced for the block.

    Returns:
        A sentence naming the problem, or None when every required field is a
        non-empty string.
    """
    if not isinstance(parsed_frontmatter, dict):
        return (
            f"frontmatter loads as {type(parsed_frontmatter).__name__} rather "
            "than a key/value mapping"
        )
    for each_field in REQUIRED_FRONTMATTER_FIELDS:
        if each_field not in parsed_frontmatter:
            return f"frontmatter carries no {each_field} field"
        field_value = parsed_frontmatter[each_field]
        if not isinstance(field_value, str):
            return (
                f"frontmatter binds {each_field} to "
                f"{type(field_value).__name__} rather than a string"
            )
        if not field_value.strip():
            return f"frontmatter binds {each_field} to an empty string"
    return None


def _agent_name_problem(parsed_frontmatter: object, expected_name: str) -> str | None:
    """Describe a name that disagrees with the file stem, or None.

    A subagent registers under the name in its frontmatter, so a name that is
    not the file stem is spawned by an id no caller uses::

        docs-agent.md -> name: docs-agent   -> ok:   None
        docs-agent.md -> name: doc-manager  -> flag: wrong spawn id

    Args:
        parsed_frontmatter: Value `yaml.safe_load` produced for the block.
        expected_name: The definition file's stem.

    Returns:
        A sentence naming the problem, or None when the name matches the stem.
    """
    if not isinstance(parsed_frontmatter, dict):
        return (
            f"frontmatter loads as {type(parsed_frontmatter).__name__} rather "
            "than a key/value mapping"
        )
    declared_name = parsed_frontmatter.get("name")
    if declared_name == expected_name:
        return None
    return (
        f"frontmatter declares name {declared_name!r} rather than "
        f"{expected_name!r}, so the agent registers under a spawn id that does "
        "not match its file"
    )


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


@pytest.mark.parametrize(
    "agent_file_name",
    (
        "docs-agent.md",
        "issue-tracker.md",
        "skill-writer-agent.md",
    ),
)
def test_p107_named_agents_yaml_safe_load_as_mapping(agent_file_name: str) -> None:
    """P-107 regression: named agents remain real YAML mappings under safe_load."""
    agent_definition_path = Path(__file__).parent / agent_file_name
    assert agent_definition_path.is_file(), (
        f"{agent_file_name} missing from agents/ — P-107 surface gone"
    )
    frontmatter_block = _frontmatter_block(agent_definition_path)
    parsed_frontmatter = yaml.safe_load(frontmatter_block)
    assert isinstance(parsed_frontmatter, dict), (
        f"{agent_file_name} frontmatter must load as a mapping for the subagent loader"
    )
    assert parsed_frontmatter.get("name") == agent_file_name.removesuffix(".md")
    assert isinstance(parsed_frontmatter.get("description"), str)
    assert parsed_frontmatter["description"].strip()


def test_every_agent_definition_yields_a_frontmatter_block() -> None:
    covered_names = {each_path.name for each_path in _agent_definition_paths()}
    uncovered_names = sorted(
        each_path.name
        for each_path in _agent_definition_candidate_paths()
        if each_path.name not in covered_names
    )
    assert not uncovered_names, (
        f"{', '.join(uncovered_names)} yield no frontmatter block, so every "
        "parametrized check in this module passes over them and the suite "
        "stays green while the definitions are unreadable"
    )


@pytest.mark.parametrize(
    "agent_definition_path",
    _codex_materializable_paths(),
    ids=lambda each_path: each_path.name,
)
def test_agent_frontmatter_parses_with_the_codex_materializer(
    agent_definition_path: Path,
) -> None:
    materializer_module = _codex_materializer_module()
    try:
        materializer_module.parse_frontmatter(
            agent_definition_path,
            agent_definition_path.read_text(encoding="utf-8"),
            agent_definition_path.name,
        )
    except materializer_module.MaterializerError as materializer_error:
        pytest.fail(
            f"{agent_definition_path.name} frontmatter is unreadable by "
            f"{MATERIALIZER_MODULE_NAME}, so the agent cannot be materialized "
            f"for Codex: {materializer_error}"
        )


@pytest.mark.parametrize(
    "agent_definition_path",
    _agent_definition_paths(),
    ids=lambda each_path: each_path.name,
)
def test_agent_frontmatter_binds_required_fields_to_non_empty_strings(
    agent_definition_path: Path,
) -> None:
    parsed_frontmatter = yaml.safe_load(_frontmatter_block(agent_definition_path))
    field_problem = _required_field_problem(parsed_frontmatter)
    assert field_problem is None, f"{agent_definition_path.name} {field_problem}"


def test_required_field_check_rejects_a_description_bound_to_nothing() -> None:
    parsed_frontmatter = yaml.safe_load("name: docs-agent\ndescription:\n")
    assert _required_field_problem(parsed_frontmatter) == (
        "frontmatter binds description to NoneType rather than a string"
    )


def test_required_field_check_rejects_a_description_bound_to_a_mapping() -> None:
    parsed_frontmatter = yaml.safe_load(
        "name: docs-agent\ndescription:\n  nested: value\n"
    )
    assert _required_field_problem(parsed_frontmatter) == (
        "frontmatter binds description to dict rather than a string"
    )


@pytest.mark.parametrize(
    "agent_definition_path",
    _agent_definition_paths(),
    ids=lambda each_path: each_path.name,
)
def test_agent_frontmatter_names_the_agent_after_its_file(
    agent_definition_path: Path,
) -> None:
    parsed_frontmatter = yaml.safe_load(_frontmatter_block(agent_definition_path))
    name_problem = _agent_name_problem(parsed_frontmatter, agent_definition_path.stem)
    assert name_problem is None, f"{agent_definition_path.name} {name_problem}"


def test_name_check_rejects_an_agent_renamed_away_from_its_file_stem() -> None:
    agent_definition_path = _agent_definition_paths()[0]
    renamed_block = _frontmatter_block(agent_definition_path).replace(
        f"name: {agent_definition_path.stem}", f"name: {RENAMED_AGENT_NAME}", 1
    )
    name_problem = _agent_name_problem(
        yaml.safe_load(renamed_block), agent_definition_path.stem
    )
    assert name_problem is not None and RENAMED_AGENT_NAME in name_problem


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
