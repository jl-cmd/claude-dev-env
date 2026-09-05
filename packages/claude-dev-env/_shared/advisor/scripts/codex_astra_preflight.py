"""Evaluate Codex usage before an Astra advisor request."""

from __future__ import annotations

import importlib
import json
import math
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from advisor_scripts_constants.astra_advisor_constants import (
    ASTRA_FALLBACK_KIND_BROKEN,
    ASTRA_FALLBACK_KIND_DECLINED,
    ASTRA_PREFLIGHT_FAILURE_REASON,
    ASTRA_PROBE_TIMEOUT_REASON,
    ASTRA_USAGE_PROBE_TIMEOUT_SECONDS,
)


@dataclass(frozen=True)
class AstraPreflight:
    eligible: bool
    percent_left: float | None
    reason: str
    fallback_kind: str | None = None


def _preflight_fallback(
    reason: str, percent_left: float | None, fallback_kind: str
) -> AstraPreflight:
    return AstraPreflight(False, percent_left, reason, fallback_kind)


def _load_usage_gate(probe_path: Path) -> Callable[[float], bool]:
    probe_directory = str(probe_path.parent)
    if probe_directory not in sys.path:
        sys.path.insert(0, probe_directory)
    return importlib.import_module("codex_usage_probe").is_codex_review_required


def _parse_probe_percent(stdout_text: str) -> tuple[float | None, str | None]:
    try:
        report = json.loads(stdout_text)
    except (TypeError, json.JSONDecodeError):
        return None, "usage report is malformed"
    if not isinstance(report, dict):
        return None, "usage report is malformed"
    raw_percent = report.get("percent_left")
    if isinstance(raw_percent, bool) or not isinstance(raw_percent, (int, float)):
        return None, "usage meter is unknown" if raw_percent is None else "usage meter is malformed"
    percent_left = float(raw_percent)
    if not math.isfinite(percent_left):
        return None, "usage meter is malformed"
    return percent_left, None


def _run_probe(
    probe_path: Path,
    process_runner: Callable[..., subprocess.CompletedProcess[str]],
) -> subprocess.CompletedProcess[str]:
    return process_runner(
        [sys.executable, str(probe_path)],
        capture_output=True,
        text=True,
        check=False,
        shell=False,
        timeout=ASTRA_USAGE_PROBE_TIMEOUT_SECONDS,
    )


def _preflight_from_probe(
    probe_path: Path, completed: subprocess.CompletedProcess[str]
) -> AstraPreflight:
    if completed.returncode != 0:
        reason = f"{ASTRA_PREFLIGHT_FAILURE_REASON}: probe exit {completed.returncode}"
        return _preflight_fallback(reason, None, ASTRA_FALLBACK_KIND_BROKEN)
    percent_left, parse_reason = _parse_probe_percent(completed.stdout)
    if parse_reason is not None or percent_left is None:
        reason = f"{ASTRA_PREFLIGHT_FAILURE_REASON}: {parse_reason or 'usage meter is unknown'}"
        return _preflight_fallback(reason, None, ASTRA_FALLBACK_KIND_BROKEN)
    if not _load_usage_gate(probe_path)(percent_left):
        reason = f"{ASTRA_PREFLIGHT_FAILURE_REASON}: usage meter is at or below the gate"
        return _preflight_fallback(reason, percent_left, ASTRA_FALLBACK_KIND_DECLINED)
    return AstraPreflight(True, percent_left, "usage meter is above the Astra gate")


def run_astra_preflight(
    probe_path: Path,
    process_runner: Callable[..., subprocess.CompletedProcess[str]],
) -> AstraPreflight:
    """Run the usage probe and evaluate Astra eligibility.

    Args:
        probe_path: Path to the installed usage probe.
        process_runner: Callable for executing the probe.

    Returns:
        The meter decision and fallback metadata.
    """
    try:
        completed = _run_probe(probe_path, process_runner)
        return _preflight_from_probe(probe_path, completed)
    except subprocess.TimeoutExpired as error:
        return _preflight_fallback(
            f"{ASTRA_PROBE_TIMEOUT_REASON}: {error}", None, ASTRA_FALLBACK_KIND_BROKEN
        )
    except (OSError, subprocess.SubprocessError, ImportError, AttributeError, TypeError, ValueError) as error:
        return _preflight_fallback(
            f"{ASTRA_PREFLIGHT_FAILURE_REASON}: {error}",
            None,
            ASTRA_FALLBACK_KIND_BROKEN,
        )
