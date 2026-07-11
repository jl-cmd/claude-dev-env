"""Constants for the Stop-hook dispatcher.

Holds the ordered hosted-hook roster for the Stop chain. The dispatcher imports
this roster to run every Stop hook in registration order inside one process.
"""

from __future__ import annotations

__all__ = [
    "ALL_STOP_HOSTED_HOOK_PATHS",
    "BLOCK_DECISION",
    "DECISION_KEY",
    "REASON_KEY",
]

BLOCK_DECISION = "block"
DECISION_KEY = "decision"
REASON_KEY = "reason"

ALL_STOP_HOSTED_HOOK_PATHS: tuple[str, ...] = (
    "blocking/hedging_language_blocker.py",
    "blocking/question_to_user_enforcer.py",
    "blocking/intent_only_ending_blocker.py",
    "blocking/session_handoff_blocker.py",
    "diagnostic/hook_log_stop_wrapper.py",
)
