"""Deterministic graders for the CDE benchmark.

Each grader kind reads a spec from ``cases.json`` and a grading context, and
returns ``pass``, ``fail``, or ``error``. ``error`` means the harness could not
grade (missing file, missing executable, timeout, no transcript). It never
counts as a behavior result.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

GraderStatus = Literal["pass", "fail", "error"]
DEFAULT_COMMAND_TIMEOUT_SECONDS = 120


@dataclass(frozen=True)
class GraderResult:
    grader_id: str
    status: GraderStatus
    detail: str


@dataclass(frozen=True)
class GradingContext:
    work_directory: Path
    case_directory: Path
    result_text: str
    transcript_path: Path | None


@dataclass(frozen=True)
class ToolEvent:
    tool_name: str
    input_text: str


def read_tool_events(transcript_path: Path) -> list[ToolEvent]:
    all_events: list[ToolEvent] = []
    for each_line in transcript_path.read_text(encoding="utf-8").splitlines():
        if not each_line.strip():
            continue
        record = json.loads(each_line)
        message = record.get("message") if isinstance(record, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            continue
        for each_block in content:
            if isinstance(each_block, dict) and each_block.get("type") == "tool_use":
                all_events.append(
                    ToolEvent(
                        tool_name=str(each_block.get("name", "")),
                        input_text=json.dumps(
                            each_block.get("input", {}), sort_keys=True
                        ),
                    )
                )
    return all_events


def _event_matches(event: ToolEvent, matcher: Mapping[str, Any]) -> bool:
    tool_pattern = str(matcher.get("tool", ".*"))
    input_pattern = str(matcher.get("input_regex", ""))
    return bool(re.fullmatch(tool_pattern, event.tool_name)) and bool(
        re.search(input_pattern, event.input_text)
    )


def _matching_positions(
    all_events: list[ToolEvent], matcher: Mapping[str, Any]
) -> list[int]:
    return [
        each_index
        for each_index, each_event in enumerate(all_events)
        if _event_matches(each_event, matcher)
    ]


def _expectation_status(is_found: bool, expectation: str) -> GraderStatus:
    if expectation == "present":
        return "pass" if is_found else "fail"
    if expectation == "absent":
        return "fail" if is_found else "pass"
    return "error"


def grade_command(spec: Mapping[str, Any], context: GradingContext) -> GraderResult:
    grader_id = str(spec["id"])
    overlay_name = spec.get("overlay")
    if overlay_name is not None:
        overlay_directory = context.case_directory / str(overlay_name)
        if not overlay_directory.is_dir():
            return GraderResult(
                grader_id, "error", f"overlay missing: {overlay_directory}"
            )
        shutil.copytree(overlay_directory, context.work_directory, dirs_exist_ok=True)
    all_arguments = [str(each_argument) for each_argument in spec["argv"]]
    bench_directory = context.case_directory.parent.parent
    all_arguments = [
        each_argument.replace("{case}", context.case_directory.as_posix()).replace(
            "{bench}", bench_directory.as_posix()
        )
        for each_argument in all_arguments
    ]
    if all_arguments[0] == "python":
        all_arguments[0] = sys.executable
    try:
        completed = subprocess.run(
            all_arguments,
            cwd=context.work_directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=int(spec.get("timeout_seconds", DEFAULT_COMMAND_TIMEOUT_SECONDS)),
            check=False,
        )
    except FileNotFoundError as missing_executable:
        return GraderResult(
            grader_id, "error", f"executable missing: {missing_executable}"
        )
    except subprocess.TimeoutExpired:
        return GraderResult(grader_id, "error", "command timed out")
    all_error_exits = [int(each_exit) for each_exit in spec.get("error_exits", [])]
    if completed.returncode in all_error_exits:
        return GraderResult(
            grader_id, "error", f"exit {completed.returncode} is a harness exit"
        )
    if completed.returncode != int(spec.get("expect_exit", 0)):
        return GraderResult(grader_id, "fail", f"exit {completed.returncode}")
    expected_fragment = spec.get("stdout_contains")
    if expected_fragment is not None and str(expected_fragment) not in completed.stdout:
        return GraderResult(grader_id, "fail", f"stdout lacks {expected_fragment!r}")
    expected_stdout = spec.get("stdout_equals")
    if expected_stdout is not None and completed.stdout.strip() != str(expected_stdout).strip():
        return GraderResult(grader_id, "fail", f"stdout was {completed.stdout.strip()[:120]!r}")
    return GraderResult(grader_id, "pass", f"exit {completed.returncode}")


def grade_file_regex(spec: Mapping[str, Any], context: GradingContext) -> GraderResult:
    grader_id = str(spec["id"])
    all_paths = sorted(
        each_path
        for each_path in context.work_directory.glob(str(spec["glob"]))
        if each_path.is_file()
    )
    if not all_paths:
        return GraderResult(grader_id, "error", f"glob matched no file: {spec['glob']}")
    pattern = re.compile(str(spec["pattern"]), re.MULTILINE)
    all_hits = [
        each_path.name
        for each_path in all_paths
        if pattern.search(each_path.read_text(encoding="utf-8", errors="replace"))
    ]
    status = _expectation_status(bool(all_hits), str(spec["expect"]))
    return GraderResult(grader_id, status, f"hits: {all_hits}")


def grade_path_exists(spec: Mapping[str, Any], context: GradingContext) -> GraderResult:
    grader_id = str(spec["id"])
    if not context.work_directory.is_dir():
        return GraderResult(grader_id, "error", "work directory missing")
    is_found = (context.work_directory / str(spec["path"])).exists()
    return GraderResult(
        grader_id, _expectation_status(is_found, str(spec["expect"])), str(spec["path"])
    )


def grade_result_regex(
    spec: Mapping[str, Any], context: GradingContext
) -> GraderResult:
    grader_id = str(spec["id"])
    if not context.result_text.strip():
        return GraderResult(grader_id, "error", "empty result text")
    is_found = bool(re.search(str(spec["pattern"]), context.result_text, re.MULTILINE))
    return GraderResult(
        grader_id,
        _expectation_status(is_found, str(spec["expect"])),
        str(spec["pattern"]),
    )


def _events_or_error(
    grader_id: str, context: GradingContext
) -> list[ToolEvent] | GraderResult:
    if context.transcript_path is None or not context.transcript_path.is_file():
        return GraderResult(grader_id, "error", "transcript missing")
    try:
        return read_tool_events(context.transcript_path)
    except json.JSONDecodeError as malformed:
        return GraderResult(grader_id, "error", f"transcript malformed: {malformed}")


def grade_transcript_order(
    spec: Mapping[str, Any], context: GradingContext
) -> GraderResult:
    """Pass when the earliest ``first`` event precedes the earliest ``then`` event."""
    grader_id = str(spec["id"])
    events_or_error = _events_or_error(grader_id, context)
    if isinstance(events_or_error, GraderResult):
        return events_or_error
    all_first_positions = _matching_positions(events_or_error, spec["first"])
    all_then_positions = _matching_positions(events_or_error, spec["then"])
    if not all_first_positions or not all_then_positions:
        return GraderResult(
            grader_id,
            "fail",
            f"first={all_first_positions[:1]} then={all_then_positions[:1]}",
        )
    is_ordered = all_first_positions[0] < all_then_positions[0]
    return GraderResult(
        grader_id,
        "pass" if is_ordered else "fail",
        f"first@{all_first_positions[0]} then@{all_then_positions[0]}",
    )


def grade_transcript_after_last(
    spec: Mapping[str, Any], context: GradingContext
) -> GraderResult:
    """Pass when a ``followed_by`` event occurs after the last ``last_of`` event."""
    grader_id = str(spec["id"])
    events_or_error = _events_or_error(grader_id, context)
    if isinstance(events_or_error, GraderResult):
        return events_or_error
    all_anchor_positions = _matching_positions(events_or_error, spec["last_of"])
    all_follow_positions = _matching_positions(events_or_error, spec["followed_by"])
    if not all_anchor_positions:
        return GraderResult(grader_id, "fail", "no anchor event")
    is_followed = (
        bool(all_follow_positions)
        and all_follow_positions[-1] > all_anchor_positions[-1]
    )
    return GraderResult(
        grader_id,
        "pass" if is_followed else "fail",
        f"last_anchor@{all_anchor_positions[-1]} follow={all_follow_positions[-1:]}",
    )


def grade_transcript_tool_regex(
    spec: Mapping[str, Any], context: GradingContext
) -> GraderResult:
    grader_id = str(spec["id"])
    events_or_error = _events_or_error(grader_id, context)
    if isinstance(events_or_error, GraderResult):
        return events_or_error
    all_positions = _matching_positions(events_or_error, spec["match"])
    status = _expectation_status(bool(all_positions), str(spec["expect"]))
    return GraderResult(grader_id, status, f"positions: {all_positions[:5]}")


GRADER_BY_KIND: dict[
    str, Callable[[Mapping[str, Any], GradingContext], GraderResult]
] = {
    "command": grade_command,
    "file_regex": grade_file_regex,
    "path_exists": grade_path_exists,
    "result_regex": grade_result_regex,
    "transcript_order": grade_transcript_order,
    "transcript_after_last": grade_transcript_after_last,
    "transcript_tool_regex": grade_transcript_tool_regex,
}


def run_graders(
    all_specs: list[Mapping[str, Any]], context: GradingContext
) -> list[GraderResult]:
    all_results: list[GraderResult] = []
    for each_spec in all_specs:
        grader = GRADER_BY_KIND.get(str(each_spec.get("kind")))
        if grader is None:
            all_results.append(
                GraderResult(
                    str(each_spec.get("id")),
                    "error",
                    f"unknown kind: {each_spec.get('kind')}",
                )
            )
            continue
        all_results.append(grader(each_spec, context))
    return all_results
