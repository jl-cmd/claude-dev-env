#!/usr/bin/env python3
"""
Stop hook that blocks Claude responses proposing to stop on account of context.

When a turn proposes stopping, summarizing to hand off, or starting a new
session because of context or token limits, the agent is reassured that ample
context remains and forced to continue the work. A mere topical mention of the
word "context" does not fire - only a self-termination or handoff proposal does.
The rule name is long-horizon-autonomy.
"""

import json
import re
import sys
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402
from hooks_constants.messages import USER_FACING_CONTEXT_REASSURANCE_NOTICE  # noqa: E402
from hooks_constants.session_handoff_blocker_constants import (  # noqa: E402
    FIRST_PERSON_SUBJECT_PATTERN,
)


def strip_code_and_quotes(text: str) -> str:
    """Remove code blocks, inline code, and blockquotes to avoid false positives.

    Args:
        text: The raw assistant message to clean.
    """
    code_block_pattern = re.compile(r"```[\s\S]*?```", re.MULTILINE)
    inline_code_pattern = re.compile(r"`[^`]+`")
    quoted_block_pattern = re.compile(r"^>.*$", re.MULTILINE)
    text = code_block_pattern.sub("", text)
    text = inline_code_pattern.sub("", text)
    text = quoted_block_pattern.sub("", text)
    return text


def split_into_sentences(text: str) -> list[str]:
    """Return the non-empty sentences of the prose.

    Args:
        text: The prose to split on sentence boundaries.
    """
    sentence_boundary_pattern = re.compile(r"(?<=[.!?])\s+")
    return [
        each_sentence.strip()
        for each_sentence in sentence_boundary_pattern.split(text)
        if each_sentence.strip()
    ]


def has_first_person_self_termination(text: str) -> bool:
    """Return whether any sentence binds a first-person subject to a stop or handoff cue.

    Args:
        text: The prose to scan sentence by sentence.
    """
    self_termination_cue_pattern = re.compile(
        r"\b(?:stop|summari[sz]\w*|wrap\s+up|wrap\s+things\s+up"
        r"|hand\s+(?:off|it\s+off|this\s+off)|pause"
        r"|continue\s+(?:this|later)|pick\s+(?:this|it)\s+up"
        r"|new\s+session|fresh\s+session|separate\s+session|clean\s+session"
        r"|running\s+(?:low|out)\s+(?:on|of)\s+(?:context|tokens)"
        r"|(?:low|short)\s+on\s+(?:context|tokens))\b",
        re.IGNORECASE,
    )
    for each_sentence in split_into_sentences(text):
        if FIRST_PERSON_SUBJECT_PATTERN.search(
            each_sentence
        ) and self_termination_cue_pattern.search(each_sentence):
            return True
    return False


def has_resource_reference_with_handoff_cue(text: str) -> bool:
    """Return whether any sentence pairs a context/token reference with a stop cue.

    Args:
        text: The prose to scan sentence by sentence.
    """
    resource_reference_pattern = re.compile(
        r"\b(?:context|token)\s+(?:budget|window|limit|count|usage)\b"
        r"|\b(?:low|short)\s+on\s+(?:context|tokens)\b"
        r"|\bto\s+(?:save|conserve|preserve|free\s+up)\s+(?:context|tokens)\b",
        re.IGNORECASE,
    )
    stop_or_handoff_cue_pattern = re.compile(
        r"\b(?:stop|summari[sz]\w*|wrap\s+up|wrap\s+things\s+up|hand\s+off"
        r"|new\s+session|pause|continue\s+later|pick\s+this\s+up\s+later)\b",
        re.IGNORECASE,
    )
    for each_sentence in split_into_sentences(text):
        if resource_reference_pattern.search(
            each_sentence
        ) and stop_or_handoff_cue_pattern.search(each_sentence):
            return True
    return False


def has_first_person_direct_handoff(text: str) -> bool:
    """Return whether any sentence binds a first-person subject to a direct-handoff cue.

    Args:
        text: The prose to scan sentence by sentence.
    """
    new_session_proposal_pattern = re.compile(
        r"\b(?:wrap\s+up|wrap\s+things\s+up|hand\s+off|hand\s+this\s+off"
        r"|hand\s+it\s+off|continue\s+this|continue\s+later|pick\s+this\s+up"
        r"|pick\s+it\s+up|pause|resume)\b"
        r"[^.!?]*"
        r"\b(?:a\s+|the\s+)?(?:new|fresh|separate|clean)\s+session\b",
        re.IGNORECASE,
    )
    running_low_pattern = re.compile(
        r"\brunning\s+(?:low|out)\s+(?:on|of)\s+(?:context|tokens)\b",
        re.IGNORECASE,
    )
    all_direct_handoff_patterns = [
        new_session_proposal_pattern,
        running_low_pattern,
    ]
    for each_sentence in split_into_sentences(text):
        if not FIRST_PERSON_SUBJECT_PATTERN.search(each_sentence):
            continue
        if any(
            each_pattern.search(each_sentence)
            for each_pattern in all_direct_handoff_patterns
        ):
            return True
    return False


def find_session_handoff_proposal(text: str) -> bool:
    """Return whether the message proposes stopping on account of context or tokens.

    Args:
        text: The raw assistant message to evaluate.
    """
    prose_text = strip_code_and_quotes(text)

    if not has_first_person_self_termination(prose_text):
        return False

    if has_first_person_direct_handoff(prose_text):
        return True

    return has_resource_reference_with_handoff_cue(prose_text)


def main() -> None:
    """Read the stop-hook payload and block turns proposing a context-driven handoff."""
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if hook_input.get("stop_hook_active", False):
        sys.exit(0)

    assistant_message = hook_input.get("last_assistant_message", "")

    if not assistant_message:
        sys.exit(0)

    if not find_session_handoff_proposal(assistant_message):
        sys.exit(0)

    block_reason = (
        "LONG-HORIZON-AUTONOMY GUARDRAIL: You have ample context remaining. Do not "
        "stop, summarize, or suggest a new session on account of context limits. "
        "Continue the work.\n\n"
        "Re-output your response continuing the task without the handoff suggestion, "
        "per the long-horizon-autonomy rule."
    )
    block_response = {
        "decision": "block",
        "reason": block_reason,
        "systemMessage": USER_FACING_CONTEXT_REASSURANCE_NOTICE,
        "suppressOutput": True,
    }
    log_hook_block(
        calling_hook_name="session_handoff_blocker.py",
        hook_event="Stop",
        block_reason=block_reason,
    )
    print(json.dumps(block_response))
    sys.exit(0)


if __name__ == "__main__":
    main()
