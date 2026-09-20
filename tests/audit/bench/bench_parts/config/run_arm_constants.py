"""Named constants the benchmark arm runner reads.

::

    ABLATE_ARM_PREFIX   "ablate:rules/a.md+rules/b.md" names an ablation arm
    ALL_ROW_COLUMNS     the TSV header the runner writes, in order
    JSON_INDENT_SPACES  the indent every JSON artifact of a run carries

The runner keeps no literal of its own, so a spelling changes in one place.
"""

from __future__ import annotations

from pathlib import Path

BENCH_DIRECTORY = Path(__file__).resolve().parents[2]

CLAUDE_DIRECTORY_NAME = ".claude"
AGENTS_DIRECTORY_NAME = ".agents"
CODEX_DIRECTORY_NAME = ".codex"
GIT_DIRECTORY_NAME = ".git"

INSTALLER_RELATIVE_PATH = Path("packages/claude-dev-env/bin/install.mjs")
ALL_AUTH_PASSTHROUGH_VARIABLES = ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN")
ALL_SESSION_VARIABLE_PREFIXES = ("CLAUDE", "ANTHROPIC")
DEFAULT_ALLOWED_TOOLS = "Bash,PowerShell,Read,Glob,Grep"
ALL_PROJECT_INSTALL_NAMES = (CLAUDE_DIRECTORY_NAME, AGENTS_DIRECTORY_NAME)
SHIM_LOG_RELATIVE_PATH = Path(GIT_DIRECTORY_NAME) / "bench-shim.log"
DEFAULT_SESSION_TIMEOUT_SECONDS = 1800
ALL_FIXTURE_CACHE_NAMES = ("__pycache__", ".pytest_cache", "*.pyc")
INSTALL_TIMEOUT_SECONDS = 600
ABLATE_ARM_PREFIX = "ablate:"
ABLATE_PATH_SEPARATOR = "+"
PACKAGE_RELATIVE_ROOT = "packages/claude-dev-env"
RUN_LABEL_CHARACTER_LIMIT = 48
JSON_INDENT_SPACES = 2
SETUP_FAILURE_SEPARATOR = "; "
HARNESS_DETAIL_CHARACTER_LIMIT = 400

GIT_CONFIG_GLOBAL_VARIABLE = "GIT_CONFIG_GLOBAL"
GIT_CONFIG_NOSYSTEM_VARIABLE = "GIT_CONFIG_NOSYSTEM"
CODEX_HOME_VARIABLE = "CODEX_HOME"
INSTALL_PSTACK_VARIABLE = "CDE_INSTALL_PSTACK"
DISABLE_AUTO_MEMORY_VARIABLE = "CLAUDE_CODE_DISABLE_AUTO_MEMORY"
SHIM_LOG_VARIABLE = "BENCH_SHIM_LOG"

ALL_LIVE_HOME_VARIABLES = ("USERPROFILE", "HOME", "HOMEDRIVE", "HOMEPATH")
ALL_RUN_SCRATCH_VARIABLES = ("TEMP", "TMP", "TMPDIR")
ALL_INIT_INVENTORY_KEYS = ("plugins", "memory_paths", "mcp_servers")
ALL_TOKEN_USAGE_KEYS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
)

ALL_GIT_INIT_ARGUMENTS = ["git", "init", "-q"]
ALL_GIT_ADD_ARGUMENTS = ["git", "add", "-A"]
ALL_GIT_COMMIT_ARGUMENTS = ["git", "commit", "-q", "-m", "fixture"]

ALL_ROW_COLUMNS = (
    "run_id",
    "case",
    "case_revision",
    "arm",
    "tree_identity",
    "repetition",
    "model",
    "claude_version",
    "exit",
    "grader_results",
    "turns",
    "tokens",
    "token_detail",
    "wall_seconds",
    "permission_denials",
    "transcript_path",
)
