"""Flag a prose term that names a code identifier a hair differently.

A change adds the field ``premium_request_interactions`` while the same
branch's docs call it the ``premium-request-budget`` field: one thing, two
names, and a reader who searches one never finds the other.

::

    code adds:  premium_request_interactions            the identifier
    prose adds: the premium-request-budget field         a hyphenated term
    flag: premium-request-budget  vs  premium_request_interactions  -- only the final word differs
    ok:   premium-request-interactions                   -- exact hyphen form, agrees
    ok:   premium-report-total  vs  premium_request_interactions  -- an earlier word differs, ordinary prose

The sweep reads a unified diff, collects the multi-word identifiers added on
code lines, and scans each added prose line for a hyphen or space variant that
renames only the final word of an identifier: it agrees on every earlier word
and differs on the last. A term that diverges in any earlier word, or shares
only one leading word, is ordinary prose. It also spares English compound
tails, singular/plural forms, stopword windows, and words that are themselves
tokens of another introduced identifier.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

parent_directory = str(Path(__file__).resolve().parent)
if parent_directory not in sys.path:
    sys.path.insert(0, parent_directory)

from pr_loop_shared_constants.terminology_sweep_constants import (  # noqa: E402
    ALL_COMMON_ENGLISH_COMPOUND_TAIL_WORDS,
    ALL_GIT_GREP_BASE_TREE_COMMAND_PREFIX,
    ALL_PROSE_STOPWORD_TOKENS,
    ALL_STRING_ESCAPE_SEQUENCES,
    ALL_TEST_FILE_NAME_INFIX_MARKERS,
    GIT_BASE_TREE_REVISION,
    IDENTIFIER_TOKEN_SEPARATOR,
    PROSE_WINDOW_WORD_SEPARATOR,
    TEST_DIRECTORY_PATH_SEGMENT,
    TEST_FILE_PREFIX,
    TEST_FILE_SUFFIX,
    ALL_DIFF_FILE_PATH_STRIP_PREFIXES,
    ALL_GIT_DIFF_CACHED_UNIFIED_ZERO_COMMAND,
    ALL_SWEEP_CODE_FILE_EXTENSIONS,
    CAMEL_CASE_IDENTIFIER_PATTERN,
    CAMEL_CASE_WORD_PATTERN,
    DIFF_ADDED_LINE_PREFIX,
    DIFF_FILE_ARGUMENT_HELP,
    DIFF_FILE_HEADER_PREFIX,
    DIFF_HUNK_HEADER_PATTERN,
    DIFF_NEW_FILE_HEADER_PREFIX,
    DIFF_OLD_FILE_HEADER_PREFIX,
    DIFF_REMOVED_LINE_PREFIX,
    GIT_DIFF_SUBPROCESS_TIMEOUT_SECONDS,
    HYPHENATED_PROSE_TOKEN_PATTERN,
    INLINE_CODE_SPAN_PATTERN,
    JAVASCRIPT_LINE_COMMENT_MARKER,
    JSDOC_CONTINUATION_MARKER,
    MARKDOWN_FILE_EXTENSION,
    MINIMUM_IDENTIFIER_TOKEN_COUNT,
    PLURAL_ES_SUFFIX_LENGTH,
    PLURAL_IES_SUFFIX_LENGTH,
    PROSE_WORD_PATTERN,
    PYTHON_COMMENT_MARKER,
    SNAKE_CASE_IDENTIFIER_PATTERN,
    STRING_LITERAL_CONTENT_PATTERN,
    TERMINOLOGY_FINDING_TEMPLATE,
    TERMINOLOGY_SWEEP_DESCRIPTION,
)

IdentifierTuple = tuple[str, ...]


def _strip_diff_path_prefix(raw_path: str) -> str:
    """Return the diff path with a leading ``a/`` or ``b/`` marker removed."""
    stripped_path = raw_path.strip()
    for each_prefix in ALL_DIFF_FILE_PATH_STRIP_PREFIXES:
        if stripped_path.startswith(each_prefix):
            return stripped_path[len(each_prefix) :]
    return stripped_path


def _parse_added_lines(diff_text: str) -> list[tuple[str, int, str]]:
    """Return each added line of a unified diff as ``(path, line_number, text)``.

    Args:
        diff_text: The unified-diff text to scan.

    Returns:
        One ``(file_path, line_number, added_text)`` triple per added line, with
        the 1-indexed line number the added line occupies in the new file.
    """
    all_added_lines: list[tuple[str, int, str]] = []
    current_file_path = ""
    next_line_number = 0
    for each_line in diff_text.split("\n"):
        if each_line.startswith(DIFF_FILE_HEADER_PREFIX):
            current_file_path = _strip_diff_path_prefix(
                each_line[len(DIFF_FILE_HEADER_PREFIX) :]
            )
            continue
        hunk_match = DIFF_HUNK_HEADER_PATTERN.match(each_line)
        if hunk_match is not None:
            next_line_number = int(hunk_match.group(1))
            continue
        if each_line.startswith(DIFF_ADDED_LINE_PREFIX):
            all_added_lines.append((current_file_path, next_line_number, each_line[1:]))
            next_line_number += 1
            continue
        if each_line.startswith(
            (DIFF_NEW_FILE_HEADER_PREFIX, DIFF_OLD_FILE_HEADER_PREFIX)
        ):
            continue
        if each_line.startswith(DIFF_REMOVED_LINE_PREFIX):
            continue
        next_line_number += 1
    return all_added_lines


def _file_extension(file_path: str) -> str:
    """Return the lowercase extension of a diff path, or the empty string."""
    return Path(file_path).suffix.lower()


def _identifier_token_tuple(identifier: str) -> IdentifierTuple:
    """Return the lowercase word tokens of a snake_case or camelCase identifier."""
    if "_" in identifier:
        return tuple(
            each_segment.lower()
            for each_segment in identifier.split("_")
            if each_segment
        )
    return tuple(
        each_piece.lower() for each_piece in CAMEL_CASE_WORD_PATTERN.findall(identifier)
    )


def _identifier_tuples_in_text(code_text: str) -> list[IdentifierTuple]:
    """Return every multi-word identifier tuple appearing in one code line."""
    all_identifier_names = SNAKE_CASE_IDENTIFIER_PATTERN.findall(code_text)
    all_identifier_names += CAMEL_CASE_IDENTIFIER_PATTERN.findall(code_text)
    all_tuples: list[IdentifierTuple] = []
    for each_name in all_identifier_names:
        token_tuple = _identifier_token_tuple(each_name)
        if len(token_tuple) >= MINIMUM_IDENTIFIER_TOKEN_COUNT:
            all_tuples.append(token_tuple)
    return all_tuples


def _collect_introduced_identifiers(
    all_added_lines: list[tuple[str, int, str]],
) -> frozenset[IdentifierTuple]:
    """Return the identifier tuples introduced on added code lines.

    Args:
        all_added_lines: Added-line triples from :func:`_parse_added_lines`.

    Returns:
        Every multi-word identifier tuple appearing on an added code line.
    """
    all_identifier_tuples: set[IdentifierTuple] = set()
    for each_file_path, _, each_text in all_added_lines:
        if _file_extension(each_file_path) in ALL_SWEEP_CODE_FILE_EXTENSIONS:
            all_identifier_tuples.update(_identifier_tuples_in_text(each_text))
    return frozenset(all_identifier_tuples)


def _prose_fragments(file_path: str, line_text: str) -> list[str]:
    """Return the prose fragments of an added line worth scanning for terms.

    A Markdown line is prose with its inline-code spans removed, since a
    backticked span names code verbatim. A code line contributes its comment
    tail, its JSDoc continuation text, and the contents of its string
    literals. A test module contributes its comment tail and JSDoc text only
    — its string literals hold fixture data, not prose.

    Args:
        file_path: The path the added line belongs to.
        line_text: The added line's text without its diff marker.

    Returns:
        The prose fragments to scan for near-miss terms.
    """
    extension = _file_extension(file_path)
    if extension == MARKDOWN_FILE_EXTENSION:
        return [INLINE_CODE_SPAN_PATTERN.sub(" ", line_text)]
    if extension not in ALL_SWEEP_CODE_FILE_EXTENSIONS:
        return []
    all_fragments: list[str] = []
    stripped_line = line_text.strip()
    if stripped_line.startswith(JSDOC_CONTINUATION_MARKER):
        all_fragments.append(stripped_line)
    all_fragments.extend(_comment_fragments(line_text))
    if not _is_test_file(file_path):
        all_fragments.extend(_string_literal_fragments(line_text))
    return all_fragments


def _is_test_file(file_path: str) -> bool:
    """Return whether a diff path names a test code module.

    A test module's string literals hold fixture data — embedded diffs,
    generated source, file trees — not documentation prose, so the sweep
    reads only its comments and JSDoc lines. A ``quota.test.mjs``, a
    ``layout.spec.ts``, and a ``fixtures.py`` under a tests directory are all
    test modules, so every one of these paths counts::

        tests/fixtures.py        -- under a tests/ directory
        api/test_quota.py        -- test_ prefixed stem
        api/quota_test.py        -- _test suffixed stem
        api/quota.test.mjs       -- .test. name marker
        api/layout.spec.ts       -- .spec. name marker

    A non-code path (a Markdown design doc) is prose worth scanning whatever
    its name, so it is never a test module here.

    Args:
        file_path: The diff path of the added line's file.

    Returns:
        True for a code file under a ``tests`` directory, or one whose name
        carries a ``test_`` prefix, a ``_test`` suffix, or a
        ``_test.``/``.test.``/``.spec.`` marker. False for any other path.
    """
    if _file_extension(file_path) not in ALL_SWEEP_CODE_FILE_EXTENSIONS:
        return False
    normalized_path = file_path.replace("\\", "/").lower()
    if TEST_DIRECTORY_PATH_SEGMENT in f"/{normalized_path}":
        return True
    basename = normalized_path.rsplit("/", 1)[-1]
    stem = Path(normalized_path).stem
    if stem.startswith(TEST_FILE_PREFIX) or stem.endswith(TEST_FILE_SUFFIX):
        return True
    return any(
        each_marker in basename for each_marker in ALL_TEST_FILE_NAME_INFIX_MARKERS
    )


def _comment_fragments(line_text: str) -> list[str]:
    """Return the comment tail of a code line, or an empty list when absent."""
    all_fragments: list[str] = []
    python_marker_index = line_text.find(PYTHON_COMMENT_MARKER)
    if python_marker_index != -1:
        all_fragments.append(
            line_text[python_marker_index + len(PYTHON_COMMENT_MARKER) :]
        )
    javascript_marker_index = line_text.find(JAVASCRIPT_LINE_COMMENT_MARKER)
    if javascript_marker_index != -1:
        all_fragments.append(
            line_text[javascript_marker_index + len(JAVASCRIPT_LINE_COMMENT_MARKER) :]
        )
    return all_fragments


def _string_literal_fragments(line_text: str) -> list[str]:
    """Return the contents of every quoted string literal on a code line.

    Escape sequences inside a literal (``\\n``, ``\\t``) are replaced with
    spaces before the words are read, so an escape letter never glues onto a
    neighbouring word as a phantom prose term. A literal left with no
    whitespace after that replacement is an identifier-shaped value — a UID,
    a key, a path — not prose, and contributes nothing.
    """
    all_fragments: list[str] = []
    for each_match in STRING_LITERAL_CONTENT_PATTERN.finditer(line_text):
        each_content = next(
            (
                each_group
                for each_group in each_match.groups()
                if each_group is not None
            ),
            "",
        )
        for each_escape in ALL_STRING_ESCAPE_SEQUENCES:
            each_content = each_content.replace(each_escape, " ")
        if not any(each_character.isspace() for each_character in each_content):
            continue
        all_fragments.append(each_content)
    return all_fragments


def _hyphenated_candidates(fragment: str) -> list[tuple[str, IdentifierTuple]]:
    """Return ``(display, token_tuple)`` for every hyphenated word in a fragment."""
    all_candidates: list[tuple[str, IdentifierTuple]] = []
    for each_match in HYPHENATED_PROSE_TOKEN_PATTERN.finditer(fragment):
        display = each_match.group(0)
        token_tuple = tuple(each_word.lower() for each_word in display.split("-"))
        all_candidates.append((display, token_tuple))
    return all_candidates


def _spaced_candidates(
    fragment: str,
    identifiers_by_first_token: dict[str, list[IdentifierTuple]],
) -> list[tuple[str, IdentifierTuple]]:
    """Return spaced word windows whose first word matches an identifier prefix.

    Only a window anchored at a known identifier prefix and sized to one of that
    prefix's identifiers is returned, which bounds the windows to the shapes the
    near-miss check can act on.

    Args:
        fragment: The prose fragment to scan.
        identifiers_by_first_token: Identifier tuples grouped by leading token.

    Returns:
        ``(display, token_tuple)`` pairs for each candidate window.
    """
    all_words = [
        each_word.lower() for each_word in PROSE_WORD_PATTERN.findall(fragment)
    ]
    all_candidates: list[tuple[str, IdentifierTuple]] = []
    for each_index, each_word in enumerate(all_words):
        for each_identifier in identifiers_by_first_token.get(each_word, []):
            window = tuple(all_words[each_index : each_index + len(each_identifier)])
            if len(window) == len(each_identifier):
                display = PROSE_WINDOW_WORD_SEPARATOR.join(window)
                all_candidates.append((display, window))
    return all_candidates


def _tokens_are_plural_variants(first_word: str, second_word: str) -> bool:
    """Return whether two words are singular/plural forms of one word.

    Covers the regular English plural rules: an appended ``s`` (``file`` /
    ``files``), an appended ``es`` (``box`` / ``boxes``), and the ``y`` to
    ``ies`` swap (``policy`` / ``policies``). The check is symmetric, so it
    holds whichever word is the singular form.
    """
    if first_word == second_word:
        return True
    shorter_word, longer_word = sorted((first_word, second_word), key=len)
    if longer_word in (shorter_word + "s", shorter_word + "es"):
        return True
    return shorter_word.endswith("y") and longer_word == shorter_word[:-1] + "ies"


def _tuples_match_ignoring_plural(
    first_tuple: IdentifierTuple, second_tuple: IdentifierTuple
) -> bool:
    """Return whether two equal-length tuples match token-for-token by plural."""
    return all(
        _tokens_are_plural_variants(each_first_word, each_second_word)
        for each_first_word, each_second_word in zip(first_tuple, second_tuple)
    )


def _diverges_only_in_final_token(
    candidate_tuple: IdentifierTuple, identifier_tuple: IdentifierTuple
) -> bool:
    """Return whether two equal-length tuples agree on every token but the last.

    ::

        candidate:  ("premium", "request", "budget")
        identifier: ("premium", "request", "interactions")
        flag: every earlier token agrees, so the prose renames the final word
        ok:   ("premium", "report", "total")  -- an earlier token diverges too

    A near-miss renames a single trailing word of an identifier, so every token
    before the last agrees by an exact or singular/plural match while the final
    token differs. A tuple no longer than the two-token identifier minimum
    cannot carry two agreeing leading tokens, so it never qualifies.

    Args:
        candidate_tuple: The prose term's lowercase token tuple.
        identifier_tuple: An introduced identifier's lowercase token tuple.

    Returns:
        True when both tuples run longer than the two-token identifier minimum,
        share the same length, agree by exact or singular/plural match on every
        token but the last, and differ on the final token.
    """
    if (
        len(candidate_tuple) <= MINIMUM_IDENTIFIER_TOKEN_COUNT
        or len(candidate_tuple) != len(identifier_tuple)
    ):
        return False
    if _tokens_are_plural_variants(candidate_tuple[-1], identifier_tuple[-1]):
        return False
    return all(
        _tokens_are_plural_variants(each_candidate_token, each_identifier_token)
        for each_candidate_token, each_identifier_token in zip(
            candidate_tuple[:-1], identifier_tuple[:-1]
        )
    )


def _word_is_identifier_vocabulary(
    prose_word: str, all_identifier_tokens: frozenset[str]
) -> bool:
    """Return whether a prose word is a token of any introduced identifier.

    A singular/plural form of an identifier token counts as the same word,
    so ``uids`` matches an identifier token ``uid``.

    Args:
        prose_word: The lowercase prose word to look up.
        all_identifier_tokens: Every token of every introduced identifier.

    Returns:
        True when the word, or a plural variant of it, is a known token.
    """
    if prose_word in all_identifier_tokens:
        return True
    if prose_word.endswith("y") and prose_word[:-1] + "ies" in all_identifier_tokens:
        return True
    if prose_word + "s" in all_identifier_tokens or prose_word + "es" in all_identifier_tokens:
        return True
    if prose_word.endswith("s") and prose_word[:-1] in all_identifier_tokens:
        return True
    if prose_word.endswith("es") and prose_word[:-PLURAL_ES_SUFFIX_LENGTH] in all_identifier_tokens:
        return True
    if prose_word.endswith("ies") and prose_word[:-PLURAL_IES_SUFFIX_LENGTH] + "y" in all_identifier_tokens:
        return True
    return False


def _near_miss_identifier(
    candidate_tuple: IdentifierTuple,
    all_identifier_tuples: frozenset[IdentifierTuple],
    identifiers_by_first_token: dict[str, list[IdentifierTuple]],
    all_identifier_tokens: frozenset[str],
) -> IdentifierTuple | None:
    """Return an identifier the candidate near-misses, or None when it does not.

    Args:
        candidate_tuple: The prose term's lowercase token tuple.
        all_identifier_tuples: Every introduced identifier tuple.
        identifiers_by_first_token: Identifier tuples grouped by leading token.
        all_identifier_tokens: Every token of every identifier on added code
            lines, used to spare prose built from real code vocabulary.

    Returns:
        The first identifier the candidate renames in only its final token. Such a
        candidate agrees on every earlier token, matches the identifier's
        length, and differs on the last token. None marks the candidate
        ordinary prose instead, on any of these grounds: it matches an
        identifier exactly; it diverges in a token before the last
        (``premium report total`` against ``premium_request_interactions``);
        it holds no more than the two-token identifier minimum; it ends in a
        common English compound tail word (``read-only``, ``data-driven``); it
        contains an English stopword (``to a``, ``each image``); it differs
        from the identifier only by a singular/plural form of one or more
        tokens (``test files`` against ``test_file``); or every diverging word
        is itself a token of some introduced identifier (``target width box``
        when ``box_height`` is also in the diff).
    """
    if not candidate_tuple or candidate_tuple in all_identifier_tuples:
        return None
    if candidate_tuple[-1] in ALL_COMMON_ENGLISH_COMPOUND_TAIL_WORDS:
        return None
    if any(each_word in ALL_PROSE_STOPWORD_TOKENS for each_word in candidate_tuple):
        return None
    for each_identifier in identifiers_by_first_token.get(candidate_tuple[0], []):
        if len(each_identifier) != len(candidate_tuple):
            continue
        if each_identifier == candidate_tuple:
            continue
        if _tuples_match_ignoring_plural(each_identifier, candidate_tuple):
            continue
        if not _diverges_only_in_final_token(candidate_tuple, each_identifier):
            continue
        diverging_words = [
            each_word
            for each_word, each_token in zip(candidate_tuple, each_identifier)
            if not _tokens_are_plural_variants(each_word, each_token)
        ]
        if all(
            _word_is_identifier_vocabulary(each_word, all_identifier_tokens)
            for each_word in diverging_words
        ):
            continue
        return each_identifier
    return None


def _findings_for_line(
    file_path: str,
    line_number: int,
    line_text: str,
    all_identifier_tuples: frozenset[IdentifierTuple],
    identifiers_by_first_token: dict[str, list[IdentifierTuple]],
    all_identifier_tokens: frozenset[str],
) -> list[str]:
    """Return the near-miss findings for one added line.

    Args:
        file_path: The path the added line belongs to.
        line_number: The added line's 1-indexed number in the new file.
        line_text: The added line's text without its diff marker.
        all_identifier_tuples: Every introduced identifier tuple.
        identifiers_by_first_token: Identifier tuples grouped by leading token.
        all_identifier_tokens: Every token of every identifier on added code
            lines, used to spare prose built from real code vocabulary.

    Returns:
        One finding string per distinct near-miss term on the line.
    """
    all_findings: list[str] = []
    reported_tuples: set[IdentifierTuple] = set()
    for each_fragment in _prose_fragments(file_path, line_text):
        all_candidates = _hyphenated_candidates(each_fragment)
        all_candidates += _spaced_candidates(each_fragment, identifiers_by_first_token)
        for each_display, each_tuple in all_candidates:
            matched_identifier = _near_miss_identifier(
                each_tuple,
                all_identifier_tuples,
                identifiers_by_first_token,
                all_identifier_tokens,
            )
            if matched_identifier is None or each_tuple in reported_tuples:
                continue
            reported_tuples.add(each_tuple)
            all_findings.append(
                TERMINOLOGY_FINDING_TEMPLATE.format(
                    file_path=file_path,
                    line_number=line_number,
                    candidate=each_display,
                    identifier=IDENTIFIER_TOKEN_SEPARATOR.join(matched_identifier),
                )
            )
    return all_findings


def sweep_diff(
    diff_text: str,
    all_preexisting_identifier_tuples: frozenset[IdentifierTuple] = frozenset(),
) -> list[str]:
    """Return every terminology near-miss finding for a unified diff.

    Args:
        diff_text: The unified-diff text to sweep.
        all_preexisting_identifier_tuples: Token tuples of added-line identifiers
            the base tree already names. A pre-existing identifier is not one
            the diff introduces, so no prose is flagged against it. Its
            tokens still count as code vocabulary.

    Returns:
        One finding string per near-miss term on an added prose line.
    """
    all_added_lines = _parse_added_lines(diff_text)
    all_identifier_tuples = _collect_introduced_identifiers(all_added_lines)
    all_identifier_tokens = frozenset(
        each_token for each_tuple in all_identifier_tuples for each_token in each_tuple
    )
    introduced_tuples = frozenset(
        each_tuple
        for each_tuple in all_identifier_tuples
        if each_tuple not in all_preexisting_identifier_tuples
    )
    if not introduced_tuples:
        return []
    introduced_by_first_token: dict[str, list[IdentifierTuple]] = {}
    for each_tuple in introduced_tuples:
        introduced_by_first_token.setdefault(each_tuple[0], []).append(each_tuple)
    all_findings: list[str] = []
    for each_file_path, each_line_number, each_text in all_added_lines:
        all_findings.extend(
            _findings_for_line(
                each_file_path,
                each_line_number,
                each_text,
                introduced_tuples,
                introduced_by_first_token,
                all_identifier_tokens,
            )
        )
    return all_findings


def repository_environment() -> dict[str, str]:
    """Return the process environment with every GIT_ variable removed.

    The sweep and the commit gate name their repository through an explicit
    root argument. An inherited GIT_DIR or GIT_WORK_TREE would override
    that root and point git at a different repository, so each spawned
    subprocess runs with a scrubbed environment.

    Returns:
        A copy of ``os.environ`` without any variable whose name starts
        with ``GIT_``.
    """
    return {
        each_key: each_setting
        for each_key, each_setting in os.environ.items()
        if not each_key.startswith("GIT_")
    }


def _identifier_names_on_added_code_lines(diff_text: str) -> frozenset[str]:
    """Return every multi-word identifier name on the diff's added code lines.

    Args:
        diff_text: The unified-diff text to scan.

    Returns:
        The distinct snake_case and camelCase names of two or more tokens.
    """
    all_names: set[str] = set()
    for each_file_path, _, each_text in _parse_added_lines(diff_text):
        if _file_extension(each_file_path) not in ALL_SWEEP_CODE_FILE_EXTENSIONS:
            continue
        all_found_names = SNAKE_CASE_IDENTIFIER_PATTERN.findall(each_text)
        all_found_names += CAMEL_CASE_IDENTIFIER_PATTERN.findall(each_text)
        for each_name in all_found_names:
            token_tuple = _identifier_token_tuple(each_name)
            if len(token_tuple) >= MINIMUM_IDENTIFIER_TOKEN_COUNT:
                all_names.add(each_name)
    return frozenset(all_names)


def _base_tree_names(
    repository_root: Path, all_names: frozenset[str]
) -> frozenset[str]:
    """Return the names the repository's base tree already contains.

    Each name is looked up as a whole word in the base revision's tree. A
    repository with no commits yet, or a lookup that git cannot run, reports
    the name as absent, so the sweep then treats it as newly introduced —
    the behaviour the sweep has with no base-tree check at all.

    Args:
        repository_root: The repository root the lookups run in.
        all_names: The identifier names to look up.

    Returns:
        The subset of names present in the base tree.
    """
    all_present_names: set[str] = set()
    for each_name in sorted(all_names):
        try:
            grep_process = subprocess.run(
                [
                    *ALL_GIT_GREP_BASE_TREE_COMMAND_PREFIX,
                    each_name,
                    GIT_BASE_TREE_REVISION,
                ],
                cwd=str(repository_root),
                capture_output=True,
                text=True,
                timeout=GIT_DIFF_SUBPROCESS_TIMEOUT_SECONDS,
                check=False,
                env=repository_environment(),
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            continue
        if grep_process.returncode == 0:
            all_present_names.add(each_name)
    return frozenset(all_present_names)


def staged_terminology_findings(
    repository_root: Path,
    all_preexisting_identifier_tuples: frozenset[IdentifierTuple] = frozenset(),
) -> list[str]:
    """Return terminology near-miss findings for a repository's staged diff.

    An identifier the base tree already names is not one the staged diff
    introduces, so no prose is flagged against it — only genuinely new
    identifiers are swept.

    Args:
        repository_root: The repository root the staged diff is read from.
        all_preexisting_identifier_tuples: Extra token tuples to treat as
            already named, added to the base-tree set the sweep skips. Empty
            by default, which sweeps exactly the base-tree result.

    Returns:
        One finding string per near-miss term on a staged added prose line, or
        an empty list when the staged diff is empty or git cannot be run.
    """
    diff_process = subprocess.run(
        list(ALL_GIT_DIFF_CACHED_UNIFIED_ZERO_COMMAND),
        cwd=str(repository_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=GIT_DIFF_SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
        env=repository_environment(),
    )
    if diff_process.returncode != 0:
        return []
    all_added_names = _identifier_names_on_added_code_lines(diff_process.stdout)
    preexisting_tuples = frozenset(
        _identifier_token_tuple(each_name)
        for each_name in _base_tree_names(repository_root, all_added_names)
    )
    return sweep_diff(
        diff_process.stdout,
        preexisting_tuples | all_preexisting_identifier_tuples,
    )


def _read_diff_text(diff_file_path: str | None) -> str:
    """Return the diff text from a file path, or from standard input when None."""
    if diff_file_path is None:
        return sys.stdin.read()
    return Path(diff_file_path).read_text(encoding="utf-8")


def _parse_arguments(all_arguments: list[str]) -> argparse.Namespace:
    """Return the parsed command-line arguments for the terminology sweep.

    Args:
        all_arguments: The argument vector following the script name.

    Returns:
        The parsed namespace carrying the optional ``diff_file`` path.
    """
    parser = argparse.ArgumentParser(description=TERMINOLOGY_SWEEP_DESCRIPTION)
    parser.add_argument(
        "--diff-file",
        dest="diff_file",
        default=None,
        help=DIFF_FILE_ARGUMENT_HELP,
    )
    return parser.parse_args(all_arguments)


def main(
    all_arguments: list[str],
    all_preexisting_identifier_tuples: frozenset[IdentifierTuple] = frozenset(),
) -> int:
    """Run the sweep and return the process exit code.

    Args:
        all_arguments: The argument vector following the script name.
        all_preexisting_identifier_tuples: Token tuples to treat as already
            named, so no prose is flagged against them. Empty by default, which
            sweeps every multi-word identifier the diff introduces.

    Returns:
        The value 1 when any near-miss finding exists, and 0 when none remain.
    """
    arguments = _parse_arguments(all_arguments)
    all_findings = sweep_diff(
        _read_diff_text(arguments.diff_file),
        all_preexisting_identifier_tuples,
    )
    for each_finding in all_findings:
        print(each_finding)
    return 1 if all_findings else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
