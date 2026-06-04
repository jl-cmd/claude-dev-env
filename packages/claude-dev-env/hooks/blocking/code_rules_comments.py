"""Comment-presence and comment-change checks for Python and JavaScript sources."""

import io
import sys
import tokenize
from collections.abc import Iterator
from pathlib import Path

_blocking_directory = str(Path(__file__).resolve().parent)
_hooks_directory = str(Path(__file__).resolve().parent.parent)
if _blocking_directory not in sys.path:
    sys.path.insert(0, _blocking_directory)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from code_rules_shared import (  # noqa: E402
    get_file_extension,
)

from hooks_constants.code_rules_enforcer_constants import (  # noqa: E402
    ALL_FREE_FORM_EXEMPT_COMMENT_BODIES,
    ALL_JAVASCRIPT_EXEMPT_COMMENT_PREFIXES,
    ALL_JAVASCRIPT_EXEMPT_INLINE_COMMENT_PREFIXES,
    ALL_JAVASCRIPT_EXTENSIONS,
    ALL_PYTHON_EXTENSIONS,
    ALL_PYTHON_TOKENIZE_FAILURE_EXCEPTIONS,
    ALL_TOKEN_ANCHORED_DIRECTIVE_BOUNDARY_CHARACTERS,
    ALL_TOKEN_ANCHORED_EXEMPT_COMMENT_BODIES,
    CHAINED_INLINE_COMMENT_PATTERN,
    MAX_COMMENT_ISSUES,
)


def check_comments_python(content: str) -> list[str]:
    """Check for comments in Python code.

    Uses ``tokenize.generate_tokens`` to find true ``COMMENT`` tokens.
    Hash characters that appear inside string literals (hex color codes,
    URL fragments, and the hash inside an f-string interpolation pattern)
    are correctly skipped because the tokenizer recognizes them as parts
    of string tokens rather than comment tokens.

    When the tokenizer cannot parse the file (partial content during
    Edit, invalid syntax), the check returns no findings rather than
    falling back to a line-walker scan — false negatives on
    syntactically-invalid drafts are preferable to false positives that
    mis-classify string-interior hash characters as comments.
    """
    issues = []
    for each_comment_token in _comment_tokens(content):
        if _is_exempt_python_comment(each_comment_token):
            continue
        line_number = each_comment_token.start[0]
        issues.append(
            f"Line {line_number}: Comment found - refactor to self-documenting code"
        )
        if len(issues) >= MAX_COMMENT_ISSUES:
            break

    return issues


def check_comments_javascript(content: str) -> list[str]:
    """Check for comments in JavaScript/TypeScript code."""
    issues = []
    lines = content.split("\n")
    is_in_multiline_comment = False

    for each_line_number, each_line in enumerate(lines, 1):
        stripped = each_line.strip()

        if not stripped:
            continue

        if is_in_multiline_comment:
            if "*/" in stripped:
                is_in_multiline_comment = False
            continue

        if stripped.startswith("/*"):
            is_in_multiline_comment = "*/" not in stripped
            if not stripped.startswith("/**"):
                issues.append(f"Line {each_line_number}: Block comment found - refactor to self-documenting code")
            continue

        if stripped.startswith("//"):
            if not stripped.startswith(ALL_JAVASCRIPT_EXEMPT_COMMENT_PREFIXES):
                issues.append(f"Line {each_line_number}: Comment found - refactor to self-documenting code")

        if len(issues) >= MAX_COMMENT_ISSUES:
            break

    return issues


def extract_comment_texts(content: str, file_path: str) -> tuple[set[str], set[str]]:
    """Extract normalized comment text strings from content for comparison.

    Returns:
        Tuple of (inline_comments, standalone_comments).
        Inline comments appear after code on the same line.
        Standalone comments are lines where the entire line is a comment.
    """
    extension = get_file_extension(file_path)
    inline_comments: set[str] = set()
    standalone_comments: set[str] = set()
    if not content:
        return inline_comments, standalone_comments

    if extension in ALL_PYTHON_EXTENSIONS:
        inline_comments, standalone_comments, _ = _extract_python_comment_sets(content)
        return inline_comments, standalone_comments

    lines = content.split("\n")

    if extension in ALL_JAVASCRIPT_EXTENSIONS:
        is_in_multiline = False
        for each_line in lines:
            stripped = each_line.strip()
            if not stripped:
                continue
            if is_in_multiline:
                if "*/" in stripped:
                    is_in_multiline = False
                continue
            if stripped.startswith("/*"):
                is_in_multiline = "*/" not in stripped
                if not stripped.startswith("/**"):
                    standalone_comments.add(stripped)
                continue
            if stripped.startswith("//"):
                if not stripped.startswith(ALL_JAVASCRIPT_EXEMPT_COMMENT_PREFIXES):
                    standalone_comments.add(stripped)
            elif "//" in each_line:
                before_slash = each_line[:each_line.index("//")]
                if before_slash.strip():
                    comment_start = stripped.index("//")
                    comment_text = stripped[comment_start + 2 :].strip()
                    if not comment_text.startswith(ALL_JAVASCRIPT_EXEMPT_INLINE_COMMENT_PREFIXES):
                        inline_comments.add(stripped[comment_start:])

    return inline_comments, standalone_comments


def check_comment_changes(old_content: str, new_content: str, file_path: str) -> list[str]:
    """Check for comment additions or removals between old and new content.

    Inline comments (after code on same line): BLOCK when added.
    Standalone comment lines: NUDGE (print advisory) when added.
    Existing comments being removed: BLOCK (comment preservation principle).

    When the file is Python and either *old_content* or *new_content* cannot
    be tokenized (common for mid-edit Edit fragments), the comparison is
    indeterminate: the per-side tokenize failure would empty one set and
    misrepresent every comment on the other side as either added or
    removed. The check returns no issues in that case — false negatives on
    syntactically-invalid drafts are preferable to false positives that
    flag legitimate comments as deleted.
    """
    issues: list[str] = []

    extension = get_file_extension(file_path)
    if extension in ALL_PYTHON_EXTENSIONS:
        old_inline, old_standalone, old_tokenize_ok = _extract_python_comment_sets(old_content)
        new_inline, new_standalone, new_tokenize_ok = _extract_python_comment_sets(new_content)
        if not (old_tokenize_ok and new_tokenize_ok):
            return issues
    else:
        old_inline, old_standalone = extract_comment_texts(old_content, file_path)
        new_inline, new_standalone = extract_comment_texts(new_content, file_path)

    added_inline = new_inline - old_inline
    if added_inline:
        sample = next(iter(added_inline))
        issues.append(f"Inline comment added: {sample[:60]} - refactor to self-documenting code")

    added_standalone = new_standalone - old_standalone
    if added_standalone:
        sample = next(iter(added_standalone))
        print(f"[CODE_RULES advisory] Standalone comment added: {sample[:60]} - prefer self-documenting code", file=sys.stderr)

    all_old = old_inline | old_standalone
    all_new = new_inline | new_standalone
    removed_comments = all_old - all_new
    if removed_comments:
        old_line_count = len([line for line in old_content.split("\n") if line.strip()])
        new_line_count = len([line for line in new_content.split("\n") if line.strip()])
        code_was_removed = new_line_count < old_line_count - len(removed_comments)
        if not code_was_removed:
            sample = next(iter(removed_comments))
            issues.append(f"Existing comment removed: {sample[:60]} - NEVER delete existing comments")

    return issues


def _python_tokens(source: str) -> Iterator[tokenize.TokenInfo]:
    """Yield Python tokens from *source* one at a time.

    Centralizes the ``tokenize.generate_tokens`` entry-point so a future
    change to the API lands in exactly one place. Iteration may raise
    any of ``ALL_PYTHON_TOKENIZE_FAILURE_EXCEPTIONS`` when the source is
    not valid Python (mid-edit Edit fragments, unterminated strings,
    mismatched indentation) — callers handle the exception according to
    their own contract (silently stop, return an indeterminate flag, etc.).
    """
    yield from tokenize.generate_tokens(io.StringIO(source).readline)


def _comment_tokens(source: str) -> Iterator[tokenize.TokenInfo]:
    """Yield COMMENT tokens from *source* one at a time.

    Streams from ``_python_tokens`` so consumers that early-exit (e.g.
    ``check_comments_python`` caps at ``MAX_COMMENT_ISSUES``) avoid
    materializing the entire token list. Silently stops on tokenize
    failure so callers receive only valid comment tokens — no
    indeterminate signal is exposed at this layer because the consumers
    that need it (``_extract_python_comment_sets``) bypass this helper.
    """
    try:
        for each_token in _python_tokens(source):
            if each_token.type == tokenize.COMMENT:
                yield each_token
    except ALL_PYTHON_TOKENIZE_FAILURE_EXCEPTIONS:
        return


def _is_exempt_python_comment(comment_token: tokenize.TokenInfo) -> bool:
    """Return True for shebangs and tooling-directive comments.

    The shebang exemption applies only when the comment token starts
    at line 1, column 0 — matching the OS-level convention that a
    shebang line is meaningful only as the first line of an executable
    file. An inline shebang-lookalike later in the file (an
    after-code occurrence on any line, or a standalone occurrence on
    the second line or later) is NOT a real shebang and remains subject to the
    no-comments rule.

    Matches any prefix listed in the token-anchored or free-form exempt-
    comment-body sets regardless of whether the directive sits flush
    against the leading hash character or carries one or more whitespace
    characters (space or tab) between the hash and the directive body.

    Token-anchored markers (``noqa``, ``pylint:``, ``pragma:``) are
    exempt only when the comment carries no chained second comment. Any
    second ``#`` after the directive body — regardless of whitespace
    around the inner hash, so ``# noqa: F401#note``,
    ``# noqa: F401 #prose``, and ``# noqa: F401  # imported for re-export``
    all qualify — indicates a second free-form inline comment
    piggybacking on the exempt marker; the trailing prose is not itself
    an exempt directive and therefore must not inherit exemption. A
    token-anchored directive body never legitimately carries a ``#``
    (noqa codes, pylint symbols, and pragma directives contain none), so
    any inner ``#`` reliably marks chained prose. Free-form markers
    (``type:``, ``TODO``, ``FIXME``, ``HACK``, ``XXX``) accept any
    trailing prose:
    ``# type:`` participates in the documented justification
    convention enforced by ``check_type_escape_hatches`` (which
    requires a trailing reason), and the TODO-family markers carry
    annotation text by convention.
    """
    comment_string = comment_token.string
    if comment_string.startswith("#!") and comment_token.start == (1, 0):
        return True
    directive_body = comment_string[1:].lstrip()
    if not directive_body:
        return True
    if directive_body.startswith(ALL_FREE_FORM_EXEMPT_COMMENT_BODIES):
        return True
    if not _starts_with_bounded_token_anchored_directive(directive_body):
        return False
    return CHAINED_INLINE_COMMENT_PATTERN.search(directive_body) is None


def _starts_with_bounded_token_anchored_directive(directive_body: str) -> bool:
    """Return True when *directive_body* opens with a real exempt directive.

    A token-anchored marker (``noqa``, ``pylint:``, ``pragma:``) counts only
    when the matched token is immediately followed by a directive boundary —
    end of string, a colon, or whitespace — so prose like
    ``noqa-but-not-really: explanation`` that merely shares the prefix does
    not inherit the exemption.

    Args:
        directive_body: The comment text with the leading hash and surrounding
            whitespace already stripped.

    Returns:
        True when a token-anchored exempt directive is present at a real token
        boundary, False otherwise.
    """
    for each_token in ALL_TOKEN_ANCHORED_EXEMPT_COMMENT_BODIES:
        if not directive_body.startswith(each_token):
            continue
        if each_token[-1] in ALL_TOKEN_ANCHORED_DIRECTIVE_BOUNDARY_CHARACTERS:
            return True
        following_text = directive_body[len(each_token):]
        if not following_text:
            return True
        next_character = following_text[0]
        if next_character.isspace():
            return True
        if next_character in ALL_TOKEN_ANCHORED_DIRECTIVE_BOUNDARY_CHARACTERS:
            return True
    return False


def _extract_python_comment_sets(content: str) -> tuple[set[str], set[str], bool]:
    """Return (inline_comments, standalone_comments, tokenize_succeeded).

    Streams *content* once via ``_python_tokens``. A tokenize failure
    (mid-edit fragment, syntax error) returns empty sets and ``False``
    so callers can treat the situation as indeterminate rather than as
    "no comments present". Inline vs standalone is decided by inspecting
    the column offset of each ``COMMENT`` token against its source
    line: an all-whitespace prefix means standalone.
    """
    inline_comments: set[str] = set()
    standalone_comments: set[str] = set()
    lines = content.split("\n")
    try:
        for each_token in _python_tokens(content):
            if each_token.type != tokenize.COMMENT:
                continue
            if _is_exempt_python_comment(each_token):
                continue
            line_number = each_token.start[0]
            column_offset = each_token.start[1]
            source_line = lines[line_number - 1] if line_number - 1 < len(lines) else ""
            text_before_comment = source_line[:column_offset]
            normalized_comment_text = each_token.string.strip()
            if not text_before_comment.strip():
                standalone_comments.add(normalized_comment_text)
            else:
                inline_comments.add(normalized_comment_text)
    except ALL_PYTHON_TOKENIZE_FAILURE_EXCEPTIONS:
        return set(), set(), False
    return inline_comments, standalone_comments, True
