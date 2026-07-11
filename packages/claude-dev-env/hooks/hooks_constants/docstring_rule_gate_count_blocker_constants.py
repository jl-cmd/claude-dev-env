"""Constants for the docstring-rule gate-count staleness blocker.

The rule file ``docstring-prose-matches-implementation.md`` enumerates the
``check_docstring_*`` gate validators that cover deterministic slices of docstring
prose, both as a spelled-out count ("Three more gate validators", "four gated
slices") and as a backticked list of the validator names. When a new gate
validator is registered but the count word is left unchanged, the rule's stated
count drifts from the validators it actually names — the same companion-doc drift
the rule itself governs. This module holds the target rule basename, the
spelled-out-number lookup, the code-fence pattern that marks lines to skip, the
patterns that find the "<count> more gate validators" and "<count> gated slices"
count clauses and the backticked ``check_*`` validator names, the args-gate name,
the issue budget, and the block-message text the hook emits.
"""

import re

__all__ = [
    "TARGET_RULE_BASENAME",
    "ALL_NUMBER_WORDS_BY_VALUE",
    "CODE_FENCE_PATTERN",
    "FREE_FORM_GATE_COUNT_PATTERN",
    "TOTAL_GATED_SLICE_COUNT_PATTERN",
    "GATE_VALIDATOR_NAME_PATTERN",
    "ARGS_GATE_VALIDATOR_NAME",
    "MAX_GATE_COUNT_ISSUES",
    "GATE_COUNT_MESSAGE_TEMPLATE",
    "GATE_COUNT_SYSTEM_MESSAGE",
    "GATE_COUNT_ADDITIONAL_CONTEXT",
]

TARGET_RULE_BASENAME: str = "docstring-prose-matches-implementation.md"

ALL_NUMBER_WORDS_BY_VALUE: dict[str, int] = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}

CODE_FENCE_PATTERN: re.Pattern[str] = re.compile(r"^\s*(?:```|~~~)")

FREE_FORM_GATE_COUNT_PATTERN: re.Pattern[str] = re.compile(
    r"\b([A-Za-z]+)\s+more\s+gate\s+validators\b",
    re.IGNORECASE,
)

TOTAL_GATED_SLICE_COUNT_PATTERN: re.Pattern[str] = re.compile(
    r"\b([A-Za-z]+)\s+gated\s+slices\b",
    re.IGNORECASE,
)

GATE_VALIDATOR_NAME_PATTERN: re.Pattern[str] = re.compile(r"`(check_[A-Za-z0-9_]+)`")

ARGS_GATE_VALIDATOR_NAME: str = "check_docstring_args_match_signature"

MAX_GATE_COUNT_ISSUES: int = 4

GATE_COUNT_MESSAGE_TEMPLATE: str = (
    "{rule_basename} states '{stated_phrase}' ({stated_count}) but names "
    "{named_count} distinct free-form gate validator(s) ({named_validators}). The "
    "rule's spelled-out gate count drifts from the validators it enumerates — the "
    "companion-doc-vs-implementation drift this rule governs. Update the count "
    "word to {named_count} and the '... gated slices' total to {total_count} in "
    "this same change, and name every gate validator the prose counts."
)

GATE_COUNT_SYSTEM_MESSAGE: str = (
    "Gate-validator count in docstring-prose-matches-implementation.md drifted "
    "from the validators it names - update the count word in this same change"
)

GATE_COUNT_ADDITIONAL_CONTEXT: str = (
    "The rule docstring-prose-matches-implementation.md states a spelled-out "
    "count of free-form docstring gate validators ('Four more gate validators') "
    "and a total ('five gated slices'), then names each validator in backticks "
    "(`check_docstring_fallback_branch_coverage`, ...). When a new "
    "`check_docstring_*` gate is added, name it in the prose and bump both count "
    "words: the 'N more gate validators' count equals the number of distinct "
    "free-form validators named after it, and the 'M gated slices' total equals "
    "that count plus one for check_docstring_args_match_signature. Keep the count "
    "words and the named-validator list in step in the same change."
)
