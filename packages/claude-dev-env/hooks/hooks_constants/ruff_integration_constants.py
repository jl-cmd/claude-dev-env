"""Ruff argv tokens shared by the staged and native check command builders.

The ruff integration assembles two command lines — a stdin-piped staged check
and a native file check — from the same executable, subcommand, and concise
output format. These tokens live here so the integration module carries no
inline argv literals.
"""

__all__ = [
    "RUFF_CHECK_SUBCOMMAND",
    "RUFF_CONCISE_OUTPUT_FORMAT",
    "RUFF_CONFIG_FLAG",
    "RUFF_EXECUTABLE",
    "RUFF_FIXED_SUMMARY_TOKEN",
    "RUFF_FORCE_EXCLUDE_FLAG",
    "RUFF_OUTPUT_FORMAT_FLAG",
    "RUFF_STDIN_FILENAME_FLAG",
    "RUFF_STDIN_MARKER",
]

RUFF_EXECUTABLE: str = "ruff"
RUFF_CHECK_SUBCOMMAND: str = "check"
RUFF_CONFIG_FLAG: str = "--config"
RUFF_OUTPUT_FORMAT_FLAG: str = "--output-format"
RUFF_CONCISE_OUTPUT_FORMAT: str = "concise"
RUFF_FORCE_EXCLUDE_FLAG: str = "--force-exclude"
RUFF_STDIN_FILENAME_FLAG: str = "--stdin-filename"
RUFF_STDIN_MARKER: str = "-"
RUFF_FIXED_SUMMARY_TOKEN: str = "Fixed"
