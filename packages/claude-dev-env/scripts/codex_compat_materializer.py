"""Deterministic, additive Claude-agent to Codex-agent materialization."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import stat
import tempfile
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable


ManagedContent = str | bytes

path_separator = "/"
toml_suffix = ".toml"
reparse_point_attribute_name = "FILE_ATTRIBUTE_REPARSE_POINT"
manifest_indentation_width = 2
publish_plan_max_positional_arguments = 3
publish_plan_failure_injector_position = 2
frontmatter_required_fields = ("name", "description")
frontmatter_unsupported_fields = ("tools", "model", "color")


class MaterializerError(ValueError):
    """Raised when a materialization request cannot be safely planned."""


class ArgumentParserError(ValueError):
    """Raised when command-line arguments cannot be parsed."""


class MaterializerArgumentParser(argparse.ArgumentParser):
    """Parse materializer arguments while keeping errors in the JSON contract."""

    def error(self, message: str) -> None:
        """Raise a reportable parser error instead of writing process output."""
        raise ArgumentParserError(message)


report_categories = (
    "written", "unchanged", "unmanaged_collision", "modified_managed",
    "stale_managed", "deleted", "unsupported", "conflicted", "errors",
)
report_categories_public_name = "REPORT_CATEGORIES"
frontmatter_allowed_fields = {"name", "description", "tools", "model", "color"}
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


def _parse_frontmatter_scalar(serialized_field_text: str) -> str | tuple[str, ...] | None:
    normalized_field_text = serialized_field_text.strip()
    if not normalized_field_text:
        return ""
    if normalized_field_text.startswith("["):
        return _parse_frontmatter_list(normalized_field_text)
    try:
        parsed = ast.literal_eval(normalized_field_text)
    except (SyntaxError, ValueError):
        if normalized_field_text[:1] in {'"', "'"} or normalized_field_text[:1] == "[":
            raise MaterializerError("malformed frontmatter value")
        return normalized_field_text
    if isinstance(parsed, str):
        return parsed
    if isinstance(parsed, list) and all(isinstance(each_entry, str) for each_entry in parsed):
        return tuple(parsed)
    raise MaterializerError("frontmatter value must be a string or string list")


def _parse_frontmatter_list(serialized_list: str) -> tuple[str, ...]:
    if not serialized_list.endswith("]"):
        raise MaterializerError("malformed frontmatter value")
    all_entries: list[str] = []
    entry_start = 1
    quote: str | None = None
    has_escape_pending = False
    for each_index, each_character in enumerate(serialized_list[1:-1], 1):
        if has_escape_pending:
            has_escape_pending = False
            continue
        if quote == '"' and each_character == "\\":
            has_escape_pending = True
            continue
        if each_character in {'"', "'"}:
            if quote is None:
                quote = each_character
            elif quote == each_character:
                quote = None
            continue
        if each_character == "," and quote is None:
            all_entries.append(_parse_frontmatter_list_entry(serialized_list[entry_start:each_index]))
            entry_start = each_index + 1
    if quote is not None or has_escape_pending:
        raise MaterializerError("malformed frontmatter value")
    all_entries.append(_parse_frontmatter_list_entry(serialized_list[entry_start:-1]))
    return tuple(all_entries) if all_entries != [""] else ()


def _parse_frontmatter_list_entry(raw_entry: str) -> str:
    entry = raw_entry.strip()
    if not entry:
        raise MaterializerError("malformed frontmatter value")
    try:
        parsed = ast.literal_eval(entry)
    except (SyntaxError, ValueError):
        if entry[0] in {'"', "'"}:
            raise MaterializerError("malformed frontmatter value")
        if any(character in entry for character in "[]{}:"):
            raise MaterializerError("malformed frontmatter value")
        return entry
    if not isinstance(parsed, str):
        raise MaterializerError("frontmatter list entries must be strings")
    return parsed


def parse_frontmatter(source_path: Path, source_text: str, relative_source: str) -> ClaudeAgent:
    """Parse one Claude agent's frontmatter.

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
    delimiters = [each_index for each_index, line in enumerate(lines[1:], 1) if line.strip() == "---"]
    if len(delimiters) != 1:
        raise MaterializerError(f"malformed frontmatter delimiters: {source_path}")
    all_fields: dict[str, str | tuple[str, ...] | None] = {}
    for each_line in lines[1 : delimiters[0]]:
        if not each_line.strip() or ":" not in each_line:
            raise MaterializerError(f"malformed frontmatter: {source_path}")
        key, serialized_field_text = each_line.split(":", 1)
        key = key.strip()
        if key in all_fields or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", key):
            raise MaterializerError(f"malformed frontmatter key: {source_path}")
        all_fields[key] = _parse_frontmatter_scalar(serialized_field_text)
    unknown = tuple(sorted(each_key for each_key in all_fields if each_key not in frontmatter_allowed_fields))
    if unknown:
        raise MaterializerError(f"unknown frontmatter keys: {source_path}")
    unsupported = tuple(sorted(each_key for each_key in all_fields if each_key in frontmatter_unsupported_fields))
    if any(not isinstance(all_fields.get(each_key), str) or not all_fields[each_key] for each_key in frontmatter_required_fields):
        raise MaterializerError(f"name and description are required: {source_path}")
    tools = all_fields.get("tools", ())
    if isinstance(tools, str):
        tools = (tools,)
    if not isinstance(tools, tuple):
        raise MaterializerError(f"tools must be a list: {source_path}")
    return ClaudeAgent(source_path, source_identity, all_fields["name"], all_fields["description"], tools, all_fields.get("model"), all_fields.get("color"), unsupported)


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


def discover_agents(config: MaterializerConfig) -> list[ClaudeAgent]:
    """Discover and parse Markdown agents below the source root.

    Args:
        config: Materializer paths and application settings.

    Returns:
        Agents discovered in deterministic relative-path order.

    Raises:
        MaterializerError: If a source path is unsafe or malformed.
    """
    if not config.source_root.exists() or _is_reparse_point(config.source_root):
        return []
    all_agents: list[ClaudeAgent] = []
    for each_path in sorted(config.source_root.rglob("*.md"), key=lambda path: path.as_posix().casefold()):
        if _is_reparse_point(each_path):
            raise MaterializerError(f"source reparse point is not allowed: {each_path}")
        relative_source = each_path.relative_to(config.source_root).as_posix()
        _validate_containment(config.source_root, each_path)
        all_agents.append(parse_frontmatter(each_path, each_path.read_text(encoding="utf-8"), relative_source))
    return all_agents


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
    previous_records = _manifest_record_by_path(load_manifest(config.manifest_path))
    existing_by_name = {
        each_path.relative_to(config.target_root).as_posix().casefold(): each_path
        for each_path in config.target_root.rglob("*")
        if not _is_known_managed_path(config.target_root, each_path, previous_records)
    } if config.target_root.exists() else {}
    for each_agent in list(all_agents):
        source_identity = _validate_source_identity(each_agent.relative_source)
        target_relative_path = _normalize_relative_path(each_agent.name + toml_suffix)
        folded_path = target_relative_path.casefold()
        if folded_path in target_by_name or folded_path in existing_by_name:
            raise MaterializerError(f"case-fold collision: {target_relative_path}")
        target_by_name[folded_path] = target_relative_path
        content = convert_agent(each_agent)
        target_path = validate_target_path(config.target_root, target_relative_path)
        if _casefold_normalized_path(target_path) == _casefold_normalized_path(config.manifest_path):
            raise MaterializerError("planned target collides with compatibility manifest")
        planned.append(PlannedFile(source_identity, target_relative_path, content, hash_content(content)))
        report.unsupported += len(each_agent.unsupported)
        report.details["unsupported"].extend(f"{source_identity}:{each_key}" for each_key in each_agent.unsupported)
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
    discovered_agents = discover_agents(config) if supplied_agents is None else supplied_agents
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


def _manifest_record_by_path(all_previous_manifest: dict[str, object]) -> dict[str, object]:
    records = all_previous_manifest["files"]
    if not isinstance(records, dict):
        raise MaterializerError("invalid compatibility manifest files")
    return records


def _is_known_managed_path(target_root: Path, target_path: Path, all_previous_records: dict[str, object]) -> bool:
    relative_path = target_path.relative_to(target_root).as_posix()
    for each_manifest_path, each_record in all_previous_records.items():
        if not isinstance(each_manifest_path, str) or each_manifest_path.casefold() != relative_path.casefold() or not isinstance(each_record, dict):
            continue
        expected_hash = each_record.get("hash")
        ownership = each_record.get("ownership")
        if not isinstance(expected_hash, str) or not isinstance(ownership, str):
            return False
        return isinstance(expected_hash, str)
    return False


def _record_target_state(config: MaterializerConfig, planned_file: PlannedFile, all_previous_records: dict[str, object], report: MaterializationReport) -> tuple[Path, bytes | None]:
    target_path = validate_target_path(config.target_root, planned_file.target_relative_path)
    previous_record = next((each_record for each_path, each_record in all_previous_records.items() if isinstance(each_path, str) and each_path.casefold() == planned_file.target_relative_path.casefold()), None)
    if not target_path.exists():
        return target_path, None
    current_bytes = target_path.read_bytes()
    expected_hash = previous_record.get("hash") if isinstance(previous_record, dict) else None
    if current_bytes == content_to_bytes(planned_file.content):
        report.unchanged += 1
        report.add_detail("unchanged", planned_file.target_relative_path)
    elif isinstance(expected_hash, str) and isinstance(previous_record, dict) and isinstance(previous_record.get("ownership"), str) and hash_content(current_bytes) == expected_hash:
        report.modified_managed += 1
        report.add_detail("modified_managed", planned_file.target_relative_path)
        report.conflicted += 1
        report.add_detail("conflicted", planned_file.target_relative_path)
    else:
        report.unmanaged_collision += 1
        report.add_detail("unmanaged_collision", planned_file.target_relative_path)
        report.conflicted += 1
        report.add_detail("conflicted", planned_file.target_relative_path)
    return target_path, current_bytes


def _remove_stale_files(config: MaterializerConfig, all_previous_records: dict[str, object], all_planned_files: list[PlannedFile], report: MaterializationReport, all_backups: dict[Path, bytes | None]) -> None:
    current_names = {each_planned_file.target_relative_path.casefold() for each_planned_file in all_planned_files}
    for each_relative_path, each_record in sorted(all_previous_records.items(), key=lambda pair: pair[0].casefold()):
        if not isinstance(each_relative_path, str) or each_relative_path.casefold() in current_names or not isinstance(each_record, dict):
            continue
        target_path = validate_target_path(config.target_root, each_relative_path)
        if not target_path.exists():
            report.add_error(f"missing managed path: {each_relative_path}")
            continue
        current_bytes = target_path.read_bytes()
        expected_hash = each_record.get("hash")
        if isinstance(expected_hash, str) and hash_content(current_bytes) == expected_hash:
            all_backups[target_path] = current_bytes
            target_path.unlink()
            report.deleted += 1
            report.add_detail("deleted", each_relative_path)
            continue
        if isinstance(expected_hash, str):
            report.modified_managed += 1
            report.add_detail("modified_managed", each_relative_path)


def _sort_report_details(report: MaterializationReport) -> None:
    for each_category in report_categories:
        if each_category == "errors":
            continue
        report.details[each_category].sort(key=str.casefold)


def _validate_planned_targets(
    all_planned_files: list[PlannedFile],
    all_previous_records: dict[str, object],
) -> None:
    folded_manifest_names = {each_key.casefold() for each_key in all_previous_records if isinstance(each_key, str)}
    if len(folded_manifest_names) != len(all_previous_records):
        raise MaterializerError("case-fold collision in compatibility manifest")
    planned_names: set[str] = set()
    for each_file in all_planned_files:
        folded_target = each_file.target_relative_path.casefold()
        if folded_target in planned_names:
            raise MaterializerError(f"case-fold collision: {each_file.target_relative_path}")
        planned_names.add(folded_target)
        has_manifest_owner = any(
            isinstance(each_path, str)
            and each_path.casefold() == folded_target
            and isinstance(each_record, dict)
            and isinstance(each_record.get("ownership"), str)
            for each_path, each_record in all_previous_records.items()
        )
        if folded_target in folded_manifest_names and not has_manifest_owner:
            raise MaterializerError("case-fold collision in compatibility manifest")


def _publish_planned_targets(
    config: MaterializerConfig,
    all_planned_files: list[PlannedFile],
    all_previous_records: dict[str, object],
    report: MaterializationReport,
    all_backups: dict[Path, bytes | None],
    failure_injector: Callable[[str], None] | None,
) -> None:
    for each_planned_file in all_planned_files:
        target_path, current_bytes = _record_target_state(config, each_planned_file, all_previous_records, report)
        if _casefold_normalized_path(target_path) == _casefold_normalized_path(config.manifest_path):
            raise MaterializerError("planned target collides with compatibility manifest")
        if current_bytes is not None:
            continue
        all_backups[target_path] = None
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
    previous_manifest = load_manifest(config.manifest_path)
    previous_records = _manifest_record_by_path(previous_manifest)
    backups: dict[Path, bytes | None] = {}
    initial_written = publication.written
    initial_deleted = publication.deleted
    try:
        _validate_planned_targets(all_planned_files, previous_records)
        _publish_planned_targets(
            config, all_planned_files, previous_records, publication, backups, failure_injector
        )
        _remove_stale_files(config, previous_records, all_planned_files, publication, backups)
        save_manifest(config.manifest_path, _build_manifest(all_planned_files), failure_injector)
    except (OSError, RuntimeError, ValueError) as error:
        _rollback_publication(backups, publication, initial_written, initial_deleted)
        raise error
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
    return _publish_plan(config, planned_files, publication, failure_injector)


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
        A parser accepting source and target roots plus the apply flag.
    """
    parser = MaterializerArgumentParser(description=__doc__)
    parser.add_argument("source_root", type=Path)
    parser.add_argument("target_root", type=Path)
    parser.add_argument("--apply", dest="should_apply", action="store_true")
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
        config = MaterializerConfig(source_root, target_root, should_apply=should_apply)
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
