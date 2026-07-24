"""Constants for the build_per_artifact_batch script.

Scalar and CLI tokens for emitting a per-artifact grok batch specification.
Shared batch-spec key names and worker defaults live in ``grok_worker_constants``.
"""

from __future__ import annotations

from dev_env_scripts_constants.grok_worker_constants import (
    DEFAULT_ROLE,
    DEFAULT_WORKER_MAX_TURNS,
    DEFAULT_WORKER_TIMEOUT_SECONDS,
    TOOL_PROFILE_BUILD,
    UTF8_ENCODING,
)

DEFAULT_OUT_FILENAME: str = "per_artifact_batch.json"
"""Default basename for the emitted batch-spec file under ``--cwd``."""

ARTIFACT_ROLE_PATH_SEPARATOR: str = "="
"""Token that splits ``ROLE_NAME=EVIDENCE_PATH`` on each ``--artifact`` value."""

JSON_INDENT_SPACES: int = 2
"""Indent width used when serializing the batch-spec JSON."""

CLI_BRIEF_FLAG: str = "--brief"
"""CLI flag naming the shared per-artifact brief file."""

CLI_CWD_FLAG: str = "--cwd"
"""CLI flag naming the working directory every worker receives."""

CLI_OUT_FLAG: str = "--out"
"""CLI flag naming the path that receives the batch-spec JSON."""

CLI_ARTIFACT_FLAG: str = "--artifact"
"""CLI flag naming one ``ROLE_NAME=EVIDENCE_PATH`` pair (repeatable)."""

CLI_TOOL_PROFILE_FLAG: str = "--tool-profile"
"""CLI flag naming the tool profile applied to every worker."""

CLI_TIMEOUT_SECONDS_FLAG: str = "--timeout-seconds"
"""CLI flag naming the per-worker timeout in seconds."""

CLI_MAX_TURNS_FLAG: str = "--max-turns"
"""CLI flag naming the per-worker max-turns cap."""

CLI_ROLE_FLAG: str = "--role"
"""CLI flag naming the preflight role recorded on the batch specification."""

DEFAULT_SHOULD_PING: bool = False
"""``should_ping`` value written on every emitted batch specification."""

EXIT_SUCCESS: int = 0
"""Process exit code when the batch spec is written successfully."""

EXIT_FAILURE: int = 1
"""Process exit code when validation fails (``BatchBuildError``)."""

STDERR_ERROR_PREFIX: str = "build-per-artifact-batch failed: "
"""Prefix on the stderr line printed when ``BatchBuildError`` is raised."""

# Re-export shared defaults so callers and the script share one import surface.
__all__ = (
    "ARTIFACT_ROLE_PATH_SEPARATOR",
    "CLI_ARTIFACT_FLAG",
    "CLI_BRIEF_FLAG",
    "CLI_CWD_FLAG",
    "CLI_MAX_TURNS_FLAG",
    "CLI_OUT_FLAG",
    "CLI_ROLE_FLAG",
    "CLI_TIMEOUT_SECONDS_FLAG",
    "CLI_TOOL_PROFILE_FLAG",
    "DEFAULT_OUT_FILENAME",
    "DEFAULT_ROLE",
    "DEFAULT_SHOULD_PING",
    "DEFAULT_WORKER_MAX_TURNS",
    "DEFAULT_WORKER_TIMEOUT_SECONDS",
    "EXIT_FAILURE",
    "EXIT_SUCCESS",
    "JSON_INDENT_SPACES",
    "STDERR_ERROR_PREFIX",
    "TOOL_PROFILE_BUILD",
    "UTF8_ENCODING",
)
