"""Configuration constants for the state_description_blocker PreToolUse hook."""

from re import IGNORECASE, Pattern, compile

ALL_COMMENT_TRANSITION_PATTERNS: list[Pattern[str]] = [
    compile(r"\binstead of\b", IGNORECASE),
    compile(r"\bpreviously\b", IGNORECASE),
    compile(r"\bnow uses\b", IGNORECASE),
    compile(r"\bnow does\b", IGNORECASE),
    compile(r"\bnow handles\b", IGNORECASE),
    compile(r"\bnow supports\b", IGNORECASE),
    compile(r"\bnow names\b", IGNORECASE),
    compile(r"\bnow includes\b", IGNORECASE),
    compile(r"\bwas previously\b", IGNORECASE),
    compile(r"\bwere previously\b", IGNORECASE),
    compile(r"\bwas formerly\b", IGNORECASE),
    compile(r"\bwas added\b", IGNORECASE),
    compile(r"\bused to\b", IGNORECASE),
    compile(r"\bno longer\b", IGNORECASE),
    compile(r"\bhas been updated\b", IGNORECASE),
    compile(r"\bhave been updated\b", IGNORECASE),
    compile(r"\bhas been changed\b", IGNORECASE),
    compile(r"\bhave been changed\b", IGNORECASE),
    compile(r"\breplaced by\b", IGNORECASE),
    compile(r"\breplaces\b", IGNORECASE),
    compile(r"\bsuperseded by\b", IGNORECASE),
    compile(r"\bsupersedes\b", IGNORECASE),
    compile(r"\bchanged from\b", IGNORECASE),
    compile(r"\bchanges from\b", IGNORECASE),
    compile(r"\bswitched from\b", IGNORECASE),
    compile(r"\bswitched to\b", IGNORECASE),
    compile(r"\bmigrated from\b", IGNORECASE),
    compile(r"\bmigrated to\b", IGNORECASE),
    compile(r"\bmoved to\b", IGNORECASE),
    compile(r"\bmoved into\b", IGNORECASE),
    compile(r"\bextracted as\b", IGNORECASE),
    compile(r"\bupdated to\b", IGNORECASE),
    compile(r"\boriginally\b", IGNORECASE),
    compile(r"\bas of\b", IGNORECASE),
]

CODE_FENCE_PATTERN: Pattern[str] = compile(r"```[\s\S]*?```")
INLINE_CODE_PATTERN: Pattern[str] = compile(r"``[^`]+``|`[^`]+`")

ALL_MARKDOWN_EXTENSIONS: frozenset[str] = frozenset(
    {".md", ".mdx", ".markdown", ".rmd"}
)

ALL_HASH_ONLY_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".py",
        ".rb",
        ".sh",
        ".bash",
        ".zsh",
        ".ps1",
        ".psm1",
        ".yaml",
        ".yml",
        ".tf",
    }
)

ALL_BLOCK_COMMENT_ONLY_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".css",
    }
)

ALL_HASH_AND_SLASH_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".php",
    }
)

ALL_BLOCK_COMMENT_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".java",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".rs",
        ".go",
        ".swift",
        ".kt",
        ".scala",
        ".php",
        ".css",
        ".scss",
        ".less",
    }
)

ALL_COMMENT_BEARING_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".java",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".rs",
        ".go",
        ".rb",
        ".php",
        ".swift",
        ".kt",
        ".scala",
        ".sh",
        ".bash",
        ".zsh",
        ".ps1",
        ".psm1",
        ".yaml",
        ".yml",
        ".tf",
        ".css",
        ".scss",
        ".less",
    }
)
