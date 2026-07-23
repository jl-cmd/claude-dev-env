#!/usr/bin/env python3
"""Select the converge pacer for a skill and host tool surface.

Pacer values::

    workflow         — Claude Workflow tool (autoconverge native)
    schedule_wakeup  — Claude ScheduleWakeup ticks (pr-converge native)
    portable         — continuous in-session driver (third-party hosts)

Rules::

    autoconverge + Workflow present             -> workflow
    autoconverge + Workflow absent              -> portable
    autoconverge + Workflow present + grok mode -> portable
    pr-converge  + ScheduleWakeup present       -> schedule_wakeup
    pr-converge  + ScheduleWakeup absent        -> portable

Import ``select_converge_pacer`` or run as a CLI::

    python select_converge_pacer.py --skill <pr-converge|autoconverge> \\
        --has-workflow <0|1> --has-schedule-wakeup <0|1> [--grok-mode <0|1>]
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

_self_dir = Path(__file__).resolve().parent
if str(_self_dir) not in sys.path:
    sys.path.insert(0, str(_self_dir))

from skills_pr_loop_constants.pacer_constants import (  # noqa: E402
    ALL_ENTRY_SKILLS,
    ALL_FALSY_FLAG_TOKENS,
    ALL_TRUTHY_FLAG_TOKENS,
    CLI_GROK_MODE_FLAG,
    CLI_HAS_SCHEDULE_WAKEUP_FLAG,
    CLI_HAS_WORKFLOW_FLAG,
    CLI_SKILL_FLAG,
    ENTRY_SKILL_AUTOCONVERGE,
    ENTRY_SKILL_JOIN_SEPARATOR,
    EXIT_SUCCESS,
    EXIT_USAGE_ERROR,
    GROK_MODE_FLAG_DEFAULT,
    INVALID_BOOL_FLAG_ERROR,
    PACER_PORTABLE,
    PACER_SCHEDULE_WAKEUP,
    PACER_WORKFLOW,
    RESULT_KEY_ENTRY_SKILL,
    RESULT_KEY_GROK_MODE,
    RESULT_KEY_HAS_SCHEDULE_WAKEUP,
    RESULT_KEY_HAS_WORKFLOW,
    RESULT_KEY_PACER,
    UNKNOWN_ENTRY_SKILL_ERROR,
)


@dataclass(frozen=True)
class ConvergePacerSelection:
    """Result of pacer selection for one skill invocation."""

    pacer: str
    entry_skill: str
    has_workflow: bool
    has_schedule_wakeup: bool
    grok_mode: bool


def parse_bool_flag(flag_token: str) -> bool:
    """Parse a CLI boolean token into a bool.

    Args:
        flag_token: Token from ``--has-workflow``, ``--has-schedule-wakeup``,
            or ``--grok-mode``.

    Returns:
        True for truthy tokens, False for falsy tokens.

    Raises:
        ValueError: When the token is not a known boolean form.
    """
    normalized_token = flag_token.strip().lower()
    if normalized_token in ALL_TRUTHY_FLAG_TOKENS:
        return True
    if normalized_token in ALL_FALSY_FLAG_TOKENS:
        return False
    raise ValueError(INVALID_BOOL_FLAG_ERROR.format(got=flag_token))


def select_converge_pacer(
    *,
    entry_skill: str,
    has_workflow: bool,
    has_schedule_wakeup: bool,
    is_grok_mode: bool = False,
) -> ConvergePacerSelection:
    """Return the pacer the named entry skill must use on this host.

    Args:
        entry_skill: ``pr-converge`` or ``autoconverge``.
        has_workflow: True when the host tool list includes ``Workflow``.
        has_schedule_wakeup: True when the host tool list includes
            ``ScheduleWakeup``.
        is_grok_mode: True when the run routes loop workers through the
            grok-first dispatcher. For ``autoconverge`` this forces the
            portable pacer; ``pr-converge`` is unaffected.

    Returns:
        A ``ConvergePacerSelection`` with the chosen ``pacer`` name.

    Raises:
        ValueError: When ``entry_skill`` is not a known converge entry.
    """
    normalized_skill = entry_skill.strip().lower()
    if normalized_skill not in ALL_ENTRY_SKILLS:
        raise ValueError(
            UNKNOWN_ENTRY_SKILL_ERROR.format(
                allowed=ENTRY_SKILL_JOIN_SEPARATOR.join(ALL_ENTRY_SKILLS),
                got=entry_skill,
            )
        )

    if normalized_skill == ENTRY_SKILL_AUTOCONVERGE:
        should_force_portable = is_grok_mode or not has_workflow
        selected_pacer = (
            PACER_PORTABLE if should_force_portable else PACER_WORKFLOW
        )
    else:
        selected_pacer = (
            PACER_SCHEDULE_WAKEUP if has_schedule_wakeup else PACER_PORTABLE
        )

    return ConvergePacerSelection(
        pacer=selected_pacer,
        entry_skill=normalized_skill,
        has_workflow=has_workflow,
        has_schedule_wakeup=has_schedule_wakeup,
        grok_mode=is_grok_mode,
    )


def selection_as_json_dict(
    selection: ConvergePacerSelection,
) -> dict[str, str | bool]:
    """Serialize a selection for JSON stdout.

    Args:
        selection: Pacer selection to serialize.

    Returns:
        Dict with stable result keys for CLI and tests.
    """
    selection_by_field = asdict(selection)
    return {
        RESULT_KEY_PACER: selection_by_field["pacer"],
        RESULT_KEY_ENTRY_SKILL: selection_by_field["entry_skill"],
        RESULT_KEY_HAS_WORKFLOW: selection_by_field["has_workflow"],
        RESULT_KEY_HAS_SCHEDULE_WAKEUP: selection_by_field[
            "has_schedule_wakeup"
        ],
        RESULT_KEY_GROK_MODE: selection_by_field["grok_mode"],
    }


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for pacer selection.

    Returns:
        Configured argument parser.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Select workflow, schedule_wakeup, or portable pacer for a "
            "converge entry skill."
        )
    )
    parser.add_argument(
        CLI_SKILL_FLAG,
        required=True,
        choices=list(ALL_ENTRY_SKILLS),
        help="Entry skill invoking converge.",
    )
    parser.add_argument(
        CLI_HAS_WORKFLOW_FLAG,
        required=True,
        help="1/true when the host tool list includes Workflow.",
    )
    parser.add_argument(
        CLI_HAS_SCHEDULE_WAKEUP_FLAG,
        required=True,
        help="1/true when the host tool list includes ScheduleWakeup.",
    )
    parser.add_argument(
        CLI_GROK_MODE_FLAG,
        default=GROK_MODE_FLAG_DEFAULT,
        help="1/true routes loop workers through the grok dispatcher.",
    )
    return parser


def main(all_argv: list[str]) -> int:
    """CLI entry: print one JSON selection line on stdout.

    Args:
        all_argv: Argument vector (without the program name).

    Returns:
        Process exit code (0 success, 2 usage/validation error).
    """
    parser = build_argument_parser()
    parsed_arguments = parser.parse_args(all_argv)
    try:
        has_workflow = parse_bool_flag(parsed_arguments.has_workflow)
        has_schedule_wakeup = parse_bool_flag(
            parsed_arguments.has_schedule_wakeup
        )
        is_grok_mode = parse_bool_flag(parsed_arguments.grok_mode)
        selection = select_converge_pacer(
            entry_skill=parsed_arguments.skill,
            has_workflow=has_workflow,
            has_schedule_wakeup=has_schedule_wakeup,
            is_grok_mode=is_grok_mode,
        )
    except ValueError as validation_error:
        print(str(validation_error), file=sys.stderr)
        return EXIT_USAGE_ERROR

    print(json.dumps(selection_as_json_dict(selection), sort_keys=True))
    return EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
