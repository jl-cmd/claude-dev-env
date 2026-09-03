"""Comment-presence and comment-change checks for Python and JavaScript sources."""

import difflib
import importlib
import io
import sys
import tokenize
from collections import Counter
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
    ALL_JAVASCRIPT_EXTENSIONS,
    ALL_PYTHON_EXTENSIONS,
    ALL_PYTHON_TOKENIZE_FAILURE_EXCEPTIONS,
    ALL_TOKEN_ANCHORED_DIRECTIVE_BOUNDARY_CHARACTERS,
    ALL_TOKEN_ANCHORED_EXEMPT_COMMENT_BODIES,
    CHAINED_INLINE_COMMENT_PATTERN,
    MAX_COMMENT_ISSUES,
)
_javascript_comment_scanner = importlib.import_module("javascript_comment_scanner")
extract_javascript_comment_occurrences = (
    _javascript_comment_scanner.extract_javascript_comment_occurrences
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


def _comment_occurrences(
    content: str, file_path: str, include_directive_comments: bool = False
) -> tuple[list[tuple[str, int, bool]], bool]:
    """Return comment occurrences with source lines and placement."""
    extension = get_file_extension(file_path)
    if extension in ALL_PYTHON_EXTENSIONS:
        return _python_comment_occurrences(content, include_directive_comments)
    if extension in ALL_JAVASCRIPT_EXTENSIONS:
        all_occurrences = extract_javascript_comment_occurrences(
            content, include_directive_comments
        )
        return [tuple(each_occurrence) for each_occurrence in all_occurrences], True
    return [], True


def extract_comment_texts(
    content: str, file_path: str, include_directive_comments: bool = False
) -> tuple[set[str], set[str]]:
    """Extract normalized comment text strings from content for comparison."""
    all_occurrences, _ = _comment_occurrences(
        content, file_path, include_directive_comments
    )
    return (
        {each_text for each_text, _each_line, each_is_inline in all_occurrences if each_is_inline},
        {each_text for each_text, _each_line, each_is_inline in all_occurrences if not each_is_inline},
    )


def _python_comment_occurrences(
    content: str, include_directive_comments: bool = True
) -> tuple[list[tuple[str, int, bool]], bool]:
    """Return Python comments with exact lines and a tokenize status."""
    source_lines = content.split("\n")
    try:
        all_tokens = list(_python_tokens(content))
    except ALL_PYTHON_TOKENIZE_FAILURE_EXCEPTIONS:
        return [], False
    all_occurrences: list[tuple[str, int, bool]] = []
    for each_token in all_tokens:
        if each_token.type != tokenize.COMMENT:
            continue
        if each_token.string.startswith("#!") and each_token.start == (1, 0):
            continue
        if not include_directive_comments and _is_exempt_python_comment(each_token):
            continue
        source_line = source_lines[each_token.start[0] - 1]
        is_inline = bool(source_line[: each_token.start[1]].strip())
        all_occurrences.append(
            (each_token.string.strip(), each_token.start[0], is_inline)
        )
    return all_occurrences, True


def check_comment_changes(old_content: str, new_content: str, file_path: str) -> list[str]:
    """Check for comment additions or removals between old and new content.

    Inline and standalone comments are blocking findings when added.
    Existing comments can be removed when the touched code no longer needs them.

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
        old_occurrences, old_tokenize_ok = _python_comment_occurrences(old_content, True)
        new_occurrences, new_tokenize_ok = _python_comment_occurrences(new_content, True)
        if not (old_tokenize_ok and new_tokenize_ok):
            return issues
    else:
        old_occurrences = extract_javascript_comment_occurrences(old_content, True)
        new_occurrences = extract_javascript_comment_occurrences(new_content, True)

    old_occurrence_counts = Counter(
        (each_text, is_inline)
        for each_text, _line_number, is_inline in old_occurrences
    )
    seen_occurrence_counts: Counter[tuple[str, bool]] = Counter()
    for each_text, each_line_number, each_is_inline in new_occurrences:
        occurrence_key = (each_text, each_is_inline)
        if seen_occurrence_counts[occurrence_key] >= old_occurrence_counts[occurrence_key]:
            comment_kind = "Inline" if each_is_inline else "Standalone"
            issues.append(
                f"Line {each_line_number}: {comment_kind} comment added: "
                f"{each_text[:60]} - refactor to self-documenting code"
            )
        seen_occurrence_counts[occurrence_key] += 1
        if len(issues) >= MAX_COMMENT_ISSUES:
            break
    issues.extend(_retained_comment_issues(old_content, new_content, file_path))

    return issues


def _line_diff_data(
    old_content: str, new_content: str
) -> tuple[set[int], set[int], dict[int, int]]:
    matcher = difflib.SequenceMatcher(
        None, old_content.splitlines(), new_content.splitlines(), autojunk=False
    )
    all_changed_lines: set[int] = set()
    all_deleted_lines: set[int] = set()
    old_line_by_new_line: dict[int, int] = {}
    for each_tag, each_old_start, each_old_end, each_new_start, each_new_end in matcher.get_opcodes():
        if each_tag == "equal":
            old_line_by_new_line.update({each_new_start + each_offset + 1: each_old_start + each_offset + 1 for each_offset in range(each_old_end - each_old_start)})
            continue
        all_changed_lines.update(range(each_new_start + 1, each_new_end + 1))
        if each_tag in {"delete", "replace"}:
            all_deleted_lines.update(range(each_old_start + 1, each_old_end + 1))
    return all_changed_lines, all_deleted_lines, old_line_by_new_line


def _matching_old_comment_line(
    each_text: str,
    each_line_number: int,
    each_is_inline: bool,
    all_old_line_by_key: dict[tuple[str, bool], list[int]],
    all_old_line_by_new_line: dict[int, int],
    all_used_old_lines: set[int],
) -> int | None:
    all_matching_old_lines = all_old_line_by_key.get((each_text, each_is_inline), [])
    mapped_old_line = all_old_line_by_new_line.get(each_line_number)
    return next(
        (each_candidate for each_candidate in (mapped_old_line, each_line_number)
         if each_candidate in all_matching_old_lines and each_candidate not in all_used_old_lines),
        None,
    )


def _is_attached_to_changed_code(
    each_line_number: int,
    each_is_inline: bool,
    old_line_number: int,
    all_changed_lines: set[int],
    all_deleted_lines: set[int],
) -> bool:
    """Return whether a retained occurrence sits on or beside changed code."""
    if each_is_inline:
        return each_line_number in all_changed_lines
    return each_line_number + 1 in all_changed_lines or old_line_number + 1 in all_deleted_lines


def _retained_comment_issues(
    old_content: str, new_content: str, file_path: str
) -> list[str]:
    (old_occurrences, old_tokenize_ok), (new_occurrences, new_tokenize_ok) = (_comment_occurrences(old_content, file_path, True), _comment_occurrences(new_content, file_path, True))
    if not (old_tokenize_ok and new_tokenize_ok):
        return []
    all_changed_lines, all_deleted_lines, old_line_by_new_line = _line_diff_data(old_content, new_content)
    old_line_by_key = {
        each_key: [each_line for each_text, each_line, each_is_inline in old_occurrences if (each_text, each_is_inline) == each_key]
        for each_key in {(each_text, each_is_inline) for each_text, _each_line, each_is_inline in old_occurrences}
    }
    used_old_lines: set[int] = set()
    issues: list[str] = []
    for each_text, each_line_number, each_is_inline in new_occurrences:
        old_line_number = _matching_old_comment_line(each_text, each_line_number, each_is_inline, old_line_by_key, old_line_by_new_line, used_old_lines)
        if old_line_number is None or not _is_attached_to_changed_code(each_line_number, each_is_inline, old_line_number, all_changed_lines, all_deleted_lines):
            continue
        used_old_lines.add(old_line_number)
        is_deleted_attachment = not each_is_inline and each_line_number + 1 not in all_changed_lines and old_line_number + 1 in all_deleted_lines
        issue_line = each_line_number if is_deleted_attachment or each_is_inline else each_line_number + 1
        comment_kind = "Inline" if each_is_inline else "Standalone"
        attachment_label = " at deleted code" if is_deleted_attachment else ""
        issues.append(f"Line {issue_line}: {comment_kind} comment still on the changed lines{attachment_label}: {each_text} - remove the comment")
        if len(issues) >= MAX_COMMENT_ISSUES:
            break
    return issues[:MAX_COMMENT_ISSUES]


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
    that need a tokenize status use the occurrence helper.
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
