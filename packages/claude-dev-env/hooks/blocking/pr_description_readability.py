"""Score PR body readability and manage its persisted strike/threshold state.

Computes Flesch Reading Ease and sentence-length metrics over the intro and
first section of a PR body, escalates repeated readability failures through a
persisted strike counter, applies the loosen/reset/enable/disable threshold
overrides, and dispatches the readability-management CLI flags.
"""

import json
import math
import os
import re
import sys
from pathlib import Path
from typing import TextIO

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from blocking.pr_description_body_audit import strip_markdown_ceremony  # noqa: E402
from hooks_constants.pr_description_enforcer_constants import (  # noqa: E402
    ATOMIC_WRITE_TEMP_SUFFIX,
    DEFAULT_READABILITY_THRESHOLDS,
    FENCED_CODE_BLOCK_PATTERN,
    FLESCH_BASE_SCORE,
    FLESCH_PERFECT_SCORE,
    FLESCH_SYLLABLES_PER_WORD_COEFFICIENT,
    FLESCH_WORDS_PER_SENTENCE_COEFFICIENT,
    HEADING_LINE_PATTERN,
    READABILITY_AVG_SENTENCE_WORDS_CEILING,
    READABILITY_ENABLED_STATE_FILE,
    READABILITY_FLESCH_LOOSEN_FACTOR,
    READABILITY_LOOSEN_CAP,
    READABILITY_MAX_SENTENCE_WORDS_CEILING,
    READABILITY_MIN_FLESCH_FLOOR,
    READABILITY_SENTENCE_WORDS_LOOSEN_FACTOR,
    READABILITY_STATE_FILE,
    READABILITY_THRESHOLD_OVERRIDE_FILE,
    ReadabilityThresholds,
)
from hooks_constants.setup_project_paths_constants import UTF8_ENCODING  # noqa: E402


def _atomic_write_json(target_path: Path, all_payload_fields: dict[str, object]) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = target_path.with_suffix(target_path.suffix + ATOMIC_WRITE_TEMP_SUFFIX)
    with open(temporary_path, "w", encoding=UTF8_ENCODING) as write_handle:
        json.dump(all_payload_fields, write_handle)
    os.replace(temporary_path, target_path)


def _read_json_or_default(
    target_path: Path, all_default_payload_fields: dict[str, object]
) -> dict[str, object]:
    if not target_path.exists():
        return dict(all_default_payload_fields)
    try:
        with open(target_path, "r", encoding=UTF8_ENCODING) as read_handle:
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
    resolved_flesch = (
        flesch_min_value if flesch_is_int else DEFAULT_READABILITY_THRESHOLDS.flesch_min
    )
    resolved_max = (
        max_sentence_value if max_is_int else DEFAULT_READABILITY_THRESHOLDS.max_sentence_words
    )
    resolved_avg = (
        avg_sentence_value if avg_is_int else DEFAULT_READABILITY_THRESHOLDS.avg_sentence_words
    )
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
    cleaned_word = "".join(
        each_character for each_character in word.lower() if each_character.isalpha()
    )
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
        sentence_words = [
            each_token for each_token in re.split(r"\s+", each_sentence) if each_token
        ]
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
    """Return the ceremony-stripped prose window scored for readability.

    Strips fenced code blocks, then builds a window from the body's intro
    paragraph plus its first section's prose. The intro paragraph ends at the
    earliest boundary among the first blank line and the first ATX header; when
    neither boundary exists the whole body is the intro. The first section runs
    from just after that first header to the next header (or end of body). The
    intro and first section are joined with a blank line and returned with
    Markdown ceremony stripped.

    Args:
        body: The raw PR body markdown text.

    Returns:
        The ceremony-stripped intro-paragraph plus first-section prose window
        used for readability scoring.
    """
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
    return strip_markdown_ceremony(combined_text)


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
        sentence_words = [
            each_token for each_token in re.split(r"\s+", each_sentence) if each_token
        ]
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
