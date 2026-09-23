"""Ask the Codex account picker for an account before an Astra advisor request."""

from __future__ import annotations

import json
import math
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from advisor_scripts_constants.astra_advisor_constants import (
    ACCOUNT_PICKER_CHOOSE_COMMAND,
    ASTRA_ACCOUNT_PICK_TIMEOUT_REASON,
    ASTRA_ACCOUNT_PICK_TIMEOUT_SECONDS,
    ASTRA_FALLBACK_KIND_BROKEN,
    ASTRA_FALLBACK_KIND_DECLINED,
    ASTRA_PREFLIGHT_FAILURE_REASON,
    CODEX_TIER_NORMAL,
)


@dataclass(frozen=True)
class AstraPreflight:
    eligible: bool
    percent_left: float | None
    reason: str
    fallback_kind: str | None = None
    codex_home: Path | None = None


def _preflight_fallback(
    reason: str, percent_left: float | None, fallback_kind: str
) -> AstraPreflight:
    return AstraPreflight(False, percent_left, reason, fallback_kind)


def _broken(detail: str) -> AstraPreflight:
    return _preflight_fallback(
        f"{ASTRA_PREFLIGHT_FAILURE_REASON}: {detail}", None, ASTRA_FALLBACK_KIND_BROKEN
    )


def _finite_percent(raw_percent: object) -> float | None:
    if isinstance(raw_percent, bool) or not isinstance(raw_percent, (int, float)):
        return None
    return float(raw_percent) if math.isfinite(raw_percent) else None


def _preflight_from_answer(field_by_name: dict[str, object]) -> AstraPreflight:
    if not isinstance(field_by_name.get("tier"), str):
        return _broken("picker answer is malformed")
    if field_by_name["tier"] != CODEX_TIER_NORMAL:
        reason = f"{ASTRA_PREFLIGHT_FAILURE_REASON}: no Codex account has room ({field_by_name.get('reason')})"
        return _preflight_fallback(reason, None, ASTRA_FALLBACK_KIND_DECLINED)
    codex_home = field_by_name.get("codex_home")
    percent_left = _finite_percent(field_by_name.get("percent_left"))
    if not isinstance(codex_home, str) or not codex_home or percent_left is None:
        return _broken("picker answer names no Codex home with room")
    reason = f"{field_by_name.get('account')} has {percent_left:.0f}% left"
    return AstraPreflight(True, percent_left, reason, codex_home=Path(codex_home))


def _run_picker(
    picker_path: Path,
    process_runner: Callable[..., subprocess.CompletedProcess[str]],
) -> subprocess.CompletedProcess[str]:
    return process_runner(
        [sys.executable, str(picker_path), ACCOUNT_PICKER_CHOOSE_COMMAND],
        capture_output=True,
        text=True,
        check=False,
        shell=False,
        timeout=ASTRA_ACCOUNT_PICK_TIMEOUT_SECONDS,
    )


def _preflight_from_picker(completed: subprocess.CompletedProcess[str]) -> AstraPreflight:
    if completed.returncode != 0:
        return _broken(f"picker exit {completed.returncode}")
    try:
        answer = json.loads(completed.stdout)
    except (TypeError, json.JSONDecodeError):
        return _broken("picker answer is malformed")
    if not isinstance(answer, dict):
        return _broken("picker answer is malformed")
    return _preflight_from_answer(answer)


def run_astra_preflight(
    picker_path: Path,
    process_runner: Callable[..., subprocess.CompletedProcess[str]],
) -> AstraPreflight:
    """Run the Codex account picker and decide whether Astra may bind.

    ::

        tier normal, codex-2, 62% left  -> eligible, codex_home of codex-2
        tier luna or wait               -> declined
        picker exit 1, bad JSON, timeout -> broken

    Args:
        picker_path: Path to ``codex_account_choice.py``.
        process_runner: Callable that runs the picker.

    Returns:
        Eligibility, the chosen account's percent left and Codex home, reason, and fallback kind.
    """
    try:
        return _preflight_from_picker(_run_picker(picker_path, process_runner))
    except subprocess.TimeoutExpired as error:
        return _preflight_fallback(
            f"{ASTRA_ACCOUNT_PICK_TIMEOUT_REASON}: {error}", None, ASTRA_FALLBACK_KIND_BROKEN
        )
    except (OSError, subprocess.SubprocessError, TypeError, ValueError) as error:
        return _broken(str(error))
