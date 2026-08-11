"""Explicit uncertainty labels that co-occur with hedge words in one sentence.

::

    ok:   This claim is unverified; the port is probably down.
    flag: The port is probably down. (no label in that sentence)

A response-wide "unverified" label does not exempt a bare hedge in another
sentence. Classification of matcher precision (OP-07B) uses the same blocking
surface: only hedges that survive this filter count toward hard-block evidence.
"""

from __future__ import annotations

import re

# Sentence ends at . ! ? when followed by space or end; keep the terminator
# attached to the sentence so labels next to periods still match.
SENTENCE_BOUNDARY_PATTERN = re.compile(r"(?<=[.!?])\s+")

ALL_EXPLICIT_UNCERTAINTY_LABEL_PATTERNS = (
    re.compile(r"\bunverified\b", re.IGNORECASE),
    re.compile(r"\bi don't know\b", re.IGNORECASE),
    re.compile(r"\bi do not know\b", re.IGNORECASE),
    re.compile(r"\bno source for this claim\b", re.IGNORECASE),
    re.compile(r"\bwithout a (credible )?source\b", re.IGNORECASE),
    re.compile(r"\bnamed (as )?unverified\b", re.IGNORECASE),
)

HEDGING_TERM_LIST_SEPARATOR = ", "

POSITIVE_CORRECTIVE_GUIDANCE = (
    "Support the claim with evidence. Label the claim unverified until a source or "
    "live probe supports it. Gather a source, run a live probe, or ask through "
    "AskUserQuestion. Re-output the complete revised response."
)

BLOCK_REASON_PREFIX = (
    "ANTI-HALLUCINATION GUARDRAIL: Add an explicit uncertainty label in the same "
    "sentence as the hedging language: "
)
