"""Shared compiled patterns for the session_handoff_blocker hook."""

import re

FIRST_PERSON_SUBJECT_PATTERN = re.compile(
    r"\b(?:i['’]?m|i['’]?ll|i\s+will|i\s+am|i\s+need\s+to|i\s+should"
    r"|i\s+recommend|i\s+suggest|let\s+me|let['’]?s"
    r"|we\s+(?:should|can|could)|we['’]?ll|we\s+are|we\s+will)\b",
    re.IGNORECASE,
)
