import json
import math
import os
import re
import shlex
import sys
from pathlib import Path
from typing import TextIO

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from blocking._gh_body_arg_utils import (  # noqa: E402
    all_body_flag_prefixes,
    all_body_flags,
    all_value_flag_equals_prefixes,
    all_value_flags,
    body_file_flag,
    body_file_flag_prefix,
    body_file_short_flag,
    body_file_short_flag_prefix,
    count_extra_tokens_to_skip_for_split_quoted_value,
    get_logical_first_line,
    iter_significant_tokens,
)


from hooks_constants.pr_description_enforcer_constants import (  # noqa: E402
    ALL_HEAVY_OPENING_HEADERS,
    ALL_HEAVY_TESTING_HEADERS,
    ALL_READABILITY_CLI_FLAG_TOKENS,
    ATOMIC_WRITE_TEMP_SUFFIX,
    BLOCKQUOTE_LINE_PATTERN,
    BLOCKQUOTE_MARKER_PATTERN,
    BOLD_PAIR_PATTERN,
    BULLET_MARKER_PATTERN,
    DEFAULT_READABILITY_THRESHOLDS,
    FENCED_CODE_BLOCK_PATTERN,
    FLESCH_BASE_SCORE,
    FLESCH_PERFECT_SCORE,
    FLESCH_SYLLABLES_PER_WORD_COEFFICIENT,
    FLESCH_WORDS_PER_SENTENCE_COEFFICIENT,
    GH_PR_COMMAND_MIN_TOKEN_COUNT,
    HEADING_LINE_PATTERN,
    HEAVY_MIN_BODY_CHARS_FOR_CLASSIFICATION,
    HEAVY_SHAPE,
    INLINE_CODE_PATTERN,
    LINK_TEXT_PATTERN,
    MINIMUM_SUBSTANTIVE_PROSE_CHARS,
    PR_GUIDE_PATH,
    READABILITY_AVG_SENTENCE_WORDS_CEILING,
    READABILITY_ENABLED_STATE_FILE,
    READABILITY_FLESCH_LOOSEN_FACTOR,
    READABILITY_LOOSEN_CAP,
    READABILITY_MAX_SENTENCE_WORDS_CEILING,
    READABILITY_MIN_FLESCH_FLOOR,
    READABILITY_SENTENCE_WORDS_LOOSEN_FACTOR,
    READABILITY_STATE_FILE,
    READABILITY_STRIKE_THRESHOLD,
    READABILITY_THRESHOLD_OVERRIDE_FILE,
    ReadabilityThresholds,
    SELF_CLOSING_REFERENCE_MESSAGE_PREFIX,
    SELF_CLOSING_REFERENCE_MESSAGE_SUFFIX,
    SELF_REFERENCE_PATTERN_TEMPLATE,
    STANDARD_SHAPE,
    TABLE_ROW_LINE_PATTERN,
    THIS_PR_OPENING_PATTERN,
    TRIVIAL_BODY_CHAR_THRESHOLD,
    TRIVIAL_SHAPE,
    WHITESPACE_RUN_PATTERN,
)

VAGUE_LANGUAGE_PATTERN = re.compile(
    r'\b(fix(?:ed)? (?:bug|issue|it)|update(?:d)? code|minor changes|various (?:fixes|updates|improvements))\b',
    re.IGNORECASE,
)


shell_variable_sigil: str = "$"
body_file_stdin_sentinel: str = "-"
all_quote_characters: frozenset[str] = frozenset({'"', "'"})
file_encoding_utf8: str = "utf-8"

_non_body_value_flags: frozenset[str] = all_value_flags - {body_file_flag, body_file_short_flag}

_non_body_value_flag_equals_prefixes: tuple[str, ...] = tuple(
    sorted(
        (
            prefix for prefix in all_value_flag_equals_prefixes
            if not prefix.startswith("--body")
            and not prefix.startswith("-b=")
            and not prefix.startswith("-F=")
        ),
        key=len,
        reverse=True,
    )
)


class PathTraversalError(Exception):
    pass

def _is_flag_shaped_token(token: str) -> bool:
    if len(token) < 2:
        return False
    if not token.startswith("-"):
        return False
    return token[1] == "-" or token[1].isalpha()


def _strip_surrounding_quotes(token: str) -> str:
    if len(token) < 2:
        return token
    first_character = token[0]
    last_character = token[-1]
    if first_character in all_quote_characters and first_character == last_character:
        return token[1:-1]
    return token


def _is_unresolvable_shell_value(token: str) -> bool:
    return token.startswith(shell_variable_sigil)


def _read_body_file_contents(file_path: str) -> str | None:
    given_path = Path(file_path)
    allowed_root = Path.cwd().resolve()
    if given_path.is_symlink():
        resolved_target = given_path.resolve()
        try:
            resolved_target.relative_to(allowed_root)
        except ValueError:
            raise PathTraversalError("symlink target resolves outside allowed root")
    resolved_path = given_path.resolve()
    if not given_path.is_absolute():
        try:
            resolved_path.relative_to(allowed_root)
        except ValueError:
            raise PathTraversalError("relative path resolves outside allowed root")
    try:
        with open(resolved_path, "r", encoding=file_encoding_utf8, errors="replace") as body_file:
            return body_file.read()
    except (FileNotFoundError, IsADirectoryError, PermissionError, OSError):
        return None


def _resolve_body_file_value(raw_value_token: str) -> str | None:
    """Return file contents, or None when the body cannot be audited.

    None means body is present but unauditable -- skip enforcement.
    This covers: stdin sentinel, unresolvable shell variables, and path-traversal-rejected paths.
    """
    stripped_value = _strip_surrounding_quotes(raw_value_token)
    if not stripped_value:
        return None
    if stripped_value == body_file_stdin_sentinel:
        return None
    if _is_unresolvable_shell_value(stripped_value):
        return None
    try:
        return _read_body_file_contents(stripped_value)
    except PathTraversalError:
        return None


def _resolve_body_string_value(raw_value_token: str) -> str | None:
    """Return the literal body string, or None when the value is an
    unresolvable shell variable.

    Distinguishing the two cases lets `main()` skip enforcement only for
    unauditable bodies; a literal `--body ""` still returns `""` and flows
    into `validate_pr_body` so the substantive-prose check blocks it.
    """
    stripped_value = _strip_surrounding_quotes(raw_value_token)
    if _is_unresolvable_shell_value(stripped_value):
        return None
    return stripped_value


def _reassemble_split_quoted_value(first_value_token: str, remaining_tokens: list[str]) -> str | None:
    extra_tokens_consumed = count_extra_tokens_to_skip_for_split_quoted_value(
        remaining_tokens,
        first_value_token,
    )
    if extra_tokens_consumed is None:
        return None
    if extra_tokens_consumed == 0:
        return first_value_token
    continuation_tokens = remaining_tokens[:extra_tokens_consumed]
    return " ".join([first_value_token, *continuation_tokens])


def _match_body_flag_equals_prefix(token: str) -> str | None:
    for each_prefix in all_body_flag_prefixes:
        if token.startswith(each_prefix):
            return each_prefix
    return None


def _match_body_file_equals_prefix(token: str) -> str | None:
    for each_prefix in (body_file_flag_prefix, body_file_short_flag_prefix):
        if token.startswith(each_prefix):
            return each_prefix
    return None


def _match_non_body_value_flag_equals_prefix(token: str) -> str | None:
    for each_prefix in _non_body_value_flag_equals_prefixes:
        if token.startswith(each_prefix):
            return each_prefix
    return None


def _scan_raw_tokens_for_body(all_raw_tokens: list[str]) -> str | None | bool:
    """Return the body value from a raw token list, or False if no body flag found.

    Returns False when no body/body-file flag is present (caller should continue).
    Returns None when a body-file flag is present but malformed (no value
    follows), OR when the body value is an unresolvable shell variable (e.g.
    `--body "$VAR"`) — in either case the body is unauditable and the caller
    skips enforcement.
    Returns str for resolved body string values. An empty string `""` is a
    literal-empty body (e.g. `--body ""`) and must still flow into
    `validate_pr_body` so the substantive-prose check blocks it.
    """
    token_index = 0
    while token_index < len(all_raw_tokens):
        current_token = all_raw_tokens[token_index]
        remaining_raw = all_raw_tokens[token_index + 1:]
        non_body_equals_prefix = _match_non_body_value_flag_equals_prefix(current_token)
        if non_body_equals_prefix is not None:
            first_value_token = current_token[len(non_body_equals_prefix):]
            extra_skip = count_extra_tokens_to_skip_for_split_quoted_value(remaining_raw, first_value_token)
            token_index += 1 + (extra_skip or 0)
            continue
        if current_token in _non_body_value_flags:
            if remaining_raw and not _is_flag_shaped_token(remaining_raw[0]):
                first_value_token = remaining_raw[0]
                extra_skip = count_extra_tokens_to_skip_for_split_quoted_value(remaining_raw[1:], first_value_token)
                token_index += 1 + 1 + (extra_skip or 0)
                continue
            token_index += 1
            continue
        body_equals_prefix = _match_body_flag_equals_prefix(current_token)
        if body_equals_prefix is not None:
            first_value_token = current_token[len(body_equals_prefix):]
            full_value_token = _reassemble_split_quoted_value(first_value_token, remaining_raw)
            if full_value_token is None:
                return None
            return _resolve_body_string_value(full_value_token)
        body_file_equals_prefix = _match_body_file_equals_prefix(current_token)
        if body_file_equals_prefix is not None:
            first_value_token = current_token[len(body_file_equals_prefix):]
            full_value_token = _reassemble_split_quoted_value(first_value_token, remaining_raw)
            if full_value_token is None:
                return None
            return _resolve_body_file_value(full_value_token)
        if current_token in all_body_flags:
            if not remaining_raw or _is_flag_shaped_token(remaining_raw[0]):
                return None
            first_value_token = remaining_raw[0]
            full_value_token = _reassemble_split_quoted_value(first_value_token, remaining_raw[1:])
            if full_value_token is None:
                return None
            return _resolve_body_string_value(full_value_token)
        if current_token in {body_file_flag, body_file_short_flag}:
            if not remaining_raw or _is_flag_shaped_token(remaining_raw[0]):
                return None
            first_value_token = remaining_raw[0]
            full_value_token = _reassemble_split_quoted_value(first_value_token, remaining_raw[1:])
            if full_value_token is None:
                return None
            return _resolve_body_file_value(full_value_token)
        token_index += 1
    return False


def extract_body_from_command(
    command: str,
    pre_tokenized: tuple[str, list[str]] | None = None,
) -> str | None:
    """Return the PR body content for validation, or None if unextractable.

    Uses iter_significant_tokens to skip values of non-body value-taking flags
    so that --body/--body-file embedded in a quoted --title value never false-matches.
    For space-form body-file flags, scans the raw token list directly because
    iter_significant_tokens consumes the value token (yielding remaining-after-value).

    If pre_tokenized is provided as (logical_line, raw_tokens), reuses those instead
    of recomputing the logical line and shlex split a second time.
    """
    if pre_tokenized is not None:
        logical_line, all_raw_tokens = pre_tokenized
    else:
        logical_line = get_logical_first_line(command)
        if not logical_line:
            return None
        try:
            all_raw_tokens = shlex.split(logical_line, posix=False)
        except ValueError:
            return None
    try:
        all_significant_tokens = list(
            iter_significant_tokens(command, pre_tokenized=(logical_line, all_raw_tokens))
        )
    except ValueError:
        return None

    significant_token_set = {each_token for each_token, _ in all_significant_tokens}
    body_flag_found_in_significant = (
        any(each_token in all_body_flags for each_token in significant_token_set)
        or any(_match_body_flag_equals_prefix(each_token) is not None for each_token in significant_token_set)
        or any(_match_body_file_equals_prefix(each_token) is not None for each_token in significant_token_set)
        or any(each_token in {body_file_flag, body_file_short_flag} for each_token in significant_token_set)
    )
    if not body_flag_found_in_significant:
        return None

    scan_outcome = _scan_raw_tokens_for_body(all_raw_tokens)
    if isinstance(scan_outcome, bool):
        return None
    return scan_outcome


def _strip_markdown_ceremony(body: str) -> str:
    """Return the body with Markdown ceremony stripped to leave underlying prose.

    Removes fenced code, inline code, heading lines, blockquote markers,
    bullet list markers, bold/emphasis markers, and Markdown link targets.
    Whitespace is preserved so callers can collapse or measure it as needed.
    """
    body_without_fences = FENCED_CODE_BLOCK_PATTERN.sub("", body)
    body_without_inline_code = INLINE_CODE_PATTERN.sub("", body_without_fences)
    body_without_blockquotes = BLOCKQUOTE_MARKER_PATTERN.sub("", body_without_inline_code)
    body_without_headings = HEADING_LINE_PATTERN.sub("", body_without_blockquotes)
    body_without_bullets = BULLET_MARKER_PATTERN.sub("", body_without_headings)
    body_without_bold = BOLD_PAIR_PATTERN.sub(r"\1", body_without_bullets)
    body_without_emphasis = body_without_bold.replace("*", "")
    body_without_links = LINK_TEXT_PATTERN.sub(r"\1", body_without_emphasis)
    return body_without_links


def _count_substantive_prose_chars(body: str) -> int:
    """Return the count of prose characters after stripping Markdown ceremony.

    Collapses internal whitespace so a body of only headers and bullets --
    no real WHY paragraph -- registers as effectively empty.
    """
    stripped_body = _strip_markdown_ceremony(body)
    body_collapsed = WHITESPACE_RUN_PATTERN.sub(' ', stripped_body).strip()
    return len(body_collapsed)


def _extract_vague_scan_text(body: str) -> str:
    """Return the prose to scan for vague language, with non-prose regions removed.

    Drops whole blockquote lines and whole pipe-delimited table rows, then strips
    the same Markdown ceremony as the prose-count path -- which removes fenced
    code, inline code, and whole heading lines. This exempts vague phrases that
    appear only inside code fences, inline code, Markdown headings, quoted
    reviewer text, or pipe-delimited example tables -- those are not the author's
    own prose. A pipe-delimited row carries at least two pipes; a line with a
    single leading pipe, or a borderless table row with no leading pipe, stays in
    scope.
    """
    without_blockquote_lines = BLOCKQUOTE_LINE_PATTERN.sub("", body)
    without_table_rows = TABLE_ROW_LINE_PATTERN.sub("", without_blockquote_lines)
    return _strip_markdown_ceremony(without_table_rows)


def _iter_section_headers(body: str) -> list[str]:
    """Return every ATX heading line in the body, preserving canonical form.

    HEADING_LINE_PATTERN matches the leading hash run (one or more hash
    characters at line start), so the result spans every ATX level.
    Downstream callers in this module only test specific two-hash header
    strings, so matching every heading level keeps the parser permissive
    without changing behaviour for the canonical two-hash header shape.

    Fenced code blocks are stripped first so example markdown nested inside ``` fences
    (a PR body that demonstrates the Heavy shape, for instance) is not counted as a
    structural header. This keeps the shape classifier and Heavy required-header check
    aligned with `_strip_markdown_ceremony`, which already strips fences before measuring.
    """
    body_without_fences = FENCED_CODE_BLOCK_PATTERN.sub("", body)
    all_headers: list[str] = []
    for each_match in HEADING_LINE_PATTERN.finditer(body_without_fences):
        header_text = each_match.group(0).strip()
        all_headers.append(header_text)
    return all_headers


def _compute_pr_body_shape(body: str) -> str:
    """Classify a PR body as `trivial`, `standard`, or `heavy` from content alone.

    Uses substantive prose chars (post-Markdown-strip) rather than raw length so the
    classifier and the ceremony-on-Trivial check both measure the same metric against
    TRIVIAL_BODY_CHAR_THRESHOLD; otherwise a body can be classified Standard by shape
    while simultaneously being flagged as Trivial-sized by the ceremony check.
    """
    substantive_length = _count_substantive_prose_chars(body)
    header_count = len(_iter_section_headers(body))

    if substantive_length < TRIVIAL_BODY_CHAR_THRESHOLD and header_count == 0:
        return TRIVIAL_SHAPE

    if substantive_length >= HEAVY_MIN_BODY_CHARS_FOR_CLASSIFICATION:
        return HEAVY_SHAPE

    return STANDARD_SHAPE


def _body_contains_any_header(body: str, all_candidate_headers: frozenset[str]) -> bool:
    body_headers_lower = {each_header.lower() for each_header in _iter_section_headers(body)}
    for each_candidate in all_candidate_headers:
        candidate_lower = each_candidate.lower()
        for each_present in body_headers_lower:
            if each_present == candidate_lower:
                return True
            if each_present.startswith(candidate_lower):
                character_after_candidate = each_present[len(candidate_lower)]
                if not (character_after_candidate.isalnum() or character_after_candidate == "_"):
                    return True
    return False


def _matches_self_closing_reference(body: str, pr_number: int) -> bool:
    pattern_source = SELF_REFERENCE_PATTERN_TEMPLATE.format(pr_number=pr_number)
    compiled_pattern = re.compile(pattern_source, re.IGNORECASE)
    return compiled_pattern.search(body) is not None


def _opens_with_this_pr_phrase(body: str) -> bool:
    return THIS_PR_OPENING_PATTERN.search(body) is not None


def _atomic_write_json(target_path: Path, all_payload_fields: dict[str, object]) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = target_path.with_suffix(target_path.suffix + ATOMIC_WRITE_TEMP_SUFFIX)
    with open(temporary_path, "w", encoding=file_encoding_utf8) as write_handle:
        json.dump(all_payload_fields, write_handle)
    os.replace(temporary_path, target_path)


def _read_json_or_default(target_path: Path, all_default_payload_fields: dict[str, object]) -> dict[str, object]:
    if not target_path.exists():
        return dict(all_default_payload_fields)
    try:
        with open(target_path, "r", encoding=file_encoding_utf8) as read_handle:
            loaded_payload = json.load(read_handle)
    except (FileNotFoundError, PermissionError, OSError, json.JSONDecodeError):
        return dict(all_default_payload_fields)
    if not isinstance(loaded_payload, dict):
        return dict(all_default_payload_fields)
    return loaded_payload


def _read_strike_count() -> int:
    payload = _read_json_or_default(READABILITY_STATE_FILE, {"strikes": 0})
    raw_count = payload.get("strikes", 0)
    if isinstance(raw_count, int) and not isinstance(raw_count, bool):
        return max(raw_count, 0)
    return 0


def _increment_strike_count() -> int:
    payload = _read_json_or_default(READABILITY_STATE_FILE, {"strikes": 0})
    raw_count = payload.get("strikes", 0)
    is_valid_integer = isinstance(raw_count, int) and not isinstance(raw_count, bool)
    starting_count = max(raw_count, 0) if is_valid_integer else 0
    new_count = starting_count + 1
    _atomic_write_json(READABILITY_STATE_FILE, {"strikes": new_count})
    return new_count


def _reset_strike_count() -> None:
    _atomic_write_json(READABILITY_STATE_FILE, {"strikes": 0})


def _load_readability_thresholds() -> ReadabilityThresholds:
    payload = _read_json_or_default(READABILITY_THRESHOLD_OVERRIDE_FILE, {})
    flesch_min_value = payload.get("flesch_min", DEFAULT_READABILITY_THRESHOLDS.flesch_min)
    max_sentence_value = payload.get(
        "max_sentence_words", DEFAULT_READABILITY_THRESHOLDS.max_sentence_words
    )
    avg_sentence_value = payload.get(
        "avg_sentence_words", DEFAULT_READABILITY_THRESHOLDS.avg_sentence_words
    )
    flesch_is_int = isinstance(flesch_min_value, int) and not isinstance(flesch_min_value, bool)
    max_is_int = isinstance(max_sentence_value, int) and not isinstance(max_sentence_value, bool)
    avg_is_int = isinstance(avg_sentence_value, int) and not isinstance(avg_sentence_value, bool)
    resolved_flesch = flesch_min_value if flesch_is_int else DEFAULT_READABILITY_THRESHOLDS.flesch_min
    resolved_max = max_sentence_value if max_is_int else DEFAULT_READABILITY_THRESHOLDS.max_sentence_words
    resolved_avg = avg_sentence_value if avg_is_int else DEFAULT_READABILITY_THRESHOLDS.avg_sentence_words
    return ReadabilityThresholds(
        flesch_min=resolved_flesch,
        max_sentence_words=resolved_max,
        avg_sentence_words=resolved_avg,
    )


def _read_loosens_used() -> int:
    payload = _read_json_or_default(READABILITY_THRESHOLD_OVERRIDE_FILE, {})
    raw_count = payload.get("loosens_used", 0)
    if isinstance(raw_count, int) and not isinstance(raw_count, bool):
        return max(raw_count, 0)
    return 0


def _is_readability_enabled() -> bool:
    payload = _read_json_or_default(READABILITY_ENABLED_STATE_FILE, {"enabled": True})
    enabled_value = payload.get("enabled", True)
    if isinstance(enabled_value, bool):
        return enabled_value
    return True


def _set_readability_enabled(enabled: bool) -> None:
    _atomic_write_json(READABILITY_ENABLED_STATE_FILE, {"enabled": enabled})


def _count_syllables_in_word(word: str) -> int:
    all_vowel_characters: frozenset[str] = frozenset("aeiouy")
    cleaned_word = "".join(each_character for each_character in word.lower() if each_character.isalpha())
    if not cleaned_word:
        return 0
    syllable_count = 0
    is_previous_character_vowel = False
    for each_character in cleaned_word:
        is_vowel = each_character in all_vowel_characters
        if is_vowel and not is_previous_character_vowel:
            syllable_count += 1
        is_previous_character_vowel = is_vowel
    if cleaned_word.endswith("e") and syllable_count > 1:
        syllable_count -= 1
    return max(syllable_count, 1)


def _split_sentences(text: str) -> list[str]:
    sentence_split_pattern = re.compile(r"[.!?]+\s+")
    cleaned_text = text.strip()
    if not cleaned_text:
        return []
    raw_pieces = sentence_split_pattern.split(cleaned_text)
    all_sentences = [each_piece.strip() for each_piece in raw_pieces if each_piece.strip()]
    return all_sentences


def _compute_flesch_reading_ease(text: str) -> float:
    all_sentences = _split_sentences(text)
    if not all_sentences:
        return FLESCH_PERFECT_SCORE
    all_words: list[str] = []
    total_syllables = 0
    for each_sentence in all_sentences:
        sentence_words = [each_token for each_token in re.split(r"\s+", each_sentence) if each_token]
        all_words.extend(sentence_words)
        for each_word in sentence_words:
            total_syllables += _count_syllables_in_word(each_word)
    total_words = len(all_words)
    if total_words == 0:
        return FLESCH_PERFECT_SCORE
    total_sentences = len(all_sentences)
    return (
        FLESCH_BASE_SCORE
        - FLESCH_WORDS_PER_SENTENCE_COEFFICIENT * (total_words / total_sentences)
        - FLESCH_SYLLABLES_PER_WORD_COEFFICIENT * (total_syllables / total_words)
    )


def _extract_readability_target_text(body: str) -> str:
    intro_paragraph = ""
    body_without_fences = FENCED_CODE_BLOCK_PATTERN.sub("", body)
    body_after_strip = body_without_fences.lstrip()
    blank_line_position = body_after_strip.find("\n\n")
    header_position_match = HEADING_LINE_PATTERN.search(body_after_strip)
    header_position = header_position_match.start() if header_position_match else -1

    if blank_line_position == -1 and header_position == -1:
        intro_paragraph = body_after_strip
    elif blank_line_position == -1:
        intro_paragraph = body_after_strip[:header_position]
    elif header_position == -1:
        intro_paragraph = body_after_strip[:blank_line_position]
    else:
        first_boundary = min(blank_line_position, header_position)
        intro_paragraph = body_after_strip[:first_boundary]

    first_body_section = ""
    if header_position_match is not None:
        section_start = header_position_match.end()
        remainder = body_after_strip[section_start:]
        next_header_match = HEADING_LINE_PATTERN.search(remainder)
        if next_header_match is not None:
            first_body_section = remainder[: next_header_match.start()]
        else:
            first_body_section = remainder

    combined_text = f"{intro_paragraph}\n\n{first_body_section}"
    return _strip_markdown_ceremony(combined_text)


def _evaluate_readability_metrics(
    target_text: str,
    thresholds: ReadabilityThresholds,
) -> list[str]:
    all_metric_violations: list[str] = []
    all_sentences = _split_sentences(target_text)
    if not all_sentences:
        return all_metric_violations
    word_counts_per_sentence: list[int] = []
    for each_sentence in all_sentences:
        sentence_words = [each_token for each_token in re.split(r"\s+", each_sentence) if each_token]
        word_counts_per_sentence.append(len(sentence_words))
    max_sentence_words = max(word_counts_per_sentence) if word_counts_per_sentence else 0
    average_sentence_words = (
        sum(word_counts_per_sentence) / len(word_counts_per_sentence)
        if word_counts_per_sentence
        else 0.0
    )
    if max_sentence_words > thresholds.max_sentence_words:
        all_metric_violations.append(
            f"Readability: longest sentence is {max_sentence_words} words "
            f"(maximum {thresholds.max_sentence_words}); "
            "split or rewrite the longest sentence"
        )
    if average_sentence_words > thresholds.avg_sentence_words:
        all_metric_violations.append(
            f"Readability: average sentence is {average_sentence_words:.1f} words "
            f"(maximum {thresholds.avg_sentence_words}); "
            "shorten or split your longest sentences"
        )
    flesch_score = _compute_flesch_reading_ease(target_text)
    if flesch_score < thresholds.flesch_min:
        all_metric_violations.append(
            f"Readability: Flesch Reading Ease is {flesch_score:.1f} "
            f"(minimum {thresholds.flesch_min}); use shorter words and sentences"
        )
    return all_metric_violations


def _build_readability_escape_hatch_message() -> str:
    return (
        "Readability strike threshold reached. Pick one: "
        "(1) python <enforcer-path> --readability-loosen to widen thresholds 10%, "
        "(2) python <enforcer-path> --readability-disable to skip the readability check, "
        "(3) python <enforcer-path> --readability-reset to zero the strike counter, "
        "(4) reply with the body plus the intended message to report a false positive."
    )


def _apply_readability_loosen() -> str:
    current_thresholds = _load_readability_thresholds()
    loosens_used = _read_loosens_used()

    if loosens_used >= READABILITY_LOOSEN_CAP:
        return "cap_reached"

    if current_thresholds.flesch_min <= READABILITY_MIN_FLESCH_FLOOR:
        return "floor_reached"

    if current_thresholds.max_sentence_words >= READABILITY_MAX_SENTENCE_WORDS_CEILING:
        return "ceiling_reached"

    if current_thresholds.avg_sentence_words >= READABILITY_AVG_SENTENCE_WORDS_CEILING:
        return "ceiling_reached"

    next_flesch = max(
        READABILITY_MIN_FLESCH_FLOOR,
        math.floor(current_thresholds.flesch_min * READABILITY_FLESCH_LOOSEN_FACTOR),
    )
    next_max_sentence = min(
        READABILITY_MAX_SENTENCE_WORDS_CEILING,
        math.ceil(current_thresholds.max_sentence_words * READABILITY_SENTENCE_WORDS_LOOSEN_FACTOR),
    )
    next_avg_sentence = min(
        READABILITY_AVG_SENTENCE_WORDS_CEILING,
        math.ceil(current_thresholds.avg_sentence_words * READABILITY_SENTENCE_WORDS_LOOSEN_FACTOR),
    )

    next_payload: dict[str, object] = {
        "flesch_min": next_flesch,
        "max_sentence_words": next_max_sentence,
        "avg_sentence_words": next_avg_sentence,
        "loosens_used": loosens_used + 1,
    }
    _atomic_write_json(READABILITY_THRESHOLD_OVERRIDE_FILE, next_payload)
    return "ok"


def _apply_readability_reset() -> None:
    _reset_strike_count()
    _atomic_write_json(READABILITY_THRESHOLD_OVERRIDE_FILE, {"loosens_used": 0})


def _resolve_positional_pr_number(token: str) -> int | None:
    """Return the PR number named by a positional token, or None if it is not one.

    Accepts either a bare integer literal or a GitHub PR URL whose final path
    segment is ``/pull/<number>``. The token may carry surrounding quotes;
    unresolvable shell variables are rejected.
    """
    stripped_candidate = _strip_surrounding_quotes(token)
    if _is_unresolvable_shell_value(stripped_candidate):
        return None
    url_match = re.match(
        r"^https?://[^/]+/[^/]+/[^/]+/pull/(\d+)(?:[/?#].*)?$",
        stripped_candidate,
    )
    if url_match is not None:
        try:
            return int(url_match.group(1))
        except ValueError:
            return None
    try:
        return int(stripped_candidate)
    except ValueError:
        return None


def _extract_pr_number_from_command(command: str) -> int | None:
    """Return the PR number positional argument from a `gh pr edit|comment` command.

    Skips value-taking non-body flags (and their value tokens) so that ``--repo owner/r``
    pairs do not consume the trailing PR number. Accepts both a bare integer literal
    and a GitHub PR URL (``https://github.com/o/r/pull/<n>``) in the positional slot.

    Args:
        command: The raw shell command captured by the hook.

    Returns:
        The PR number when one positional value (integer or URL) is present, else None.
    """
    logical_line = get_logical_first_line(command)
    if not logical_line:
        return None
    try:
        all_tokens = shlex.split(logical_line, posix=False)
    except ValueError:
        return None
    if len(all_tokens) < GH_PR_COMMAND_MIN_TOKEN_COUNT:
        return None
    if all_tokens[0] != "gh" or all_tokens[1] != "pr":
        return None
    subcommand_token = all_tokens[2]
    if subcommand_token not in {"edit", "comment"}:
        return None
    all_value_taking_bare_flags: frozenset[str] = (
        _non_body_value_flags | all_body_flags | {body_file_flag, body_file_short_flag}
    )
    token_index = GH_PR_COMMAND_MIN_TOKEN_COUNT
    while token_index < len(all_tokens):
        current_token = all_tokens[token_index]
        matched_equals_prefix = (
            _match_non_body_value_flag_equals_prefix(current_token)
            or _match_body_flag_equals_prefix(current_token)
            or _match_body_file_equals_prefix(current_token)
        )
        if matched_equals_prefix is not None:
            first_value_token = current_token[len(matched_equals_prefix):]
            remaining_raw_tokens = all_tokens[token_index + 1:]
            extra_skip = count_extra_tokens_to_skip_for_split_quoted_value(
                remaining_raw_tokens, first_value_token
            ) or 0
            token_index += 1 + extra_skip
            continue
        if current_token in all_value_taking_bare_flags:
            token_index += 1
            if token_index < len(all_tokens):
                token_index += 1
            continue
        if _is_flag_shaped_token(current_token):
            token_index += 1
            continue
        resolved_pr_number = _resolve_positional_pr_number(current_token)
        if resolved_pr_number is not None:
            return resolved_pr_number
        return None
    return None


def validate_pr_body(body: str, pr_number: int | None = None) -> list[str]:
    """Audit a PR body against the Anthropic claude-code style rules.

    Args:
        body: The PR body markdown text to audit.
        pr_number: The PR number when known (gh pr edit / gh pr comment); None at gh pr create time.

    Returns:
        A list of human-readable violation messages. Empty when the body passes.
    """
    violations: list[str] = []

    substantive_chars = _count_substantive_prose_chars(body)
    if substantive_chars < MINIMUM_SUBSTANTIVE_PROSE_CHARS:
        violations.append(
            "PR body lacks substantive prose -- include a Why paragraph or "
            "substantive explanation, not only headers and bullets"
        )

    body_shape = _compute_pr_body_shape(body)

    if body_shape == HEAVY_SHAPE:
        if not _body_contains_any_header(body, ALL_HEAVY_OPENING_HEADERS):
            violations.append(
                f"Heavy PR body missing required opening header -- add one of "
                f"{sorted(ALL_HEAVY_OPENING_HEADERS)}"
            )
        if not _body_contains_any_header(body, ALL_HEAVY_TESTING_HEADERS):
            violations.append(
                f"Heavy PR body missing required testing-category header -- add one of "
                f"{sorted(ALL_HEAVY_TESTING_HEADERS)}"
            )

    body_has_any_header = len(_iter_section_headers(body)) > 0
    body_is_trivial_sized = substantive_chars < TRIVIAL_BODY_CHAR_THRESHOLD
    if body_has_any_header and body_is_trivial_sized:
        violations.append(
            "Trivial PR body contains a ceremony header -- drop every header "
            "and write the one-sentence body directly"
        )

    if pr_number is not None and _matches_self_closing_reference(body, pr_number):
        violations.append(
            f"{SELF_CLOSING_REFERENCE_MESSAGE_PREFIX}{pr_number}{SELF_CLOSING_REFERENCE_MESSAGE_SUFFIX}"
        )

    if _opens_with_this_pr_phrase(body):
        violations.append(
            "PR body opens with 'This PR ...' -- open with an imperative verb "
            "(Adds, Fixes, Updates, Removes, Tightens, Ports)"
        )

    vague_scan_text = _extract_vague_scan_text(body)
    vague_matches = VAGUE_LANGUAGE_PATTERN.findall(vague_scan_text)
    if vague_matches:
        violations.append(
            f"Vague language detected: {', '.join(vague_matches)} -- "
            "be specific about what changed and why"
        )

    if _is_readability_enabled():
        thresholds = _load_readability_thresholds()
        target_text = _extract_readability_target_text(body)
        metric_violations = _evaluate_readability_metrics(target_text, thresholds)
        if metric_violations:
            post_increment_count = _increment_strike_count()
            if post_increment_count >= READABILITY_STRIKE_THRESHOLD:
                violations.append(_build_readability_escape_hatch_message())
            else:
                violations.extend(metric_violations)

    return violations


def _dispatch_cli_flag(
    flag_token: str,
    output_stream: TextIO,
    error_stream: TextIO,
) -> None:
    """Handle a single readability-management CLI flag and exit the process."""
    if flag_token == "--readability-loosen":
        outcome = _apply_readability_loosen()
        if outcome == "cap_reached":
            error_stream.write(
                "loosen cap reached; use --readability-disable or --readability-reset\n"
            )
            sys.exit(1)
        if outcome in {"floor_reached", "ceiling_reached"}:
            error_stream.write(
                "thresholds already at floor/ceiling; use --readability-disable or --readability-reset\n"
            )
            sys.exit(1)
        output_stream.write("readability thresholds loosened 10%\n")
        sys.exit(0)
    if flag_token == "--readability-reset":
        _apply_readability_reset()
        output_stream.write("readability strike counter and override thresholds reset\n")
        sys.exit(0)
    if flag_token == "--readability-disable":
        _set_readability_enabled(False)
        output_stream.write("readability check disabled\n")
        sys.exit(0)
    if flag_token == "--readability-enable":
        _set_readability_enabled(True)
        output_stream.write("readability check enabled\n")
        sys.exit(0)


def _command_carries_body_flag(command: str) -> bool:
    """Return True when the command string carries any body or body-file flag.

    Detects the body/body-file forms accepted by ``gh pr {create,edit,comment}``:

    - Long flags: a single ``"--body" in command`` substring check catches
      every long form — ``--body``, ``--body=<value>``, ``--body-file``, and
      ``--body-file=<value>`` — because ``--body`` is a prefix of
      ``--body-file``. No separate ``--body-file`` check is needed.
    - Short flags, space-separated: ``-b <value>``, ``-F <value>`` — matched
      as `` -b `` and `` -F `` so the literal substring cannot collide with a
      surrounding token (e.g. ``-base``, ``-Foo``).
    - Short flags, equal-attached: ``-b=<value>``, ``-F=<value>`` — matched
      as `` -b=`` and `` -F=`` for the same anti-collision reason. The test
      suite relies on this detection path.

    Args:
        command: The raw shell command captured by the hook.

    Returns:
        True if any documented body or body-file flag appears in the command.
    """
    return (
        "--body" in command
        or " -b " in command
        or " -b=" in command
        or " -F " in command
        or " -F=" in command
    )


def main() -> None:
    for each_argv_token in sys.argv[1:]:
        if each_argv_token in ALL_READABILITY_CLI_FLAG_TOKENS:
            _dispatch_cli_flag(
                each_argv_token,
                output_stream=sys.stdout,
                error_stream=sys.stderr,
            )
            return

    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    if tool_name != "Bash":
        sys.exit(0)

    command = input_data.get("tool_input", {}).get("command", "")
    if not command:
        sys.exit(0)

    has_any_body_flag = _command_carries_body_flag(command)
    is_pr_create = "gh pr create" in command and has_any_body_flag
    is_pr_edit = "gh pr edit" in command and has_any_body_flag
    is_pr_comment = "gh pr comment" in command and has_any_body_flag

    if not (is_pr_create or is_pr_edit or is_pr_comment):
        sys.exit(0)

    body = extract_body_from_command(command)

    if body is None:
        sys.exit(0)

    extracted_pr_number = None
    if is_pr_edit or is_pr_comment:
        extracted_pr_number = _extract_pr_number_from_command(command)

    violations = validate_pr_body(body, pr_number=extracted_pr_number)

    if violations:
        violation_list = "; ".join(violations)
        pr_guide_reference = f" @{PR_GUIDE_PATH}" if os.path.exists(PR_GUIDE_PATH) else ""
        denial_reason = (
            f"BLOCKED: [PR_DESCRIPTION] {violation_list}. "
            f"Use the pr-description-writer agent to author the body in Anthropic claude-code style. "
            f"Guide:{pr_guide_reference}"
        )
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": denial_reason,
            }
        }
        print(json.dumps(result))
        sys.stdout.flush()

    sys.exit(0)


if __name__ == "__main__":
    main()
