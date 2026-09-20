"""Deterministic graders for the CDE benchmark.

Each grader kind reads a spec from ``cases.json`` and a grading context, and
returns ``pass``, ``fail``, or ``error``. ``error`` means the harness could not
grade (missing file, missing executable, timeout, no transcript). It never
counts as a behavior score.
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
from typing import Literal

from bench_parts.config.graders_constants import (
    DEFAULT_COMMAND_TIMEOUT_SECONDS,
    DETAIL_CHARACTER_LIMIT,
)

GraderStatus = Literal["pass", "fail", "error"]


@dataclass(frozen=True)
class GraderVerdict:
    grader_id: str
    status: GraderStatus
    detail: str


@dataclass(frozen=True)
class GradingContext:
    work_directory: Path
    case_directory: Path
    reply_text: str
    transcript_path: Path | None


@dataclass(frozen=True)
class ToolEvent:
    tool_name: str
    input_text: str


def _all_tool_use_records(record: object) -> list[Mapping[str, object]]:
    if not isinstance(record, dict):
        return []
    message = record.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, list):
        return []
    return [
        each_block
        for each_block in content
        if isinstance(each_block, dict) and each_block.get("type") == "tool_use"
    ]


def read_tool_events(transcript_path: Path) -> list[ToolEvent]:
    """Read one session transcript into the tool calls it holds.

    ::

        a line with a tool_use block   ->   one ToolEvent, input as sorted JSON
        a blank line                   ->   skipped

    Args:
        transcript_path: The JSONL transcript a session wrote.

    Returns:
        The tool calls in the order the session made them.
    """
    all_events: list[ToolEvent] = []
    for each_line in transcript_path.read_text(encoding="utf-8").splitlines():
        if not each_line.strip():
            continue
        for each_block in _all_tool_use_records(json.loads(each_line)):
            all_events.append(
                ToolEvent(
                    tool_name=str(each_block.get("name", "")),
                    input_text=json.dumps(each_block.get("input", {}), sort_keys=True),
                )
            )
    return all_events


def _event_matches(event: ToolEvent, all_matcher_fields: Mapping[str, object]) -> bool:
    tool_pattern = str(all_matcher_fields.get("tool", ".*"))
    input_pattern = str(all_matcher_fields.get("input_regex", ""))
    return bool(re.fullmatch(tool_pattern, event.tool_name)) and bool(
        re.search(input_pattern, event.input_text)
    )


def _matching_positions(
    all_events: list[ToolEvent], all_matcher_fields: Mapping[str, object]
) -> list[int]:
    return [
        each_index
        for each_index, each_event in enumerate(all_events)
        if _event_matches(each_event, all_matcher_fields)
    ]


def _expectation_status(is_found: bool, expectation: str) -> GraderStatus:
    if expectation == "present":
        return "pass" if is_found else "fail"
    if expectation == "absent":
        return "fail" if is_found else "pass"
    return "error"


def _overlay_failure(
    grader_id: str, all_spec_fields: Mapping[str, object], context: GradingContext
) -> GraderVerdict | None:
    overlay_name = all_spec_fields.get("overlay")
    if overlay_name is None:
        return None
    overlay_directory = context.case_directory / str(overlay_name)
    if not overlay_directory.is_dir():
        return GraderVerdict(grader_id, "error", f"overlay missing: {overlay_directory}")
    shutil.copytree(overlay_directory, context.work_directory, dirs_exist_ok=True)
    return None


def _prepared_arguments(
    all_spec_fields: Mapping[str, object], context: GradingContext
) -> list[str]:
    bench_directory = context.case_directory.parent.parent
    all_arguments = [
        str(each_argument)
        .replace("{case}", context.case_directory.as_posix())
        .replace("{bench}", bench_directory.as_posix())
        for each_argument in all_spec_fields["argv"]
    ]
    if all_arguments[0] == "python":
        all_arguments[0] = sys.executable
    return all_arguments


def _command_verdict(
    grader_id: str,
    all_spec_fields: Mapping[str, object],
    completed: subprocess.CompletedProcess[str],
) -> GraderVerdict:
    all_error_exits = [
        int(each_exit) for each_exit in all_spec_fields.get("error_exits", [])
    ]
    if completed.returncode in all_error_exits:
        return GraderVerdict(
            grader_id, "error", f"exit {completed.returncode} is a harness exit"
        )
    if completed.returncode != int(all_spec_fields.get("expect_exit", 0)):
        return GraderVerdict(grader_id, "fail", f"exit {completed.returncode}")
    expected_fragment = all_spec_fields.get("stdout_contains")
    if expected_fragment is not None and str(expected_fragment) not in completed.stdout:
        return GraderVerdict(grader_id, "fail", f"stdout lacks {expected_fragment!r}")
    expected_stdout = all_spec_fields.get("stdout_equals")
    if expected_stdout is not None and completed.stdout.strip() != str(expected_stdout).strip():
        return GraderVerdict(
            grader_id,
            "fail",
            f"stdout was {completed.stdout.strip()[:DETAIL_CHARACTER_LIMIT]!r}",
        )
    return GraderVerdict(grader_id, "pass", f"exit {completed.returncode}")


def grade_command(
    all_spec_fields: Mapping[str, object], context: GradingContext
) -> GraderVerdict:
    """Run one command in the work directory and read its exit and stdout.

    ::

        exit matches expect_exit, stdout holds the fragment   ->   pass
        exit sits in error_exits                              ->   error
        the executable is missing                             ->   error

    Args:
        all_spec_fields: One command spec from ``cases.json``.
        context: The work directory, case directory, reply, and transcript.

    Returns:
        A GraderVerdict naming the exit status the command reached.
    """
    grader_id = str(all_spec_fields["id"])
    overlay_failure = _overlay_failure(grader_id, all_spec_fields, context)
    if overlay_failure is not None:
        return overlay_failure
    all_arguments = _prepared_arguments(all_spec_fields, context)
    try:
        completed = subprocess.run(
            all_arguments,
            cwd=context.work_directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=int(
                all_spec_fields.get("timeout_seconds", DEFAULT_COMMAND_TIMEOUT_SECONDS)
            ),
            check=False,
        )
    except FileNotFoundError as missing_executable:
        return GraderVerdict(
            grader_id, "error", f"executable missing: {missing_executable}"
        )
    except subprocess.TimeoutExpired:
        return GraderVerdict(grader_id, "error", "command timed out")
    return _command_verdict(grader_id, all_spec_fields, completed)


def grade_file_regex(
    all_spec_fields: Mapping[str, object], context: GradingContext
) -> GraderVerdict:
    """Search the files a glob matches for one pattern.

    ::

        glob matches a.py, pattern hits, expect present   ->   pass
        glob matches nothing                              ->   error

    Args:
        all_spec_fields: One file_regex spec from ``cases.json``.
        context: The work directory the glob runs in.

    Returns:
        A GraderVerdict naming the files the pattern hit.
    """
    grader_id = str(all_spec_fields["id"])
    all_paths = sorted(
        each_path
        for each_path in context.work_directory.glob(str(all_spec_fields["glob"]))
        if each_path.is_file()
    )
    if not all_paths:
        return GraderVerdict(
            grader_id, "error", f"glob matched no file: {all_spec_fields['glob']}"
        )
    pattern = re.compile(str(all_spec_fields["pattern"]), re.MULTILINE)
    all_hits = [
        each_path.name
        for each_path in all_paths
        if pattern.search(each_path.read_text(encoding="utf-8", errors="replace"))
    ]
    status = _expectation_status(bool(all_hits), str(all_spec_fields["expect"]))
    return GraderVerdict(grader_id, status, f"hits: {all_hits}")


def grade_path_exists(
    all_spec_fields: Mapping[str, object], context: GradingContext
) -> GraderVerdict:
    """Read whether one path under the work directory is there.

    ::

        path is there, expect present   ->   pass
        the work directory is missing   ->   error

    Args:
        all_spec_fields: One path_exists spec from ``cases.json``.
        context: The work directory the path is read against.

    Returns:
        A GraderVerdict naming the path it read.
    """
    grader_id = str(all_spec_fields["id"])
    if not context.work_directory.is_dir():
        return GraderVerdict(grader_id, "error", "work directory missing")
    is_found = (context.work_directory / str(all_spec_fields["path"])).exists()
    return GraderVerdict(
        grader_id,
        _expectation_status(is_found, str(all_spec_fields["expect"])),
        str(all_spec_fields["path"]),
    )


def grade_reply_regex(
    all_spec_fields: Mapping[str, object], context: GradingContext
) -> GraderVerdict:
    """Search the session's own reply text for one pattern.

    ::

        the reply holds the pattern, expect present   ->   pass
        the reply is empty                            ->   error

    Args:
        all_spec_fields: One result_regex spec from ``cases.json``.
        context: The grading context carrying the session reply.

    Returns:
        A GraderVerdict naming the pattern it searched for.
    """
    grader_id = str(all_spec_fields["id"])
    if not context.reply_text.strip():
        return GraderVerdict(grader_id, "error", "empty reply text")
    is_found = bool(
        re.search(str(all_spec_fields["pattern"]), context.reply_text, re.MULTILINE)
    )
    return GraderVerdict(
        grader_id,
        _expectation_status(is_found, str(all_spec_fields["expect"])),
        str(all_spec_fields["pattern"]),
    )


def _events_or_failure(
    grader_id: str, context: GradingContext
) -> list[ToolEvent] | GraderVerdict:
    if context.transcript_path is None or not context.transcript_path.is_file():
        return GraderVerdict(grader_id, "error", "transcript missing")
    try:
        return read_tool_events(context.transcript_path)
    except json.JSONDecodeError as malformed:
        return GraderVerdict(grader_id, "error", f"transcript malformed: {malformed}")


def grade_transcript_order(
    all_spec_fields: Mapping[str, object], context: GradingContext
) -> GraderVerdict:
    """Pass when the earliest ``first`` event precedes the earliest ``then`` event.

    ::

        first@2 then@5   ->   pass
        no first event   ->   fail

    Args:
        all_spec_fields: One transcript_order spec from ``cases.json``.
        context: The grading context carrying the transcript path.

    Returns:
        A GraderVerdict naming the two positions it compared.
    """
    grader_id = str(all_spec_fields["id"])
    all_events = _events_or_failure(grader_id, context)
    if isinstance(all_events, GraderVerdict):
        return all_events
    all_first_positions = _matching_positions(all_events, all_spec_fields["first"])
    all_then_positions = _matching_positions(all_events, all_spec_fields["then"])
    if not all_first_positions or not all_then_positions:
        return GraderVerdict(
            grader_id,
            "fail",
            f"first={all_first_positions[:1]} then={all_then_positions[:1]}",
        )
    is_ordered = all_first_positions[0] < all_then_positions[0]
    return GraderVerdict(
        grader_id,
        "pass" if is_ordered else "fail",
        f"first@{all_first_positions[0]} then@{all_then_positions[0]}",
    )


def grade_transcript_after_last(
    all_spec_fields: Mapping[str, object], context: GradingContext
) -> GraderVerdict:
    """Pass when a ``followed_by`` event occurs after the last ``last_of`` event.

    ::

        last anchor@4, follow@7   ->   pass
        no anchor event           ->   fail

    Args:
        all_spec_fields: One transcript_after_last spec from ``cases.json``.
        context: The grading context carrying the transcript path.

    Returns:
        A GraderVerdict naming the anchor and follow positions.
    """
    grader_id = str(all_spec_fields["id"])
    all_events = _events_or_failure(grader_id, context)
    if isinstance(all_events, GraderVerdict):
        return all_events
    all_anchor_positions = _matching_positions(all_events, all_spec_fields["last_of"])
    all_follow_positions = _matching_positions(
        all_events, all_spec_fields["followed_by"]
    )
    if not all_anchor_positions:
        return GraderVerdict(grader_id, "fail", "no anchor event")
    is_followed = (
        bool(all_follow_positions)
        and all_follow_positions[-1] > all_anchor_positions[-1]
    )
    return GraderVerdict(
        grader_id,
        "pass" if is_followed else "fail",
        f"last_anchor@{all_anchor_positions[-1]} follow={all_follow_positions[-1:]}",
    )


def grade_transcript_tool_regex(
    all_spec_fields: Mapping[str, object], context: GradingContext
) -> GraderVerdict:
    """Search the transcript for a tool call whose input matches one pattern.

    ::

        a matching call, expect present   ->   pass
        the transcript is missing         ->   error

    Args:
        all_spec_fields: One transcript_tool_regex spec from ``cases.json``.
        context: The grading context carrying the transcript path.

    Returns:
        A GraderVerdict naming the first few matching positions.
    """
    grader_id = str(all_spec_fields["id"])
    all_events = _events_or_failure(grader_id, context)
    if isinstance(all_events, GraderVerdict):
        return all_events
    all_positions = _matching_positions(all_events, all_spec_fields["match"])
    status = _expectation_status(bool(all_positions), str(all_spec_fields["expect"]))
    return GraderVerdict(grader_id, status, f"positions: {all_positions[:5]}")


GRADER_BY_KIND: dict[
    str, Callable[[Mapping[str, object], GradingContext], GraderVerdict]
] = {
    "command": grade_command,
    "file_regex": grade_file_regex,
    "path_exists": grade_path_exists,
    "result_regex": grade_reply_regex,
    "transcript_order": grade_transcript_order,
    "transcript_after_last": grade_transcript_after_last,
    "transcript_tool_regex": grade_transcript_tool_regex,
}


def run_graders(
    all_specs: list[Mapping[str, object]], context: GradingContext
) -> list[GraderVerdict]:
    """Run every grader a case names and collect what each one reached.

    ::

        a spec whose kind is registered   ->   that grader's verdict
        a spec naming an unknown kind     ->   an error verdict

    Args:
        all_specs: The grader specs one case carries.
        context: The grading context every grader reads.

    Returns:
        One verdict per spec, in the order the case names them.
    """
    all_verdicts: list[GraderVerdict] = []
    for each_spec in all_specs:
        grader = GRADER_BY_KIND.get(str(each_spec.get("kind")))
        if grader is None:
            all_verdicts.append(
                GraderVerdict(
                    str(each_spec.get("id")),
                    "error",
                    f"unknown kind: {each_spec.get('kind')}",
                )
            )
            continue
        all_verdicts.append(grader(each_spec, context))
    return all_verdicts
