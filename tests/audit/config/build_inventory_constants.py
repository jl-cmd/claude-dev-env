"""Named constants for the repository inventory and dependency ledger build."""

from __future__ import annotations

import re

PACKAGE_ROOT = "packages/claude-dev-env/"
SYMLINK_MODE = "120000"

PATH_SEPARATOR = "/"
WORD_SEPARATOR = "_"
COLUMN_SEPARATOR = "\t"
LINE_SEPARATOR = "\n"
SUMMARY_LIST_SEPARATOR = ";"
FLAG_DETAIL_SEPARATOR = ","
FIELD_SEPARATOR = " "
NUL_SEPARATOR = "\0"
NUL_BYTE = b"\0"
NEWLINE_BYTE = b"\n"
SPACE_BYTE = b" "
UTF8_ENCODING = "utf-8"
ASCII_ENCODING = "ascii"
DECODE_ERROR_POLICY = "replace"

PYTHON_SUFFIX = ".py"
JAVASCRIPT_MODULE_SUFFIX = ".mjs"
JAVASCRIPT_SUFFIX = ".js"
TYPESCRIPT_SUFFIX = ".ts"
MARKDOWN_SUFFIX = ".md"
JSON_SUFFIX = ".json"
TOML_SUFFIX = ".toml"
YML_SUFFIX = ".yml"
YAML_SUFFIX = ".yaml"
SHELL_SUFFIX = ".sh"
POWERSHELL_SUFFIX = ".ps1"
BATCH_SUFFIX = ".cmd"
XML_SUFFIX = ".xml"
ARCHIVE_SUFFIX = ".archive"

MODULE_INITIALIZER_BASENAME = "__init__.py"
MODULE_INITIALIZER_STEM = "__init__"
MODULE_INITIALIZER_TAIL = "/__init__.py"
JAVASCRIPT_INDEX_TAIL = "/index.mjs"
TEST_MODULE_PREFIX = "test_"
CURRENT_DIRECTORY_PREFIX = "./"
HOME_DIRECTORY_PREFIX = "~/"
PARENT_DIRECTORY_PREFIX = "../"
RELATIVE_PREFIX_LENGTH = 2
PARENT_PREFIX_LENGTH = 3

ARCHIVE_ITEM_KIND = "archive_item"
INSTRUCTION_FILE_KIND = "instruction_file"
TEST_KIND = "test"
SHARED_MODULE_KIND = "shared_module"
SKILL_KIND = "skill"
AGENT_KIND = "agent"
COMMAND_KIND = "command"
SETTINGS_MANIFEST_KIND = "settings_manifest"
GIT_HOOK_KIND = "git_hook"
HOOK_MODULE_KIND = "hook_module"
HOOK_SUPPORT_KIND = "hook_support"
CODEX_PROJECTION_KIND = "codex_projection"
CURSOR_PROJECTION_KIND = "cursor_projection"
DOC_KIND = "doc"
AUDIT_RUBRIC_KIND = "audit_rubric"
CI_WORKFLOW_KIND = "ci_workflow"
CI_SUPPORT_KIND = "ci_support"
ROOT_CONFIG_KIND = "root_config"
SYMLINK_KIND = "symlink"
RULE_KIND = "rule"
SYSTEM_PROMPT_KIND = "system_prompt"
AGENT_STYLE_KIND = "output_style"
BIN_SCRIPT_KIND = "bin_script"
SCRIPTS_MODULE_KIND = "scripts_module"

IMPORTS_RELATION = "imports"
INVOKES_RELATION = "invokes"
REGISTERS_RELATION = "registers"
REFERENCES_RELATION = "references"
PROJECTS_RELATION = "projects"
INSTALLS_RELATION = "installs"
TESTS_RELATION = "tests"

SHIPPED_YES = "yes"
SHIPPED_NO = "no"
SHIPPED_UNKNOWN = "unknown"

ARCHIVED_SKILLS_PREFIX = ".agents/skills-archived/"
ARCHIVED_RULES_PREFIX = "rules-archived/"
SHARED_SKILLS_PREFIX = ".agents/skills/_shared/"
SKILLS_PREFIX = ".agents/skills/"
AGENTS_PREFIX = ".agents/agents/"
HOOKS_PREFIX = "hooks/"
GIT_HOOKS_PREFIX = "hooks/git-hooks/"
HOOKS_MANIFEST_INNER_PATH = "hooks/hooks.json"
HOOK_CONSTANTS_SEGMENT = "/hooks_constants/"
CODEX_BASENAME_PREFIX = "codex-"
CODEX_RULES_PREFIX = "codex-rules/"
SKILL_ARCHIVE_PREFIX = "skill-archive/"
CURSOR_SKILLS_PREFIX = ".cursor/skills/"
CURSOR_DIRECTORY_PREFIX = ".cursor"
CURSOR_IGNORE_PATH = ".cursorignore"
WORKFLOWS_PREFIX = ".github/workflows/"
GITHUB_PREFIX = ".github/"
CLAUDE_HOOKS_PREFIX = ".claude/hooks/"
CLAUDE_PLUGIN_PREFIX = ".claude-plugin/"
CLAUDE_HOME_PREFIX = ".claude/"
DOCS_PREFIX = "docs/"
CONFIG_PREFIX = "config/"
CHANGELOG_BASENAME = "CHANGELOG.md"
PACKAGE_MANIFEST_INNER_PATH = "package.json"
SURFACES_MANIFEST_INNER_PATH = "installable-surfaces.manifest.json"
INSTALLER_INNER_PATH = "bin/install.mjs"
SKILL_REGISTRY_BASENAME = "ever-shipped-skills.mjs"
INVENTORY_TABLE_NAME = "inventory.tsv"
DEPENDENCY_TABLE_NAME = "dependencies.tsv"
DEFAULT_DESTINATION_NAME = "data"
SHIP_NEGATION_MARKER = "!"
NAME_WORD_SEPARATOR = "-"
NO_IMPORTER_PLACEHOLDER = "none"
CHANGELOG_MARKER = "CHANGELOG"

UNREACHABLE_MODULE_FLAG = "unreachable_module"
HOOK_UNREGISTERED_FLAG = "hook_unregistered"
ARCHIVE_IN_SHIPPED_PATH_FLAG = "archive_in_shipped_path"
TEST_SUBJECT_GONE_FLAG = "test_subject_gone"
EXACT_DUPLICATE_FLAG = "exact_duplicate"
TEST_SUBJECT_GONE_DETAIL = (
    "no named subject, import, or mention resolves to a tracked non-test file"
)
COVERAGE_FAULT_MESSAGE = "coverage fault: tracked paths and component files differ"

MAXIMUM_BASENAME_CANDIDATES = 3
MINIMUM_NAME_MENTION_LENGTH = 6
NULL_BYTE_SCAN_LENGTH = 4096
BLOB_SIZE_FIELD_INDEX = 2
DIGEST_PREFIX_LENGTH = 12
MAXIMUM_LISTED_IMPORTERS = 3
MAXIMUM_LISTED_DUPLICATES = 6
MINIMUM_DUPLICATE_GROUP_SIZE = 2
REPOSITORY_ROOT_PARENT_INDEX = 2
SUCCESS_EXIT_CODE = 0

ALL_LIST_FILES_ARGUMENTS = ("ls-files", "-s", "-z")
ALL_BLOB_BATCH_ARGUMENTS = ("cat-file", "--batch")

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
ALL_ROOT_MANIFEST_BASENAMES = frozenset(
    {"package.json", "release-please-config.json", ".release-please-manifest.json"}
)
ALL_ROOT_DOC_BASENAMES = frozenset({"README.md", "LICENSE"})

ALL_EXECUTABLE_SUFFIXES = (
    PYTHON_SUFFIX,
    JAVASCRIPT_MODULE_SUFFIX,
    JAVASCRIPT_SUFFIX,
    POWERSHELL_SUFFIX,
    SHELL_SUFFIX,
    BATCH_SUFFIX,
)
ALL_TEXT_SUFFIXES = (
    PYTHON_SUFFIX,
    JAVASCRIPT_MODULE_SUFFIX,
    JAVASCRIPT_SUFFIX,
    TYPESCRIPT_SUFFIX,
    ".tsx",
    JSON_SUFFIX,
    MARKDOWN_SUFFIX,
    YML_SUFFIX,
    YAML_SUFFIX,
    TOML_SUFFIX,
    POWERSHELL_SUFFIX,
    SHELL_SUFFIX,
    XML_SUFFIX,
    ".txt",
    ".ini",
    ".cfg",
    ".html",
    BATCH_SUFFIX,
    ARCHIVE_SUFFIX,
    ".example",
    "",
)
ALL_JAVASCRIPT_SOURCE_SUFFIXES = (
    JAVASCRIPT_MODULE_SUFFIX,
    JAVASCRIPT_SUFFIX,
    TYPESCRIPT_SUFFIX,
)
ALL_SETTINGS_MANIFEST_SUFFIXES = (JSON_SUFFIX, TOML_SUFFIX)
ALL_PROSE_SOURCE_SUFFIXES = (
    MARKDOWN_SUFFIX,
    YML_SUFFIX,
    YAML_SUFFIX,
    SHELL_SUFFIX,
    POWERSHELL_SUFFIX,
    BATCH_SUFFIX,
    XML_SUFFIX,
)
ALL_NAMING_SUBJECT_SUFFIXES = (
    PYTHON_SUFFIX,
    JAVASCRIPT_MODULE_SUFFIX,
    JAVASCRIPT_SUFFIX,
    MARKDOWN_SUFFIX,
    JSON_SUFFIX,
    POWERSHELL_SUFFIX,
    SHELL_SUFFIX,
)
ALL_TEST_MODULE_SUFFIXES = ("_test.py", ".test.mjs", ".test.js")
ALL_TEST_SUBJECT_SUFFIXES = (".test.mjs", ".test.js", "_test.py")
TEST_SUPPORT_SUFFIX = "_test_support.py"
ALL_TEST_DIRECTORY_MARKERS = ("/tests/", "/fixtures/", "/test_files/")

ALL_PACKAGE_KIND_BY_PREFIX = (
    ("rules/", RULE_KIND),
    ("commands/", COMMAND_KIND),
    ("system-prompts/", SYSTEM_PROMPT_KIND),
    ("output-styles/", AGENT_STYLE_KIND),
    ("audit-rubrics/", AUDIT_RUBRIC_KIND),
    ("docs/", DOC_KIND),
    ("_shared/", SHARED_MODULE_KIND),
    ("bin/", BIN_SCRIPT_KIND),
    ("scripts/sync_to_cursor/", CURSOR_PROJECTION_KIND),
    ("scripts/", SCRIPTS_MODULE_KIND),
)

ALL_INVENTORY_COLUMNS = (
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
ALL_DEPENDENCY_COLUMNS = ("source_id", "relation", "target_id")

REACHABILITY_RELATIONS = frozenset(
    {
        IMPORTS_RELATION,
        INVOKES_RELATION,
        REGISTERS_RELATION,
        REFERENCES_RELATION,
        PROJECTS_RELATION,
    }
)
CODE_KINDS = frozenset(
    {
        HOOK_MODULE_KIND,
        HOOK_SUPPORT_KIND,
        SHARED_MODULE_KIND,
        SCRIPTS_MODULE_KIND,
        BIN_SCRIPT_KIND,
    }
)
NAMED_COMPONENT_KINDS = frozenset({SKILL_KIND, AGENT_KIND, COMMAND_KIND})
NON_LIVE_KINDS = frozenset({TEST_KIND, ARCHIVE_ITEM_KIND})

ALL_PROOF_CLASS_BY_KIND: dict[str, str] = {
    RULE_KIND: "OUTPUT",
    SKILL_KIND: "OUTPUT",
    AGENT_KIND: "OUTPUT",
    COMMAND_KIND: "OUTPUT",
    SYSTEM_PROMPT_KIND: "OUTPUT",
    INSTRUCTION_FILE_KIND: "OUTPUT",
    AGENT_STYLE_KIND: "OUTPUT",
    AUDIT_RUBRIC_KIND: "OUTPUT",
    HOOK_MODULE_KIND: "SAFETY",
    HOOK_SUPPORT_KIND: "SAFETY",
    GIT_HOOK_KIND: "SAFETY",
    SHARED_MODULE_KIND: "INFRASTRUCTURE",
    BIN_SCRIPT_KIND: "INFRASTRUCTURE",
    SCRIPTS_MODULE_KIND: "INFRASTRUCTURE",
    SETTINGS_MANIFEST_KIND: "INFRASTRUCTURE",
    CI_WORKFLOW_KIND: "INFRASTRUCTURE",
    CI_SUPPORT_KIND: "INFRASTRUCTURE",
    TEST_KIND: "INFRASTRUCTURE",
    ROOT_CONFIG_KIND: "INFRASTRUCTURE",
    SYMLINK_KIND: "COMPATIBILITY",
    CODEX_PROJECTION_KIND: "COMPATIBILITY",
    CURSOR_PROJECTION_KIND: "COMPATIBILITY",
    DOC_KIND: "DOCUMENTATION",
    ARCHIVE_ITEM_KIND: "ARCHIVE",
}

ALL_PROOF_METHOD_BY_CLASS: dict[str, str] = {
    "OUTPUT": "benchmark ablation: with versus without on the representative task set",
    "SAFETY": "drive the named bad behavior with and without the item; show unique prevention",
    "COMPATIBILITY": "install into the named client and show the dependency breaks without it",
    "INFRASTRUCTURE": "remove in a disposable copy; run install, pack, and CI operations",
    "DOCUMENTATION": "confirm the described behavior is retained and the doc is not loaded",
    "ARCHIVE": "show absence from packed tarball, installed tree, and agent context",
}

CONTEXT_LOADED_KINDS = frozenset(
    {
        RULE_KIND,
        SKILL_KIND,
        AGENT_KIND,
        COMMAND_KIND,
        SYSTEM_PROMPT_KIND,
        INSTRUCTION_FILE_KIND,
        AGENT_STYLE_KIND,
    }
)
CONTEXT_UNKNOWN_KINDS = frozenset(
    {
        HOOK_MODULE_KIND,
        DOC_KIND,
        AUDIT_RUBRIC_KIND,
        CURSOR_PROJECTION_KIND,
        CODEX_PROJECTION_KIND,
    }
)

MENTION_TOKEN = re.compile(
    r"[A-Za-z0-9_@.\-/\\]*[A-Za-z0-9_\-]\.[A-Za-z][A-Za-z0-9]{0,5}"
)
NAME_TOKEN = re.compile(r"[a-z0-9][a-z0-9_\-]{4,}[a-z0-9]")
PYTHON_IMPORT = re.compile(
    r"^\s*(?:from\s+([.\w]+)\s+import\s+(\([^)]*\)|[\w, ]+)|import\s+([\w., ]+))",
    re.MULTILINE,
)
IMPORTED_NAME = re.compile(r"(?:^|[,(])\s*(\w+)")
JAVASCRIPT_IMPORT = re.compile(
    r"""(?:from\s+|import\s*\(\s*|require\(\s*|import\s+)['"](\.{1,2}/[^'"]+)['"]"""
)
CONTENT_DIRECTORIES_DECLARATION = re.compile(r"CONTENT_DIRECTORIES\s*=\s*\[([^\]]*)\]")
QUOTED_ENTRY = re.compile(r"['\"]([^'\"]+)['\"]")
CONFTEST_BASENAME = "conftest.py"
SYMLINK_TARGET_MARKER = "symlink->"
PACKAGE_FILES_KEY = "files"
MANIFEST_DIRECTORIES_KEY = "directories"
MANIFEST_ROOT_FILES_KEY = "root_files"
