#!/usr/bin/env python3
"""Stop hook for bare hedging words that mark unverified claims.

Words like "likely" or "probably" stand in for evidence. When prose-style
enforcement is on, a hedge word blocks the response unless the same sentence
carries an explicit uncertainty label (unverified, I don't know, no source for
this claim). A label in another sentence does not exempt a bare hedge.

::

    pass:  This claim is unverified; the deploy is probably blocked.
    flag:  This claim is unverified. The deploy is probably blocked.

When enforcement is off, surviving bare hedges emit privacy-safe advisory
candidates (OP-07B). See rules/hedging-claims.md and
docs/references/prose-style-enforcement.md.
"""

import json
import os
import re
import sys
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from blocking.config.prose_style_enforcement_constants import (  # noqa: E402
    prose_style_enforcement_enabled_in_environment,
)
from hooks_constants.hedging_uncertainty_constants import (  # noqa: E402
    ALL_EXPLICIT_UNCERTAINTY_LABEL_PATTERNS,
    BLOCK_REASON_PREFIX,
    HEDGING_TERM_LIST_SEPARATOR,
    POSITIVE_CORRECTIVE_GUIDANCE,
    SENTENCE_BOUNDARY_PATTERN,
)
from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402
from hooks_constants.messages import USER_FACING_NOTICE  # noqa: E402
from hooks_constants.prose_matcher_precision_constants import (  # noqa: E402
    MATCHER_ID_HEDGING_WORD,
    MAXIMUM_ADVISORY_EMITS_PER_CALL,
)
from hooks_constants.text_stripping import strip_code_and_quotes  # noqa: E402
from observability.prose_matcher_advisory import emit_advisory_candidate  # noqa: E402

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RESEARCH_MODE_SKILL_SEARCH_PATHS = [
    os.path.join(PLUGIN_ROOT, "skills", "research-mode", "SKILL.md"),
    os.path.join(os.path.expanduser("~"), ".claude", "skills", "research-mode", "SKILL.md"),
    os.path.join(os.path.expanduser("~"), ".claude", "plugins", "marketplaces", "claude-deep-research", "skills", "research-mode", "SKILL.md"),
]

HEDGING_WORDS = [
    r"\blikely\b",
    r"\bunlikely\b",
    r"\bprobably\b",
    r"\bprobable\b",
    r"\bpresumably\b",
    r"\bperhaps\b",
    r"\bpossibly\b",
    r"\bseemingly\b",
    r"\bapparently\b",
    r"\barguably\b",
    r"\bsupposedly\b",
    r"\bostensibly\b",
    r"\bconceivably\b",
    r"\bplausibly\b",
]

HEDGING_PHRASES = [
    r"\bmight be\b",
    r"\bcould be\b",
    r"\bseems to be\b",
    r"\bappears to be\b",
    r"\bin all likelihood\b",
    r"\bmore likely than not\b",
    r"\bit.s possible that\b",
]

ALL_HEDGING_PATTERNS = [
    re.compile(pattern, re.IGNORECASE) for pattern in HEDGING_WORDS + HEDGING_PHRASES
]


def _sentence_carries_explicit_uncertainty(sentence: str) -> bool:
    """Return True when the sentence labels the claim as unknown or unverified."""
    for each_label_pattern in ALL_EXPLICIT_UNCERTAINTY_LABEL_PATTERNS:
        if each_label_pattern.search(sentence):
            return True
    return False


def _hedging_terms_in_prose_slice(prose_slice: str) -> list[str]:
    """Return unique hedge terms found in one prose slice (sentence or full text)."""
    matched_terms: list[str] = []
    for each_pattern in ALL_HEDGING_PATTERNS:
        for each_match in each_pattern.findall(prose_slice):
            normalized_term = each_match.strip().lower()
            if normalized_term not in matched_terms:
                matched_terms.append(normalized_term)
    return matched_terms


def find_hedging_words(text: str) -> list[str]:
    """Return all hedging words/phrases in the stripped prose (any sentence)."""
    prose_text = strip_code_and_quotes(text)
    return _hedging_terms_in_prose_slice(prose_text)


def find_blocking_hedging_terms(text: str) -> list[str]:
    """Return hedge terms that lack an explicit uncertainty label in-sentence.

    ::

        find_blocking_hedging_terms("Unverified: the port is probably down.")
            -> []
        find_blocking_hedging_terms("Unverified. The port is probably down.")
            -> ["probably"]

    Args:
        text: Full assistant message, including code and quotes.

    Returns:
        Unique bare hedge terms that still warrant a block or advisory emit.
    """
    prose_text = strip_code_and_quotes(text)
    if not prose_text.strip():
        return []

    all_sentences = SENTENCE_BOUNDARY_PATTERN.split(prose_text)
    if len(all_sentences) <= 1:
        all_sentences = [prose_text]

    matched_terms: list[str] = []
    for each_sentence in all_sentences:
        if not each_sentence.strip():
            continue
        if _sentence_carries_explicit_uncertainty(each_sentence):
            continue
        for each_term in _hedging_terms_in_prose_slice(each_sentence):
            if each_term not in matched_terms:
                matched_terms.append(each_term)
    return matched_terms


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if hook_input.get("stop_hook_active", False):
        sys.exit(0)

    assistant_message = hook_input.get("last_assistant_message", "")

    if not assistant_message:
        sys.exit(0)

    found_hedging_terms = find_blocking_hedging_terms(assistant_message)

    if not found_hedging_terms:
        sys.exit(0)

    if not prose_style_enforcement_enabled_in_environment():
        try:
            for each_term in found_hedging_terms[:MAXIMUM_ADVISORY_EMITS_PER_CALL]:
                emit_advisory_candidate(
                    MATCHER_ID_HEDGING_WORD,
                    "Stop",
                    f"{each_term}:{assistant_message[:120]}",
                )
        except (ImportError, OSError, TypeError, ValueError):
            pass
        sys.exit(0)

    formatted_term_list = HEDGING_TERM_LIST_SEPARATOR.join(
        f'"{term}"' for term in found_hedging_terms
    )

    resolved_skill_path: str | None = None
    for each_skill_path in RESEARCH_MODE_SKILL_SEARCH_PATHS:
        if os.path.exists(each_skill_path):
            resolved_skill_path = each_skill_path
            break

    if resolved_skill_path is not None:
        skill_reference = f"under the research-mode constraints defined in:\n\n{resolved_skill_path}"
    else:
        skill_reference = (
            "under research-mode constraints "
            "(no research-mode skill installed; verify with sources or prompt the user via AskUserQuestion with potential options + context)"
        )

    block_reason = (
        f"{BLOCK_REASON_PREFIX}{formatted_term_list}. "
        f"Rewrite {skill_reference}\n\n"
        f"{POSITIVE_CORRECTIVE_GUIDANCE}"
    )
    block_response = {
        "decision": "block",
        "reason": block_reason,
        "systemMessage": USER_FACING_NOTICE,
        "suppressOutput": True,
    }
    log_hook_block(
        calling_hook_name="hedging_language_blocker.py",
        hook_event="Stop",
        block_reason=block_reason,
    )
    print(json.dumps(block_response))
    sys.exit(0)


if __name__ == "__main__":
    main()