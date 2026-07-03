"""Write durable resume-handoff files for a pr-loop run.

A converge loop can stop mid-run: a paused tick, a budget cutoff, a killed
session. The next session then has no pointer to where the run was. This writer
drops that pointer somewhere the OS temp sweep cannot purge.

::

    write_handoff.py --pr-number <N> --head-ref <branch> --phase tick
        --resume-command "claude --resume /pr-converge" [--state-file <PATH>]
    writes:  ~/.claude/runtime/pr-loop/<run-name>/handoff.json + HANDOFF.md
    plus:    state-copy.json  (only when --state-file is given)

It records the resume command, the phase reached, the steps already done, and a
copy of the loop state, so a fresh session picks up without re-deriving it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_self_dir = Path(__file__).resolve().parent
if str(_self_dir) not in sys.path:
    sys.path.insert(0, str(_self_dir))

from _path_resolver import build_run_name  # noqa: E402
from skills_pr_loop_constants.handoff_constants import (  # noqa: E402
    ATOMIC_STAGING_SUFFIX,
    COMPLETED_STEPS_SEPARATOR,
    DEFAULT_NEXT_STEP_LINE,
    ALL_HANDOFF_DIR_SEGMENTS,
    HANDOFF_JSON_FILENAME,
    HANDOFF_JSON_INDENT,
    HANDOFF_MARKDOWN_FILENAME,
    HANDOFF_MARKDOWN_TEMPLATE,
    NO_STATE_SNAPSHOT_LINE,
    NO_STEPS_DONE_LINE,
    STATE_COPY_FILENAME,
    STEP_LINE_SEPARATOR,
)


def _now_iso() -> str:
    """Return the current UTC time as an ISO-format timestamp string.

    Returns:
        The stamp recorded on the handoff so a reader knows how fresh it is.
    """
    return datetime.now(timezone.utc).isoformat()


def _handoff_base_dir() -> Path:
    """Return the durable base directory that holds every run's handoff folder.

    Returns:
        The ``~/.claude/runtime/pr-loop`` path under the user's home directory.
    """
    return Path.home().joinpath(*ALL_HANDOFF_DIR_SEGMENTS)


def resolve_handoff_dir(run_name: str) -> Path:
    """Resolve the durable handoff directory for a run name.

    Args:
        run_name: Run name token (from build_run_name).

    Returns:
        Absolute path to the run's handoff directory under the durable base.
    """
    return _handoff_base_dir() / run_name


def _write_text_atomic(target_path: Path, text: str) -> None:
    """Write text to a path atomically via a staging file and a rename.

    Args:
        target_path: Destination file path.
        text: Full file contents to write.
    """
    target_path.parent.mkdir(parents=True, exist_ok=True)
    staging_path = target_path.with_name(
        f"{target_path.name}{ATOMIC_STAGING_SUFFIX}.{os.getpid()}"
    )
    staging_path.write_text(text, encoding="utf-8")
    os.replace(staging_path, target_path)


def _snapshot_state(handoff_dir: Path, state_file: Path | None) -> str | None:
    """Copy a loop state file into the handoff directory when one is supplied.

    Args:
        handoff_dir: The run's durable handoff directory.
        state_file: Loop state file to snapshot, or None to skip the copy.

    Returns:
        The forward-slash path of the copy to trust, or None when no state
        file was supplied.
    """
    if state_file is None:
        return None
    state_copy_path = handoff_dir / STATE_COPY_FILENAME
    _write_text_atomic(state_copy_path, state_file.read_text(encoding="utf-8"))
    return state_copy_path.as_posix()


def _steps_markdown_block(all_completed_steps: list[str]) -> str:
    """Render the completed steps as a markdown bullet list.

    Args:
        all_completed_steps: Steps already finished this run.

    Returns:
        A bullet list, or a placeholder line when no steps are recorded.
    """
    if not all_completed_steps:
        return NO_STEPS_DONE_LINE
    return STEP_LINE_SEPARATOR.join(f"- {each_step}" for each_step in all_completed_steps)


def _build_handoff_markdown(
    *,
    pr_number: int,
    head_ref: str,
    phase: str,
    resume_command: str,
    trusted_state_path: str | None,
    all_completed_steps: list[str],
    note: str | None,
) -> str:
    """Build the human-facing HANDOFF.md body for a fresh session.

    Args:
        pr_number: Pull request number.
        head_ref: Head branch ref.
        phase: The checkpoint the run reached.
        resume_command: The exact command a fresh session runs to resume.
        trusted_state_path: The state-copy path to trust, or None.
        all_completed_steps: Steps already finished this run.
        note: Free-text next-step note, or None.

    Returns:
        The rendered markdown document.
    """
    state_line = (
        f"Trust this state snapshot: {trusted_state_path}"
        if trusted_state_path is not None
        else NO_STATE_SNAPSHOT_LINE
    )
    return HANDOFF_MARKDOWN_TEMPLATE.format(
        pr_number=pr_number,
        head_ref=head_ref,
        phase=phase,
        resume_command=resume_command,
        state_line=state_line,
        steps_block=_steps_markdown_block(all_completed_steps),
        next_step=note if note else DEFAULT_NEXT_STEP_LINE,
    )


def write_handoff(
    *,
    pr_number: int,
    head_ref: str,
    phase: str,
    resume_command: str,
    state_file: Path | None = None,
    run_id: str | None = None,
    all_completed_steps: list[str] | None = None,
    note: str | None = None,
) -> Path:
    """Write handoff.json, HANDOFF.md, and an optional state copy for a run.

    Names the run with build_run_name and places the files under the durable
    handoff directory. When a state file is supplied, its contents are copied to
    state-copy.json and that copy path is recorded as the state to trust.

    Args:
        pr_number: Pull request number.
        head_ref: Head branch ref.
        phase: The checkpoint the run reached (e.g. 'tick', 'teardown').
        resume_command: The exact command a fresh session runs to resume.
        state_file: Loop state file to snapshot, or None to skip the copy.
        run_id: Workflow run id to resume from, or None.
        all_completed_steps: Steps already finished this run, or None.
        note: Free-text next-step note for the fresh session, or None.

    Returns:
        Path to the run's durable handoff directory.
    """
    steps_done = all_completed_steps if all_completed_steps else []
    run_name = build_run_name(pr_number, head_ref, is_multi_pr=False)
    handoff_dir = resolve_handoff_dir(run_name)
    handoff_dir.mkdir(parents=True, exist_ok=True)

    trusted_state_path = _snapshot_state(handoff_dir, state_file)
    payload = {
        "pr_number": pr_number,
        "head_ref": head_ref,
        "phase": phase,
        "resume_command": resume_command,
        "run_id": run_id,
        "state_file": trusted_state_path,
        "completed_steps": steps_done,
        "note": note,
        "timestamp": _now_iso(),
    }
    _write_text_atomic(
        handoff_dir / HANDOFF_JSON_FILENAME,
        json.dumps(payload, indent=HANDOFF_JSON_INDENT) + "\n",
    )
    _write_text_atomic(
        handoff_dir / HANDOFF_MARKDOWN_FILENAME,
        _build_handoff_markdown(
            pr_number=pr_number,
            head_ref=head_ref,
            phase=phase,
            resume_command=resume_command,
            trusted_state_path=trusted_state_path,
            all_completed_steps=steps_done,
            note=note,
        ),
    )
    return handoff_dir


def _split_completed_steps(raw_steps: str) -> list[str]:
    """Split a comma-separated steps argument into a trimmed, non-empty list.

    Args:
        raw_steps: The raw --completed-steps CLI value.

    Returns:
        The individual step names with surrounding whitespace removed.
    """
    return [
        each_segment.strip()
        for each_segment in raw_steps.split(COMPLETED_STEPS_SEPARATOR)
        if each_segment.strip()
    ]


def parse_arguments(all_argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        all_argv: Command-line argument list.

    Returns:
        Parsed namespace with the handoff fields.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr-number", type=int, required=True)
    parser.add_argument("--head-ref", required=True)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--resume-command", required=True)
    parser.add_argument("--state-file", type=Path, default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--completed-steps", default="")
    parser.add_argument("--note", default=None)
    return parser.parse_args(all_argv)


def _write_handoff_from_arguments(arguments: argparse.Namespace) -> Path:
    """Map parsed CLI arguments onto a write_handoff call.

    Args:
        arguments: The namespace parse_arguments produced.

    Returns:
        Path to the run's durable handoff directory.
    """
    return write_handoff(
        pr_number=arguments.pr_number,
        head_ref=arguments.head_ref,
        phase=arguments.phase,
        resume_command=arguments.resume_command,
        state_file=arguments.state_file,
        run_id=arguments.run_id,
        all_completed_steps=_split_completed_steps(arguments.completed_steps),
        note=arguments.note,
    )


def main(all_arguments: list[str]) -> int:
    """Entry point: write the handoff files and print the durable directory.

    Args:
        all_arguments: Command-line arguments.

    Returns:
        0 on success, 1 on a state-file read or write failure.
    """
    arguments = parse_arguments(all_arguments)
    try:
        handoff_dir = _write_handoff_from_arguments(arguments)
    except (OSError, UnicodeDecodeError) as read_or_write_error:
        print(f"write_handoff failed: {read_or_write_error}", file=sys.stderr)
        return 1
    print(handoff_dir.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
