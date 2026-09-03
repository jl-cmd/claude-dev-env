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
unreadable by the other. `scripts/codex_compat_materializer.py` loads the
block through YAML with duplicate-key rejection, so block-scalar descriptions
and empty `tools: []` lists parse::

    ok:   description: |
            multi-line body
    ok:   tools: []

That reader still counts fence lines across the whole file, so a bare `---`
anywhere in the body reads as a second frontmatter fence::

    ok:   ```yaml ... ``` example blocks in the body
    flag: a `---` line inside a body example  <- counted as a fence

Each definition also has to carry a `name` and a `description` bound to a
non-empty string, and a `name` equal to its file stem — a mapping that loads
but binds `description` to nothing, or names an agent the file does not,
registers a subagent the caller cannot spawn::

    ok:   clean-coder.md  -> name: clean-coder
    flag: clean-coder.md  -> name: doc-manager   <- wrong spawn id
    flag: description:                          <- loads as None, loader needs text

Every check above is parametrized over the definitions that yield a
frontmatter block, so a file that yields none would drop out of all of them
and leave the suite green while unreadable. The block is what the fence lines
delimit, so the file that opens no fence or never closes one is exactly the
broken file these checks exist to catch::

    ok:   clean-coder.md  -> ---  name/description  ---   <- block found
    flag: clean-coder.md  -> ---  name/description        <- no closing fence,
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
CODE_QUALITY_AGENT_FILENAME = "code-quality-agent.md"
CODE_QUALITY_READ_ONLY_TOOLS = ("Read", "Grep", "Glob")
INSTRUCTION_ALIAS_FILENAMES = frozenset({"AGENTS.md", "CLAUDE.md"})
FRONTMATTER_FENCE_LINE = "---"
MATERIALIZER_MODULE_NAME = "codex_compat_materializer"
MATERIALIZER_MODULE_PATH = (
    Path(__file__).resolve().parent.parent.parent / "scripts" / f"{MATERIALIZER_MODULE_NAME}.py"
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
    """Return every markdown file in this directory that is an agent definition.

    This is the floor the parametrized checks are measured against: each of
    these files is expected to yield a frontmatter block, so one that does not
    is a broken definition rather than a file to pass over.

    Returns:
        Every agent-definition `*.md` path in this directory, sorted.
    """
    agents_directory = Path(__file__).parent
    return tuple(
        each_markdown_file
        for each_markdown_file in sorted(agents_directory.glob("*.md"))
        if each_markdown_file.name not in INSTRUCTION_ALIAS_FILENAMES
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
def _codex_materializer_module() -> ModuleType:
    """Load the package's YAML frontmatter materializer from disk.

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

        clean-coder.md -> name: clean-coder   -> ok:   None
        clean-coder.md -> name: doc-manager  -> flag: wrong spawn id

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
        "clean-coder.md",
        "issue-tracker.md",
        "skill-writer-agent.md",
    ),
)
def named_agents_yaml_safe_load_as_mapping(agent_file_name: str) -> None:
    """P-107 regression: named agents remain real YAML mappings under safe_load."""
    agent_definition_path = Path(__file__).parent / agent_file_name
    assert agent_definition_path.is_file(), (
        f"{agent_file_name} missing from agents/ — P-107 surface gone"
    )
    parsed_frontmatter = yaml.safe_load(_frontmatter_block(agent_definition_path))
    field_problem = _required_field_problem(parsed_frontmatter)
    assert field_problem is None, f"{agent_file_name} {field_problem}"
    name_problem = _agent_name_problem(
        parsed_frontmatter, agent_definition_path.stem
    )
    assert name_problem is None, f"{agent_file_name} {name_problem}"


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
    _agent_definition_paths(),
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


def _clean_coder_body() -> str:
    return (Path(__file__).parent / "clean-coder.md").read_text(encoding="utf-8")


SOURCE_LINK_PATTERN = re.compile(
    r"`(?P<installed><(?:managed-root|agents-home)>/[^`]+)` "
    r"\(source fallback: `(?P<source>packages/claude-dev-env/[^`]+)`\)"
)

EXPECTED_SOURCE_LINK_PAIRS = {
    "clean-coder.md": frozenset({
        (
            "<managed-root>/docs/CODE_RULES.md#5-no-abbreviations",
            "packages/claude-dev-env/docs/CODE_RULES.md#5-no-abbreviations",
        ),
        (
            "<managed-root>/docs/CODE_RULES.md",
            "packages/claude-dev-env/docs/CODE_RULES.md",
        ),
        (
            "<managed-root>/hooks/blocking/code_rules_enforcer.py",
            "packages/claude-dev-env/hooks/blocking/code_rules_enforcer.py",
        ),
        (
            "<managed-root>/rules/code-standards.md",
            "packages/claude-dev-env/rules/code-standards.md",
        ),
        (
            "<managed-root>/rules/file-global-constants.md",
            "packages/claude-dev-env/rules/file-global-constants.md",
        ),
        (
            "<managed-root>/rules/windows-filesystem-safe.md",
            "packages/claude-dev-env/rules/windows-filesystem-safe.md",
        ),
        (
            "<managed-root>/rules/gh-cli-conventions.md",
            "packages/claude-dev-env/rules/gh-cli-conventions.md",
        ),
        (
            "<managed-root>/rules/plain-illustrative-docstrings.md",
            "packages/claude-dev-env/rules/plain-illustrative-docstrings.md",
        ),
        (
            "<managed-root>/rules/testing.md",
            "packages/claude-dev-env/rules/testing.md",
        ),
        (
            "<managed-root>/rules/anti-corollary-tests.md",
            "packages/claude-dev-env/rules/anti-corollary-tests.md",
        ),
        (
            "<managed-root>/rules/paired-test-coverage.md",
            "packages/claude-dev-env/rules/paired-test-coverage.md",
        ),
        (
            "<managed-root>/rules/bdd.md",
            "packages/claude-dev-env/rules/bdd.md",
        ),
        (
            "<managed-root>/rules/ask-user-question-required.md",
            "packages/claude-dev-env/rules/ask-user-question-required.md",
        ),
        (
            "<managed-root>/rules/verify-before-asking.md",
            "packages/claude-dev-env/rules/verify-before-asking.md",
        ),
        (
            "<managed-root>/rules/filesystem-search.md",
            "packages/claude-dev-env/rules/filesystem-search.md",
        ),
        (
            "<managed-root>/rules/shell-invocation.md",
            "packages/claude-dev-env/rules/shell-invocation.md",
        ),
        (
            "<managed-root>/rules/verify-runtime-state.md",
            "packages/claude-dev-env/rules/verify-runtime-state.md",
        ),
        (
            "<managed-root>/rules/doc-inventory-integrity.md",
            "packages/claude-dev-env/rules/doc-inventory-integrity.md",
        ),
        (
            "<managed-root>/rules/docstring-prose-matches-implementation.md",
            "packages/claude-dev-env/rules/docstring-prose-matches-implementation.md",
        ),
        (
            "<managed-root>/rules/durable-post-artifacts.md",
            "packages/claude-dev-env/rules/durable-post-artifacts.md",
        ),
        (
            "<managed-root>/rules/failure-blast-radius.md",
            "packages/claude-dev-env/rules/failure-blast-radius.md",
        ),
        (
            "<managed-root>/rules/git-workflow.md",
            "packages/claude-dev-env/rules/git-workflow.md",
        ),
        (
            "<managed-root>/rules/re-stage-before-commit.md",
            "packages/claude-dev-env/rules/re-stage-before-commit.md",
        ),
        (
            "<managed-root>/rules/agent-spawn-protocol.md",
            "packages/claude-dev-env/rules/agent-spawn-protocol.md",
        ),
        (
            "<managed-root>/rules/workers-done-before-complete.md",
            "packages/claude-dev-env/rules/workers-done-before-complete.md",
        ),
    }),
    "code-quality-agent.md": frozenset({
        (
            "<managed-root>/audit-rubrics/category_rubrics/category-a-api-contracts.md",
            "packages/claude-dev-env/audit-rubrics/category_rubrics/category-a-api-contracts.md",
        ),
        (
            "<managed-root>/audit-rubrics/category_rubrics/category-b-selector-engine-compat.md",
            "packages/claude-dev-env/audit-rubrics/category_rubrics/category-b-selector-engine-compat.md",
        ),
        (
            "<managed-root>/audit-rubrics/category_rubrics/category-c-resource-cleanup.md",
            "packages/claude-dev-env/audit-rubrics/category_rubrics/category-c-resource-cleanup.md",
        ),
        (
            "<managed-root>/audit-rubrics/category_rubrics/category-d-scoping-and-ordering.md",
            "packages/claude-dev-env/audit-rubrics/category_rubrics/category-d-scoping-and-ordering.md",
        ),
        (
            "<managed-root>/audit-rubrics/category_rubrics/category-e-dead-code.md",
            "packages/claude-dev-env/audit-rubrics/category_rubrics/category-e-dead-code.md",
        ),
        (
            "<managed-root>/audit-rubrics/category_rubrics/category-f-silent-failures.md",
            "packages/claude-dev-env/audit-rubrics/category_rubrics/category-f-silent-failures.md",
        ),
        (
            "<managed-root>/audit-rubrics/category_rubrics/category-g-bounds-and-overflow.md",
            "packages/claude-dev-env/audit-rubrics/category_rubrics/category-g-bounds-and-overflow.md",
        ),
        (
            "<managed-root>/audit-rubrics/category_rubrics/category-h-security-boundaries.md",
            "packages/claude-dev-env/audit-rubrics/category_rubrics/category-h-security-boundaries.md",
        ),
        (
            "<managed-root>/audit-rubrics/category_rubrics/category-i-concurrency.md",
            "packages/claude-dev-env/audit-rubrics/category_rubrics/category-i-concurrency.md",
        ),
        (
            "<managed-root>/audit-rubrics/category_rubrics/category-j-code-rules-compliance.md",
            "packages/claude-dev-env/audit-rubrics/category_rubrics/category-j-code-rules-compliance.md",
        ),
        (
            "<managed-root>/audit-rubrics/category_rubrics/category-k-codebase-conflicts.md",
            "packages/claude-dev-env/audit-rubrics/category_rubrics/category-k-codebase-conflicts.md",
        ),
        (
            "<managed-root>/audit-rubrics/category_rubrics/category-l-behavior-equivalence.md",
            "packages/claude-dev-env/audit-rubrics/category_rubrics/category-l-behavior-equivalence.md",
        ),
        (
            "<managed-root>/audit-rubrics/category_rubrics/category-m-producer-consumer-cardinality.md",
            "packages/claude-dev-env/audit-rubrics/category_rubrics/category-m-producer-consumer-cardinality.md",
        ),
        (
            "<managed-root>/audit-rubrics/category_rubrics/category-n-test-name-scenario-verifier.md",
            "packages/claude-dev-env/audit-rubrics/category_rubrics/category-n-test-name-scenario-verifier.md",
        ),
        (
            "<managed-root>/audit-rubrics/category_rubrics/category-o-docstring-vs-impl-drift.md",
            "packages/claude-dev-env/audit-rubrics/category_rubrics/category-o-docstring-vs-impl-drift.md",
        ),
        (
            "<managed-root>/audit-rubrics/category_rubrics/category-p-name-vs-behavior-contract.md",
            "packages/claude-dev-env/audit-rubrics/category_rubrics/category-p-name-vs-behavior-contract.md",
        ),
        (
            "<managed-root>/audit-rubrics/category_rubrics/category-q-cross-surface-claims.md",
            "packages/claude-dev-env/audit-rubrics/category_rubrics/category-q-cross-surface-claims.md",
        ),
    }),
    "pr-description-writer.md": frozenset({
        (
            "<agents-home>/skills/pr-title-description/SKILL.md",
            "packages/claude-dev-env/.agents/skills/pr-title-description/SKILL.md",
        ),
        (
            "<managed-root>/rules/gh-cli-conventions.md#body-content-goes-in-a-file",
            "packages/claude-dev-env/rules/gh-cli-conventions.md#body-content-goes-in-a-file",
        ),
    }),
}


def _assert_source_link_contract(agent_file_name: str, agent_text: str) -> None:
    agents_directory = Path(__file__).parent
    repository_root = agents_directory.parents[3]
    actual_source_links = frozenset(SOURCE_LINK_PATTERN.findall(agent_text))
    expected_source_links = EXPECTED_SOURCE_LINK_PAIRS[agent_file_name]
    assert actual_source_links == expected_source_links, (
        f"{agent_file_name} source links must match the complete expected set"
    )
    for each_installed_path, each_source_path in actual_source_links:
        installed_suffix = each_installed_path.split(">/", 1)[1]
        source_suffix = each_source_path.removeprefix("packages/claude-dev-env/")
        source_suffix = source_suffix.removeprefix(".agents/")
        assert installed_suffix == source_suffix, (
            f"installed/source suffix mismatch: {each_installed_path} -> "
            f"{each_source_path}"
        )
        source_file_path = repository_root / each_source_path.split("#", 1)[0]
        assert source_file_path.is_file(), (
            f"source fallback must be a file: {each_source_path}"
        )


def test_named_agents_document_installed_paths_and_source_fallbacks() -> None:
    agents_directory = Path(__file__).parent
    for each_agent_file_name in (
        "clean-coder.md",
        "code-quality-agent.md",
        "pr-description-writer.md",
    ):
        agent_text = (agents_directory / each_agent_file_name).read_text(
            encoding="utf-8"
        )
        _assert_source_link_contract(each_agent_file_name, agent_text)
        for each_stale_prefix in (
            "../docs/",
            "../hooks/",
            "../rules/",
            "../audit-rubrics/",
            "../skills/descriptions/",
            "../skills/comments/",
        ):
            assert each_stale_prefix not in agent_text, (
                f"{each_agent_file_name} must not use stale relative guide "
                f"path {each_stale_prefix}"
            )


def test_source_link_contract_rejects_missing_pair() -> None:
    body = _clean_coder_body()
    missing_pair_text = (
        "`<managed-root>/hooks/blocking/code_rules_enforcer.py` "
        "(source fallback: `packages/claude-dev-env/hooks/blocking/"
        "code_rules_enforcer.py`)"
    )
    mutated_body = body.replace(missing_pair_text, "", 1)
    with pytest.raises(AssertionError):
        _assert_source_link_contract("clean-coder.md", mutated_body)


def test_source_link_contract_rejects_altered_valid_file() -> None:
    body = _clean_coder_body()
    mutated_body = body.replace(
        "`<managed-root>/docs/CODE_RULES.md` (source fallback: "
        "`packages/claude-dev-env/docs/CODE_RULES.md`)",
        "`<managed-root>/docs/CODE_RULES.md` (source fallback: "
        "`packages/claude-dev-env/rules/code-standards.md`)",
        1,
    )
    with pytest.raises(AssertionError):
        _assert_source_link_contract("clean-coder.md", mutated_body)


def test_source_link_contract_rejects_directory_fallback() -> None:
    body = _clean_coder_body()
    mutated_body = body.replace(
        "`<managed-root>/docs/CODE_RULES.md` (source fallback: "
        "`packages/claude-dev-env/docs/CODE_RULES.md`)",
        "`<managed-root>/docs/CODE_RULES.md` (source fallback: "
        "`packages/claude-dev-env/docs`)",
        1,
    )
    with pytest.raises(AssertionError):
        _assert_source_link_contract("clean-coder.md", mutated_body)


def test_named_agents_resolve_active_managed_root_and_agents_home() -> None:
    agents_directory = Path(__file__).parent
    for each_agent_file_name in (
        "clean-coder.md",
        "code-quality-agent.md",
        "pr-description-writer.md",
    ):
        agent_text = (agents_directory / each_agent_file_name).read_text(
            encoding="utf-8"
        )
        assert "active managed root" in agent_text.lower()
        assert "active agents home" in agent_text.lower()
        assert "CLAUDE_CONFIG_DIR" in agent_text
        assert "--target" in agent_text
        assert "<managed-root>/" in agent_text
        assert "<agents-home>/" in agent_text
        assert "do not assume" in agent_text.lower()


def test_clean_coder_never_globs_or_reads_dotenv_files() -> None:
    body = _clean_coder_body()
    assert "`**/.env`" not in body
    assert "`**/.env.*`" not in body
    assert "Never open `.env`" in body or "Do **not** glob or open `.env`" in body
    assert re.search(r"(?i)glob.*\.env|\.env.*glob", body) is None or "Do **not** glob or open `.env`" in body


def test_clean_coder_uses_task_local_config_discovery() -> None:
    body = _clean_coder_body()
    assert "task-local" in body.lower()
    assert "project-wide preload" in body.lower() or "Do **not** glob the whole tree" in body
    assert "Issue all five Glob calls" not in body
    assert "Issue all seven Glob calls" not in body


def test_clean_coder_loads_scoped_agents_files_before_editing() -> None:
    body = _clean_coder_body()
    assert "scoped AGENTS.md" in body
    assert body.count("Load scoped AGENTS.md files first.") == 1
    assert "repository root" in body.lower()
    assert "target directory" in body.lower()
    assert "unrelated" in body.lower()


def test_clean_coder_explains_red_green_refactor_steps() -> None:
    body = _clean_coder_body()
    assert "behavior change" in body.lower()
    assert "failing test" in body.lower()
    assert "RED" in body
    assert "GREEN" in body
    assert "REFACTOR" in body
    assert "write production behavior before red" in body.lower()


def test_clean_coder_distinguishes_code_rules_precheck_from_full_quality_gates() -> None:
    body = _clean_coder_body()
    assert "mechanical CODE_RULES" in body
    assert "does not run tests" in body
    assert "full quality gate" in body.lower()
    assert "ruff" in body.lower()
    assert "mypy" in body.lower()


def test_clean_coder_has_hook_specific_workflow() -> None:
    body = _clean_coder_body()
    assert "Hook-specific workflow" in body
    assert "production entry point" in body.lower()
    assert "JSON" in body
    assert "registered" in body.lower()


def test_clean_coder_keeps_warm_session_advisor_triggers() -> None:
    body = _clean_coder_body().lower()
    assert "warm `session-advisor`" in body
    assert "before substantive work" in body
    assert "when you believe the task is complete" in body
    assert "when stuck" in body
    assert "change of approach" in body
    assert "before any commit" in body



def test_clean_coder_separates_constants_and_caller_search() -> None:
    body = _clean_coder_body()
    assert "task-local constants search" in body
    assert "caller boundary" in body


def test_clean_coder_scopes_task_artifact_guidance() -> None:
    body = _clean_coder_body()
    assert "Follow the target repo's policy for scratch, planning, and image files" in body
    assert "No scratch/planning artifacts" not in body


def test_clean_coder_links_canonical_policy_areas() -> None:
    body = _clean_coder_body()
    required_links = (
        "<managed-root>/docs/CODE_RULES.md#5-no-abbreviations",
        "<managed-root>/rules/testing.md",
        "<managed-root>/rules/ask-user-question-required.md",
        "<managed-root>/rules/verify-runtime-state.md",
        "<managed-root>/rules/doc-inventory-integrity.md",
        "<managed-root>/rules/failure-blast-radius.md",
        "<managed-root>/rules/git-workflow.md",
        "<managed-root>/rules/workers-done-before-complete.md",
    )
    assert all(each_link in body for each_link in required_links)


def test_clean_coder_preserves_existing_comment_instruction() -> None:
    body = _clean_coder_body()
    assert (
        "Note every existing comment so you can leave each one untouched on lines "
        "that remain otherwise unchanged."
    ) in body

def test_clean_coder_examples_import_constants_from_config() -> None:
    body = _clean_coder_body()
    assert "from config.timing import MAXIMUM_RETRIES" in body
    assert re.search(r"(?m)^MAXIMUM_RETRIES\s*=\s*\d+", body) is None


def test_clean_coder_loads_scoped_agents_before_claude() -> None:
    body = _clean_coder_body()
    agents_instruction_at = body.index("Load scoped AGENTS.md files first")
    claude_instruction_at = body.index("Then read the applicable `CLAUDE.md`")
    assert agents_instruction_at < claude_instruction_at
    assert "every applicable `AGENTS.md`" in body
    assert "closest file wins" in body


def test_clean_coder_requires_red_green_refactor_for_behavior_changes() -> None:
    body = _clean_coder_body()
    assert "every behavior change" in body
    assert "red → green → refactor" in body
    assert "run it red" in body


def test_clean_coder_distinguishes_full_gate_from_candidate_check() -> None:
    body = _clean_coder_body()
    assert "pre-check tests CODE_RULES only" in body
    assert "full project gate" in body
    assert "candidate enforcer check" in body
    assert "not the full gate" in body


def test_clean_coder_defines_a_hook_specific_workflow() -> None:
    body = _clean_coder_body()
    assert "Hook-specific workflow" in body
    assert "hooks/AGENTS.md" in body
    assert "stdin JSON" in body
    assert "exit code" in body
    assert "registration" in body
    assert "constants package" in body
    assert "check.ps1" in body
    assert "every applicable test file and suite" in body


def test_clean_coder_uses_target_package_aware_hook_paths() -> None:
    body = _clean_coder_body()
    hook_workflow = body.split("## Hook-specific workflow", 1)[1].split(
        "## Session advisor", 1
    )[0]
    hook_path_pattern = re.compile(
        r"`(?P<managed><managed-root>/(?P<relative>hooks/AGENTS\.md|scripts/check\.ps1))` "
        r"\(default: `(?P<default>~/.claude/(?P=relative))`; "
        r"source fallback: `(?P<source>packages/claude-dev-env/(?P=relative))`\)"
    )
    path_pairs = {
        (
            each_match.group("managed"),
            each_match.group("default"),
            each_match.group("source"),
        )
        for each_match in hook_path_pattern.finditer(hook_workflow)
    }
    expected_pairs = {
        (
            "<managed-root>/hooks/AGENTS.md",
            "~/.claude/hooks/AGENTS.md",
            "packages/claude-dev-env/hooks/AGENTS.md",
        ),
        (
            "<managed-root>/scripts/check.ps1",
            "~/.claude/scripts/check.ps1",
            "packages/claude-dev-env/scripts/check.ps1",
        ),
    }
    assert path_pairs == expected_pairs
    assert len(path_pairs) == len(expected_pairs)
    repository_root = Path(__file__).parent.parents[3]
    for each_source_path in (
        "packages/claude-dev-env/hooks/AGENTS.md",
        "packages/claude-dev-env/scripts/check.ps1",
    ):
        assert (repository_root / each_source_path).is_file()
    assert "active managed root" in hook_workflow
    assert "`~/.claude`" in hook_workflow
    assert "`--target`" in hook_workflow
    assert "`CLAUDE_CONFIG_DIR`" in hook_workflow


def test_clean_coder_uses_the_callers_warm_advisor_at_approved_triggers() -> None:
    body = _clean_coder_body()
    assert "Consult the advisor the spawn ticket names" in body
    assert "orchestrating session" in body
    assert "warm `session-advisor`" in body
    assert "before first write" in body
    assert "before locking a plan or interpretation" in body
    assert "before a hard-to-reverse action" in body
    assert "after repeated failure or a stall" in body
    assert "changing approach" in body
    assert "before completion" in body
    assert "do not bind or spawn another advisor" in body


def test_clean_coder_policy_targets_exist_in_source_package() -> None:
    _assert_source_link_contract("clean-coder.md", _clean_coder_body())


def test_code_quality_agent_allows_only_read_and_search_tools() -> None:
    agent_definition_path = Path(__file__).parent / CODE_QUALITY_AGENT_FILENAME
    parsed_frontmatter = yaml.safe_load(_frontmatter_block(agent_definition_path))

    assert parsed_frontmatter["tools"] == list(CODE_QUALITY_READ_ONLY_TOOLS)


def test_code_quality_agent_contract_forbids_mutating_commands() -> None:
    agent_definition_path = Path(__file__).parent / CODE_QUALITY_AGENT_FILENAME
    body = agent_definition_path.read_text(encoding="utf-8")
    assert "Use only `Read`, `Grep`, and `Glob`." in body
    assert "Author zero edits." in body
    assert "Run zero commits or pushes." in body
    assert "run no commands that write files or create PRs." in body


def test_clean_coder_defines_a_liveness_boundary_for_dead_code_cleanup() -> None:
    body = _clean_coder_body()
    assert "orphaned or dead code" in body.lower()
    assert "liveness boundary" in body
    assert "live entry point" in body
    assert "public API, plugin hook, or reflective dispatch" in body


def test_clean_coder_hands_the_full_diff_to_code_quality_agent() -> None:
    body = _clean_coder_body()
    assert "Full Code Quality Agent review handoff" in body
    assert "code-quality-agent" in body
    assert "full diff" in body
    assert "all A–Q categories" in body


    assert "Repair each actionable finding" in body
    assert "rerun focused checks and the full project gate on the post-repair diff" in body
    assert "Record both results" in body


def test_clean_coder_uses_evidence_based_completion_language() -> None:
    body = _clean_coder_body()
    assert "Evidence-Based Code Generation" in body
    assert "recorded check results" in body
    assert "Do not claim defect-free code" in body
    assert "Zero-Defect" not in body
    assert "zero-defect" not in body


def test_clean_coder_example_contains_real_code() -> None:
    body = _clean_coder_body()
    example = body.split("```python", 1)[1].split("```", 1)[0]
    assert "..." not in example
    assert "pass" not in example
    assert "NotImplementedError" not in example


def test_clean_coder_requires_evidence_based_completion_wording() -> None:
    body = _clean_coder_body()
    assert "# Clean Coder — Evidence-Based Code Generation" in body
    assert "reviewers find nothing" not in body
    assert "Write clear code. Provide test and review evidence." in body
    assert "candidate check" in body
    assert "focused tests" in body
    assert "full project gate" in body
    assert "recorded check results" in body
    assert "review evidence" in body
    assert "open questions" in body
    assert "Do not claim defect-free code" in body


def test_clean_coder_follows_target_package_constant_layouts() -> None:
    body = _clean_coder_body()
    assert "target package's existing constants layout" in body
    assert "Reuse first" in body
    assert "shared policy" in body
    assert "multiple consumers" in body
    assert "file-global-constants" in body
    assert "add the constant to the appropriate config file" not in body


def test_clean_coder_allows_requested_plan_packets_and_product_assets() -> None:
    body = _clean_coder_body()
    assert "No unasked scratch files" in body
    assert "valid plan packets" in body
    assert "uncommitted working files" in body
    assert "durable artifacts release" in body
    assert "not the repository tree" in body
    assert "docs/plans/*.md" not in body
    assert "or image assets" not in body


def test_clean_coder_links_canonical_naming_guidance() -> None:
    body = _clean_coder_body()
    assert "canonical naming guidance" in body
    assert "CODE_RULES.md §5" in body
    assert "`each_` loops" not in body
    assert "`is_`/`has_`/`should_`/`can_`" not in body


def test_clean_coder_groups_session_policy_references() -> None:
    body = _clean_coder_body()
    assert "Session policy map" in body
    for each_policy_group in (
        "Tests",
        "Questions",
        "Search and shell",
        "Runtime checks",
        "Documentation",
        "Batch failures",
        "Git",
        "Worker coordination",
    ):
        assert each_policy_group in body
    assert "ask-user-question-required.md" in body
    assert "workers-done-before-complete.md" in body
    assert "verify-runtime-state.md" in body
    assert "Material implementation questions must return to the caller" in body
    assert "AskUserQuestion" in body
    assert "do not ask in plain text or guess" in body

    expected_session_policy_files = (
        "testing.md",
        "anti-corollary-tests.md",
        "ask-user-question-required.md",
        "verify-before-asking.md",
        "filesystem-search.md",
        "shell-invocation.md",
        "verify-runtime-state.md",
        "doc-inventory-integrity.md",
        "docstring-prose-matches-implementation.md",
        "failure-blast-radius.md",
        "git-workflow.md",
        "re-stage-before-commit.md",
        "agent-spawn-protocol.md",
        "workers-done-before-complete.md",
    )
    session_policy_map = body[body.index("## Session policy map") :]
    session_policy_links = SOURCE_LINK_PATTERN.findall(session_policy_map)
    for each_policy_file_name in expected_session_policy_files:
        assert (
            f"<managed-root>/rules/{each_policy_file_name}",
            f"packages/claude-dev-env/rules/{each_policy_file_name}",
        ) in session_policy_links
