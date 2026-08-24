#!/usr/bin/env python3
"""``build_converge_task_list.py`` — ordered review tasks for a run.

Step 1 of autoconverge / portable pr-converge: call this script. Do not invent
tasks in prose. The final task is always all runnable code reviews CLEAN on
the same HEAD.

::

    python build_converge_task_list.py \\
        [--bugbot-down 0|1] [--copilot-down 0|1] \\
        [--codex-down 0|1] [--codex-required 0|1]

Stdout JSON::

    {
      "tasks": [...],
      "runnable_review_ids": [...],
      "skipped_review_ids": [...],
      "final_task_id": "all_runnable_reviews_clean_same_head",
      "done_when": "..."
    }
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_self_dir = Path(__file__).resolve().parent
if str(_self_dir) not in sys.path:
    sys.path.insert(0, str(_self_dir))

from select_converge_pacer import parse_bool_flag  # noqa: E402
from skills_pr_loop_constants.converge_task_list_constants import (  # noqa: E402
    CLI_BUGBOT_DOWN_FLAG,
    CLI_CODEX_DOWN_FLAG,
    CLI_CODEX_REQUIRED_FLAG,
    CLI_COPILOT_DOWN_FLAG,
    DONE_WHEN_TEXT,
    EXIT_SUCCESS,
    EXIT_USAGE_ERROR,
    RESULT_KEY_DONE_WHEN,
    RESULT_KEY_FINAL_TASK_ID,
    RESULT_KEY_RUNNABLE_REVIEW_IDS,
    RESULT_KEY_SKIPPED_REVIEW_IDS,
    RESULT_KEY_TASKS,
    SKIP_REASON_BUGBOT_DOWN,
    SKIP_REASON_CODEX_DOWN,
    SKIP_REASON_CODEX_NOT_REQUIRED,
    SKIP_REASON_COPILOT_DOWN,
    TASK_FIELD_ID,
    TASK_FIELD_IS_RUNNABLE,
    TASK_FIELD_KIND,
    TASK_FIELD_SKIP_REASON,
    TASK_FIELD_TITLE,
    TASK_ID_ALL_CLEAN_SAME_HEAD,
    TASK_ID_BUGBOT,
    TASK_ID_BUGTEAM,
    TASK_ID_CODE_REVIEW,
    TASK_ID_CODEX,
    TASK_ID_COPILOT,
    TASK_KIND_FINAL,
    TASK_KIND_REVIEW,
    TASK_TITLE_ALL_CLEAN_SAME_HEAD,
    TASK_TITLE_BUGBOT,
    TASK_TITLE_BUGTEAM,
    TASK_TITLE_CODE_REVIEW,
    TASK_TITLE_CODEX,
    TASK_TITLE_COPILOT,
)


def _review_task(
    *,
    task_id: str,
    title: str,
    is_runnable: bool,
    skip_reason: str | None,
) -> dict[str, object]:
    task: dict[str, object] = {
        TASK_FIELD_ID: task_id,
        TASK_FIELD_TITLE: title,
        TASK_FIELD_KIND: TASK_KIND_REVIEW,
        TASK_FIELD_IS_RUNNABLE: is_runnable,
    }
    if skip_reason is not None:
        task[TASK_FIELD_SKIP_REASON] = skip_reason
    return task


def _append_always_runnable_reviews(
    all_tasks: list[dict[str, object]],
) -> None:
    all_tasks.append(
        _review_task(
            task_id=TASK_ID_CODE_REVIEW,
            title=TASK_TITLE_CODE_REVIEW,
            is_runnable=True,
            skip_reason=None,
        )
    )
    all_tasks.append(
        _review_task(
            task_id=TASK_ID_BUGTEAM,
            title=TASK_TITLE_BUGTEAM,
            is_runnable=True,
            skip_reason=None,
        )
    )


def _append_bugbot_task(
    all_tasks: list[dict[str, object]],
    *,
    is_bugbot_down: bool,
) -> None:
    if is_bugbot_down:
        all_tasks.append(
            _review_task(
                task_id=TASK_ID_BUGBOT,
                title=TASK_TITLE_BUGBOT,
                is_runnable=False,
                skip_reason=SKIP_REASON_BUGBOT_DOWN,
            )
        )
        return
    all_tasks.append(
        _review_task(
            task_id=TASK_ID_BUGBOT,
            title=TASK_TITLE_BUGBOT,
            is_runnable=True,
            skip_reason=None,
        )
    )


def _append_copilot_task(
    all_tasks: list[dict[str, object]],
    *,
    is_copilot_down: bool,
) -> None:
    if is_copilot_down:
        all_tasks.append(
            _review_task(
                task_id=TASK_ID_COPILOT,
                title=TASK_TITLE_COPILOT,
                is_runnable=False,
                skip_reason=SKIP_REASON_COPILOT_DOWN,
            )
        )
        return
    all_tasks.append(
        _review_task(
            task_id=TASK_ID_COPILOT,
            title=TASK_TITLE_COPILOT,
            is_runnable=True,
            skip_reason=None,
        )
    )


def _append_codex_task(
    all_tasks: list[dict[str, object]],
    *,
    is_codex_down: bool,
    is_codex_required: bool,
) -> None:
    if is_codex_down:
        all_tasks.append(
            _review_task(
                task_id=TASK_ID_CODEX,
                title=TASK_TITLE_CODEX,
                is_runnable=False,
                skip_reason=SKIP_REASON_CODEX_DOWN,
            )
        )
        return
    if not is_codex_required:
        all_tasks.append(
            _review_task(
                task_id=TASK_ID_CODEX,
                title=TASK_TITLE_CODEX,
                is_runnable=False,
                skip_reason=SKIP_REASON_CODEX_NOT_REQUIRED,
            )
        )
        return
    all_tasks.append(
        _review_task(
            task_id=TASK_ID_CODEX,
            title=TASK_TITLE_CODEX,
            is_runnable=True,
            skip_reason=None,
        )
    )


def _append_final_task(all_tasks: list[dict[str, object]]) -> None:
    all_tasks.append(
        {
            TASK_FIELD_ID: TASK_ID_ALL_CLEAN_SAME_HEAD,
            TASK_FIELD_TITLE: TASK_TITLE_ALL_CLEAN_SAME_HEAD,
            TASK_FIELD_KIND: TASK_KIND_FINAL,
            TASK_FIELD_IS_RUNNABLE: True,
        }
    )


def _partition_review_ids(
    all_tasks: list[dict[str, object]],
) -> tuple[list[str], list[str]]:
    all_runnable_review_ids = [
        str(each_task[TASK_FIELD_ID])
        for each_task in all_tasks
        if each_task[TASK_FIELD_KIND] == TASK_KIND_REVIEW
        and each_task[TASK_FIELD_IS_RUNNABLE] is True
    ]
    all_skipped_review_ids = [
        str(each_task[TASK_FIELD_ID])
        for each_task in all_tasks
        if each_task[TASK_FIELD_KIND] == TASK_KIND_REVIEW
        and each_task[TASK_FIELD_IS_RUNNABLE] is False
    ]
    return all_runnable_review_ids, all_skipped_review_ids


def build_converge_task_list(
    *,
    is_bugbot_down: bool,
    is_copilot_down: bool,
    is_codex_down: bool,
    is_codex_required: bool,
) -> dict[str, object]:
    """Return the ordered task list and done criterion for one converge run.

    Args:
        is_bugbot_down: Skip Bugbot as a runnable review.
        is_copilot_down: Skip Copilot as a runnable review.
        is_codex_down: Skip Codex even when usage would require it.
        is_codex_required: Weekly usage / policy requires a Codex review.

    Returns:
        JSON-serializable control object with ``tasks`` and ``done_when``.
    """
    all_tasks: list[dict[str, object]] = []
    _append_always_runnable_reviews(all_tasks)
    _append_bugbot_task(all_tasks, is_bugbot_down=is_bugbot_down)
    _append_copilot_task(all_tasks, is_copilot_down=is_copilot_down)
    _append_codex_task(
        all_tasks,
        is_codex_down=is_codex_down,
        is_codex_required=is_codex_required,
    )
    _append_final_task(all_tasks)
    all_runnable_review_ids, all_skipped_review_ids = _partition_review_ids(
        all_tasks
    )
    return {
        RESULT_KEY_TASKS: all_tasks,
        RESULT_KEY_RUNNABLE_REVIEW_IDS: all_runnable_review_ids,
        RESULT_KEY_SKIPPED_REVIEW_IDS: all_skipped_review_ids,
        RESULT_KEY_FINAL_TASK_ID: TASK_ID_ALL_CLEAN_SAME_HEAD,
        RESULT_KEY_DONE_WHEN: DONE_WHEN_TEXT,
    }


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for ``build_converge_task_list``.

    Returns:
        Configured argument parser.
    """
    parser = argparse.ArgumentParser(description="build_converge_task_list")
    parser.add_argument(CLI_BUGBOT_DOWN_FLAG, default="0")
    parser.add_argument(CLI_COPILOT_DOWN_FLAG, default="0")
    parser.add_argument(CLI_CODEX_DOWN_FLAG, default="0")
    parser.add_argument(CLI_CODEX_REQUIRED_FLAG, default="0")
    return parser


def main(all_argv: list[str]) -> int:
    """CLI entry: print one task-list JSON object on stdout.

    Args:
        all_argv: Argument vector without program name.

    Returns:
        Process exit code.
    """
    parser = build_argument_parser()
    parsed_arguments = parser.parse_args(all_argv)
    try:
        task_list_payload = build_converge_task_list(
            is_bugbot_down=parse_bool_flag(parsed_arguments.bugbot_down),
            is_copilot_down=parse_bool_flag(parsed_arguments.copilot_down),
            is_codex_down=parse_bool_flag(parsed_arguments.codex_down),
            is_codex_required=parse_bool_flag(parsed_arguments.codex_required),
        )
    except ValueError as validation_error:
        print(str(validation_error), file=sys.stderr)
        return EXIT_USAGE_ERROR
    print(json.dumps(task_list_payload, sort_keys=True))
    return EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
