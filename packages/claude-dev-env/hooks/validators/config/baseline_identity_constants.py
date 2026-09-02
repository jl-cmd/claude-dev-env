"""Patterns and placeholders the baseline gate masks a violation message with.

Config files are exempt from the string-literal magic-value checks, so the
regex fragments and the placeholder text the scope-agnostic message shape needs
live here rather than inline in ``run_all_validators.py``.
"""

QUALIFIED_SCOPE_NAME_SEPARATOR = "."
WORD_BOUNDARY_PATTERN = r"\b"
STANDALONE_NUMBER_PATTERN = r"(?<![A-Za-z0-9_])\d+(?![A-Za-z0-9_])"
SCOPE_NAME_PLACEHOLDER = "<name>"
SHAPE_NUMBER_PLACEHOLDER = "<number>"
