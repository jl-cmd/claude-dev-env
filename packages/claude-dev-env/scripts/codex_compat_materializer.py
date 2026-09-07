"""Deterministic, additive Claude-agent to Codex-agent materialization."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import tempfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import NoReturn

import tomllib
import yaml

ManagedContent = str | bytes

path_separator = "/"
toml_suffix = ".toml"
reparse_point_attribute_name = "FILE_ATTRIBUTE_REPARSE_POINT"
manifest_indentation_width = 2
publish_plan_max_positional_arguments = 3
publish_plan_failure_injector_position = 2
frontmatter_unsupported_fields = ("tools", "model", "color", "disable-model-invocation")
instruction_alias_filenames = frozenset({"AGENTS.md", "CLAUDE.md"})
failure_blast_radius_rule_relative_path = "rules/failure-blast-radius.md"
codex_instruction_target_path = "AGENTS.md"
codex_instruction_section_heading = "## Excerpt for repository-instruction sessions"
codex_hook_manifest_source_path = "hooks/hooks.json"
codex_hook_manifest_target_path = "hooks.json"
codex_hook_event_name = "PreToolUse"
codex_hook_matcher = "apply_patch"
codex_enforcer_script_relative_path = "hooks/blocking/code_rules_enforcer.py"
codex_enforcer_script_name = "code_rules_enforcer.py"
codex_enforcer_path_suffix = path_separator + codex_enforcer_script_relative_path
codex_hook_command_token_pattern = r'''(?:"[^"]*"|'[^']*'|\S+)'''
codex_hook_records_field_name = "hooks"
codex_hook_command_field_name = "command"
codex_hook_matcher_field_name = "matcher"
codex_retired_hook_relative_path = "session" + path_separator + "untracked_repo_detector.py"
codex_retired_hook_commands = frozenset(
    (each_prefix + codex_retired_hook_relative_path).casefold()
    for each_prefix in (
        "", "hooks/", "${CLAUDE_PLUGIN_ROOT}/hooks/", "$CODEX_HOME/hooks/",
        "${CODEX_HOME}/hooks/", "%CODEX_HOME%/hooks/", "$env:CODEX_HOME/hooks/",
        "${env:CODEX_HOME}/hooks/", "~/.codex/hooks/",
        "$HOME/.codex/hooks/", "${HOME}/.codex/hooks/"
    )
)
codex_default_home_hook_path_suffix = "/.codex/hooks/" + codex_retired_hook_relative_path
codex_hook_merge_action = "merge"
codex_hook_timeout_seconds = 60
codex_hook_dependency_manifest = (
    "hooks/blocking/__init__.py",
    "hooks/blocking/code_rules_annotations_length.py",
    "hooks/blocking/code_rules_banned_identifiers.py",
    "hooks/blocking/code_rules_blast_radius.py",
    "hooks/blocking/code_rules_boolean_mustcheck.py",
    "hooks/blocking/code_rules_command_dispatch.py",
    "hooks/blocking/code_rules_comments.py",
    "hooks/blocking/javascript_comment_scanner.py",
    "hooks/blocking/code_rules_constants_config.py",
    "hooks/blocking/codex_apply_patch.py",
    "hooks/blocking/config/__init__.py",
    "hooks/blocking/config/codex_apply_patch_constants.py",
    "hooks/blocking/code_rules_docstrings.py",
    "hooks/blocking/code_rules_duplicate_body.py",
    "hooks/blocking/code_rules_enforcer.py",
    "hooks/blocking/code_rules_imports_logging.py",
    "hooks/blocking/code_rules_js_conventions.py",
    "hooks/blocking/code_rules_magic_values.py",
    "hooks/blocking/code_rules_naming_collection.py",
    "hooks/blocking/code_rules_optional_params.py",
    "hooks/blocking/code_rules_orphan_css_class.py",
    "hooks/blocking/code_rules_paired_test.py",
    "hooks/blocking/code_rules_path_utils.py",
    "hooks/blocking/code_rules_paths_syspath.py",
    "hooks/blocking/code_rules_probe_chains.py",
    "hooks/blocking/code_rules_probe_detection.py",
    "hooks/blocking/code_rules_probe_recording.py",
    "hooks/blocking/code_rules_shared.py",
    "hooks/blocking/code_rules_string_magic.py",
    "hooks/blocking/code_rules_test_assertions.py",
    "hooks/blocking/code_rules_test_branching_except.py",
    "hooks/blocking/code_rules_test_isolation.py",
    "hooks/blocking/code_rules_test_layout.py",
    "hooks/blocking/code_rules_type_escape.py",
    "hooks/blocking/code_rules_typeddict_stub.py",
    "hooks/hooks_constants/__init__.py",
    "hooks/hooks_constants/any_type_config.py",
    "hooks/hooks_constants/banned_identifiers_constants.py",
    "hooks/hooks_constants/blast_radius_constants.py",
    "hooks/hooks_constants/blocking_check_limits.py",
    "hooks/hooks_constants/code_rules_enforcer_constants.py",
    "hooks/hooks_constants/code_rules_path_utils_constants.py",
    "hooks/hooks_constants/command_dispatch_constants.py",
    "hooks/hooks_constants/duplicate_function_body_constants.py",
    "hooks/hooks_constants/hardcoded_user_path_constants.py",
    "hooks/hooks_constants/harness_scratchpad_constants.py",
    "hooks/hooks_constants/hook_block_logger.py",
    "hooks/hooks_constants/inline_tuple_string_magic_constants.py",
    "hooks/hooks_constants/js_conventions_constants.py",
    "hooks/hooks_constants/multi_edit_reconstruction.py",
    "hooks/hooks_constants/orphan_css_class_constants.py",
    "hooks/hooks_constants/paired_test_coverage_constants.py",
    "hooks/hooks_constants/setup_project_paths_constants.py",
    "hooks/hooks_constants/stuttering_check_config.py",
    "hooks/hooks_constants/stuttering_import_binding_constants.py",
    "hooks/hooks_constants/subprocess_budget_completeness_content.py",
    "hooks/hooks_constants/sys_path_insert_constants.py",
    "hooks/hooks_constants/test_layout_constants.py",
    "hooks/hooks_constants/unused_module_import_constants.py",
    "hooks/hooks_constants/validation_phase_constants.py",
)
full_prune_opt_in_flag = "--allow-prune-all"
unreadable_source_root_message = (
    "source root is missing or is not a directory, so nothing was planned or changed; "
    "check the source root path and re-run"
)
reparse_source_root_message = "source root is a reparse point, so nothing was planned or changed"
full_prune_refusal_message = (
    "refusing to delete every managed file: the plan is empty while the manifest still records "
    "{count} of them, so the target root was left untouched; re-run with " + full_prune_opt_in_flag
    + " to remove them"
)
unmanaged_target_message = (
    "unmanaged file at planned target {path}: the compatibility manifest does not record it, so it "
    "may be yours and it was not overwritten. Review it, then move or delete {path} inside the "
    "target root and re-run. An interrupted run leaves a file whose bytes already match the plan, "
    "and such a file is adopted automatically"
)


class MaterializerError(ValueError):
    """Raised when a materialization request cannot be safely planned."""


class MaterializerRunFatal(MaterializerError):
    """Raised when invalid materializer state stops the whole run."""


class ArgumentParserError(ValueError):
    """Raised when command-line arguments cannot be parsed."""


class MaterializerArgumentParser(argparse.ArgumentParser):
    """Parse materializer arguments while keeping errors in the JSON contract."""

    def error(self, message: str) -> NoReturn:
        """Raise a reportable parser error instead of writing process output."""
        raise ArgumentParserError(message)


report_categories = (
    "written", "unchanged", "adopted", "unmanaged_collision", "modified_managed",
    "stale_managed", "deleted", "unsupported", "conflicted", "errors",
)
report_categories_public_name = "REPORT_CATEGORIES"
frontmatter_allowed_fields = {
    "name", "description", "tools", "model", "color", "disable-model-invocation"
}
line_separator = "\n"
comma_separator = ", "


def __getattr__(name: str) -> tuple[str, ...]:
    if name == report_categories_public_name:
        return report_categories
    raise AttributeError(name)


@dataclass(frozen=True)
class MaterializerConfig:
    source_root: Path
    target_root: Path
    manifest_path: Path | None = None
    should_apply: bool = False
    should_allow_full_prune: bool = False

    def __post_init__(self) -> None:
        source = self.source_root.expanduser().resolve()
        target = self.target_root.expanduser().resolve()
        if source == target or source in target.parents or target in source.parents:
            raise MaterializerError("source and target roots must not overlap")
        object.__setattr__(self, "source_root", source)
        object.__setattr__(self, "target_root", target)
        manifest = (self.manifest_path or target / ".codex-compat-manifest.json").expanduser().resolve()
        if target not in manifest.parents:
            raise MaterializerError("manifest must be inside the target root")
        object.__setattr__(self, "manifest_path", manifest)


@dataclass(frozen=True)
class ClaudeAgent:
    source_path: Path
    relative_source: str
    name: str
    description: str
    tools: tuple[str, ...] = ()
    model: str | None = None
    color: str | None = None
    unsupported: tuple[str, ...] = ()


@dataclass(frozen=True)
class ManifestRecord:
    """One compatibility-manifest entry, as the publication logic reads it.

    A field that failed validation is carried as ``None``, so ownership questions
    read as attribute checks rather than repeated isinstance guards::

        {"hash": "ab12..", "ownership": "codex-compat"} -> ok:   owned, refreshable
        {"hash": "ab12.."}                              -> flag: unowned, preserved

    The manifest also stores ``source`` and ``marker`` for inspection. No code path
    reads either, so neither appears here.

    Args:
        content_hash: Hash the tool recorded when it last published the file.
        ownership: Ownership marker the tool recorded alongside that hash.
    """

    content_hash: str | None
    ownership: str | None

    @property
    def is_owned_by_tool(self) -> bool:
        """Report whether this entry carries both fields that prove tool ownership."""
        return self.content_hash is not None and self.ownership is not None


ManifestRecordByPath = dict[str, ManifestRecord | None]


@dataclass(frozen=True)
class PlannedFile:
    source_identity: str
    target_relative_path: str
    content: ManagedContent
    content_hash: str
    ownership: str = "codex-compat"
    generated_marker: str = "codex-compat-generated-v1"
    action: str = "write"


@dataclass
class MaterializationReport:
    written: int = 0
    unchanged: int = 0
    adopted: int = 0
    unmanaged_collision: int = 0
    modified_managed: int = 0
    stale_managed: int = 0
    deleted: int = 0
    unsupported: int = 0
    conflicted: int = 0
    errors: int = 0
    error_details: list[str] = field(default_factory=list)
    details: dict[str, list[str]] = field(default_factory=lambda: {each_category: [] for each_category in report_categories})
    planned_files: list[PlannedFile] = field(default_factory=list)
    is_generation_incomplete: bool = False
    is_reconciliation_required: bool = False

    @property
    def incomplete_generation(self) -> bool:
        return self.is_generation_incomplete

    @incomplete_generation.setter
    def incomplete_generation(self, is_incomplete: bool) -> None:
        self.is_generation_incomplete = is_incomplete

    @property
    def reconcile_required(self) -> bool:
        return self.is_reconciliation_required

    @reconcile_required.setter
    def reconcile_required(self, is_required: bool) -> None:
        self.is_reconciliation_required = is_required

    @property
    def preserved(self) -> int:
        """Return the legacy name for unchanged planned files."""
        return self.unchanged + self.modified_managed + self.stale_managed

    def add_detail(self, category: str, relative_path: str) -> None:
        self.details[category].append(relative_path)

    def add_error(self, message: str) -> None:
        self.errors += 1
        self.error_details.append(message)
        self.add_detail("errors", message)


def _normalize_relative_path(path: str) -> str:
    canonical_path = path.replace("\\", path_separator)
    if not canonical_path or canonical_path.startswith(("/", "//")) or re.match(r"^[A-Za-z]:($|/)", canonical_path):
        raise MaterializerError("rooted path is not allowed")
    path_parts = canonical_path.split(path_separator)
    if any(each_part in ("", ".", "..") for each_part in path_parts) or canonical_path != path_separator.join(path_parts):
        raise MaterializerError("path is not normalized or contains traversal")
    return canonical_path


def _casefold_normalized_path(path: Path) -> str:
    return path.as_posix().casefold()


def _validate_source_identity(relative_source: str) -> str:
    canonical_source = _normalize_relative_path(relative_source)
    if canonical_source.startswith(".") or canonical_source.casefold().startswith(("private/", "private\\")):
        raise MaterializerError("private source identity is not allowed")
    return canonical_source


def _is_reparse_point(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        attributes = path.stat(follow_symlinks=False).st_file_attributes
    except (AttributeError, OSError):
        return False
    return bool(attributes & getattr(stat, reparse_point_attribute_name, 0))


def _validate_containment(root: Path, candidate: Path) -> Path:
    resolved = candidate.resolve()
    if root not in (resolved, *resolved.parents):
        raise MaterializerError("path resolves outside target root")
    return resolved


def validate_target_path(target_root: Path, relative_path: str) -> Path:
    """Resolve a relative target path inside a safe target root.

    Args:
        target_root: Directory that must contain the resolved path.
        relative_path: Normalized path relative to ``target_root``.

    Returns:
        The resolved target path.

    Raises:
        MaterializerError: If the path is rooted, unsafe, or crosses a reparse point.
    """
    canonical_path = _normalize_relative_path(relative_path)
    root = target_root.resolve()
    candidate = root.joinpath(*canonical_path.split(path_separator))
    for each_parent in (root, *candidate.parents):
        if each_parent.exists() and _is_reparse_point(each_parent):
            raise MaterializerError("target path crosses a reparse point")
    return _validate_containment(root, candidate)


class _UniqueKeySafeLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate mapping keys (safe_load keeps last)."""


def _construct_mapping_rejecting_duplicates(
    loader: yaml.SafeLoader,
    node: yaml.nodes.MappingNode,
    is_deep: bool = False,
) -> dict:
    mapping: dict = {}
    for each_key_node, each_field_node in node.value:
        key = loader.construct_object(each_key_node, deep=is_deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                None,
                None,
                f"duplicate key {key!r}",
                each_key_node.start_mark,
            )
        mapping[key] = loader.construct_object(each_field_node, deep=is_deep)
    return mapping


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping_rejecting_duplicates,
)


def _require_nonempty_string(field_content: object, source_path: Path) -> str:
    if not isinstance(field_content, str):
        raise MaterializerError(f"name and description are required: {source_path}")
    if not field_content.strip():
        raise MaterializerError(f"name and description are required: {source_path}")
    return field_content


def _require_optional_string(
    field_content: object, field_name: str, source_path: Path
) -> str | None:
    if field_content is None:
        return None
    if not isinstance(field_content, str):
        raise MaterializerError(f"{field_name} must be a string: {source_path}")
    return field_content


def _require_tools_list(tools_content: object, source_path: Path) -> tuple[str, ...]:
    if tools_content is None:
        return ()
    if isinstance(tools_content, str):
        return (tools_content,)
    if not isinstance(tools_content, list):
        raise MaterializerError(f"tools must be a list: {source_path}")
    if not all(isinstance(each_entry, str) for each_entry in tools_content):
        raise MaterializerError(f"tools must be a list: {source_path}")
    return tuple(tools_content)


def parse_frontmatter(source_path: Path, source_text: str, relative_source: str) -> ClaudeAgent:
    """Parse one Claude agent's frontmatter through validated YAML.

    Args:
        source_path: Path used in validation errors.
        source_text: Markdown source containing the frontmatter block.
        relative_source: Safe source identity recorded in the manifest.

    Returns:
        The parsed Claude agent.

    Raises:
        MaterializerError: If frontmatter syntax or required fields are invalid.
    """
    source_identity = _validate_source_identity(relative_source)
    lines = source_text.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        raise MaterializerError(f"malformed frontmatter: {source_path}")
    delimiters = [
        each_index for each_index, line in enumerate(lines[1:], 1) if line.strip() == "---"
    ]
    if len(delimiters) != 1:
        raise MaterializerError(f"malformed frontmatter delimiters: {source_path}")
    frontmatter_text = line_separator.join(lines[1 : delimiters[0]]) + line_separator
    try:
        parsed_fields = yaml.load(frontmatter_text, Loader=_UniqueKeySafeLoader)
    except yaml.YAMLError as yaml_error:
        raise MaterializerError(f"malformed frontmatter: {source_path}") from yaml_error
    if not isinstance(parsed_fields, dict):
        raise MaterializerError(f"malformed frontmatter: {source_path}")
    for each_key in parsed_fields:
        if not isinstance(each_key, str) or not re.fullmatch(
            r"[A-Za-z][A-Za-z0-9_-]*", each_key
        ):
            raise MaterializerError(f"malformed frontmatter key: {source_path}")
    unknown = tuple(
        sorted(
            each_key
            for each_key in parsed_fields
            if each_key not in frontmatter_allowed_fields
        )
    )
    if unknown:
        raise MaterializerError(f"unknown frontmatter keys: {source_path}")
    unsupported = tuple(
        sorted(
            each_key
            for each_key in parsed_fields
            if each_key in frontmatter_unsupported_fields
        )
    )
    name = _require_nonempty_string(parsed_fields.get("name"), source_path)
    description = _require_nonempty_string(
        parsed_fields.get("description"), source_path
    )
    tools = _require_tools_list(parsed_fields.get("tools"), source_path)
    model = _require_optional_string(parsed_fields.get("model"), "model", source_path)
    color = _require_optional_string(parsed_fields.get("color"), "color", source_path)
    return ClaudeAgent(
        source_path,
        source_identity,
        name,
        description,
        tools,
        model,
        color,
        unsupported,
    )


def convert_agent(agent: ClaudeAgent) -> str:
    """Convert a Claude agent to validated Codex TOML content.

    Args:
        agent: Parsed Claude agent to convert.

    Returns:
        UTF-8 text containing the generated TOML document.

    Raises:
        MaterializerError: If the generated TOML cannot be validated.
    """
    toml_string = lambda text: json.dumps(text, ensure_ascii=False)
    content = line_separator.join((f"name = {toml_string(agent.name)}", f"description = {toml_string(agent.description)}", f"developer_instructions = {toml_string('Claude tools: ' + comma_separator.join(agent.tools))}")) + line_separator
    tomllib.loads(content)
    return content


def render_codex_failure_blast_radius(rule_content: str) -> str:
    """Extract the repository-instruction contract from the canonical rule.

    Args:
        rule_content: Canonical failure blast-radius rule text.

    Returns:
        The fenced repository-instruction excerpt with a trailing newline.

    Raises:
        MaterializerError: If the canonical rule lacks the required excerpt.
    """
    heading_start = rule_content.find(codex_instruction_section_heading)
    if heading_start < 0:
        raise MaterializerError("failure blast-radius rule requires a Codex excerpt")
    fence_start = rule_content.find("```", heading_start)
    if fence_start < 0:
        raise MaterializerError("failure blast-radius rule requires a Codex excerpt")
    content_start = rule_content.find(line_separator, fence_start)
    fence_end = rule_content.find(line_separator + "```", content_start + 1)
    if content_start < 0 or fence_end < 0:
        raise MaterializerError("failure blast-radius rule requires a complete Codex excerpt")
    return rule_content[content_start + len(line_separator) : fence_end].rstrip() + line_separator


def _build_codex_instruction_projection(config: MaterializerConfig) -> PlannedFile | None:
    """Build the managed AGENTS.md projection when the canonical rule is present."""
    source_path = config.source_root / failure_blast_radius_rule_relative_path
    if not source_path.exists() and not _is_reparse_point(source_path):
        return None
    source_path = _validated_source_file(config, failure_blast_radius_rule_relative_path, "failure blast-radius rule")
    rule_content = source_path.read_text(encoding="utf-8")
    projected_content = render_codex_failure_blast_radius(rule_content)
    return PlannedFile(
        failure_blast_radius_rule_relative_path,
        codex_instruction_target_path,
        projected_content,
        hash_content(projected_content),
    )


def _read_json_object(file_path: Path, description: str) -> dict[str, object]:
    """Read one JSON object and report the required content shape."""
    try:
        parsed_json = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MaterializerError(f"{description} requires readable UTF-8 content: {file_path}") from error
    if not isinstance(parsed_json, dict):
        raise MaterializerError(f"{description} must be a JSON object: {file_path}")
    if not all(isinstance(each_key, str) for each_key in parsed_json):
        raise MaterializerError(f"{description} requires string keys: {file_path}")
    return {each_key: each_record for each_key, each_record in parsed_json.items()}


def _validated_source_file(
    config: MaterializerConfig, relative_path: str, description: str
) -> Path:
    """Resolve one source file while rejecting reparse points and escapes."""
    source_path = config.source_root.joinpath(*relative_path.split(path_separator))
    current_path = config.source_root
    for each_part in relative_path.split(path_separator):
        current_path /= each_part
        if current_path.exists() and _is_reparse_point(current_path):
            raise MaterializerRunFatal(
                f"{description} source reparse point is not allowed: {relative_path}"
            )
    resolved_path = _validate_containment(config.source_root, source_path)
    if not resolved_path.is_file():
        raise MaterializerError(f"{description} source file is missing: {relative_path}")
    return resolved_path


def _validated_agent_iterable(candidate: object) -> tuple[ClaudeAgent, ...]:
    """Validate the optional agent iterable used by the legacy call form."""
    if not isinstance(candidate, Iterable):
        raise TypeError("agent collection requires an iterable")
    all_candidate_agents = tuple(candidate)
    if not all(isinstance(each_agent, ClaudeAgent) for each_agent in all_candidate_agents):
        raise TypeError("agent collection requires ClaudeAgent entries")
    return all_candidate_agents


def _validated_planned_file_iterable(candidate: object) -> tuple[PlannedFile, ...]:
    """Validate planned files passed through the legacy publication call form."""
    if not isinstance(candidate, Iterable):
        raise TypeError("planned files require an iterable")
    all_candidate_files = tuple(candidate)
    if not all(isinstance(each_file, PlannedFile) for each_file in all_candidate_files):
        raise TypeError("planned files require PlannedFile entries")
    return all_candidate_files


def _find_codex_hook_source(config: MaterializerConfig) -> Path | None:
    """Find the source hook manifest alongside the compatibility sources."""
    all_candidates = (
        config.source_root / codex_hook_manifest_source_path,
        config.source_root / Path(codex_hook_manifest_source_path).name,
    )
    for each_path in all_candidates:
        if each_path.exists() or _is_reparse_point(each_path):
            relative_path = each_path.relative_to(config.source_root).as_posix()
            return _validated_source_file(config, relative_path, "Codex hook manifest")
    return None


def _resolved_codex_enforcer_command(config: MaterializerConfig) -> str:
    """Build the target-root command for the focused Codex enforcer."""
    script_path = (config.target_root / codex_enforcer_script_relative_path).resolve()
    return f'python3 "{script_path}"'


def _source_codex_enforcer_hook(
    all_source_manifest: dict[str, object], command: str
) -> dict[str, object] | None:
    """Read the source enforcer hook shape and resolve its target command."""
    all_events = all_source_manifest.get("hooks")
    if not isinstance(all_events, dict):
        raise MaterializerError("source Codex hook manifest requires a hooks object")
    all_pre_tool_use = all_events.get(codex_hook_event_name)
    if not isinstance(all_pre_tool_use, list):
        raise MaterializerError("source Codex hook manifest requires a PreToolUse list")
    for each_entry in all_pre_tool_use:
        if not isinstance(each_entry, dict) or each_entry.get("matcher") != codex_hook_matcher:
            continue
        all_hook_records = each_entry.get("hooks")
        if not isinstance(all_hook_records, list):
            continue
        for each_hook in all_hook_records:
            if not isinstance(each_hook, dict):
                continue
            if not _is_code_rules_enforcer_hook(each_hook):
                continue
            resolved_hook = dict(each_hook)
            resolved_hook[codex_hook_command_field_name] = command
            return resolved_hook
    return None


def _hook_records(raw_hooks: object) -> list[dict[str, object]]:
    """Validate and copy a Codex hook-record list."""
    if not isinstance(raw_hooks, list):
        raise MaterializerError("Codex hook manifest entry requires a hooks list")
    if not all(isinstance(each_hook, dict) for each_hook in raw_hooks):
        raise MaterializerError("Codex hook manifest requires valid hook entries")
    return [dict(each_hook) for each_hook in raw_hooks]


def _is_code_rules_enforcer_hook(all_hook_record: dict[str, object]) -> bool:
    """Report whether a hook record names the focused code-rules enforcer."""
    command = str(all_hook_record.get(codex_hook_command_field_name, ""))
    normalized_command = command.replace("\\", path_separator)
    all_command_tokens = (
        each_token.strip("\"'")
        for each_token in re.findall(codex_hook_command_token_pattern, normalized_command)
    )
    return any(
        each_token in (codex_enforcer_script_name, codex_enforcer_script_relative_path)
        or each_token.endswith(codex_enforcer_path_suffix)
        for each_token in all_command_tokens
    )


def _is_managed_codex_enforcer_hook(
    all_hook_record: dict[str, object], managed_command: str
) -> bool:
    """Report whether a hook record is the materializer's target command."""
    command = all_hook_record.get(codex_hook_command_field_name)
    if not isinstance(command, str):
        return False
    normalized_command = command.replace("\\", path_separator)
    normalized_managed_command = managed_command.replace("\\", path_separator)
    if os.name == "nt":
        return normalized_command.casefold() == normalized_managed_command.casefold()
    return normalized_command == normalized_managed_command


def _without_managed_codex_enforcer(
    entry: object, managed_command: str
) -> object | None:
    """Remove the managed enforcer while preserving every other hook record."""
    if not isinstance(entry, dict):
        return entry
    if entry.get("matcher") != codex_hook_matcher:
        return entry
    copied_entry = dict(entry)
    all_hook_records = copied_entry.get(codex_hook_records_field_name)
    if not isinstance(all_hook_records, list):
        return copied_entry
    all_retained_hooks = [
        each_hook
        for each_hook in all_hook_records
        if not isinstance(each_hook, dict)
        or not _is_managed_codex_enforcer_hook(each_hook, managed_command)
    ]
    if all_retained_hooks == all_hook_records:
        return copied_entry
    if not all_retained_hooks:
        return None
    copied_entry[codex_hook_records_field_name] = all_retained_hooks
    return copied_entry


def _remove_managed_codex_enforcer(
    all_target_manifest: dict[str, object], managed_command: str
) -> dict[str, object]:
    """Remove the retired managed enforcer from the target manifest."""
    all_events = all_target_manifest.get(codex_hook_records_field_name, {})
    if not isinstance(all_events, dict):
        raise MaterializerError("Codex hook manifest requires a hooks object")
    all_pre_tool_use = all_events.get(codex_hook_event_name)
    if all_pre_tool_use is None:
        return _prune_retired_codex_hooks(all_target_manifest)
    if not isinstance(all_pre_tool_use, list):
        raise MaterializerError("Codex hook manifest requires a PreToolUse list")
    all_retained_entries: list[object] = []
    for each_entry in all_pre_tool_use:
        maybe_retained_entry = _without_managed_codex_enforcer(
            each_entry, managed_command
        )
        if maybe_retained_entry is not None:
            all_retained_entries.append(maybe_retained_entry)
    merged_events = dict(all_events)
    merged_events[codex_hook_event_name] = all_retained_entries
    merged_manifest = dict(all_target_manifest)
    merged_manifest[codex_hook_records_field_name] = merged_events
    return _prune_retired_codex_hooks(merged_manifest)


def _is_retired_codex_hook_command(command: object) -> bool:
    """Report whether a command names a known retired hook path."""
    if not isinstance(command, str):
        return False
    normalized_command = command.replace("\\", path_separator)
    return any(
        (
            each_token.strip("\"'").casefold() in codex_retired_hook_commands
            or each_token.strip("\"'").casefold().endswith(codex_default_home_hook_path_suffix)
        )
        for each_token in re.findall(codex_hook_command_token_pattern, normalized_command)
    )


def _prune_retired_codex_hooks(
    all_target_manifest: dict[str, object],
) -> dict[str, object]:
    """Remove known retired hook groups from every valid event list."""
    all_events = all_target_manifest.get(codex_hook_records_field_name)
    if not isinstance(all_events, dict):
        return dict(all_target_manifest)
    event_groups_by_name: dict[str, object] = {}
    for each_event_name, each_raw_groups in all_events.items():
        if not isinstance(each_raw_groups, list):
            event_groups_by_name[each_event_name] = each_raw_groups
            continue
        all_kept_groups: list[object] = []
        for each_group in each_raw_groups:
            if not isinstance(each_group, dict):
                all_kept_groups.append(each_group)
                continue
            all_raw_hooks = each_group.get(codex_hook_records_field_name)
            if not isinstance(all_raw_hooks, list):
                all_kept_groups.append(each_group)
                continue
            if not isinstance(each_group.get(codex_hook_matcher_field_name), str):
                all_kept_groups.append(each_group)
                continue
            copied_group = dict(each_group)
            copied_group[codex_hook_records_field_name] = [
                each_hook
                for each_hook in all_raw_hooks
                if not (
                    isinstance(each_hook, dict)
                    and _is_retired_codex_hook_command(
                        each_hook.get(codex_hook_command_field_name)
                    )
                )
            ]
            if not all_raw_hooks or copied_group[codex_hook_records_field_name]:
                all_kept_groups.append(copied_group)
        if all_kept_groups:
            event_groups_by_name[each_event_name] = all_kept_groups
    pruned_manifest = dict(all_target_manifest)
    pruned_manifest[codex_hook_records_field_name] = event_groups_by_name
    return pruned_manifest


def _codex_enforcer_hooks(all_manifest: object) -> tuple[dict[str, object], ...]:
    """Return enforcer records from the target apply-patch matcher."""
    if not isinstance(all_manifest, dict):
        return ()
    all_events = all_manifest.get("hooks")
    if not isinstance(all_events, dict):
        return ()
    all_pre_tool_use = all_events.get(codex_hook_event_name)
    if not isinstance(all_pre_tool_use, list):
        return ()
    all_enforcer_hooks: list[dict[str, object]] = []
    for each_entry in all_pre_tool_use:
        if not isinstance(each_entry, dict) or each_entry.get("matcher") != codex_hook_matcher:
            continue
        try:
            all_hook_records = _hook_records(
                each_entry.get(codex_hook_records_field_name, [])
            )
        except MaterializerError:
            continue
        for each_hook in all_hook_records:
            if _is_code_rules_enforcer_hook(each_hook):
                all_enforcer_hooks.append(each_hook)
    return tuple(all_enforcer_hooks)


def _has_modified_codex_enforcer_hook(
    current_bytes: bytes, planned_content: ManagedContent
) -> bool:
    """Report whether an existing enforcer record differs from the plan."""
    try:
        current_manifest = json.loads(current_bytes.decode("utf-8"))
        planned_manifest = json.loads(content_to_bytes(planned_content).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return True
    current_hooks = _codex_enforcer_hooks(current_manifest)
    if not current_hooks:
        return False
    planned_hooks = _codex_enforcer_hooks(planned_manifest)
    if all(each_hook in current_hooks for each_hook in planned_hooks):
        return False
    return current_hooks != planned_hooks


def _merge_codex_hook_manifest(
    all_target_manifest: dict[str, object],
    all_focused_hook: dict[str, object] | None,
    managed_command: str,
) -> dict[str, object]:
    """Preserve target hook order while merging one deterministic enforcer entry."""
    if all_focused_hook is None:
        return _remove_managed_codex_enforcer(all_target_manifest, managed_command)
    all_events = all_target_manifest.get(codex_hook_records_field_name, {})
    if not isinstance(all_events, dict):
        raise MaterializerError("Codex hook manifest requires a hooks object")
    all_pre_tool_use = all_events.get(codex_hook_event_name, [])
    if not isinstance(all_pre_tool_use, list):
        raise MaterializerError("Codex hook manifest requires a PreToolUse list")
    merged_pre_tool_use: list[object] = []
    merged_apply_patch_entry: dict[str, object] | None = None
    merged_hooks: list[dict[str, object]] = []
    for each_entry in all_pre_tool_use:
        if not isinstance(each_entry, dict):
            merged_pre_tool_use.append(each_entry)
            continue
        copied_entry = dict(each_entry)
        if copied_entry.get("matcher") != codex_hook_matcher:
            merged_pre_tool_use.append(copied_entry)
            continue
        all_hook_records = copied_entry.get(codex_hook_records_field_name, [])
        if not isinstance(all_hook_records, list) or not all(
            isinstance(each_hook, dict) for each_hook in all_hook_records
        ):
            merged_pre_tool_use.append(copied_entry)
            continue
        if merged_apply_patch_entry is None:
            merged_apply_patch_entry = copied_entry
            merged_hooks = [
                each_hook
                for each_hook in all_hook_records
                if not _is_managed_codex_enforcer_hook(each_hook, managed_command)
            ]
            merged_apply_patch_entry[codex_hook_records_field_name] = merged_hooks
            merged_pre_tool_use.append(merged_apply_patch_entry)
        else:
            merged_hooks.extend(
                each_hook
                for each_hook in all_hook_records
                if not _is_managed_codex_enforcer_hook(each_hook, managed_command)
            )
    if merged_apply_patch_entry is None:
        merged_apply_patch_entry = {
            "matcher": codex_hook_matcher,
            codex_hook_records_field_name: merged_hooks,
        }
        merged_pre_tool_use.append(merged_apply_patch_entry)
    merged_hooks.append(all_focused_hook)
    merged_events = dict(all_events)
    merged_events[codex_hook_event_name] = merged_pre_tool_use
    merged_manifest = dict(all_target_manifest)
    merged_manifest[codex_hook_records_field_name] = merged_events
    return _prune_retired_codex_hooks(merged_manifest)


def _build_codex_hook_projection(config: MaterializerConfig) -> PlannedFile | None:
    """Build an additive managed hooks.json projection when its source exists."""
    source_path = _find_codex_hook_source(config)
    if source_path is None:
        return None
    source_manifest = _read_json_object(source_path, "source Codex hook manifest")
    target_path = config.target_root / codex_hook_manifest_target_path
    target_manifest = (
        _read_json_object(target_path, "target Codex hook manifest")
        if target_path.is_file()
        else {"hooks": {}}
    )
    managed_command = _resolved_codex_enforcer_command(config)
    focused_hook = _source_codex_enforcer_hook(source_manifest, managed_command)
    projected_manifest = _merge_codex_hook_manifest(
        target_manifest, focused_hook, managed_command
    )
    projected_content = json.dumps(projected_manifest, ensure_ascii=False, indent=manifest_indentation_width) + line_separator
    return PlannedFile(
        codex_hook_manifest_source_path,
        codex_hook_manifest_target_path,
        projected_content,
        hash_content(projected_content),
        action=codex_hook_merge_action,
    )


def _build_codex_hook_dependency_projection(
    config: MaterializerConfig,
) -> list[PlannedFile]:
    """Build the reviewed source files required by the target enforcer."""
    if not _has_source_codex_enforcer(config):
        return []
    all_dependencies: list[PlannedFile] = []
    for each_relative_path in codex_hook_dependency_manifest:
        source_path = _validated_source_file(
            config, each_relative_path, "reviewed Codex hook dependency"
        )
        try:
            dependency_content = source_path.read_bytes()
        except OSError as error:
            raise MaterializerError(
                f"reviewed Codex hook dependency has unreadable bytes: {each_relative_path}"
            ) from error
        all_dependencies.append(
            PlannedFile(
                each_relative_path,
                each_relative_path,
                dependency_content,
                hash_content(dependency_content),
            )
        )
    return all_dependencies


def _has_source_codex_enforcer(config: MaterializerConfig) -> bool:
    """Report whether hooks.json registers the enforcer."""
    source_path = _find_codex_hook_source(config)
    if source_path is None:
        return False
    source_manifest = _read_json_object(source_path, "source Codex hook manifest")
    managed_command = _resolved_codex_enforcer_command(config)
    return _source_codex_enforcer_hook(source_manifest, managed_command) is not None


def discover_agents(config: MaterializerConfig) -> list[ClaudeAgent]:
    """Discover and parse Markdown agents below the source root.

    Args:
        config: Materializer paths and application settings.

    An unreachable source root is an error rather than an empty discovery, so a
    mistyped path or an offline share never reads as "this tree holds no agents"::

        source root missing   -> flag: MaterializerError, nothing planned
        source root empty     -> ok:   [] , and publication asks for prune consent

    Returns:
        Agents discovered in deterministic relative-path order.

    Raises:
        MaterializerError: If the source root is unreachable, or a source path is unsafe or malformed.
    """
    if not config.source_root.is_dir():
        raise MaterializerError(f"{unreadable_source_root_message}: {config.source_root}")
    if _is_reparse_point(config.source_root):
        raise MaterializerError(f"{reparse_source_root_message}: {config.source_root}")
    all_agents: list[ClaudeAgent] = []
    for each_path in sorted(config.source_root.rglob("*.md"), key=lambda path: path.as_posix().casefold()):
        if each_path.name in instruction_alias_filenames:
            _validate_containment(config.source_root, each_path)
            continue
        if _is_reparse_point(each_path):
            raise MaterializerError(f"source reparse point is not allowed: {each_path}")
        relative_source = each_path.relative_to(config.source_root).as_posix()
        if relative_source == failure_blast_radius_rule_relative_path:
            _validate_containment(config.source_root, each_path)
            continue
        _validate_containment(config.source_root, each_path)
        all_agents.append(parse_frontmatter(each_path, each_path.read_text(encoding="utf-8"), relative_source))
    return all_agents


def _case_fold_collision_error(target_relative_path: str) -> MaterializerRunFatal:
    """Build the error for two target names that differ only by letter case."""
    return MaterializerRunFatal(f"case-fold collision: {target_relative_path}")


def _validate_orphan_target_is_adoptable(
    config: MaterializerConfig,
    existing_path: Path | None,
    target_relative_path: str,
    content: ManagedContent,
) -> None:
    """Allow an unrecorded target file only when its bytes already match the plan.

    A run interrupted between the file replacement and the manifest save leaves a
    file the manifest does not record. Byte-identical content proves the tool wrote
    it, so the next run adopts it instead of stopping forever::

        Nova.toml bytes == planned bytes  -> ok:   adopted, publication continues
        Nova.toml bytes != planned bytes  -> flag: MaterializerError naming the remedy

    Args:
        config: Materializer paths and application settings.
        existing_path: Target-root path already holding the planned name, or ``None``.
        target_relative_path: Normalized relative path the plan publishes.
        content: Content the plan would publish at that path.

    Raises:
        MaterializerError: If the existing file differs from the plan or differs only in case.
    """
    if existing_path is None:
        return
    if existing_path.relative_to(config.target_root).as_posix() != target_relative_path:
        raise _case_fold_collision_error(target_relative_path)
    if not existing_path.is_file() or existing_path.read_bytes() != content_to_bytes(content):
        raise MaterializerError(unmanaged_target_message.format(path=target_relative_path))


def _configured_manifest_path(config: MaterializerConfig) -> Path:
    """Return the manifest path established during configuration validation."""
    if config.manifest_path is None:
        raise MaterializerError("compatibility manifest path requires configuration")
    return config.manifest_path


def _build_plan(config: MaterializerConfig, all_agents: Iterable[ClaudeAgent]) -> tuple[list[PlannedFile], MaterializationReport]:
    """Build planned agent publications and their report.

    Args:
        config: Materializer paths and application settings.
        all_agents: Optional parsed agents used by callers that inject discovery results.

    Returns:
        Planned files and the report describing unsupported agent fields.

    Raises:
        MaterializerError: If a source or target path collides or is unsafe.
    """
    report = MaterializationReport()
    planned: list[PlannedFile] = []
    target_by_name: dict[str, str] = {}
    manifest_path = _configured_manifest_path(config)
    previous_records = _manifest_record_by_path(load_manifest(manifest_path))
    existing_by_name = {
        each_path.relative_to(config.target_root).as_posix().casefold(): each_path
        for each_path in config.target_root.rglob("*")
        if not _is_known_managed_path(config.target_root, each_path, previous_records)
    } if config.target_root.exists() else {}
    for each_agent in list(all_agents):
        source_identity = _validate_source_identity(each_agent.relative_source)
        target_relative_path = _normalize_relative_path(each_agent.name + toml_suffix)
        folded_path = target_relative_path.casefold()
        if folded_path in target_by_name:
            raise MaterializerRunFatal(f"case-fold collision: {target_relative_path}")
        content = convert_agent(each_agent)
        _validate_orphan_target_is_adoptable(config, existing_by_name.get(folded_path), target_relative_path, content)
        target_by_name[folded_path] = target_relative_path
        target_path = validate_target_path(config.target_root, target_relative_path)
        if _casefold_normalized_path(target_path) == _casefold_normalized_path(manifest_path):
            raise MaterializerRunFatal("planned target collides with compatibility manifest")
        planned.append(PlannedFile(source_identity, target_relative_path, content, hash_content(content)))
        report.unsupported += len(each_agent.unsupported)
        report.details["unsupported"].extend(f"{source_identity}:{each_key}" for each_key in each_agent.unsupported)
    codex_instruction = _build_codex_instruction_projection(config)
    if codex_instruction is not None:
        folded_path = codex_instruction.target_relative_path.casefold()
        if folded_path in target_by_name:
            raise _case_fold_collision_error(codex_instruction.target_relative_path)
        _validate_orphan_target_is_adoptable(
            config,
            existing_by_name.get(folded_path),
            codex_instruction.target_relative_path,
            codex_instruction.content,
        )
        validate_target_path(config.target_root, codex_instruction.target_relative_path)
        planned.append(codex_instruction)
        target_by_name[folded_path] = codex_instruction.target_relative_path
    codex_hooks = _build_codex_hook_projection(config)
    if codex_hooks is not None:
        all_hook_dependencies = _build_codex_hook_dependency_projection(config)
        for each_dependency in all_hook_dependencies:
            folded_dependency_path = each_dependency.target_relative_path.casefold()
            if folded_dependency_path in target_by_name:
                raise _case_fold_collision_error(each_dependency.target_relative_path)
            validate_target_path(config.target_root, each_dependency.target_relative_path)
            target_by_name[folded_dependency_path] = each_dependency.target_relative_path
            planned.append(each_dependency)
        folded_path = codex_hooks.target_relative_path.casefold()
        if folded_path in target_by_name:
            raise _case_fold_collision_error(codex_hooks.target_relative_path)
        validate_target_path(config.target_root, codex_hooks.target_relative_path)
        planned.append(codex_hooks)
    report.planned_files = planned
    return planned, report


def build_plan(config: MaterializerConfig, *all_arguments: object, **all_keywords: object) -> tuple[list[PlannedFile], MaterializationReport]:
    """Build a plan while preserving the legacy optional-agent call form.

    Args:
        config: Materializer paths and application settings.
        all_arguments: Optional positional discovered-agent iterable.
        all_keywords: Optional ``all_agents`` keyword argument.

    Returns:
        Planned files and the report describing unsupported agent fields.

    Raises:
        TypeError: If more than one agent iterable or an unknown keyword is supplied.
        MaterializerError: If a source or target path collides or is unsafe.
    """
    supplied_agents = all_keywords.pop("all_agents", None)
    if all_keywords or len(all_arguments) > 1:
        raise TypeError("build_plan accepts at most one agent iterable")
    if all_arguments:
        if supplied_agents is not None:
            raise TypeError("build_plan received duplicate all_agents")
        supplied_agents = all_arguments[0]
    discovered_agents = (
        discover_agents(config)
        if supplied_agents is None
        else _validated_agent_iterable(supplied_agents)
    )
    return _build_plan(config, discovered_agents)


def content_to_bytes(content: ManagedContent) -> bytes:
    """Encode managed text while preserving already-encoded bytes.

    Args:
        content: Text or bytes intended for publication.

    Returns:
        UTF-8 bytes for the managed content.
    """
    if isinstance(content, bytes):
        return content
    return content.encode("utf-8")


def hash_content(content: ManagedContent) -> str:
    return hashlib.sha256(content_to_bytes(content)).hexdigest()


def _atomic_write(
    target_path: Path,
    content: ManagedContent,
    failure_injector: Callable[[str], None] | None,
) -> None:
    """Write managed content through a temporary file and replace atomically.

    Args:
        target_path: Destination path for the replacement.
        content: Text or bytes to write.
        failure_injector: Test seam invoked before replacement, or ``None``.

    Raises:
        OSError: If the temporary file or replacement cannot be written.
        RuntimeError: If the failure injector requests a failed publication.
        ValueError: If the content cannot be encoded.

    The optional injector is a test seam. When supplied, it runs after the
    temporary file is durable and before the destination replacement.

    Raises:
        OSError: If the temporary file or replacement cannot be written.
        RuntimeError: If the failure injector requests a failed publication.
        ValueError: If the content cannot be encoded.
    """
    target_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target_path.name}.", dir=target_path.parent)
    try:
        with os.fdopen(descriptor, "wb") as temporary_file:
            temporary_file.write(content_to_bytes(content))
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        if failure_injector is not None:
            failure_injector(str(target_path))
        os.replace(temporary_name, target_path)
    except (OSError, RuntimeError, ValueError):
        Path(temporary_name).unlink(missing_ok=True)
        raise


def atomic_write(target_path: Path, content: ManagedContent, *all_arguments: object, **all_keywords: object) -> None:
    """Preserve the legacy atomic-write call form while using an explicit core.

    Args:
        target_path: Destination path for the replacement.
        content: Text or bytes to write.
        all_arguments: Legacy positional failure-injector argument.
        all_keywords: Legacy keyword failure-injector argument.

    Raises:
        TypeError: If more than one failure injector is supplied or it is not callable.
        OSError, RuntimeError, ValueError: If the atomic replacement cannot be completed.
    """
    failure_injector = all_keywords.pop("failure_injector", None)
    if all_keywords or len(all_arguments) > 1:
        raise TypeError("atomic_write accepts at most one failure injector")
    if all_arguments:
        failure_injector = all_arguments[0]
    if failure_injector is not None and not callable(failure_injector):
        raise TypeError("failure injector must be callable")
    _atomic_write(target_path, content, failure_injector)


def load_manifest(manifest_path: Path) -> dict[str, object]:
    """Load a compatibility manifest or return its empty schema.

    Args:
        manifest_path: Manifest file to read.

    Returns:
        A validated manifest mapping.

    Raises:
        MaterializerError: If the manifest has an unsupported shape.
    """
    if not manifest_path.exists():
        return {"version": 1, "files": {}}
    parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict) or parsed.get("version") != 1 or not isinstance(parsed.get("files"), dict):
        raise MaterializerError("invalid compatibility manifest")
    return parsed


def save_manifest(manifest_path: Path, all_manifest: dict[str, object], failure_injector: Callable[[str], None] | None = None) -> None:
    """Atomically save the compatibility manifest last.

    Args:
        manifest_path: Destination manifest path.
        all_manifest: Manifest mapping to serialize.
        failure_injector: Optional test seam invoked before replacement.

    Raises:
        OSError: If the temporary file or replacement cannot be written.
        RuntimeError: If the failure injector requests a failed publication.
    """
    content = json.dumps(all_manifest, ensure_ascii=False, sort_keys=True, indent=manifest_indentation_width) + "\n"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{manifest_path.name}.", dir=manifest_path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as temporary_file:
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        if failure_injector is not None:
            failure_injector("manifest_before_replace")
        os.replace(temporary_name, manifest_path)
    except (OSError, RuntimeError, ValueError):
        Path(temporary_name).unlink(missing_ok=True)
        raise


def _parse_manifest_record(raw_record: object) -> ManifestRecord | None:
    """Read one manifest entry into a record, or ``None`` when it is not an object."""
    if not isinstance(raw_record, dict):
        return None
    expected_hash = raw_record.get("hash")
    ownership = raw_record.get("ownership")
    return ManifestRecord(
        expected_hash if isinstance(expected_hash, str) else None,
        ownership if isinstance(ownership, str) else None,
    )


def _manifest_record_by_path(all_previous_manifest: dict[str, object]) -> ManifestRecordByPath:
    """Parse the manifest's file entries once, so untyped JSON stops here.

    Every path stays in the mapping even when its entry is unreadable, because the
    case-fold checks count the names the manifest claims::

        {"Luna.toml": {"hash": "ab12..", "ownership": "codex-compat"}} -> ok:   record
        {"Luna.toml": 7}                                              -> flag: None

    Args:
        all_previous_manifest: Validated manifest mapping from ``load_manifest``.

    Returns:
        Each manifest path mapped to its record, or to ``None`` when unreadable.

    Raises:
        MaterializerError: If the manifest's file entries are not a mapping.
    """
    records = all_previous_manifest["files"]
    if not isinstance(records, dict):
        raise MaterializerError("invalid compatibility manifest files")
    return {each_path: _parse_manifest_record(each_record) for each_path, each_record in records.items()}


def _find_manifest_record(all_previous_records: ManifestRecordByPath, target_relative_path: str) -> ManifestRecord | None:
    for each_path, each_record in all_previous_records.items():
        if each_path.casefold() == target_relative_path.casefold():
            return each_record
    return None


def _is_known_managed_path(target_root: Path, target_path: Path, all_previous_records: ManifestRecordByPath) -> bool:
    relative_path = target_path.relative_to(target_root).as_posix()
    previous_record = _find_manifest_record(all_previous_records, relative_path)
    return previous_record is not None and previous_record.is_owned_by_tool


def _is_pristine_managed(previous_record: ManifestRecord | None, current_bytes: bytes) -> bool:
    """Report whether on-disk bytes are exactly what the tool last published there."""
    if previous_record is None or not previous_record.is_owned_by_tool:
        return False
    return hash_content(current_bytes) == previous_record.content_hash


def _record_target_conflict(report: MaterializationReport, target_relative_path: str, previous_record: ManifestRecord | None) -> None:
    report.conflicted += 1
    report.add_detail("conflicted", target_relative_path)
    if previous_record is None:
        report.unmanaged_collision += 1
        report.add_detail("unmanaged_collision", target_relative_path)
        return
    report.modified_managed += 1
    report.add_detail("modified_managed", target_relative_path)


def _record_target_state(config: MaterializerConfig, planned_file: PlannedFile, all_previous_records: ManifestRecordByPath, report: MaterializationReport) -> tuple[Path, bytes | None, bool]:
    """Classify one planned target and say whether publication may overwrite it.

    The manifest hash decides ownership, so a file the tool wrote is refreshed and a
    file the user edited is preserved::

        target absent                    -> ok:   publish
        on-disk bytes == planned bytes   -> ok:   unchanged, no write
        _has_modified_codex_enforcer_hook -> flag: conflicted, preserved untouched
        on-disk hash == manifest hash    -> ok:   publish, the tool owns these bytes
        on-disk hash != manifest hash    -> flag: conflicted, preserved untouched

    Args:
        config: Materializer paths and application settings.
        planned_file: Planned publication for this target.
        all_previous_records: Manifest records from the last successful run.
        report: Report object to update in place.

    Returns:
        The resolved target path, its current bytes when it exists, and whether to publish.
    """
    target_path = validate_target_path(config.target_root, planned_file.target_relative_path)
    if not target_path.exists():
        return target_path, None, True
    current_bytes = target_path.read_bytes()
    previous_record = _find_manifest_record(all_previous_records, planned_file.target_relative_path)
    if current_bytes == content_to_bytes(planned_file.content):
        _record_matching_target(report, planned_file.target_relative_path, previous_record)
        return target_path, current_bytes, False
    if planned_file.action == codex_hook_merge_action:
        if _has_modified_codex_enforcer_hook(current_bytes, planned_file.content):
            _record_target_conflict(report, planned_file.target_relative_path, previous_record)
            return target_path, current_bytes, False
        return target_path, current_bytes, True
    if _is_pristine_managed(previous_record, current_bytes):
        return target_path, current_bytes, True
    _record_target_conflict(report, planned_file.target_relative_path, previous_record)
    return target_path, current_bytes, False


def _record_matching_target(report: MaterializationReport, target_relative_path: str, previous_record: ManifestRecord | None) -> None:
    report.unchanged += 1
    report.add_detail("unchanged", target_relative_path)
    if previous_record is not None:
        return
    report.adopted += 1
    report.add_detail("adopted", target_relative_path)


def _remove_stale_files(config: MaterializerConfig, all_previous_records: ManifestRecordByPath, all_planned_files: list[PlannedFile], report: MaterializationReport, all_backups: dict[Path, bytes | None]) -> None:
    current_names = {each_planned_file.target_relative_path.casefold() for each_planned_file in all_planned_files}
    for each_relative_path, each_record in sorted(all_previous_records.items(), key=lambda pair: pair[0].casefold()):
        if each_relative_path.casefold() in current_names or each_record is None:
            continue
        target_path = validate_target_path(config.target_root, each_relative_path)
        if not target_path.exists():
            report.add_error(f"missing managed path: {each_relative_path}")
            continue
        current_bytes = target_path.read_bytes()
        expected_hash = each_record.content_hash
        if expected_hash is not None and hash_content(current_bytes) == expected_hash:
            all_backups[target_path] = current_bytes
            target_path.unlink()
            report.deleted += 1
            report.add_detail("deleted", each_relative_path)
            continue
        if expected_hash is not None:
            report.modified_managed += 1
            report.add_detail("modified_managed", each_relative_path)


def _sort_report_details(report: MaterializationReport) -> None:
    for each_category in report_categories:
        if each_category == "errors":
            continue
        report.details[each_category].sort(key=str.casefold)


def _validate_planned_targets(
    all_planned_files: list[PlannedFile],
    all_previous_records: ManifestRecordByPath,
) -> None:
    folded_manifest_names = {each_key.casefold() for each_key in all_previous_records}
    if len(folded_manifest_names) != len(all_previous_records):
        raise MaterializerError("case-fold collision in compatibility manifest")
    planned_names: set[str] = set()
    for each_file in all_planned_files:
        folded_target = each_file.target_relative_path.casefold()
        if folded_target in planned_names:
            raise _case_fold_collision_error(each_file.target_relative_path)
        planned_names.add(folded_target)
        has_manifest_owner = any(
            each_path.casefold() == folded_target
            and each_record is not None
            and each_record.ownership is not None
            for each_path, each_record in all_previous_records.items()
        )
        if folded_target in folded_manifest_names and not has_manifest_owner:
            raise MaterializerError("case-fold collision in compatibility manifest")


def _publish_planned_targets(
    config: MaterializerConfig,
    all_planned_files: list[PlannedFile],
    all_previous_records: ManifestRecordByPath,
    report: MaterializationReport,
    all_backups: dict[Path, bytes | None],
    failure_injector: Callable[[str], None] | None,
) -> None:
    manifest_path = _configured_manifest_path(config)
    for each_planned_file in all_planned_files:
        target_path, current_bytes, is_publishable = _record_target_state(config, each_planned_file, all_previous_records, report)
        if _casefold_normalized_path(target_path) == _casefold_normalized_path(manifest_path):
            raise MaterializerError("planned target collides with compatibility manifest")
        if not is_publishable:
            continue
        all_backups[target_path] = current_bytes
        atomic_write(target_path, each_planned_file.content, failure_injector)
        report.written += 1
        report.add_detail("written", each_planned_file.target_relative_path)


def _build_manifest(all_planned_files: list[PlannedFile]) -> dict[str, object]:
    return {
        "version": 1,
        "files": {
            each_file.target_relative_path: {
                "source": each_file.source_identity,
                "hash": each_file.content_hash,
                "ownership": each_file.ownership,
                "marker": each_file.generated_marker,
            }
            for each_file in all_planned_files
        },
    }


def _rollback_publication(
    all_backups: dict[Path, bytes | None],
    report: MaterializationReport,
    initial_written: int,
    initial_deleted: int,
) -> None:
    for each_target_path, each_previous_content in reversed(tuple(all_backups.items())):
        try:
            if each_previous_content is None:
                each_target_path.unlink(missing_ok=True)
            else:
                atomic_write(each_target_path, each_previous_content)
        except OSError:
            report.reconcile_required = True
            report.add_error(f"rollback failed: {each_target_path}")
    report.incomplete_generation = True
    report.reconcile_required = True
    report.written = initial_written
    report.deleted = initial_deleted
    report.details["written"] = report.details["written"][:initial_written]
    report.details["deleted"] = report.details["deleted"][:initial_deleted]
    report.add_error("incomplete_generation/reconcile_required")
    _sort_report_details(report)


def _validate_full_prune_consent(
    config: MaterializerConfig,
    all_planned_files: list[PlannedFile],
    all_previous_records: ManifestRecordByPath,
) -> None:
    """Require an explicit opt-in before an empty plan erases every managed file.

    An empty plan means every managed file is stale, so publication would delete the
    whole set. That is a legitimate request and also what a mistyped source root
    produces, so the caller has to ask for it by name::

        empty plan, empty manifest              -> ok:   nothing to delete
        empty plan, managed files, opt-in given -> ok:   prune proceeds
        empty plan, managed files, no opt-in    -> flag: MaterializerError, nothing deleted

    Args:
        config: Materializer paths and application settings.
        all_planned_files: Files the current run would publish.
        all_previous_records: Manifest records from the last successful run.

    Raises:
        MaterializerError: If the run would delete every managed file without the opt-in.
    """
    if all_planned_files or not all_previous_records or config.should_allow_full_prune:
        return
    raise MaterializerError(full_prune_refusal_message.format(count=len(all_previous_records)))


def _publish_plan(
    config: MaterializerConfig,
    all_planned_files: Iterable[PlannedFile],
    report: MaterializationReport,
    failure_injector: Callable[[str], None] | None,
) -> MaterializationReport:
    """Publish planned files with rollback and manifest-last semantics.

    Args:
        config: Materializer paths and application settings.
        all_planned_files: Files to publish, including generic non-TOML content.
        report: Report object to update in place.
        failure_injector: Test seam invoked before each replacement, or ``None``.

    Returns:
        The updated materialization report.

    Raises:
        OSError, RuntimeError, ValueError: If publication fails after rollback.
    """
    publication = report
    all_planned_files = list(all_planned_files)
    publication.planned_files = all_planned_files
    if not config.should_apply:
        return publication
    manifest_path = _configured_manifest_path(config)
    previous_manifest = load_manifest(manifest_path)
    previous_records = _manifest_record_by_path(previous_manifest)
    _validate_full_prune_consent(config, all_planned_files, previous_records)
    backups: dict[Path, bytes | None] = {}
    initial_written = publication.written
    initial_deleted = publication.deleted
    try:
        _validate_planned_targets(all_planned_files, previous_records)
        _publish_planned_targets(
            config, all_planned_files, previous_records, publication, backups, failure_injector
        )
        _remove_stale_files(config, previous_records, all_planned_files, publication, backups)
        save_manifest(manifest_path, _build_manifest(all_planned_files), failure_injector)
    except (OSError, RuntimeError, ValueError):
        _rollback_publication(backups, publication, initial_written, initial_deleted)
        raise
    _sort_report_details(publication)
    return publication


def publish_plan(config: MaterializerConfig, *all_arguments: object, **all_keywords: object) -> MaterializationReport:
    """Publish a plan while preserving the legacy optional-argument call form.

    Args:
        config: Materializer paths and application settings.
        all_arguments: Planned files, optional report, and optional injector.
        all_keywords: ``all_planned_files``, ``report``, or ``failure_injector``.

    Returns:
        The updated materialization report.

    Raises:
        TypeError: If required data is missing or arguments are duplicated.
        OSError, RuntimeError, ValueError: If publication fails after rollback.
    """
    planned_files = all_keywords.pop("all_planned_files", None)
    report = all_keywords.pop("report", None)
    failure_injector = all_keywords.pop("failure_injector", None)
    if all_keywords or (planned_files is None and not all_arguments) or len(all_arguments) > publish_plan_max_positional_arguments:
        raise TypeError("publish_plan requires planned files and accepts at most three values")
    if planned_files is not None and all_arguments:
        raise TypeError("publish_plan received duplicate planned files")
    if planned_files is None:
        planned_files = all_arguments[0]
    if len(all_arguments) > 1:
        if report is not None:
            raise TypeError("publish_plan received duplicate report")
        report = all_arguments[1]
    if len(all_arguments) > publish_plan_failure_injector_position:
        if failure_injector is not None:
            raise TypeError("publish_plan received duplicate failure injector")
        failure_injector = all_arguments[2]
    publication = report if isinstance(report, MaterializationReport) else MaterializationReport()
    all_planned_files = _validated_planned_file_iterable(planned_files)
    if failure_injector is not None and not callable(failure_injector):
        raise TypeError("failure injector requires a callable")
    return _publish_plan(config, all_planned_files, publication, failure_injector)


def _redact_private_paths(
    message: str,
    config: MaterializerConfig | None,
    all_private_paths: Iterable[Path],
) -> str:
    redacted_message = message
    configured_paths = (
        (config.source_root, config.target_root, config.manifest_path)
        if config is not None
        else ()
    )
    for each_private_path in (*configured_paths, *all_private_paths):
        redacted_message = redacted_message.replace(str(each_private_path), "<private-path>")
    return redacted_message


def _build_report_payload(
    report: MaterializationReport,
    config: MaterializerConfig | None,
    should_apply: bool,
    all_private_paths: Iterable[Path],
) -> dict[str, object]:
    report_payload = {each_category: getattr(report, each_category) for each_category in report_categories}
    report_payload["incomplete_generation"] = report.incomplete_generation
    report_payload["reconcile_required"] = report.reconcile_required
    report_payload["error_details"] = [
        _redact_private_paths(each_message, config, all_private_paths)
        for each_message in sorted(report.error_details, key=str.casefold)
    ]
    report_payload["details"] = {
        each_category: [_redact_private_paths(each_message, config, all_private_paths) for each_message in messages]
        for each_category, messages in report.details.items()
    }
    report_payload["dry_run"] = not should_apply
    return report_payload


def create_argument_parser() -> argparse.ArgumentParser:
    """Create the command-line parser for compatibility materialization.

    Returns:
        A parser accepting source and target roots, the apply flag, and the prune opt-in.
    """
    parser = MaterializerArgumentParser(description=__doc__)
    parser.add_argument("source_root", type=Path)
    parser.add_argument("target_root", type=Path)
    parser.add_argument("--apply", dest="should_apply", action="store_true")
    parser.add_argument(full_prune_opt_in_flag, dest="should_allow_full_prune", action="store_true")
    return parser


def main(*all_arguments: object) -> int:
    """Run materialization from command-line arguments.

    Args:
        all_arguments: Optional argument list; no value uses process arguments.

    Returns:
        Zero after reporting the materialization result.

    Raises:
        TypeError: If the optional argument list has an invalid shape or type.
        MaterializerError: If the source and target configuration is unsafe.
        OSError, RuntimeError, ValueError: If discovery, planning, or publication fails.
    """
    report = MaterializationReport()
    config: MaterializerConfig | None = None
    should_apply = False
    source_root: Path | None = None
    target_root: Path | None = None
    try:
        if len(all_arguments) > 1:
            raise TypeError("main accepts at most one argument list")
        cli_arguments = all_arguments[0] if all_arguments else None
        if cli_arguments is not None and not isinstance(cli_arguments, list):
            raise TypeError("main argument must be a list of command-line strings")
        options = create_argument_parser().parse_args(cli_arguments)
        should_apply = options.should_apply
        source_root = options.source_root
        target_root = options.target_root
        if source_root is None or target_root is None:
            raise TypeError("materializer roots are required")
        config = MaterializerConfig(
            source_root,
            target_root,
            should_apply=should_apply,
            should_allow_full_prune=options.should_allow_full_prune,
        )
        discovered_agents = discover_agents(config)
        planned, report = build_plan(config, all_agents=discovered_agents)
        publish_plan(config, all_planned_files=planned, report=report, failure_injector=None)
    except (MaterializerError, OSError, RuntimeError, ValueError) as error:
        report.add_error(str(error))
    all_private_paths = tuple(
        each_path
        for each_path in (source_root, target_root)
        if each_path is not None
    )
    report_payload = _build_report_payload(report, config, should_apply, all_private_paths)
    print(json.dumps(report_payload, sort_keys=True))
    return 1 if report.errors or report.conflicted else 0


if __name__ == "__main__":
    raise SystemExit(main())
