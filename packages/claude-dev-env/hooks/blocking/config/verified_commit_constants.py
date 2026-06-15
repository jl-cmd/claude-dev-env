"""Constants for the verified-commit gate hook family.

Shared by ``verification_verdict_store.py``, ``verified_commit_gate.py``,
and ``verifier_verdict_minter.py`` so every tunable lives in one place.
"""

from __future__ import annotations

GIT_TIMEOUT_SECONDS = 30
ROOT_KEY_HEX_LENGTH = 16
VERDICT_JSON_INDENT = 2
CLAUDE_HOME_DIRECTORY_NAME = ".claude"
VERDICT_DIRECTORY_NAME = "verification"
VERDICT_DIRECTORY_NAME_SEPARATOR_PATTERN = r"['\"\\/,\s]+"
VERDICT_DIRECTORY_PATH_BOUNDARY_PATTERN = r"(?=['\"]*[\\/,])"
RELATIVE_VERDICT_DIRECTORY_PATTERN = r"(?:^|(?<=[\s;&|(='\"]))verification[\\/]"
VERDICT_PATH_GLUE_PATTERN = r"['\"+\\/\s]*[\\/]['\"+\\/\s]*"
VERDICT_DIRECTORY_CHANGE_TARGET_PATTERN = r"[ \t]+['\"]?verification[\\/]?['\"]?(?=[\s;&|]|$)"
VERDICT_PATH_JOINED_VARIABLE_PATTERN = r"\$\{?(\w+)\}?[\\/]|[\\/]\$\{?(\w+)\}?"
VERDICT_PATH_VARIABLE_ASSIGNMENT_PATTERN = r"(?:^|(?<=[\s;&|(]))%s=(\S+)"
VERDICT_FILE_RELATIVE_REFERENCE_PATTERN = (
    rf"(?:^|(?<=[\s;&|(='\"\\/]))verification[\\/][0-9a-f]{{{ROOT_KEY_HEX_LENGTH}}}\.json"
)
PATH_OBFUSCATION_PRIMITIVE_PATTERN = (
    r"chr\s*\(|bytes\.fromhex\s*\(|b64decode\s*\(|codecs\.decode\s*\("
    r"|(?:bytes|bytearray)\s*\(\s*\[|\[char\[?\]?\]"
)
ALL_VERDICT_PATH_SEGMENT_NAMES = (".claude", "verification")
ALL_VERDICT_PATH_SEGMENT_BODIES = ("claude", "verification")
HEX_TOKEN_PATTERN = r"(?<![0-9a-fx])([0-9a-f]{6,})(?![0-9a-f])"
BASE64_TOKEN_PATTERN = r"[A-Za-z0-9+/]{8,}={0,2}"
CHARACTER_CODE_SEQUENCE_PATTERN = r"\d{1,3}(?:\s*,\s*\d{1,3})+"
CHR_CALL_CHAIN_PATTERN = r"chr\(\s*\d{1,3}\s*\)(?:\s*\+\s*chr\(\s*\d{1,3}\s*\))+"
CHR_CALL_CODE_PATTERN = r"chr\(\s*(\d{1,3})\s*\)"
HEX_DIGITS_PER_BYTE = 2
FILE_WRITE_PRIMITIVE_PATTERN = (
    r"\bopen\s*\(|\.write_text\s*\(|\.write_bytes\s*\("
    r"|Out-File|Set-Content|Add-Content|\btee\b|>"
)
NON_REDIRECT_FILE_WRITE_PRIMITIVE_PATTERN = (
    r"\bopen\s*\(|\.write_text\s*\(|\.write_bytes\s*\("
    r"|Out-File|Set-Content|Add-Content|\btee\b"
)
WRITE_CALL_REGION_PATTERN = (
    r"(?:\bopen\s*\(|\.write_text\s*\(|\.write_bytes\s*\("
    r"|Out-File|Set-Content|Add-Content|\btee\b)[^;&|\n]*"
)
VERDICT_KEY_ALL_PASS = "all_pass"
VERDICT_KEY_MANIFEST_SHA256 = "manifest_sha256"
VERDICT_KEY_FINDINGS = "findings"
SUBAGENTS_DIRECTORY_NAME = "subagents"
AGENT_TRANSCRIPT_GLOB = "agent-*.jsonl"
AGENT_META_SIDECAR_SUFFIX = ".meta.json"
AGENT_META_TYPE_KEY = "agentType"
TRANSCRIPT_ENTRY_TYPE_KEY = "type"
TRANSCRIPT_ASSISTANT_ENTRY_TYPE = "assistant"
TRANSCRIPT_MESSAGE_KEY = "message"
TRANSCRIPT_CONTENT_KEY = "content"
TRANSCRIPT_CONTENT_TYPE_KEY = "type"
TRANSCRIPT_TEXT_CONTENT_TYPE = "text"
TRANSCRIPT_TEXT_KEY = "text"
VERDICT_FENCE_PATTERN = r"```verdict\s*\n(.*?)```"
MANIFEST_HASH_CLI_FLAG = "--manifest-hash"
DOCS_ONLY_EXTENSIONS = frozenset(
    {".md", ".txt", ".rst", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico"}
)
PYTHON_EXTENSION = ".py"
TEST_FILE_PREFIX = "test_"
TEST_FILE_SUFFIX = "_test.py"
CONFTEST_FILE_NAME = "conftest.py"
MINIMUM_STATUS_FIELD_COUNT = 2
ALL_FALLBACK_BASE_REFERENCES = ("origin/main", "origin/master")
ALL_TOOLING_STATE_PREFIXES = (
    ".claude/verification/",
    ".claude/worktrees/",
    ".claude/daemon/",
    ".claude/teams/",
    ".claude/sessions/",
    ".cursor/worktrees/",
)
GATED_GIT_SUBCOMMANDS = frozenset({"commit", "push"})
ALL_GIT_BINARY_NAMES = frozenset({"git", "git.exe"})
VALUE_TAKING_GIT_OPTIONS = frozenset({"-C", "-c", "--git-dir", "--work-tree", "--namespace"})
REPO_DIRECTORY_OPTION = "-C"
WORK_TREE_OPTION = "--work-tree"
DIRECTORY_CHANGE_VERBS = frozenset({"cd", "pushd", "set-location", "sl"})
DIRECTORY_CHANGE_PATH_OPTIONS = frozenset({"-path", "-literalpath"})
DIRECTORY_CHANGE_OPTION_TERMINATOR = "--"
DIRECTORY_CHANGE_PATTERN_PREFIX = r"(?:^|(?<=[\s;&|(]))(?:"
DIRECTORY_CHANGE_PATTERN_SUFFIX = r")(?=\s|$)"
DIRECTORY_CHANGE_OPTION_PREFIX_PATTERN = r"(?:[ \t]+(?:%s)(?=\s|$))*"
DIRECTORY_CHANGE_TARGET_PATTERN = r"[ \t]+['\"]?\S*"
CLAUDE_HOME_TARGET_BOUNDARY_PATTERN = r"[\\/]?['\"]?(?=[\s;&|]|$)"
VERDICT_DIRECTORY_TARGET_BOUNDARY_PATTERN = r"[\\/]?['\"]?(?=[\s;&|]|$)"
COMMAND_AFTER_DIRECTORY_CHANGE_PATTERN = r"[;&|\n][\s]*\S"
OPTION_WITH_VALUE_STEP = 2
ALL_GATED_TOOL_NAMES = ("Bash", "PowerShell")
HASH_PREVIEW_LENGTH = 16
MINTING_AGENT_TYPE = "code-verifier"
VERDICT_DIRECTORY_GUARD_MESSAGE = (
    "BLOCKED: [VERDICT_DIRECTORY_GUARD] Shell access to the verification "
    "verdict directory (~/.claude/verification/) is denied. Only the "
    "verifier_verdict_minter.py SubagentStop hook writes verdict files; a "
    "shell write here would forge a passing verdict and defeat the "
    "verified-commit gate. Spawn the code-verifier agent to earn a verdict "
    "instead of writing one."
)
CORRECTIVE_MESSAGE = (
    "BLOCKED: [VERIFIED_COMMIT_GATE] This branch surface has no passing "
    "verification verdict. Spawn the code-verifier agent (Agent tool, "
    "subagent_type 'code-verifier') with the task texts, the diff scope, "
    "and recorded baselines; when it finishes with a clean verdict the "
    "SubagentStop hook mints the verdict and this command will pass. Any "
    "file change after verification invalidates the verdict, so verify "
    "last. Exempt automatically: docs/image files, pytest test files, and "
    "Python files whose docstring- and comment-stripped AST is unchanged "
    "(comment-only edits in non-Python files are not exempt)."
)
