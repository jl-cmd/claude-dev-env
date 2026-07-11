"""Constants for the python-style checks validator.

Two counts the checks compare against. One says how many blank lines belong
between one top-level function and the next. The other says how many
command-line arguments the runner needs before it has a file to check.
"""

__all__ = [
    "EXPECTED_BLANK_LINES_BETWEEN_FUNCTIONS",
    "MINIMUM_ARGUMENT_COUNT",
]

EXPECTED_BLANK_LINES_BETWEEN_FUNCTIONS: int = 2

MINIMUM_ARGUMENT_COUNT: int = 2
