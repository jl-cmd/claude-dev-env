#!/usr/bin/env python3
"""
Stop hook that blocks Claude responses containing hedging language.

Words like "likely", "probably", "presumably" signal unverified claims.
When detected, Claude is forced to re-check and respond with verified facts.
"""

import json
import os
import re
import sys
from pathlib import Path


def _insert_hooks_tree_for_imports() -> None:
    hooks_tree = Path(__file__).resolve().parent.parent
    hooks_tree_string = str(hooks_tree)
    if hooks_tree_string not in sys.path:
        sys.path.insert(0, hooks_tree_string)


_insert_hooks_tree_for_imports()

from config.messages import USER_FACING_NOTICE

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

CODE_BLOCK_PATTERN = re.compile(r"```[\s\S]*?```", re.MULTILINE)
INLINE_CODE_PATTERN = re.compile(r"`[^`]+`")
QUOTED_BLOCK_PATTERN = re.compile(r"^>.*$", re.MULTILINE)


def strip_code_and_quotes(text: str) -> str:
    """Remove code blocks, inline code, and blockquotes to avoid false positives."""
    text = CODE_BLOCK_PATTERN.sub("", text)
    text = INLINE_CODE_PATTERN.sub("", text)
    text = QUOTED_BLOCK_PATTERN.sub("", text)
    return text


def find_hedging_words(text: str) -> list[str]:
    """Return all hedging words/phrases found in the text."""
    prose_text = strip_code_and_quotes(text)
    matched_terms = []

    for pattern in ALL_HEDGING_PATTERNS:
        all_matches = pattern.findall(prose_text)
        for each_match in all_matches:
            normalized_term = each_match.strip().lower()
            if normalized_term not in matched_terms:
                matched_terms.append(normalized_term)

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

    found_hedging_terms = find_hedging_words(assistant_message)

    if not found_hedging_terms:
        sys.exit(0)

    formatted_term_list = ", ".join(f'"{term}"' for term in found_hedging_terms)

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
            "(no research-mode skill installed; verify with sources or reply 'I don't know')"
        )

    block_response = {
        "decision": "block",
        "reason": (
            f"ANTI-HALLUCINATION GUARDRAIL: Your response contains hedging language: "
            f"{formatted_term_list}. "
            f"These words signal unverified claims. You MUST rewrite your response "
            f"{skill_reference}\n\n"
            f"Do NOT simply remove the hedging word and keep the unverified claim. "
            f"Either VERIFY it with a source or replace it with 'I don't know'.\n\n"
            f"You MUST re-output the complete, revised response with the corrections applied."
        ),
        "systemMessage": USER_FACING_NOTICE,
        "suppressOutput": True,
    }

    print(json.dumps(block_response))
    sys.exit(0)


if __name__ == "__main__":
    main()
