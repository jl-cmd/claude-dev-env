#!/usr/bin/env python3
"""
Stop hook that blocks Claude responses asking the user questions in prose.

User-directed questions must route through the AskUserQuestion tool so the user
sees structured options with labels. When the final paragraph of the response
ends with a question mark or contains a recognized preamble phrase
("would you like", "should I", "do you want", "want me to", etc.), Claude is
forced to re-output the response with the ask moved into an AskUserQuestion
tool call.
"""

import json
import re
import sys
from pathlib import Path


def _insert_hooks_tree_for_imports() -> None:
    hooks_tree = Path(__file__).resolve().parent.parent
    hooks_tree_string = str(hooks_tree)
    if hooks_tree_string not in sys.path:
        sys.path.insert(0, hooks_tree_string)


_insert_hooks_tree_for_imports()

from config.messages import USER_FACING_ASKUSERQUESTION_NOTICE


def strip_code_and_quotes(text: str) -> str:
    """Remove code blocks, inline code, and blockquotes to avoid false positives."""
    code_block_pattern = re.compile(r"```[\s\S]*?```", re.MULTILINE)
    inline_code_pattern = re.compile(r"`[^`]+`")
    quoted_block_pattern = re.compile(r"^>.*$", re.MULTILINE)
    text = code_block_pattern.sub("", text)
    text = inline_code_pattern.sub("", text)
    text = quoted_block_pattern.sub("", text)
    return text


def extract_final_paragraph(text: str) -> str:
    """Return the last non-empty paragraph of the prose after stripping code and quotes."""
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


def find_user_directed_question_indicators(text: str) -> list[str]:
    """Return indicator names for every user-directed question signal in the final paragraph."""
    all_preamble_patterns = [
        (re.compile(regex_text, re.IGNORECASE), display_name)
        for regex_text, display_name in [
            (r"\bwould\s+you\s+like\b", "would you like"),
            (r"\bshould\s+i\b", "should i"),
            (r"\bdo\s+you\s+want\b", "do you want"),
            (r"\bwhich\s+would\s+you\s+prefer\b", "which would you prefer"),
            (r"\blet\s+me\s+know\s+if\b", "let me know if"),
            (r"\blet\s+me\s+know\s+which\b", "let me know which"),
            (r"\blet\s+me\s+know\s+whether\b", "let me know whether"),
            (r"\bplease\s+confirm\b", "please confirm"),
            (r"\bplease\s+let\s+me\s+know\b", "please let me know"),
            (r"\bwant\s+me\s+to\b", "want me to"),
        ]
    ]
    terminal_question_mark_pattern = re.compile(r"\?[\s\"'\)\]\}]*\Z")
    terminal_question_mark_indicator = "terminal question mark in final paragraph"

    final_paragraph = extract_final_paragraph(text)
    if not final_paragraph:
        return []

    matched_indicators: list[str] = []

    if terminal_question_mark_pattern.search(final_paragraph.rstrip()):
        matched_indicators.append(terminal_question_mark_indicator)

    for each_pattern, each_display_name in all_preamble_patterns:
        if (
            each_pattern.search(final_paragraph)
            and each_display_name not in matched_indicators
        ):
            matched_indicators.append(each_display_name)

    return matched_indicators


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

    matched_indicators = find_user_directed_question_indicators(assistant_message)

    if not matched_indicators:
        sys.exit(0)

    formatted_indicator_list = ", ".join(
        f'"{each_indicator}"' for each_indicator in matched_indicators
    )

    block_response = {
        "decision": "block",
        "reason": (
            f"ASKUSERQUESTION GUARDRAIL: Your response asks the user a question in prose "
            f"(indicators: {formatted_indicator_list}). "
            f"User-directed questions must route through the AskUserQuestion tool so the user "
            f"sees structured options with labels.\n\n"
            f"Re-output your response with the trailing question removed from prose and moved "
            f"into an AskUserQuestion tool call. Rhetorical questions answered in the same "
            f"paragraph are allowed; questions inside code fences, inline code, and blockquotes "
            f"are ignored.\n\n"
            f"You MUST re-output the complete, revised response with the correction applied."
        ),
        "systemMessage": USER_FACING_ASKUSERQUESTION_NOTICE,
        "suppressOutput": True,
    }

    print(json.dumps(block_response))
    sys.exit(0)


if __name__ == "__main__":
    main()
