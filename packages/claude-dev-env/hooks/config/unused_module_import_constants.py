"""Constants for the unused module-level import scan in ``code_rules_enforcer``."""

import io
import re
import tokenize

PYFLAKES_UNUSED_IMPORT_RULE_CODE: str = "F401"
NOQA_DIRECTIVE_PATTERN: re.Pattern[str] = re.compile(
    r"#\s*noqa\b(?:\s*:\s*([^\n#]+))?",
    re.IGNORECASE,
)
MAX_UNUSED_IMPORT_ISSUES: int = 25
UNUSED_IMPORT_GUIDANCE: str = (
    "remove unused import; if kept for side effects, mark with `# noqa: F401`"
)
TYPE_CHECKING_IDENTIFIER: str = "TYPE_CHECKING"
ALL_TYPING_MODULE_NAMES: frozenset[str] = frozenset({"typing", "typing_extensions"})


def _comment_text_from_line(line_text: str) -> str | None:
    try:
        for each_token in tokenize.generate_tokens(io.StringIO(line_text).readline):
            if each_token.type == tokenize.COMMENT:
                return each_token.string
    except tokenize.TokenError:
        return None
    return None


def line_suppresses_unused_import_via_noqa(line_text: str) -> bool:
    """Return True only for bare ``# noqa`` / ``#noqa`` or a code list that includes F401."""
    comment_text = _comment_text_from_line(line_text)
    if comment_text is None:
        return False
    match = NOQA_DIRECTIVE_PATTERN.search(comment_text)
    if match is None:
        return False
    codes_part = match.group(1)
    if codes_part is None or not codes_part.strip():
        return True
    for each_fragment in codes_part.split(","):
        stripped = each_fragment.strip()
        if not stripped:
            continue
        first_token = stripped.split()[0]
        if first_token.upper() == PYFLAKES_UNUSED_IMPORT_RULE_CODE:
            return True
    return False
