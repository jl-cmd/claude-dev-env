#!/usr/bin/env python3
"""
Stop hook that routes Claude responses ending on a promise about future work.

When a turn ends on a forward-looking statement of intent ("I'll now run the
tests", "Let me implement the fix"), the agent completes the work with tool
calls during the turn. AskUserQuestion routes work that requires input only the
user can provide. The rule name is long-horizon-autonomy.
"""

import json
import re
import sys
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from blocking.config.prose_style_enforcement_constants import (  # noqa: E402
    prose_style_enforcement_enabled_in_environment,
)
from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402
from hooks_constants.messages import USER_FACING_INTENT_ENDING_NOTICE  # noqa: E402
from hooks_constants.text_stripping import strip_code_and_quotes  # noqa: E402


def extract_final_paragraph(text: str) -> str:
    """Return the last non-empty paragraph of the prose after stripping code and quotes.

    Args:
        text: The raw assistant message to extract the closing paragraph from.
    """
    paragraph_split_pattern = re.compile(r"\n\s*\n")
    prose_text = strip_code_and_quotes(text)
    candidate_paragraphs = [
        each_paragraph.strip()
        for each_paragraph in paragraph_split_pattern.split(prose_text)
        if each_paragraph.strip()
    ]
    if not candidate_paragraphs:
        return ""
    return candidate_paragraphs[-1]


def extract_first_sentence(paragraph: str) -> str:
    """Return the first sentence of a paragraph.

    Args:
        paragraph: The paragraph whose leading sentence is needed.
    """
    sentence_boundary_pattern = re.compile(r"(?<=[.!?])\s+")
    sentences = sentence_boundary_pattern.split(paragraph.strip(), maxsplit=1)
    if not sentences:
        return ""
    return sentences[0].strip()


def find_intent_only_ending(text: str) -> bool:
    """Return whether the final paragraph ends the turn on a promise about undone work.

    Args:
        text: The raw assistant message to evaluate.
    """
    future_intent_opener_pattern = re.compile(
        r"^(?:(?:now|next|then|okay|alright)\s*,?\s*)?"
        r"(?:i['’]ll(?:\s+now|\s+go\s+ahead\s+and|\s+proceed\s+to)?"
        r"|i\s+will"
        r"|i['’]m\s+going\s+to"
        r"|i\s+am\s+going\s+to"
        r"|i['’]m\s+about\s+to"
        r"|i\s+plan\s+to"
        r"|let\s+me"
        r"|let['’]s"
        r"|going\s+to)\b",
        re.IGNORECASE,
    )
    undone_work_verb_pattern = re.compile(
        r"\b(?:run|start|implement|create|write|add|fix|update|check|test|wire"
        r"|build|deploy|push|git\s+commit|commit\s+the\s+changes"
        r"|commit\s+the\s+fix|investigate|set\s+up|refactor|generate"
        r"|install|continue|look\s+into)\b",
        re.IGNORECASE,
    )
    next_steps_lead_in_pattern = re.compile(r"^next\s+steps?:", re.IGNORECASE)
    second_person_subject_pattern = re.compile(
        r"\b(?:you|your|you['’]?re|user['’]?s?)\b",
        re.IGNORECASE,
    )

    final_paragraph = extract_final_paragraph(text)
    if not final_paragraph:
        return False

    if next_steps_lead_in_pattern.match(final_paragraph):
        return not second_person_subject_pattern.search(final_paragraph)

    first_sentence = extract_first_sentence(final_paragraph)
    if not future_intent_opener_pattern.match(first_sentence):
        return False

    return bool(undone_work_verb_pattern.search(first_sentence))


def main() -> None:
    """Read the stop-hook payload and block turns that end on a promise of undone work."""
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if hook_input.get("stop_hook_active", False):
        sys.exit(0)

    if not prose_style_enforcement_enabled_in_environment():
        sys.exit(0)

    assistant_message = hook_input.get("last_assistant_message", "")

    if not assistant_message:
        sys.exit(0)

    if not find_intent_only_ending(assistant_message):
        sys.exit(0)

    block_reason = (
        "LONG-HORIZON-AUTONOMY GUARDRAIL: Complete the promised work with tool calls "
        "during this turn. Route the question through an AskUserQuestion tool call "
        "when the work requires input only the user can provide, then end the turn "
        "cleanly.\n\n"
        "Re-output the complete response with the work performed, per the "
        "long-horizon-autonomy rule."
    )
    block_response = {
        "decision": "block",
        "reason": block_reason,
        "systemMessage": USER_FACING_INTENT_ENDING_NOTICE,
        "suppressOutput": True,
    }
    log_hook_block(
        calling_hook_name="intent_only_ending_blocker.py",
        hook_event="Stop",
        block_reason=block_reason,
    )
    print(json.dumps(block_response))
    sys.exit(0)


if __name__ == "__main__":
    main()
