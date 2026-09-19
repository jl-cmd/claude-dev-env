"""Build the whole-repository inventory and dependency ledger from `git ls-files`.

The walk reads blobs from the git index, so the output does not depend on the
checkout's line endings. Ship lists are read only to reconcile the `shipped`
column; they never decide which paths are inventoried.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

PACKAGE_ROOT = "packages/claude-dev-env/"
SYMLINK_MODE = "120000"
INSTRUCTION_BASENAMES = frozenset(
    {"CLAUDE.md", "AGENTS.md", "copilot-instructions.md", "BUGBOT.md"}
)
UBIQUITOUS_BASENAMES = frozenset(
    {
        "CLAUDE.md",
        "AGENTS.md",
        "SKILL.md",
        "README.md",
        "__init__.py",
        "conftest.py",
        "package.json",
        "settings.json",
        "pyproject.toml",
        ".gitignore",
        "config.py",
        "constants.py",
    }
)
EXECUTABLE_SUFFIXES = (".py", ".mjs", ".js", ".ps1", ".sh", ".cmd")
TEXT_SUFFIXES = (
    ".py",
    ".mjs",
    ".js",
    ".ts",
    ".tsx",
    ".json",
    ".md",
    ".yml",
    ".yaml",
    ".toml",
    ".ps1",
    ".sh",
    ".xml",
    ".txt",
    ".ini",
    ".cfg",
    ".html",
    ".cmd",
    ".archive",
    ".example",
    "",
)
MAXIMUM_BASENAME_CANDIDATES = 3
MINIMUM_NAME_MENTION_LENGTH = 6
INVENTORY_COLUMNS = (
    "component_id",
    "path",
    "kind",
    "proof_class",
    "shipped",
    "loaded_into_agent_context",
    "registered_in",
    "bytes",
    "lines",
    "planned_proof_method",
    "disposition",
)
DEPENDENCY_COLUMNS = ("source_id", "relation", "target_id")
REACHABILITY_RELATIONS = frozenset(
    {"imports", "invokes", "registers", "references", "projects"}
)
CODE_KINDS = frozenset(
    {"hook_module", "hook_support", "shared_module", "scripts_module", "bin_script"}
)

PROOF_CLASS_BY_KIND: dict[str, str] = {
    "rule": "OUTPUT",
    "skill": "OUTPUT",
    "agent": "OUTPUT",
    "command": "OUTPUT",
    "system_prompt": "OUTPUT",
    "instruction_file": "OUTPUT",
    "output_style": "OUTPUT",
    "audit_rubric": "OUTPUT",
    "hook_module": "SAFETY",
    "hook_support": "SAFETY",
    "git_hook": "SAFETY",
    "shared_module": "INFRASTRUCTURE",
    "bin_script": "INFRASTRUCTURE",
    "scripts_module": "INFRASTRUCTURE",
    "settings_manifest": "INFRASTRUCTURE",
    "ci_workflow": "INFRASTRUCTURE",
    "ci_support": "INFRASTRUCTURE",
    "test": "INFRASTRUCTURE",
    "root_config": "INFRASTRUCTURE",
    "symlink": "COMPATIBILITY",
    "codex_projection": "COMPATIBILITY",
    "cursor_projection": "COMPATIBILITY",
    "doc": "DOCUMENTATION",
    "audit_record": "DOCUMENTATION",
    "archive_item": "ARCHIVE",
}

PROOF_METHOD_BY_CLASS: dict[str, str] = {
    "OUTPUT": "benchmark ablation: with versus without on the representative task set",
    "SAFETY": "drive the named bad behavior with and without the item; show unique prevention",
    "COMPATIBILITY": "install into the named client and show the dependency breaks without it",
    "INFRASTRUCTURE": "remove in a disposable copy; run install, pack, and CI operations",
    "DOCUMENTATION": "confirm the described behavior is retained and the doc is not loaded",
    "ARCHIVE": "show absence from packed tarball, installed tree, and agent context",
}

CONTEXT_LOADED_KINDS = frozenset(
    {
        "rule",
        "skill",
        "agent",
        "command",
        "system_prompt",
        "instruction_file",
        "output_style",
    }
)
CONTEXT_UNKNOWN_KINDS = frozenset(
    {"hook_module", "doc", "audit_rubric", "cursor_projection", "codex_projection"}
)

MENTION_TOKEN = re.compile(
    r"[A-Za-z0-9_@.\-/\\]*[A-Za-z0-9_\-]\.[A-Za-z][A-Za-z0-9]{0,5}"
)
NAME_TOKEN = re.compile(r"[a-z0-9][a-z0-9_\-]{4,}[a-z0-9]")
PYTHON_IMPORT = re.compile(
    r"^\s*(?:from\s+([.\w]+)\s+import\s+(\([^)]*\)|[\w, ]+)|import\s+([\w., ]+))", re.MULTILINE
)
IMPORTED_NAME = re.compile(r"(?:^|[,(])\s*(\w+)")
JAVASCRIPT_IMPORT = re.compile(
    r"""(?:from\s+|import\s*\(\s*|require\(\s*|import\s+)['"](\.{1,2}/[^'"]+)['"]"""
)


@dataclass(frozen=True)
class TrackedFile:
    path: str
    mode: str
    blob_id: str
    content: bytes


@dataclass
class Component:
    component_id: str
    path: str
    kind: str
    all_files: list[TrackedFile] = field(default_factory=list)


@dataclass(frozen=True)
class ShipLists:
    package_files: tuple[str, ...]
    package_negations: tuple[str, ...]
    manifest_directories: tuple[str, ...]
    manifest_root_files: tuple[str, ...]
    content_directories: tuple[str, ...]


@dataclass(frozen=True)
class Edge:
    source_id: str
    relation: str
    target_id: str


def run_git(
    repository_root: Path, all_arguments: list[str], stdin_bytes: bytes | None = None
) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(repository_root), *all_arguments],
        input=stdin_bytes,
        capture_output=True,
        check=True,
    )
    return completed.stdout


def read_tracked_files(repository_root: Path) -> list[TrackedFile]:
    listing = run_git(repository_root, ["ls-files", "-s", "-z"]).decode("utf-8")
    all_entries: list[tuple[str, str, str]] = []
    for each_record in listing.split("\0"):
        if not each_record:
            continue
        metadata, path = each_record.split("\t", 1)
        mode, blob_id, _stage = metadata.split(" ")
        all_entries.append((path, mode, blob_id))
    request = "".join(f"{blob_id}\n" for _path, _mode, blob_id in all_entries).encode(
        "ascii"
    )
    stream = run_git(repository_root, ["cat-file", "--batch"], request)
    all_files: list[TrackedFile] = []
    cursor = 0
    for path, mode, blob_id in all_entries:
        header_end = stream.index(b"\n", cursor)
        size = int(stream[cursor:header_end].split(b" ")[2])
        body_start = header_end + 1
        all_files.append(
            TrackedFile(path, mode, blob_id, stream[body_start : body_start + size])
        )
        cursor = body_start + size + 1
    return sorted(all_files, key=lambda each_file: each_file.path)


def is_test_path(path: str) -> bool:
    basename = posixpath.basename(path)
    if basename.startswith("test_") and basename.endswith(".py"):
        return True
    if (
        basename.endswith(("_test.py", ".test.mjs", ".test.js"))
        or basename == "conftest.py"
    ):
        return True
    if basename.endswith("_test_support.py"):
        return True
    return any(
        each_marker in f"/{path}"
        for each_marker in ("/tests/", "/fixtures/", "/test_files/")
    )


def directory_group(path: str, prefix: str) -> str:
    remainder = path[len(prefix) :]
    return prefix + remainder.split("/", 1)[0]


def classify_package_path(path: str, inner: str) -> tuple[str, str]:
    basename = posixpath.basename(inner)
    if inner.startswith(".agents/skills-archived/"):
        return "archive_item", directory_group(
            path, PACKAGE_ROOT + ".agents/skills-archived/"
        )
    if inner.startswith("rules-archived/"):
        return "archive_item", path
    if basename in INSTRUCTION_BASENAMES:
        return "instruction_file", path
    if is_test_path(inner):
        return "test", path
    if inner.startswith(".agents/skills/_shared/"):
        return "shared_module", path
    if inner.startswith(".agents/skills/"):
        return "skill", directory_group(path, PACKAGE_ROOT + ".agents/skills/")
    if inner.startswith(".agents/agents/"):
        return "agent", path
    if inner == "hooks/hooks.json":
        return "settings_manifest", path
    if inner.startswith("hooks/git-hooks/"):
        return "git_hook", path
    if inner.startswith("hooks/"):
        is_entry_module = (
            inner.endswith(EXECUTABLE_SUFFIXES)
            and "/hooks_constants/" not in f"/{inner}"
        )
        return ("hook_module" if is_entry_module else "hook_support"), path
    for each_prefix, each_kind in (
        ("rules/", "rule"),
        ("commands/", "command"),
        ("system-prompts/", "system_prompt"),
        ("output-styles/", "output_style"),
        ("audit-rubrics/", "audit_rubric"),
        ("docs/", "doc"),
        ("_shared/", "shared_module"),
        ("bin/", "bin_script"),
        ("scripts/sync_to_cursor/", "cursor_projection"),
        ("scripts/", "scripts_module"),
    ):
        if inner.startswith(each_prefix):
            return each_kind, path
    if basename.startswith("codex-") or inner.startswith("codex-rules/"):
        return "codex_projection", path
    if basename == "CHANGELOG.md":
        return "doc", path
    if basename.endswith((".json", ".toml")):
        return "settings_manifest", path
    return "root_config", path


def classify_path(tracked_file: TrackedFile) -> tuple[str, str]:
    path = tracked_file.path
    basename = posixpath.basename(path)
    if tracked_file.mode == SYMLINK_MODE:
        return "symlink", path
    if path.startswith("skill-archive/"):
        has_directory = "/" in path[len("skill-archive/") :]
        return "archive_item", (
            directory_group(path, "skill-archive/") if has_directory else path
        )
    if path.startswith("docs/records/"):
        has_directory = "/" in path[len("docs/records/") :]
        return "archive_item", (
            directory_group(path, "docs/records/") if has_directory else path
        )
    if basename.endswith(".archive"):
        return "archive_item", path
    if path.startswith(".audit/"):
        return "audit_record", directory_group(path, ".audit/")
    if path.startswith(PACKAGE_ROOT):
        return classify_package_path(path, path[len(PACKAGE_ROOT) :])
    if basename in INSTRUCTION_BASENAMES:
        return "instruction_file", path
    if is_test_path(path):
        return "test", path
    if path.startswith(".cursor/skills/") and "/" in path[len(".cursor/skills/") :]:
        return "cursor_projection", directory_group(path, ".cursor/skills/")
    if path.startswith(".cursor") or path == ".cursorignore":
        return "cursor_projection", path
    if path.startswith(".github/workflows/"):
        return "ci_workflow", path
    if path.startswith(".github/"):
        return "ci_support", path
    if path.startswith(".claude/hooks/"):
        return (
            "hook_module" if path.endswith(EXECUTABLE_SUFFIXES) else "hook_support"
        ), path
    if path.startswith((".claude-plugin/", ".claude/")) or basename in {
        "package.json",
        "release-please-config.json",
        ".release-please-manifest.json",
    }:
        return "settings_manifest", path
    if path.startswith("docs/") or basename in {"README.md", "LICENSE"}:
        return "doc", path
    if path.startswith("config/"):
        return "ci_support", path
    return "root_config", path


def build_components(all_files: list[TrackedFile]) -> dict[str, Component]:
    component_by_id: dict[str, Component] = {}
    for each_file in all_files:
        kind, component_path = classify_path(each_file)
        component_id = f"{kind}:{component_path}"
        if component_id not in component_by_id:
            component_by_id[component_id] = Component(
                component_id, component_path, kind
            )
        component_by_id[component_id].all_files.append(each_file)
    return component_by_id


def decode_text(tracked_file: TrackedFile) -> str:
    suffix = posixpath.splitext(tracked_file.path)[1].lower()
    if suffix not in TEXT_SUFFIXES or b"\0" in tracked_file.content[:4096]:
        return ""
    return tracked_file.content.decode("utf-8", errors="replace")


def find_tracked_json(all_files: list[TrackedFile], path: str) -> dict[str, object]:
    for each_file in all_files:
        if each_file.path == path:
            parsed = json.loads(each_file.content.decode("utf-8"))
            return parsed if isinstance(parsed, dict) else {}
    return {}


def string_items(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(each_item for each_item in value if isinstance(each_item, str))


def read_ship_lists(all_files: list[TrackedFile]) -> ShipLists:
    package = find_tracked_json(all_files, PACKAGE_ROOT + "package.json")
    manifest = find_tracked_json(
        all_files, PACKAGE_ROOT + "installable-surfaces.manifest.json"
    )
    all_package_entries = string_items(package.get("files"))
    installer_text = ""
    for each_file in all_files:
        if each_file.path == PACKAGE_ROOT + "bin/install.mjs":
            installer_text = decode_text(each_file)
    declaration = re.search(r"CONTENT_DIRECTORIES\s*=\s*\[([^\]]*)\]", installer_text)
    all_content_directories = (
        tuple(re.findall(r"['\"]([^'\"]+)['\"]", declaration.group(1)))
        if declaration
        else ()
    )
    return ShipLists(
        package_files=tuple(
            each_entry
            for each_entry in all_package_entries
            if not each_entry.startswith("!")
        ),
        package_negations=tuple(
            each_entry[1:]
            for each_entry in all_package_entries
            if each_entry.startswith("!")
        ),
        manifest_directories=string_items(manifest.get("directories")),
        manifest_root_files=string_items(manifest.get("root_files")),
        content_directories=all_content_directories,
    )


def matches_ship_entry(inner_path: str, all_entries: tuple[str, ...]) -> bool:
    for each_entry in all_entries:
        directory = each_entry.rstrip("/") + "/"
        if inner_path == each_entry.rstrip("/") or inner_path.startswith(directory):
            return True
    return False


def shipped_status(component: Component, ship_lists: ShipLists) -> str:
    if not ship_lists.package_files:
        return "unknown"
    if not component.path.startswith(PACKAGE_ROOT):
        return "no"
    all_inner_paths = [
        each_file.path[len(PACKAGE_ROOT) :] for each_file in component.all_files
    ]
    all_verdicts = {
        matches_ship_entry(each_inner, ship_lists.package_files)
        for each_inner in all_inner_paths
    }
    if all_verdicts == {True}:
        return "yes"
    return "no" if all_verdicts == {False} else "unknown"


def context_status(component: Component, shipped: str) -> str:
    if component.kind in CONTEXT_LOADED_KINDS:
        if component.kind == "instruction_file" or shipped == "yes":
            return "yes"
        return "unknown"
    if component.kind in CONTEXT_UNKNOWN_KINDS:
        return "unknown"
    return "no"


class MentionIndex:
    """Resolve a path-like token to the components whose files it names."""

    def __init__(self, component_by_id: dict[str, Component]) -> None:
        self.component_id_by_path: dict[str, str] = {}
        self.all_paths_by_basename: dict[str, list[str]] = defaultdict(list)
        self.component_id_by_name: dict[str, str] = {}
        for each_component in component_by_id.values():
            for each_file in each_component.all_files:
                self.component_id_by_path[each_file.path] = each_component.component_id
                self.all_paths_by_basename[posixpath.basename(each_file.path)].append(
                    each_file.path
                )
            if each_component.kind in {"skill", "agent", "command"}:
                name = posixpath.splitext(posixpath.basename(each_component.path))[0]
                if len(name) >= MINIMUM_NAME_MENTION_LENGTH and "-" in name:
                    self.component_id_by_name[name] = each_component.component_id

    def resolve_token(self, token: str, source_directory: str) -> set[str]:
        normalized = token.replace("\\", "/").lstrip("@").lstrip("/")
        while normalized.startswith(("./", "~/")):
            normalized = normalized[2:]
        basename = posixpath.basename(normalized)
        all_candidates = self.all_paths_by_basename.get(basename)
        if not all_candidates:
            return set()
        if normalized.startswith("../") or "/" not in normalized:
            relative = posixpath.normpath(posixpath.join(source_directory, normalized))
            if relative in self.component_id_by_path:
                return {self.component_id_by_path[relative]}
        stripped = normalized
        while stripped.startswith("../"):
            stripped = stripped[3:]
        if "/" in stripped:
            all_suffix_matches = [
                each_path
                for each_path in all_candidates
                if f"/{each_path}".endswith(f"/{stripped}")
            ]
            if all_suffix_matches:
                return {
                    self.component_id_by_path[each_path]
                    for each_path in all_suffix_matches
                }
        if (
            basename in UBIQUITOUS_BASENAMES
            or len(all_candidates) > MAXIMUM_BASENAME_CANDIDATES
        ):
            return set()
        return {self.component_id_by_path[each_path] for each_path in all_candidates}


def resolve_python_module(
    module: str, source_path: str, index: MentionIndex
) -> set[str]:
    all_parts = [each_part for each_part in module.split(".") if each_part]
    if not all_parts:
        return set()
    all_found: set[str] = set()
    for each_tail in (
        "/".join(all_parts) + ".py",
        "/".join(all_parts) + "/__init__.py",
    ):
        basename = posixpath.basename(each_tail)
        all_matches = [
            each_path
            for each_path in index.all_paths_by_basename.get(basename, [])
            if f"/{each_path}".endswith(f"/{each_tail}")
        ]
        source_directory = posixpath.dirname(source_path)
        all_nearby = [
            each_path
            for each_path in all_matches
            if posixpath.dirname(each_path).startswith(source_directory)
        ]
        for each_path in all_nearby or all_matches:
            all_found.add(index.component_id_by_path[each_path])
    return all_found


def python_import_targets(text: str, source_path: str, index: MentionIndex) -> set[str]:
    all_targets: set[str] = set()
    for each_match in PYTHON_IMPORT.finditer(text):
        from_module, imported_names, plain_modules = each_match.groups()
        if from_module:
            all_targets |= resolve_python_module(from_module, source_path, index)
            for each_name in IMPORTED_NAME.findall(imported_names or ""):
                all_targets |= resolve_python_module(
                    f"{from_module}.{each_name}", source_path, index
                )
        for each_module in (plain_modules or "").split(","):
            all_targets |= resolve_python_module(
                each_module.strip().split(" ")[0], source_path, index
            )
    return all_targets


def javascript_import_targets(
    text: str, source_path: str, index: MentionIndex
) -> set[str]:
    all_targets: set[str] = set()
    for each_specifier in JAVASCRIPT_IMPORT.findall(text):
        resolved = posixpath.normpath(
            posixpath.join(posixpath.dirname(source_path), each_specifier)
        )
        for each_candidate in (
            resolved,
            resolved + ".mjs",
            resolved + ".js",
            resolved + "/index.mjs",
        ):
            if each_candidate in index.component_id_by_path:
                all_targets.add(index.component_id_by_path[each_candidate])
    return all_targets


def is_registry(component: Component) -> bool:
    return component.kind == "settings_manifest" or component.path.endswith(
        "ever-shipped-skills.mjs"
    )


def mention_relation(source: Component, source_path: str, target: Component) -> str:
    if is_registry(source):
        return "registers"
    if source.kind in {"codex_projection", "cursor_projection"}:
        return "projects"
    target_is_executable = target.path.endswith(EXECUTABLE_SUFFIXES)
    if target_is_executable and source_path.endswith(
        (".md", ".yml", ".yaml", ".sh", ".ps1", ".cmd", ".xml")
    ):
        return "invokes"
    return "references"


def test_subject_stems(test_path: str) -> list[str]:
    basename = posixpath.basename(test_path)
    for each_suffix in (".test.mjs", ".test.js", "_test.py"):
        if basename.endswith(each_suffix):
            return [basename[: -len(each_suffix)]]
    if basename.startswith("test_") and basename.endswith(".py"):
        return [basename[len("test_") : -len(".py")]]
    return []


def naming_subjects(test_path: str, index: MentionIndex) -> set[str]:
    all_subjects: set[str] = set()
    for each_stem in test_subject_stems(test_path):
        all_words = each_stem.split("_")
        for each_length in range(len(all_words), 0, -1):
            prefix = "_".join(all_words[:each_length])
            for each_extension in (".py", ".mjs", ".js", ".md", ".json", ".ps1", ".sh"):
                for each_path in index.all_paths_by_basename.get(
                    prefix + each_extension, []
                ):
                    if not is_test_path(each_path):
                        all_subjects.add(index.component_id_by_path[each_path])
            if all_subjects:
                return all_subjects
    return all_subjects


def build_edges(
    component_by_id: dict[str, Component], ship_lists: ShipLists
) -> set[Edge]:
    index = MentionIndex(component_by_id)
    all_edges: set[Edge] = set()
    for each_component in component_by_id.values():
        source_id = each_component.component_id
        for each_file in each_component.all_files:
            text = decode_text(each_file)
            if each_file.mode == SYMLINK_MODE:
                target_directory = posixpath.normpath(
                    posixpath.join(posixpath.dirname(each_file.path), text.strip())
                )
                for each_path, each_target_id in index.component_id_by_path.items():
                    if each_path.startswith(target_directory + "/"):
                        all_edges.add(Edge(source_id, "projects", each_target_id))
                continue
            if not text:
                continue
            all_import_targets: set[str] = set()
            if each_file.path.endswith(".py"):
                all_import_targets = python_import_targets(text, each_file.path, index)
            elif each_file.path.endswith((".mjs", ".js", ".ts")):
                all_import_targets = javascript_import_targets(
                    text, each_file.path, index
                )
            for each_target_id in all_import_targets:
                all_edges.add(Edge(source_id, "imports", each_target_id))
            source_directory = posixpath.dirname(each_file.path)
            for each_token in set(MENTION_TOKEN.findall(text)):
                for each_target_id in index.resolve_token(each_token, source_directory):
                    if each_target_id in all_import_targets:
                        continue
                    relation = mention_relation(
                        each_component, each_file.path, component_by_id[each_target_id]
                    )
                    all_edges.add(Edge(source_id, relation, each_target_id))
            for each_name in (
                set(NAME_TOKEN.findall(text)) & index.component_id_by_name.keys()
            ):
                target = component_by_id[index.component_id_by_name[each_name]]
                all_edges.add(
                    Edge(
                        source_id,
                        mention_relation(each_component, each_file.path, target),
                        target.component_id,
                    )
                )
            if each_component.kind == "test":
                for each_subject_id in naming_subjects(each_file.path, index):
                    all_edges.add(Edge(source_id, "tests", each_subject_id))
    installer_id = index.component_id_by_path.get(PACKAGE_ROOT + "bin/install.mjs")
    if installer_id:
        for each_component in component_by_id.values():
            inner = each_component.path[len(PACKAGE_ROOT) :]
            if each_component.path.startswith(PACKAGE_ROOT) and matches_ship_entry(
                inner, ship_lists.content_directories
            ):
                all_edges.add(
                    Edge(installer_id, "installs", each_component.component_id)
                )
    return {
        each_edge
        for each_edge in all_edges
        if each_edge.source_id != each_edge.target_id
    }


def count_lines(component: Component) -> int:
    return sum(
        each_file.content.count(b"\n")
        + (1 if each_file.content and not each_file.content.endswith(b"\n") else 0)
        for each_file in component.all_files
    )


def inventory_rows(
    component_by_id: dict[str, Component], all_edges: set[Edge], ship_lists: ShipLists
) -> list[tuple[str, ...]]:
    all_registrars: dict[str, set[str]] = defaultdict(set)
    for each_edge in all_edges:
        if each_edge.relation == "registers":
            all_registrars[each_edge.target_id].add(
                component_by_id[each_edge.source_id].path
            )
    all_rows: list[tuple[str, ...]] = []
    for each_id in sorted(component_by_id):
        component = component_by_id[each_id]
        proof_class = PROOF_CLASS_BY_KIND[component.kind]
        shipped = shipped_status(component, ship_lists)
        registered_in = ";".join(sorted(all_registrars[each_id]))
        if component.kind == "symlink":
            registered_in = (
                "symlink->" + component.all_files[0].content.decode("utf-8").strip()
            )
        all_rows.append(
            (
                each_id,
                component.path,
                component.kind,
                proof_class,
                shipped,
                context_status(component, shipped),
                registered_in,
                str(sum(len(each_file.content) for each_file in component.all_files)),
                str(count_lines(component)),
                PROOF_METHOD_BY_CLASS[proof_class],
                "",
            )
        )
    return all_rows


def is_live_source(component: Component) -> bool:
    return (
        component.kind not in {"test", "archive_item", "audit_record"}
        and "CHANGELOG" not in component.path
    )


def removal_flags(
    component_by_id: dict[str, Component], all_edges: set[Edge], ship_lists: ShipLists
) -> list[tuple[str, str, str]]:
    all_live_inbound: dict[str, set[str]] = defaultdict(set)
    all_registered: set[str] = set()
    all_outbound: dict[str, set[str]] = defaultdict(set)
    for each_edge in all_edges:
        all_outbound[each_edge.source_id].add(each_edge.target_id)
        if each_edge.relation in REACHABILITY_RELATIONS and is_live_source(
            component_by_id[each_edge.source_id]
        ):
            all_live_inbound[each_edge.target_id].add(each_edge.source_id)
            if each_edge.relation == "registers":
                all_registered.add(each_edge.target_id)
    all_flags: list[tuple[str, str, str]] = []
    all_ids_by_blob: dict[str, list[str]] = defaultdict(list)
    for each_id, each_component in component_by_id.items():
        shipped = shipped_status(each_component, ship_lists)
        if (
            each_component.kind in CODE_KINDS
            and each_component.path.endswith(EXECUTABLE_SUFFIXES)
            and not all_live_inbound[each_id]
            and "__init__" not in each_id
        ):
            all_flags.append(
                (
                    "unreachable_module",
                    each_id,
                    f"no inbound live edge; registered=no; shipped={shipped}",
                )
            )
        if (
            each_component.kind == "hook_module"
            and each_id not in all_registered
            and "__init__" not in each_id
        ):
            all_importers = ",".join(sorted(all_live_inbound[each_id])[:3]) or "none"
            all_flags.append(
                (
                    "hook_unregistered",
                    each_id,
                    f"no hooks.json or settings registration; live inbound: {all_importers}",
                )
            )
        if each_component.kind == "archive_item" and shipped != "no":
            all_flags.append(
                (
                    "archive_in_shipped_path",
                    each_id,
                    f"shipped={shipped} through package.json files",
                )
            )
        if each_component.kind == "test" and test_subject_stems(each_component.path):
            all_live_targets = [
                each_target
                for each_target in all_outbound[each_id]
                if component_by_id[each_target].kind != "test"
            ]
            if not all_live_targets:
                all_flags.append(
                    (
                        "test_subject_gone",
                        each_id,
                        "no named subject, import, or mention resolves to a tracked non-test file",
                    )
                )
        for each_file in each_component.all_files:
            if each_file.content.strip():
                all_ids_by_blob[hashlib.sha256(each_file.content).hexdigest()].append(
                    each_file.path
                )
    for each_digest, all_paths in all_ids_by_blob.items():
        if len(all_paths) > 1:
            all_flags.append(
                (
                    "exact_duplicate",
                    all_paths[0],
                    f"sha256 {each_digest[:12]} x{len(all_paths)}: "
                    + ";".join(all_paths[1:6]),
                )
            )
    return sorted(all_flags)


def ship_list_mismatches(
    ship_lists: ShipLists, all_files: list[TrackedFile]
) -> list[str]:
    all_package_entries = {
        each_entry.rstrip("/") for each_entry in ship_lists.package_files
    }
    all_manifest_entries = set(ship_lists.manifest_directories) | set(
        ship_lists.manifest_root_files
    )
    all_inner_paths = [
        each_file.path[len(PACKAGE_ROOT) :]
        for each_file in all_files
        if each_file.path.startswith(PACKAGE_ROOT)
    ]
    all_mismatches: list[str] = []
    for each_entry in sorted(all_package_entries - all_manifest_entries):
        all_mismatches.append(
            f"package.json files lists '{each_entry}'; installable-surfaces manifest does not"
        )
    for each_entry in sorted(all_manifest_entries - all_package_entries):
        all_mismatches.append(
            f"installable-surfaces manifest lists '{each_entry}'; package.json files does not"
        )
    for each_entry in sorted(
        all_package_entries | all_manifest_entries | set(ship_lists.content_directories)
    ):
        if not matches_ship_entry(each_entry, tuple(all_inner_paths)) and not any(
            each_inner == each_entry or each_inner.startswith(each_entry + "/")
            for each_inner in all_inner_paths
        ):
            all_mismatches.append(
                f"ship list names '{each_entry}'; no tracked file sits under it"
            )
    for each_top in sorted(
        {each_inner.split("/", 1)[0] for each_inner in all_inner_paths}
    ):
        if not matches_ship_entry(each_top, tuple(all_package_entries)) and not any(
            each_entry.startswith(each_top + "/") for each_entry in all_package_entries
        ):
            all_mismatches.append(
                f"tracked top-level '{each_top}' is outside package.json files"
            )
    return all_mismatches


def render_table(
    all_columns: tuple[str, ...], all_rows: list[tuple[str, ...]]
) -> bytes:
    all_lines = ["\t".join(all_columns)] + [
        "\t".join(each_row) for each_row in all_rows
    ]
    return ("\n".join(all_lines) + "\n").encode("utf-8")


def build(repository_root: Path, output_directory: Path) -> list[str]:
    all_files = read_tracked_files(repository_root)
    component_by_id = build_components(all_files)
    ship_lists = read_ship_lists(all_files)
    all_edges = build_edges(component_by_id, ship_lists)
    all_mapped_paths = [
        each_file.path
        for each_component in component_by_id.values()
        for each_file in each_component.all_files
    ]
    if sorted(all_mapped_paths) != [each_file.path for each_file in all_files]:
        raise SystemExit("coverage fault: tracked paths and component files differ")
    output_directory.mkdir(parents=True, exist_ok=True)
    (output_directory / "inventory.tsv").write_bytes(
        render_table(
            INVENTORY_COLUMNS, inventory_rows(component_by_id, all_edges, ship_lists)
        )
    )
    all_edge_rows = sorted(
        (each_edge.source_id, each_edge.relation, each_edge.target_id)
        for each_edge in all_edges
    )
    (output_directory / "dependencies.tsv").write_bytes(
        render_table(DEPENDENCY_COLUMNS, all_edge_rows)
    )
    all_report_lines = [
        f"files\t{len(all_files)}",
        f"components\t{len(component_by_id)}",
        f"edges\t{len(all_edges)}",
    ]
    all_report_lines += [
        f"mismatch\t{each_line}"
        for each_line in ship_list_mismatches(ship_lists, all_files)
    ]
    all_report_lines += [
        "\t".join(each_flag)
        for each_flag in removal_flags(component_by_id, all_edges, ship_lists)
    ]
    return all_report_lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    default_root = Path(__file__).resolve().parents[2]
    parser.add_argument("--repository-root", type=Path, default=default_root)
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path(__file__).resolve().parent / "data",
    )
    arguments = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    for each_line in build(arguments.repository_root, arguments.output_directory):
        print(each_line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
