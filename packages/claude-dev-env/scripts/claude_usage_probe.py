#!/usr/bin/env python3
"""Thin wrapper over the usage-pause session meter for claude-review.

Composes ``skills/usage-pause/scripts/resolve_usage_window.py`` (OAuth
usage endpoint) and prints a skill-facing JSON report. Does not implement a
second OAuth client.

::

    python claude_usage_probe.py
    {"session_utilization": 42.0, "weekly_utilization": 63.0,
     "weekly_near_cap": false, "session_has_usage_left": true,
     "source": "probe", "probe_ok": true}

``session_has_usage_left`` is true when ``session_utilization`` is not null
and strictly below ``SESSION_UTILIZATION_NO_USAGE_THRESHOLD``, false when
at or above the threshold, and null when the session meter is unknown.
Probe failure never invents meters: ``probe_ok`` is false and
``source`` is ``unavailable``.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from dev_env_scripts_constants.claude_chain_constants import (  # noqa: E402
    CLAUDE_HOME_SUBDIRECTORY,
)
from dev_env_scripts_constants.claude_usage_probe_constants import (  # noqa: E402
    EXIT_CODE_PROBE_REPORT,
    RESOLVE_USAGE_WINDOW_SCRIPT_NAME,
    RESULT_KEY_PROBE_OK,
    RESULT_KEY_SESSION_HAS_USAGE_LEFT,
    RESULT_KEY_SESSION_UTILIZATION,
    RESULT_KEY_SOURCE,
    RESULT_KEY_WEEKLY_NEAR_CAP,
    RESULT_KEY_WEEKLY_UTILIZATION,
    SESSION_UTILIZATION_NO_USAGE_THRESHOLD,
    SKILLS_DIRECTORY_NAME,
    SOURCE_UNAVAILABLE,
    USAGE_PAUSE_SCRIPTS_DIRECTORY_NAME,
    USAGE_PAUSE_SKILL_NAME,
    USAGE_PROBE_DECODE_ERROR_POLICY,
    USAGE_PROBE_ENCODING,
    USAGE_PROBE_SUBPROCESS_TIMEOUT_SECONDS,
)

TextCapturingSubprocessRunner = Callable[
    ...,
    subprocess.CompletedProcess[str],
]

usage_probe_subprocess_runner: TextCapturingSubprocessRunner = subprocess.run
usage_probe_package_root: Path | None = None
usage_probe_home_directory: Path | None = None
usage_probe_resolve_script_path: Path | None = None


@dataclass(frozen=True)
class ClaudeUsageProbeReport:
    """Skill-facing report from one Claude session usage probe.

    ::

        session_utilization=42, weekly_near_cap=False
            # ok: session_has_usage_left True, probe_ok True
        session_utilization=100
            # flag: session_has_usage_left False (force chain)
        probe_ok=False, source="unavailable"
            # flag: meters null; skill still proceeds

    Attributes:
        session_utilization: Percent of the 5-hour window spent, or None.
        weekly_utilization: Percent of the weekly window spent, or None.
        weekly_near_cap: Weekly near-cap WARN flag, or None when unknown.
        session_has_usage_left: True when session meter is known and below
            threshold; False when drained; None when unknown.
        source: Resolver source label, or ``unavailable``.
        probe_ok: True only when the usage-pause resolver succeeded.
    """

    session_utilization: float | None
    weekly_utilization: float | None
    weekly_near_cap: bool | None
    session_has_usage_left: bool | None
    source: str
    probe_ok: bool


def locate_resolve_usage_window_script() -> Path:
    """Return the usage-pause resolver path (checkout first, then install).

    ::

        locate_resolve_usage_window_script()
            # ok: <package>/skills/usage-pause/scripts/resolve_usage_window.py
            # or ~/.claude/skills/usage-pause/scripts/resolve_usage_window.py

    Returns:
        Absolute path to ``resolve_usage_window.py``. The checkout path wins
        when the file exists; otherwise the installed ``~/.claude`` path is
        returned even when missing so callers can report unavailable.
    """
    package_root = (
        usage_probe_package_root
        if usage_probe_package_root is not None
        else Path(__file__).resolve().parent.parent
    )
    checkout_script_path = (
        package_root
        / SKILLS_DIRECTORY_NAME
        / USAGE_PAUSE_SKILL_NAME
        / USAGE_PAUSE_SCRIPTS_DIRECTORY_NAME
        / RESOLVE_USAGE_WINDOW_SCRIPT_NAME
    )
    if checkout_script_path.is_file():
        return checkout_script_path
    home_directory = (
        usage_probe_home_directory
        if usage_probe_home_directory is not None
        else Path.home()
    )
    return (
        home_directory
        / CLAUDE_HOME_SUBDIRECTORY
        / SKILLS_DIRECTORY_NAME
        / USAGE_PAUSE_SKILL_NAME
        / USAGE_PAUSE_SCRIPTS_DIRECTORY_NAME
        / RESOLVE_USAGE_WINDOW_SCRIPT_NAME
    )


def session_has_usage_left_from_utilization(
    session_utilization: float | None,
) -> bool | None:
    """Decide whether the 5-hour session meter still has usage left.

    ::

        session_has_usage_left_from_utilization(42.0)   # ok: True
        session_has_usage_left_from_utilization(100.0)  # ok: False
        session_has_usage_left_from_utilization(None)   # ok: None

    Args:
        session_utilization: Percent of the 5-hour window spent, or null.

    Returns:
        True when utilization is known and strictly below
        ``SESSION_UTILIZATION_NO_USAGE_THRESHOLD``, False when known and at or
        above that threshold, None when unknown.
    """
    if session_utilization is None:
        return None
    no_usage_threshold = SESSION_UTILIZATION_NO_USAGE_THRESHOLD
    return session_utilization < no_usage_threshold


def should_force_chain_mode(session_has_usage_left: bool | None) -> bool:
    """Return True when a drained primary session must force chain mode.

    ::

        should_force_chain_mode(False)  # ok: True
        should_force_chain_mode(True)   # ok: False
        should_force_chain_mode(None)   # ok: False

    Args:
        session_has_usage_left: Probe decision, or None when the meter is
            unknown / the probe failed.

    Returns:
        True only when the probe proved the primary session has no usage left.
    """
    return session_has_usage_left is False


def build_unavailable_usage_probe_report() -> ClaudeUsageProbeReport:
    """Return the report used when the usage-pause resolver is unavailable.

    ::

        build_unavailable_usage_probe_report().probe_ok  # ok: False

    Returns:
        Report with null meters, null ``session_has_usage_left``,
        ``source`` unavailable, and ``probe_ok`` false.
    """
    return ClaudeUsageProbeReport(
        session_utilization=None,
        weekly_utilization=None,
        weekly_near_cap=None,
        session_has_usage_left=None,
        source=SOURCE_UNAVAILABLE,
        probe_ok=False,
    )


def build_usage_probe_report(
    *,
    session_utilization: float | None,
    weekly_utilization: float | None,
    weekly_near_cap: bool | None,
    source: str,
) -> ClaudeUsageProbeReport:
    """Build the skill-facing report from resolved usage-pause fields.

    ::

        build_usage_probe_report(
            session_utilization=10,
            weekly_utilization=20,
            weekly_near_cap=False,
            source="probe",
        ).session_has_usage_left  # ok: True

    Args:
        session_utilization: Percent of the 5-hour window spent, or null.
        weekly_utilization: Percent of the weekly window spent, or null.
        weekly_near_cap: Weekly near-cap flag, or null when unknown.
        source: Resolver source label from usage-pause.

    Returns:
        Skill-facing report with ``session_has_usage_left`` and ``probe_ok``.
    """
    return ClaudeUsageProbeReport(
        session_utilization=session_utilization,
        weekly_utilization=weekly_utilization,
        weekly_near_cap=weekly_near_cap,
        session_has_usage_left=session_has_usage_left_from_utilization(
            session_utilization
        ),
        source=source,
        probe_ok=True,
    )


def probe_claude_usage() -> ClaudeUsageProbeReport:
    """Run the usage-pause resolver and return the skill-facing report.

    ::

        probe_claude_usage()  # ok: ClaudeUsageProbeReport(...)

    Returns:
        Skill-facing report. Never raises for resolver failure; returns the
        unavailable report instead.
    """
    script_path = (
        usage_probe_resolve_script_path
        if usage_probe_resolve_script_path is not None
        else locate_resolve_usage_window_script()
    )
    if not script_path.is_file():
        return build_unavailable_usage_probe_report()
    try:
        completed_process = usage_probe_subprocess_runner(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            encoding=USAGE_PROBE_ENCODING,
            errors=USAGE_PROBE_DECODE_ERROR_POLICY,
            timeout=USAGE_PROBE_SUBPROCESS_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return build_unavailable_usage_probe_report()
    if completed_process.returncode != 0:
        return build_unavailable_usage_probe_report()
    return _report_from_resolver_stdout(completed_process.stdout)


def encode_usage_probe_report(probe_report: ClaudeUsageProbeReport) -> str:
    """Serialize a usage-probe report as one JSON line for stdout.

    Args:
        probe_report: Report from ``probe_claude_usage``.

    Returns:
        JSON text with a trailing newline.
    """
    encoded_payload = {
        RESULT_KEY_SESSION_UTILIZATION: probe_report.session_utilization,
        RESULT_KEY_WEEKLY_UTILIZATION: probe_report.weekly_utilization,
        RESULT_KEY_WEEKLY_NEAR_CAP: probe_report.weekly_near_cap,
        RESULT_KEY_SESSION_HAS_USAGE_LEFT: probe_report.session_has_usage_left,
        RESULT_KEY_SOURCE: probe_report.source,
        RESULT_KEY_PROBE_OK: probe_report.probe_ok,
    }
    return json.dumps(encoded_payload) + "\n"


def main(all_command_arguments: Sequence[str] | None = None) -> int:
    """Run the probe CLI and print one JSON report on stdout.

    Args:
        all_command_arguments: Unused argv after the program name (reserved).

    Returns:
        ``EXIT_CODE_PROBE_REPORT`` after writing a report, including when
        ``probe_ok`` is false. Operational probe failure is encoded in the
        report rather than a non-zero exit.
    """
    del all_command_arguments
    probe_report = probe_claude_usage()
    sys.stdout.write(encode_usage_probe_report(probe_report))
    return EXIT_CODE_PROBE_REPORT


def _as_optional_float(maybe_number: object) -> float | None:
    if maybe_number is None:
        return None
    if isinstance(maybe_number, bool):
        return None
    if isinstance(maybe_number, (int, float)):
        return float(maybe_number)
    return None


def _as_optional_bool(maybe_flag: object) -> bool | None:
    if isinstance(maybe_flag, bool):
        return maybe_flag
    return None


def _report_from_resolver_stdout(
    resolver_stdout: str | None,
) -> ClaudeUsageProbeReport:
    try:
        decoded_payload = json.loads(resolver_stdout or "")
    except json.JSONDecodeError:
        return build_unavailable_usage_probe_report()
    if not isinstance(decoded_payload, dict):
        return build_unavailable_usage_probe_report()
    maybe_source = decoded_payload.get(RESULT_KEY_SOURCE)
    if not isinstance(maybe_source, str) or not maybe_source:
        return build_unavailable_usage_probe_report()
    return build_usage_probe_report(
        session_utilization=_as_optional_float(
            decoded_payload.get(RESULT_KEY_SESSION_UTILIZATION)
        ),
        weekly_utilization=_as_optional_float(
            decoded_payload.get(RESULT_KEY_WEEKLY_UTILIZATION)
        ),
        weekly_near_cap=_as_optional_bool(
            decoded_payload.get(RESULT_KEY_WEEKLY_NEAR_CAP)
        ),
        source=maybe_source,
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
