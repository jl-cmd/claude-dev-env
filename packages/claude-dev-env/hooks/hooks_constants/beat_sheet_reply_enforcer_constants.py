"""Tunables for the beat_sheet_reply_enforcer Stop hook.

::

    BEAT_MAXIMUM_WORDS_PER_LINE
        ok:   "Ship the fix today."             flag: a 20-word run-on line
    BEAT_MAXIMUM_LINE_COUNT
        ok:   7 beats                            flag: 14 beats

Holds the beat-shape thresholds the `beat-sheet` skill names (line word cap,
line count cap), the skill-install search paths used to resolve a concrete
`SKILL.md` path for the corrective message, the transcript-record keys used
to detect a `beat-sheet` Skill invocation within the current turn, and the
notice shown when the hook blocks. The reply-length escape prefix and the
jargon wordlist are imported directly from their owning modules
(`eli11_reply_enforcer_constants` and `plain_language_blocker`) rather than
duplicated here.
"""

import os

__all__ = [
    "BEAT_MAXIMUM_LINE_COUNT",
    "BEAT_MAXIMUM_WORDS_PER_LINE",
    "ALL_BEAT_SHEET_SKILL_SEARCH_PATHS",
    "BEAT_SHEET_SKILL_TARGET_NAME",
    "SKILL_TOOL_NAME",
    "TRANSCRIPT_CONTENT_KEY",
    "TRANSCRIPT_MESSAGE_KEY",
    "TRANSCRIPT_PROMPT_ID_KEY",
    "TRANSCRIPT_TOOL_INPUT_KEY",
    "TRANSCRIPT_TOOL_INPUT_SKILL_KEY",
    "TRANSCRIPT_TOOL_NAME_KEY",
    "TRANSCRIPT_TOOL_USE_CONTENT_TYPE",
    "USER_FACING_BEAT_SHEET_NOTICE",
    "VIOLATION_SEPARATOR",
]

BEAT_MAXIMUM_WORDS_PER_LINE = 12
BEAT_MAXIMUM_LINE_COUNT = 10

VIOLATION_SEPARATOR = "; "
USER_FACING_BEAT_SHEET_NOTICE = "Beat-sheet shape violated - rewriting the reply..."

SKILL_TOOL_NAME = "Skill"
BEAT_SHEET_SKILL_TARGET_NAME = "beat-sheet"

_PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ALL_BEAT_SHEET_SKILL_SEARCH_PATHS = [
    os.path.join(_PLUGIN_ROOT, "skills", "beat-sheet", "SKILL.md"),
    os.path.join(os.path.expanduser("~"), ".claude", "skills", "beat-sheet", "SKILL.md"),
]

TRANSCRIPT_PROMPT_ID_KEY = "promptId"
TRANSCRIPT_MESSAGE_KEY = "message"
TRANSCRIPT_CONTENT_KEY = "content"
TRANSCRIPT_TOOL_USE_CONTENT_TYPE = "tool_use"
TRANSCRIPT_TOOL_NAME_KEY = "name"
TRANSCRIPT_TOOL_INPUT_KEY = "input"
TRANSCRIPT_TOOL_INPUT_SKILL_KEY = "skill"
