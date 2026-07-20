#!/usr/bin/env python3
"""portable_converge_driver phase machine (deterministic only).

The agent never invents phase transitions, wait delays, clean stamps, or
ready decisions from prose. It runs this CLI, reads JSON, and either:

* executes the named ``commands`` (shell helpers already scripted), or
* performs the single judgment step named in ``next`` (fix implementation,
  worker spawn body) and reports outcomes back through this CLI.

::

    portable_converge_driver.py open-run --skill autoconverge \\
        --has-workflow 0 --has-schedule-wakeup 0 \\
        --owner O --repo R --pr-number N --cwd DIR --state-dir DIR \\
        [--session-model third-party] [--copilot-down 0|1] [--bugbot-down 0|1] \\
        [--codex-down 0|1] [--codex-required 0|1]

    portable_converge_driver.py after-code-review --state-file PATH \\
        --returncode 0 --dirty-tree 0 --current-head SHA \\
        --served-command ''|in_session|chain-command

    portable_converge_driver.py after-bugteam --state-file PATH \\
        --pushed 0|1 --converged 0|1 --current-head SHA

    portable_converge_driver.py after-bugbot --state-file PATH \\
        --classification clean|dirty|absent|down --current-head SHA \\
        [--inline-lag 0|1]

    portable_converge_driver.py after-codex --state-file PATH \\
        --classification clean|dirty|down --current-head SHA

    portable_converge_driver.py after-copilot-wait --state-file PATH \\
        --review-surfaced 0|1 --classification clean|dirty|absent|down \\
        --current-head SHA

    portable_converge_driver.py after-ready-check --state-file PATH \\
        --check-exit 0|1|2 --current-head SHA

    portable_converge_driver.py show-state --state-file PATH

Successful code-review serve: returncode 0 only. ``served_command`` is
informational (empty / ``in_session`` / chain argv) and does not decide
success. Non-zero returncode is always a failed serve.

After Bugbot clean or down, the machine runs the Codex step (or the
codex-down / not-required waiver) before COPILOT_WAIT or check_ready.

When ``--codex-down`` is off, open-run and every codex decision point probe
weekly usage through ``codex_usage_probe`` so ``codex_required`` matches
``check_convergence`` (CLI ``--codex-required 1`` still forces the step on).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Mapping

_self_dir = Path(__file__).resolve().parent
if str(_self_dir) not in sys.path:
    sys.path.insert(0, str(_self_dir))

from build_converge_task_list import build_converge_task_list  # noqa: E402
from select_converge_pacer import (  # noqa: E402
    parse_bool_flag,
    select_converge_pacer,
)
from skills_pr_loop_constants.pacer_constants import (  # noqa: E402
    CLI_HAS_SCHEDULE_WAKEUP_FLAG,
    CLI_HAS_WORKFLOW_FLAG,
    CLI_SKILL_FLAG,
    PACER_PORTABLE,
)
from skills_pr_loop_constants.portable_driver_constants import (  # noqa: E402
    ALL_CLASSIFICATIONS,
    ALL_CODEX_CLASSIFICATIONS,
    ALL_COPILOT_CLASSIFICATIONS,
    ALL_GIT_REV_PARSE_HEAD_ARGV,
    BLOCKER_BUGBOT_WAIT_CAP,
    BLOCKER_COPILOT_WAIT_CAP,
    BLOCKER_INLINE_LAG_CAP,
    BLOCKER_NOT_PORTABLE,
    BLOCKER_PREFLIGHT,
    BLOCKER_REVIEW_FAILED,
    BUGBOT_ABSENT_WAIT_HARD_CAP,
    BUGBOT_INLINE_LAG_WAIT_SECONDS,
    CHECK_CONVERGENCE_BUGBOT_DOWN_FLAG,
    CHECK_CONVERGENCE_CODEX_CLEAN_AT_FLAG,
    CHECK_CONVERGENCE_CODEX_DOWN_FLAG,
    CHECK_CONVERGENCE_COPILOT_DOWN_FLAG,
    CHECK_CONVERGENCE_OWNER_FLAG,
    CHECK_CONVERGENCE_PR_NUMBER_FLAG,
    CHECK_CONVERGENCE_RELATIVE_PATH,
    CHECK_CONVERGENCE_REPO_FLAG,
    CLASSIFICATION_ABSENT,
    CLASSIFICATION_DIRTY,
    CLASSIFICATION_DOWN,
    CLI_BUGBOT_DOWN_FLAG,
    CLI_CHECK_CONVERGENCE_EXIT_FLAG,
    CLI_CLASSIFICATION_FLAG,
    CLI_CODEX_DOWN_FLAG,
    CLI_CODEX_REQUIRED_FLAG,
    CLI_CONVERGED_FLAG,
    CLI_COPILOT_DOWN_FLAG,
    CLI_CURRENT_HEAD_FLAG,
    CLI_CWD_FLAG,
    CLI_DESCRIPTION,
    CLI_DIRTY_TREE_FLAG,
    CLI_INLINE_LAG_FLAG,
    CLI_OWNER_FLAG,
    CLI_PR_NUMBER_FLAG,
    CLI_PUSHED_FLAG,
    CLI_REPO_FLAG,
    CLI_RETURNCODE_FLAG,
    CLI_REVIEW_SURFACED_FLAG,
    CLI_SERVED_COMMAND_FLAG,
    CLI_SESSION_MODEL_FLAG,
    CLI_STATE_DIR_FLAG,
    CLI_STATE_FILE_FLAG,
    CODEX_REVIEW_SCRIPTS_DIRNAME,
    CODEX_REVIEW_SKILL_DIRNAME,
    COMMAND_AFTER_BUGBOT,
    COMMAND_AFTER_BUGTEAM,
    COMMAND_AFTER_CODE_REVIEW,
    COMMAND_AFTER_CODEX,
    COMMAND_AFTER_COPILOT_WAIT,
    COMMAND_AFTER_READY_CHECK,
    COMMAND_OPEN_RUN,
    COMMAND_SHOW_STATE,
    COPILOT_WAIT_HARD_CAP,
    DEFAULT_SESSION_MODEL,
    DEFAULT_WAIT_SECONDS,
    EXIT_CONTRACT_ERROR,
    EXIT_SUCCESS,
    EXIT_USAGE_ERROR,
    INLINE_LAG_STREAK_CAP,
    INVOKE_CODE_REVIEW_EFFORT_ARGUMENT,
    INVOKE_CODE_REVIEW_RELATIVE_PATH,
    PORTABLE_SCRIPTS_TO_SKILLS_PARENT_HOPS,
    POST_CLEAN_COMMENT_CWD_FLAG,
    POST_CLEAN_COMMENT_EFFORT_FLAG,
    POST_CLEAN_COMMENT_HEAD_SHA_FLAG,
    POST_CLEAN_COMMENT_MODE_CHAIN,
    POST_CLEAN_COMMENT_MODE_FLAG,
    POST_CLEAN_COMMENT_MODE_IN_SESSION,
    POST_CLEAN_COMMENT_RELATIVE_PATH,
    POST_CLEAN_COMMENT_SERVED_COMMAND_FLAG,
    NEXT_APPLY_FIXES,
    NEXT_CHECK_READY,
    NEXT_MARK_READY,
    NEXT_POLL_WAIT,
    NEXT_REQUEST_COPILOT,
    NEXT_RUN_BUGBOT_GATE,
    NEXT_RUN_BUGTEAM,
    NEXT_RUN_CODE_REVIEW,
    NEXT_RUN_CODEX,
    NEXT_STOP_BLOCKED,
    PHASE_BLOCKED,
    PHASE_BUGBOT,
    PHASE_BUGTEAM,
    PHASE_CODE_REVIEW,
    PHASE_COPILOT_WAIT,
    PHASE_READY,
    PREFLIGHT_WORKTREE_SCRIPT_NAME,
    RESULT_KEY_BLOCKER,
    RESULT_KEY_BUGBOT_DOWN,
    RESULT_KEY_CODEX_DOWN,
    RESULT_KEY_COMMANDS,
    RESULT_KEY_COPILOT_DOWN,
    RESULT_KEY_CURRENT_HEAD,
    RESULT_KEY_ENTRY_SKILL,
    RESULT_KEY_MESSAGE,
    RESULT_KEY_NEXT,
    RESULT_KEY_OWNER,
    RESULT_KEY_PACER,
    RESULT_KEY_PHASE,
    RESULT_KEY_PR_NUMBER,
    RESULT_KEY_REPO,
    RESULT_KEY_STATE_FILE,
    RESULT_KEY_STATUS,
    RESULT_KEY_TICK_COUNT,
    RESULT_KEY_WAIT_SECONDS,
    SERVED_COMMAND_IN_SESSION,
    STATE_FILENAME,
    STATE_JSON_INDENT,
    MARK_READY_GH_BINARY,
    MARK_READY_PR_TOKEN,
    MARK_READY_REPO_FLAG,
    MARK_READY_SUBCOMMAND,
    STATE_KEY_CODEX_CLEAN_AT,
    STATE_KEY_CODEX_DOWN,
    STATE_KEY_CODEX_REQUIRED,
    STATE_KEY_CODE_REVIEW_CLEAN_AT,
    STATE_KEY_CWD,
    STATE_KEY_SERVED_COMMAND,
    STATE_KEY_PENDING_NEXT,
    STATE_KEY_PENDING_WAIT_SECONDS,
    STATE_KEY_SESSION_MODEL,
    STATE_STAGING_SUFFIX,
    STATUS_ERROR,
    STATUS_OK,
)
from skills_pr_loop_constants.preflight_constants import (  # noqa: E402
    MODE_ARG_FLAG,
    MODE_STRICT,
    OWNER_ARG_FLAG,
    REPO_ARG_FLAG,
)

_skills_directory_for_codex = Path(__file__).resolve().parent
_remaining_codex_path_hops = PORTABLE_SCRIPTS_TO_SKILLS_PARENT_HOPS
while _remaining_codex_path_hops > 0:
    _skills_directory_for_codex = _skills_directory_for_codex.parent
    _remaining_codex_path_hops -= 1
_codex_scripts_directory = (
    _skills_directory_for_codex
    / CODEX_REVIEW_SKILL_DIRNAME
    / CODEX_REVIEW_SCRIPTS_DIRNAME
)
_codex_scripts_text = str(_codex_scripts_directory)
if _codex_scripts_text not in sys.path:
    sys.path.insert(0, _codex_scripts_text)

from codex_review_scripts_constants.codex_usage_probe_constants import (  # noqa: E402
    USAGE_REPORT_KEY_PERCENT_LEFT,
)
from codex_usage_probe import (  # noqa: E402
    is_codex_review_required,
    probe_weekly_usage_via_subprocess,
)

_EMPTY_COMMANDS: list[str] = []


def _home_path(*parts: str) -> Path:
    return Path.home().joinpath(*parts)


def _emit(all_payload: Mapping[str, object]) -> None:
    print(json.dumps(dict(all_payload), sort_keys=True))


def _error_payload(message: str, **extra: object) -> dict[str, object]:
    all_payload: dict[str, object] = {
        RESULT_KEY_STATUS: STATUS_ERROR,
        RESULT_KEY_MESSAGE: message,
    }
    all_payload.update(extra)
    return all_payload


def load_state(state_file: Path) -> dict[str, object]:
    """Load loop state JSON from disk.

    Args:
        state_file: Path to ``pr-converge-state.json``.

    Returns:
        Parsed state mapping.

    Raises:
        ValueError: When the file is missing or not a JSON object.
    """
    if not state_file.is_file():
        raise ValueError(f"state file missing: {state_file}")
    loaded = json.loads(state_file.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"state file is not a JSON object: {state_file}")
    return loaded


def save_state(state_file: Path, all_state: Mapping[str, object]) -> None:
    """Write loop state JSON atomically.

    Args:
        state_file: Destination path.
        all_state: State mapping to persist.
    """
    state_file.parent.mkdir(parents=True, exist_ok=True)
    staging_path = state_file.with_suffix(state_file.suffix + STATE_STAGING_SUFFIX)
    staging_path.write_text(
        json.dumps(dict(all_state), indent=STATE_JSON_INDENT, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    os.replace(staging_path, state_file)


def build_initial_state(
    *,
    current_head: str,
    entry_skill: str,
    is_copilot_down: bool,
    is_bugbot_down: bool,
    owner: str,
    repo: str,
    pr_number: int,
    is_codex_down: bool = False,
    is_codex_required: bool = False,
    session_model: str = DEFAULT_SESSION_MODEL,
    cwd_path: str | None = None,
) -> dict[str, object]:
    """Build the initial portable loop state for a PR head.

    Args:
        current_head: Current PR head SHA.
        entry_skill: ``pr-converge`` or ``autoconverge``.
        is_copilot_down: Copilot gate skipped for the whole run.
        is_bugbot_down: Bugbot gate skipped for the whole run.
        owner: Repository owner.
        repo: Repository name.
        pr_number: Pull request number.
        is_codex_down: Codex gate skipped (disabled or opted out).
        is_codex_required: Codex is required by usage/policy for this run.
        session_model: Alias passed to invoke_code_review on re-entry.
        cwd_path: PR worktree path for invoke_code_review --cwd.

    Returns:
        New state mapping at ``CODE_REVIEW``.
    """
    return {
        "phase": PHASE_CODE_REVIEW,
        "tick_count": 0,
        "bugbot_clean_at": None,
        "code_review_clean_at": None,
        "bugteam_clean_at": None,
        "copilot_clean_at": None,
        STATE_KEY_CODEX_CLEAN_AT: None,
        "merge_state_status": None,
        "current_head": current_head,
        "copilot_wait_count": 0,
        "bugbot_wait_count": 0,
        "copilot_down": is_copilot_down,
        "bugbot_down": is_bugbot_down,
        STATE_KEY_CODEX_DOWN: is_codex_down,
        STATE_KEY_CODEX_REQUIRED: is_codex_required,
        "inline_lag_streak": 0,
        "pacer": PACER_PORTABLE,
        "entry_skill": entry_skill,
        "owner": owner,
        "repo": repo,
        "pr_number": pr_number,
        "blocker": None,
        STATE_KEY_PENDING_NEXT: NEXT_RUN_CODE_REVIEW,
        STATE_KEY_SESSION_MODEL: session_model,
        STATE_KEY_CWD: cwd_path,
    }


def _reset_push_invalidated_markers(all_state: dict[str, object]) -> None:
    all_state["bugbot_clean_at"] = None
    all_state["code_review_clean_at"] = None
    all_state["bugteam_clean_at"] = None
    all_state["copilot_clean_at"] = None
    all_state[STATE_KEY_CODEX_CLEAN_AT] = None
    all_state["merge_state_status"] = None
    all_state["copilot_wait_count"] = 0
    all_state["bugbot_wait_count"] = 0
    all_state["inline_lag_streak"] = 0
    all_state["bugbot_down"] = False
    all_state[STATE_KEY_CODEX_DOWN] = False
    all_state[STATE_KEY_SERVED_COMMAND] = ""


def _sync_task_list_from_down_flags(all_state: dict[str, object]) -> None:
    all_task_list = build_converge_task_list(
        is_bugbot_down=bool(all_state.get("bugbot_down")),
        is_copilot_down=bool(all_state.get("copilot_down")),
        is_codex_down=bool(all_state.get(STATE_KEY_CODEX_DOWN)),
        is_codex_required=bool(all_state.get(STATE_KEY_CODEX_REQUIRED)),
    )
    all_state["tasks"] = all_task_list["tasks"]
    all_state["final_task_id"] = all_task_list["final_task_id"]
    all_state["runnable_review_ids"] = all_task_list["runnable_review_ids"]
    all_state["done_when"] = all_task_list["done_when"]


def probe_weekly_usage_requires_codex() -> bool:
    """Return whether live weekly Codex usage requires a review stamp.

    Matches ``check_convergence``: unknown percent and probe failures never
    require a review. A known percent above the shared threshold does.

    Returns:
        True only when the weekly probe exits successfully with a percent
        that ``is_codex_review_required`` accepts as required.
    """
    try:
        usage_report = probe_weekly_usage_via_subprocess()
    except (
        FileNotFoundError,
        OSError,
        subprocess.TimeoutExpired,
        subprocess.SubprocessError,
        json.JSONDecodeError,
        ValueError,
        TypeError,
        KeyError,
    ):
        return False
    raw_percent = usage_report.get(USAGE_REPORT_KEY_PERCENT_LEFT)
    if isinstance(raw_percent, bool):
        return False
    if isinstance(raw_percent, (int, float)):
        return is_codex_review_required(float(raw_percent))
    return False


def resolve_codex_required_flag(
    *,
    is_codex_down: bool,
    is_codex_required: bool,
) -> bool:
    """Resolve whether Codex is a runnable review for this run.

    Args:
        is_codex_down: Codex gate skipped (disabled or opted out).
        is_codex_required: CLI force-on (``--codex-required 1``).

    Returns:
        False when Codex is down; otherwise the CLI force-on flag or the
        live weekly usage probe (same rule as ``check_convergence``).
    """
    if is_codex_down:
        return False
    if is_codex_required:
        return True
    return probe_weekly_usage_requires_codex()


def _ensure_codex_required_matches_usage(all_state: dict[str, object]) -> None:
    """Promote ``codex_required`` when live usage requires a stamp.

    Args:
        all_state: Mutable loop state; may set ``codex_required`` and refresh
            the task list when the probe requires Codex.
    """
    if all_state.get(STATE_KEY_CODEX_DOWN):
        return
    if all_state.get(STATE_KEY_CODEX_REQUIRED):
        return
    if not probe_weekly_usage_requires_codex():
        return
    all_state[STATE_KEY_CODEX_REQUIRED] = True
    _sync_task_list_from_down_flags(all_state)


def _maybe_reset_on_head_change(
    all_state: dict[str, object], current_head: str
) -> None:
    prior_head = all_state.get("current_head")
    if (
        isinstance(prior_head, str)
        and prior_head
        and prior_head != current_head
    ):
        _reset_push_invalidated_markers(all_state)
        _sync_task_list_from_down_flags(all_state)
    all_state["current_head"] = current_head


def _code_review_commands(
    *,
    cwd_path: Path,
    session_model: str,
) -> list[str]:
    invoke_path = _home_path(*INVOKE_CODE_REVIEW_RELATIVE_PATH.split("/"))
    return [
        "python",
        str(invoke_path),
        "--cwd",
        str(cwd_path),
        "--session-model",
        session_model,
        INVOKE_CODE_REVIEW_EFFORT_ARGUMENT,
    ]


def _code_review_commands_from_state(
    all_state: Mapping[str, object],
) -> list[str]:
    stored_session_model = all_state.get(STATE_KEY_SESSION_MODEL)
    cwd_path = _cwd_path_from_state(all_state)
    if isinstance(stored_session_model, str) and stored_session_model:
        session_model = stored_session_model
    else:
        session_model = DEFAULT_SESSION_MODEL
    return _code_review_commands(
        cwd_path=cwd_path, session_model=session_model
    )


def _cwd_path_from_state(all_state: Mapping[str, object]) -> Path:
    stored_cwd = all_state.get(STATE_KEY_CWD)
    if isinstance(stored_cwd, str) and stored_cwd:
        return Path(stored_cwd)
    return Path.cwd()


def _resolve_clean_comment_mode(served_command: str) -> str | None:
    if not served_command:
        return None
    if served_command == SERVED_COMMAND_IN_SESSION:
        return POST_CLEAN_COMMENT_MODE_IN_SESSION
    return POST_CLEAN_COMMENT_MODE_CHAIN


def _clean_comment_commands(
    *,
    cwd_path: Path,
    head_sha: str,
    served_command: str,
) -> list[str]:
    post_path = _home_path(*POST_CLEAN_COMMENT_RELATIVE_PATH.split("/"))
    all_arguments = [
        "python",
        str(post_path),
        POST_CLEAN_COMMENT_CWD_FLAG,
        str(cwd_path),
        POST_CLEAN_COMMENT_HEAD_SHA_FLAG,
        head_sha,
        POST_CLEAN_COMMENT_EFFORT_FLAG,
        INVOKE_CODE_REVIEW_EFFORT_ARGUMENT,
    ]
    if served_command:
        all_arguments += [
            POST_CLEAN_COMMENT_SERVED_COMMAND_FLAG,
            served_command,
        ]
    resolved_mode = _resolve_clean_comment_mode(served_command)
    if resolved_mode is not None:
        all_arguments += [POST_CLEAN_COMMENT_MODE_FLAG, resolved_mode]
    return all_arguments


def _clean_comment_commands_from_state(
    all_state: Mapping[str, object],
    *,
    head_sha: str,
    served_command: str,
) -> list[str]:
    return _clean_comment_commands(
        cwd_path=_cwd_path_from_state(all_state),
        head_sha=head_sha,
        served_command=served_command,
    )


def _mark_ready_commands(all_state: Mapping[str, object]) -> list[str]:
    owner = str(all_state["owner"])
    repo = str(all_state["repo"])
    return [
        MARK_READY_GH_BINARY,
        MARK_READY_PR_TOKEN,
        MARK_READY_SUBCOMMAND,
        str(all_state["pr_number"]),
        MARK_READY_REPO_FLAG,
        f"{owner}/{repo}",
    ]


def _check_convergence_commands(
    *,
    owner: str,
    repo: str,
    pr_number: int,
    is_copilot_down: bool,
    is_bugbot_down: bool,
    is_codex_down: bool,
    codex_clean_at: str | None,
) -> list[str]:
    check_path = _home_path(*CHECK_CONVERGENCE_RELATIVE_PATH.split("/"))
    all_arguments = [
        "python",
        str(check_path),
        CHECK_CONVERGENCE_OWNER_FLAG,
        owner,
        CHECK_CONVERGENCE_REPO_FLAG,
        repo,
        CHECK_CONVERGENCE_PR_NUMBER_FLAG,
        str(pr_number),
    ]
    if is_copilot_down:
        all_arguments.append(CHECK_CONVERGENCE_COPILOT_DOWN_FLAG)
    if is_bugbot_down:
        all_arguments.append(CHECK_CONVERGENCE_BUGBOT_DOWN_FLAG)
    if is_codex_down:
        all_arguments.append(CHECK_CONVERGENCE_CODEX_DOWN_FLAG)
    if codex_clean_at:
        all_arguments.extend(
            [CHECK_CONVERGENCE_CODEX_CLEAN_AT_FLAG, codex_clean_at]
        )
    return all_arguments


def _state_pr_number(all_state: Mapping[str, object]) -> int:
    return int(str(all_state["pr_number"]))


def _codex_clean_at_or_none(all_state: Mapping[str, object]) -> str | None:
    maybe_stamp = all_state.get(STATE_KEY_CODEX_CLEAN_AT)
    if isinstance(maybe_stamp, str) and maybe_stamp:
        return maybe_stamp
    return None


def _check_convergence_commands_from_state(
    all_state: Mapping[str, object],
) -> list[str]:
    return _check_convergence_commands(
        owner=str(all_state["owner"]),
        repo=str(all_state["repo"]),
        pr_number=_state_pr_number(all_state),
        is_copilot_down=bool(all_state.get("copilot_down")),
        is_bugbot_down=bool(all_state.get("bugbot_down")),
        is_codex_down=bool(all_state.get(STATE_KEY_CODEX_DOWN)),
        codex_clean_at=_codex_clean_at_or_none(all_state),
    )


def _base_ok_payload(
    all_state: Mapping[str, object], state_file: Path
) -> dict[str, object]:
    return {
        RESULT_KEY_STATUS: STATUS_OK,
        RESULT_KEY_PHASE: all_state["phase"],
        RESULT_KEY_STATE_FILE: str(state_file),
        RESULT_KEY_CURRENT_HEAD: all_state.get("current_head"),
        RESULT_KEY_TICK_COUNT: all_state.get("tick_count"),
        RESULT_KEY_PACER: all_state.get("pacer", PACER_PORTABLE),
        RESULT_KEY_ENTRY_SKILL: all_state.get("entry_skill"),
        RESULT_KEY_OWNER: all_state.get("owner"),
        RESULT_KEY_REPO: all_state.get("repo"),
        RESULT_KEY_PR_NUMBER: all_state.get("pr_number"),
        RESULT_KEY_COPILOT_DOWN: bool(all_state.get("copilot_down")),
        RESULT_KEY_BUGBOT_DOWN: bool(all_state.get("bugbot_down")),
        RESULT_KEY_CODEX_DOWN: bool(all_state.get(STATE_KEY_CODEX_DOWN)),
    }


def _store_pending_wait_seconds(
    all_state: dict[str, object],
    *,
    wait_seconds: int | None,
) -> None:
    if wait_seconds is None:
        all_state.pop(STATE_KEY_PENDING_WAIT_SECONDS, None)
        return
    all_state[STATE_KEY_PENDING_WAIT_SECONDS] = wait_seconds


def _resolve_poll_wait_seconds(all_state: Mapping[str, object]) -> int:
    pending_wait_seconds = all_state.get(STATE_KEY_PENDING_WAIT_SECONDS)
    if isinstance(pending_wait_seconds, int):
        return pending_wait_seconds
    return DEFAULT_WAIT_SECONDS


def _finish_ok(
    all_state: dict[str, object],
    state_file: Path,
    *,
    next_action: str,
    all_commands: list[str],
    wait_seconds: int | None,
    blocker: str | None,
    all_extra_fields: Mapping[str, object] | None,
) -> tuple[dict[str, object], int]:
    all_state[STATE_KEY_PENDING_NEXT] = next_action
    _store_pending_wait_seconds(all_state, wait_seconds=wait_seconds)
    resolved_commands = all_commands
    if next_action == NEXT_RUN_CODE_REVIEW:
        resolved_commands = _code_review_commands_from_state(all_state)
    save_state(state_file, all_state)
    all_payload = _base_ok_payload(all_state, state_file)
    all_payload[RESULT_KEY_NEXT] = next_action
    all_payload[RESULT_KEY_COMMANDS] = resolved_commands
    if wait_seconds is not None:
        all_payload[RESULT_KEY_WAIT_SECONDS] = wait_seconds
    if blocker is not None:
        all_payload[RESULT_KEY_BLOCKER] = blocker
    if all_extra_fields is not None:
        all_payload.update(dict(all_extra_fields))
    return all_payload, EXIT_SUCCESS


def _run_preflight(
    *,
    cwd_path: Path,
    owner: str,
    repo: str,
) -> tuple[dict[str, object] | None, int]:
    preflight_script = _self_dir / PREFLIGHT_WORKTREE_SCRIPT_NAME
    preflight_process = subprocess.run(
        [
            sys.executable,
            str(preflight_script),
            OWNER_ARG_FLAG,
            owner,
            REPO_ARG_FLAG,
            repo,
            MODE_ARG_FLAG,
            MODE_STRICT,
        ],
        cwd=str(cwd_path),
        check=False,
        capture_output=True,
        text=True,
    )
    if preflight_process.returncode == 0:
        return None, EXIT_SUCCESS
    return (
        _error_payload(
            preflight_process.stdout.strip()
            or preflight_process.stderr.strip()
            or "preflight failed",
            blocker=BLOCKER_PREFLIGHT,
        ),
        EXIT_CONTRACT_ERROR,
    )


def _read_git_head(
    cwd_path: Path,
) -> tuple[str | None, dict[str, object] | None, int]:
    head_process = subprocess.run(
        list(ALL_GIT_REV_PARSE_HEAD_ARGV),
        cwd=str(cwd_path),
        check=False,
        capture_output=True,
        text=True,
    )
    if head_process.returncode != 0:
        return (
            None,
            _error_payload(
                "git rev-parse HEAD failed", blocker=BLOCKER_PREFLIGHT
            ),
            EXIT_CONTRACT_ERROR,
        )
    return head_process.stdout.strip(), None, EXIT_SUCCESS


def _seed_open_run_task_list_and_finish(
    *,
    current_head: str,
    entry_skill: str,
    is_copilot_down: bool,
    is_bugbot_down: bool,
    is_codex_down: bool,
    is_codex_required: bool,
    owner: str,
    repo: str,
    pr_number: int,
    state_file: Path,
    cwd_path: Path,
    session_model: str,
) -> tuple[dict[str, object], int]:
    all_task_list = build_converge_task_list(
        is_bugbot_down=is_bugbot_down,
        is_copilot_down=is_copilot_down,
        is_codex_down=is_codex_down,
        is_codex_required=is_codex_required,
    )
    all_state = build_initial_state(
        current_head=current_head,
        entry_skill=entry_skill,
        is_copilot_down=is_copilot_down,
        is_bugbot_down=is_bugbot_down,
        is_codex_down=is_codex_down,
        is_codex_required=is_codex_required,
        owner=owner,
        repo=repo,
        pr_number=pr_number,
        session_model=session_model,
        cwd_path=str(cwd_path),
    )
    all_state["tasks"] = all_task_list["tasks"]
    all_state["final_task_id"] = all_task_list["final_task_id"]
    all_state["runnable_review_ids"] = all_task_list["runnable_review_ids"]
    all_state["done_when"] = all_task_list["done_when"]
    return _finish_ok(
        all_state,
        state_file,
        next_action=NEXT_RUN_CODE_REVIEW,
        all_commands=_code_review_commands(
            cwd_path=cwd_path, session_model=session_model
        ),
        wait_seconds=None,
        blocker=None,
        all_extra_fields=all_task_list,
    )


def run_open_run(
    *,
    entry_skill: str,
    has_workflow: bool,
    has_schedule_wakeup: bool,
    owner: str,
    repo: str,
    pr_number: int,
    cwd_path: Path,
    state_dir: Path,
    session_model: str,
    is_copilot_down: bool,
    is_bugbot_down: bool,
    is_codex_down: bool = False,
    is_codex_required: bool = False,
) -> tuple[dict[str, object], int]:
    """Select pacer, require portable, preflight worktree, seed state + tasks.

    Args:
        entry_skill: Converge entry skill name.
        has_workflow: Host exposes Workflow.
        has_schedule_wakeup: Host exposes ScheduleWakeup.
        owner: Repository owner.
        repo: Repository name.
        pr_number: Pull request number.
        cwd_path: PR worktree path.
        state_dir: Directory for ``pr-converge-state.json``.
        session_model: Alias passed to invoke_code_review.
        is_copilot_down: Skip Copilot as a runnable review.
        is_bugbot_down: Skip Bugbot as a runnable review.
        is_codex_down: Skip Codex as a runnable review.
        is_codex_required: Codex is required by usage/policy for this run.

    Returns:
        Payload and process exit code. Payload includes the scripted task list
        from ``build_converge_task_list.py``; final task is all runnable reviews
        CLEAN on the same HEAD.
    """
    selection = select_converge_pacer(
        entry_skill=entry_skill,
        has_workflow=has_workflow,
        has_schedule_wakeup=has_schedule_wakeup,
    )
    if selection.pacer != PACER_PORTABLE:
        return (
            _error_payload(
                "open-run is only for pacer=portable",
                blocker=BLOCKER_NOT_PORTABLE,
                pacer=selection.pacer,
            ),
            EXIT_CONTRACT_ERROR,
        )
    maybe_error, preflight_exit = _run_preflight(
        cwd_path=cwd_path, owner=owner, repo=repo
    )
    if maybe_error is not None:
        return maybe_error, preflight_exit
    current_head, maybe_head_error, head_exit = _read_git_head(cwd_path)
    if maybe_head_error is not None or current_head is None:
        return maybe_head_error or _error_payload(
            "git rev-parse HEAD failed", blocker=BLOCKER_PREFLIGHT
        ), head_exit
    state_dir.mkdir(parents=True, exist_ok=True)
    resolved_codex_required = resolve_codex_required_flag(
        is_codex_down=is_codex_down,
        is_codex_required=is_codex_required,
    )
    return _seed_open_run_task_list_and_finish(
        current_head=current_head,
        entry_skill=selection.entry_skill,
        is_copilot_down=is_copilot_down,
        is_bugbot_down=is_bugbot_down,
        is_codex_down=is_codex_down,
        is_codex_required=resolved_codex_required,
        owner=owner,
        repo=repo,
        pr_number=pr_number,
        state_file=state_dir / STATE_FILENAME,
        cwd_path=cwd_path,
        session_model=session_model,
    )


def _is_successful_serve(*, returncode: int) -> bool:
    """Return True when code-review completed a successful serve.

    Args:
        returncode: Helper process exit code.

    Returns:
        Whether the serve counts as successful for phase advance.
    """
    return returncode == 0


def run_after_code_review(
    *,
    state_file: Path,
    returncode: int,
    is_dirty_tree: bool,
    served_command: str,
    current_head: str,
) -> tuple[dict[str, object], int]:
    """Advance state from a code-review helper result.

    Args:
        state_file: Loop state path.
        returncode: Helper process exit code.
        is_dirty_tree: Working tree dirty after review.
        served_command: Serving binary, ``in_session``, or empty when unknown.
            Success is decided solely by ``returncode == 0``, but on the clean
            path this value is stored in state and drives the ``--mode`` and
            ``--served-command`` flags of the emitted clean-comment argv, so an
            empty or wrong token degrades the posted comment.
        current_head: SHA after the review step.

    Returns:
        Payload and process exit code.
    """
    all_state = load_state(state_file)
    _maybe_reset_on_head_change(all_state, current_head)
    all_state["tick_count"] = int(all_state.get("tick_count") or 0) + 1

    is_successful_serve = _is_successful_serve(returncode=returncode)
    if not is_successful_serve:
        all_state["phase"] = PHASE_CODE_REVIEW
        all_state["blocker"] = BLOCKER_REVIEW_FAILED
        return _finish_ok(
            all_state,
            state_file,
            next_action=NEXT_RUN_CODE_REVIEW,
            all_commands=_EMPTY_COMMANDS,
            wait_seconds=None,
            blocker=BLOCKER_REVIEW_FAILED,
            all_extra_fields=None,
        )

    if is_dirty_tree:
        all_state["phase"] = PHASE_CODE_REVIEW
        all_state["code_review_clean_at"] = None
        return _finish_ok(
            all_state,
            state_file,
            next_action=NEXT_APPLY_FIXES,
            all_commands=_EMPTY_COMMANDS,
            wait_seconds=None,
            blocker=None,
            all_extra_fields=None,
        )

    all_state[STATE_KEY_CODE_REVIEW_CLEAN_AT] = current_head
    all_state[STATE_KEY_SERVED_COMMAND] = served_command
    all_state["phase"] = PHASE_BUGTEAM
    all_state["blocker"] = None
    return _finish_ok(
        all_state,
        state_file,
        next_action=NEXT_RUN_BUGTEAM,
        all_commands=_clean_comment_commands_from_state(
            all_state,
            head_sha=current_head,
            served_command=served_command,
        ),
        wait_seconds=None,
        blocker=None,
        all_extra_fields=None,
    )


def _needs_codex_step(all_state: Mapping[str, object]) -> bool:
    if all_state.get(STATE_KEY_CODEX_DOWN):
        return False
    current_head = all_state.get("current_head")
    if (
        isinstance(current_head, str)
        and all_state.get(STATE_KEY_CODEX_CLEAN_AT) == current_head
    ):
        return False
    if all_state.get(STATE_KEY_CODEX_REQUIRED):
        return True
    return probe_weekly_usage_requires_codex()


def _advance_after_codex_resolved(
    all_state: dict[str, object],
    state_file: Path,
) -> tuple[dict[str, object], int]:
    if all_state.get("copilot_down"):
        all_state["phase"] = PHASE_READY
        return _finish_ok(
            all_state,
            state_file,
            next_action=NEXT_CHECK_READY,
            all_commands=_check_convergence_commands_from_state(all_state),
            wait_seconds=None,
            blocker=None,
            all_extra_fields=None,
        )
    all_state["phase"] = PHASE_COPILOT_WAIT
    return _finish_ok(
        all_state,
        state_file,
        next_action=NEXT_REQUEST_COPILOT,
        all_commands=_EMPTY_COMMANDS,
        wait_seconds=None,
        blocker=None,
        all_extra_fields=None,
    )


def _advance_after_bugbot_resolved(
    all_state: dict[str, object],
    state_file: Path,
) -> tuple[dict[str, object], int]:
    _ensure_codex_required_matches_usage(all_state)
    if _needs_codex_step(all_state):
        all_state["phase"] = PHASE_BUGBOT
        return _finish_ok(
            all_state,
            state_file,
            next_action=NEXT_RUN_CODEX,
            all_commands=_EMPTY_COMMANDS,
            wait_seconds=None,
            blocker=None,
            all_extra_fields=None,
        )
    return _advance_after_codex_resolved(all_state, state_file)


def _after_bugteam_converged(
    all_state: dict[str, object],
    state_file: Path,
    current_head: str,
) -> tuple[dict[str, object], int]:
    all_state["bugteam_clean_at"] = current_head
    if not all_state.get("bugbot_down"):
        all_state["phase"] = PHASE_BUGBOT
        return _finish_ok(
            all_state,
            state_file,
            next_action=NEXT_RUN_BUGBOT_GATE,
            all_commands=_EMPTY_COMMANDS,
            wait_seconds=None,
            blocker=None,
            all_extra_fields=None,
        )
    return _advance_after_bugbot_resolved(all_state, state_file)


def run_after_bugteam(
    *,
    state_file: Path,
    is_pushed: bool,
    is_converged: bool,
    current_head: str,
) -> tuple[dict[str, object], int]:
    """Advance state from a bugteam outcome.

    Args:
        state_file: Loop state path.
        is_pushed: Bugteam pushed commits.
        is_converged: Bugteam reported clean with no push.
        current_head: SHA after bugteam.

    Returns:
        Payload and process exit code.
    """
    all_state = load_state(state_file)
    _maybe_reset_on_head_change(all_state, current_head)
    all_state["tick_count"] = int(all_state.get("tick_count") or 0) + 1

    if is_pushed:
        _reset_push_invalidated_markers(all_state)
        _sync_task_list_from_down_flags(all_state)
        all_state["phase"] = PHASE_CODE_REVIEW
        return _finish_ok(
            all_state,
            state_file,
            next_action=NEXT_RUN_CODE_REVIEW,
            all_commands=_EMPTY_COMMANDS,
            wait_seconds=None,
            blocker=None,
            all_extra_fields=None,
        )

    if is_converged:
        return _after_bugteam_converged(all_state, state_file, current_head)

    all_state["phase"] = PHASE_CODE_REVIEW
    return _finish_ok(
        all_state,
        state_file,
        next_action=NEXT_APPLY_FIXES,
        all_commands=_EMPTY_COMMANDS,
        wait_seconds=None,
        blocker=None,
        all_extra_fields=None,
    )


def _after_bugbot_down(
    all_state: dict[str, object],
    state_file: Path,
) -> tuple[dict[str, object], int]:
    all_state["bugbot_down"] = True
    _sync_task_list_from_down_flags(all_state)
    return _advance_after_bugbot_resolved(all_state, state_file)


def _after_bugbot_dirty(
    all_state: dict[str, object],
    state_file: Path,
    *,
    is_inline_lag: bool,
) -> tuple[dict[str, object], int]:
    if not is_inline_lag:
        all_state["inline_lag_streak"] = 0
        all_state["phase"] = PHASE_CODE_REVIEW
        return _finish_ok(
            all_state,
            state_file,
            next_action=NEXT_APPLY_FIXES,
            all_commands=_EMPTY_COMMANDS,
            wait_seconds=None,
            blocker=None,
            all_extra_fields=None,
        )
    streak = int(all_state.get("inline_lag_streak") or 0) + 1
    all_state["inline_lag_streak"] = streak
    if streak >= INLINE_LAG_STREAK_CAP:
        all_state["phase"] = PHASE_BLOCKED
        all_state["blocker"] = BLOCKER_INLINE_LAG_CAP
        return _finish_ok(
            all_state,
            state_file,
            next_action=NEXT_STOP_BLOCKED,
            all_commands=_EMPTY_COMMANDS,
            wait_seconds=None,
            blocker=BLOCKER_INLINE_LAG_CAP,
            all_extra_fields=None,
        )
    all_state["phase"] = PHASE_BUGBOT
    return _finish_ok(
        all_state,
        state_file,
        next_action=NEXT_POLL_WAIT,
        all_commands=_EMPTY_COMMANDS,
        wait_seconds=BUGBOT_INLINE_LAG_WAIT_SECONDS,
        blocker=None,
        all_extra_fields=None,
    )


def _after_bugbot_clean(
    all_state: dict[str, object],
    state_file: Path,
    current_head: str,
) -> tuple[dict[str, object], int]:
    all_state["bugbot_clean_at"] = current_head
    all_state["inline_lag_streak"] = 0
    return _advance_after_bugbot_resolved(all_state, state_file)


def run_after_codex(
    *,
    state_file: Path,
    classification: str,
    current_head: str,
) -> tuple[dict[str, object], int]:
    """Advance state from a Codex review step outcome.

    Args:
        state_file: Loop state path.
        classification: clean, dirty, or down.
        current_head: Current PR head SHA.

    Returns:
        Payload and process exit code.
    """
    if classification not in ALL_CODEX_CLASSIFICATIONS:
        return (
            _error_payload(f"unknown classification: {classification!r}"),
            EXIT_USAGE_ERROR,
        )
    all_state = load_state(state_file)
    _maybe_reset_on_head_change(all_state, current_head)
    all_state["tick_count"] = int(all_state.get("tick_count") or 0) + 1

    if classification == CLASSIFICATION_DIRTY:
        _reset_push_invalidated_markers(all_state)
        _sync_task_list_from_down_flags(all_state)
        all_state["phase"] = PHASE_CODE_REVIEW
        return _finish_ok(
            all_state,
            state_file,
            next_action=NEXT_APPLY_FIXES,
            all_commands=_EMPTY_COMMANDS,
            wait_seconds=None,
            blocker=None,
            all_extra_fields=None,
        )

    if classification == CLASSIFICATION_DOWN:
        all_state[STATE_KEY_CODEX_DOWN] = True
        _sync_task_list_from_down_flags(all_state)
        return _advance_after_codex_resolved(all_state, state_file)

    all_state[STATE_KEY_CODEX_CLEAN_AT] = current_head
    return _advance_after_codex_resolved(all_state, state_file)


def run_after_bugbot(
    *,
    state_file: Path,
    classification: str,
    current_head: str,
    is_inline_lag: bool,
) -> tuple[dict[str, object], int]:
    """Advance state from a Bugbot terminal-gate outcome.

    Args:
        state_file: Loop state path.
        classification: clean, dirty, absent, or down.
        current_head: Current PR head SHA.
        is_inline_lag: Body dirty but zero inline findings.

    Returns:
        Payload and process exit code.
    """
    if classification not in ALL_CLASSIFICATIONS:
        return (
            _error_payload(f"unknown classification: {classification!r}"),
            EXIT_USAGE_ERROR,
        )
    all_state = load_state(state_file)
    _maybe_reset_on_head_change(all_state, current_head)
    all_state["tick_count"] = int(all_state.get("tick_count") or 0) + 1

    if classification == CLASSIFICATION_DOWN:
        return _after_bugbot_down(all_state, state_file)
    if classification == CLASSIFICATION_DIRTY:
        return _after_bugbot_dirty(
            all_state, state_file, is_inline_lag=is_inline_lag
        )
    if classification == CLASSIFICATION_ABSENT:
        wait_count = int(all_state.get("bugbot_wait_count") or 0) + 1
        all_state["bugbot_wait_count"] = wait_count
        if wait_count >= BUGBOT_ABSENT_WAIT_HARD_CAP:
            all_state["phase"] = PHASE_BLOCKED
            all_state["blocker"] = BLOCKER_BUGBOT_WAIT_CAP
            return _finish_ok(
                all_state,
                state_file,
                next_action=NEXT_STOP_BLOCKED,
                all_commands=_EMPTY_COMMANDS,
                wait_seconds=None,
                blocker=BLOCKER_BUGBOT_WAIT_CAP,
                all_extra_fields=None,
            )
        all_state["phase"] = PHASE_BUGBOT
        return _finish_ok(
            all_state,
            state_file,
            next_action=NEXT_POLL_WAIT,
            all_commands=_EMPTY_COMMANDS,
            wait_seconds=DEFAULT_WAIT_SECONDS,
            blocker=None,
            all_extra_fields=None,
        )
    return _after_bugbot_clean(all_state, state_file, current_head)


def _after_copilot_not_surfaced(
    all_state: dict[str, object],
    state_file: Path,
) -> tuple[dict[str, object], int]:
    wait_count = int(all_state.get("copilot_wait_count") or 0) + 1
    all_state["copilot_wait_count"] = wait_count
    if wait_count >= COPILOT_WAIT_HARD_CAP:
        all_state["phase"] = PHASE_BLOCKED
        all_state["blocker"] = BLOCKER_COPILOT_WAIT_CAP
        return _finish_ok(
            all_state,
            state_file,
            next_action=NEXT_STOP_BLOCKED,
            all_commands=_EMPTY_COMMANDS,
            wait_seconds=None,
            blocker=BLOCKER_COPILOT_WAIT_CAP,
            all_extra_fields=None,
        )
    all_state["phase"] = PHASE_COPILOT_WAIT
    return _finish_ok(
        all_state,
        state_file,
        next_action=NEXT_POLL_WAIT,
        all_commands=_EMPTY_COMMANDS,
        wait_seconds=DEFAULT_WAIT_SECONDS,
        blocker=None,
        all_extra_fields=None,
    )


def _after_copilot_clean(
    all_state: dict[str, object],
    state_file: Path,
    current_head: str,
) -> tuple[dict[str, object], int]:
    all_state["copilot_clean_at"] = current_head
    all_state["phase"] = PHASE_READY
    return _finish_ok(
        all_state,
        state_file,
        next_action=NEXT_CHECK_READY,
        all_commands=_check_convergence_commands_from_state(all_state),
        wait_seconds=None,
        blocker=None,
        all_extra_fields=None,
    )


def _after_copilot_down(
    all_state: dict[str, object],
    state_file: Path,
) -> tuple[dict[str, object], int]:
    all_state["copilot_down"] = True
    _sync_task_list_from_down_flags(all_state)
    all_state["phase"] = PHASE_READY
    return _finish_ok(
        all_state,
        state_file,
        next_action=NEXT_CHECK_READY,
        all_commands=_check_convergence_commands_from_state(all_state),
        wait_seconds=None,
        blocker=None,
        all_extra_fields=None,
    )


def _after_copilot_surfaced(
    all_state: dict[str, object],
    state_file: Path,
    *,
    classification: str,
    current_head: str,
) -> tuple[dict[str, object], int]:
    if classification not in ALL_COPILOT_CLASSIFICATIONS:
        return (
            _error_payload(f"unknown classification: {classification!r}"),
            EXIT_USAGE_ERROR,
        )
    if classification == CLASSIFICATION_DIRTY:
        all_state["copilot_wait_count"] = 0
        all_state["phase"] = PHASE_CODE_REVIEW
        return _finish_ok(
            all_state,
            state_file,
            next_action=NEXT_APPLY_FIXES,
            all_commands=_EMPTY_COMMANDS,
            wait_seconds=None,
            blocker=None,
            all_extra_fields=None,
        )
    if classification == CLASSIFICATION_ABSENT:
        return _after_copilot_not_surfaced(all_state, state_file)
    if classification == CLASSIFICATION_DOWN:
        return _after_copilot_down(all_state, state_file)
    return _after_copilot_clean(all_state, state_file, current_head)


def run_after_copilot_wait(
    *,
    state_file: Path,
    is_review_surfaced: bool,
    classification: str,
    current_head: str,
) -> tuple[dict[str, object], int]:
    """Advance state from a Copilot wait poll.

    Args:
        state_file: Loop state path.
        is_review_surfaced: A Copilot review exists at current_head.
        classification: clean, dirty, absent, or down when surfaced.
        current_head: Current PR head SHA.

    Returns:
        Payload and process exit code.
    """
    all_state = load_state(state_file)
    _maybe_reset_on_head_change(all_state, current_head)
    all_state["tick_count"] = int(all_state.get("tick_count") or 0) + 1
    if not is_review_surfaced:
        return _after_copilot_not_surfaced(all_state, state_file)
    return _after_copilot_surfaced(
        all_state,
        state_file,
        classification=classification,
        current_head=current_head,
    )


def run_after_ready_check(
    *,
    state_file: Path,
    check_exit: int,
    current_head: str,
) -> tuple[dict[str, object], int]:
    """Advance state from check_convergence exit code.

    Args:
        state_file: Loop state path.
        check_exit: Process exit from check_convergence.py.
        current_head: Current PR head SHA.

    Returns:
        Payload and process exit code.
    """
    all_state = load_state(state_file)
    _maybe_reset_on_head_change(all_state, current_head)
    all_state["tick_count"] = int(all_state.get("tick_count") or 0) + 1
    if check_exit == 0:
        all_state["phase"] = PHASE_READY
        all_state["blocker"] = None
        return _finish_ok(
            all_state,
            state_file,
            next_action=NEXT_MARK_READY,
            all_commands=_mark_ready_commands(all_state),
            wait_seconds=None,
            blocker=None,
            all_extra_fields=None,
        )

    if check_exit == 1:
        _ensure_codex_required_matches_usage(all_state)
        if _needs_codex_step(all_state):
            all_state["phase"] = PHASE_BUGBOT
            return _finish_ok(
                all_state,
                state_file,
                next_action=NEXT_RUN_CODEX,
                all_commands=_EMPTY_COMMANDS,
                wait_seconds=None,
                blocker=None,
                all_extra_fields=None,
            )
        all_state["phase"] = PHASE_CODE_REVIEW
        return _finish_ok(
            all_state,
            state_file,
            next_action=NEXT_APPLY_FIXES,
            all_commands=_EMPTY_COMMANDS,
            wait_seconds=None,
            blocker=None,
            all_extra_fields=None,
        )

    all_state["phase"] = PHASE_BLOCKED
    all_state["blocker"] = f"check_convergence_exit_{check_exit}"
    return _finish_ok(
        all_state,
        state_file,
        next_action=NEXT_STOP_BLOCKED,
        all_commands=_EMPTY_COMMANDS,
        wait_seconds=None,
        blocker=str(all_state["blocker"]),
        all_extra_fields=None,
    )


def _register_open_run_arguments(
    open_run_parser: argparse.ArgumentParser,
) -> None:
    open_run_parser.add_argument(CLI_SKILL_FLAG, required=True)
    open_run_parser.add_argument(CLI_HAS_WORKFLOW_FLAG, required=True)
    open_run_parser.add_argument(CLI_HAS_SCHEDULE_WAKEUP_FLAG, required=True)
    open_run_parser.add_argument(CLI_OWNER_FLAG, required=True)
    open_run_parser.add_argument(CLI_REPO_FLAG, required=True)
    open_run_parser.add_argument(CLI_PR_NUMBER_FLAG, required=True, type=int)
    open_run_parser.add_argument(CLI_CWD_FLAG, required=True)
    open_run_parser.add_argument(CLI_STATE_DIR_FLAG, required=True)
    open_run_parser.add_argument(
        CLI_SESSION_MODEL_FLAG, default=DEFAULT_SESSION_MODEL
    )
    open_run_parser.add_argument(CLI_COPILOT_DOWN_FLAG, default="0")
    open_run_parser.add_argument(CLI_BUGBOT_DOWN_FLAG, default="0")
    open_run_parser.add_argument(CLI_CODEX_DOWN_FLAG, default="0")
    open_run_parser.add_argument(CLI_CODEX_REQUIRED_FLAG, default="0")


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the multi-command CLI parser.

    Returns:
        Configured argument parser.
    """
    parser = argparse.ArgumentParser(description=CLI_DESCRIPTION)
    all_subparsers = parser.add_subparsers(dest="command", required=True)

    open_run_parser = all_subparsers.add_parser(COMMAND_OPEN_RUN)
    _register_open_run_arguments(open_run_parser)

    after_review_parser = all_subparsers.add_parser(COMMAND_AFTER_CODE_REVIEW)
    after_review_parser.add_argument(CLI_STATE_FILE_FLAG, required=True)
    after_review_parser.add_argument(
        CLI_RETURNCODE_FLAG, required=True, type=int
    )
    after_review_parser.add_argument(CLI_DIRTY_TREE_FLAG, required=True)
    after_review_parser.add_argument(CLI_SERVED_COMMAND_FLAG, default="")
    after_review_parser.add_argument(CLI_CURRENT_HEAD_FLAG, required=True)

    after_bugteam_parser = all_subparsers.add_parser(COMMAND_AFTER_BUGTEAM)
    after_bugteam_parser.add_argument(CLI_STATE_FILE_FLAG, required=True)
    after_bugteam_parser.add_argument(CLI_PUSHED_FLAG, required=True)
    after_bugteam_parser.add_argument(CLI_CONVERGED_FLAG, required=True)
    after_bugteam_parser.add_argument(CLI_CURRENT_HEAD_FLAG, required=True)

    after_bugbot_parser = all_subparsers.add_parser(COMMAND_AFTER_BUGBOT)
    after_bugbot_parser.add_argument(CLI_STATE_FILE_FLAG, required=True)
    after_bugbot_parser.add_argument(CLI_CLASSIFICATION_FLAG, required=True)
    after_bugbot_parser.add_argument(CLI_CURRENT_HEAD_FLAG, required=True)
    after_bugbot_parser.add_argument(CLI_INLINE_LAG_FLAG, default="0")

    after_codex_parser = all_subparsers.add_parser(COMMAND_AFTER_CODEX)
    after_codex_parser.add_argument(CLI_STATE_FILE_FLAG, required=True)
    after_codex_parser.add_argument(CLI_CLASSIFICATION_FLAG, required=True)
    after_codex_parser.add_argument(CLI_CURRENT_HEAD_FLAG, required=True)

    after_copilot_parser = all_subparsers.add_parser(COMMAND_AFTER_COPILOT_WAIT)
    after_copilot_parser.add_argument(CLI_STATE_FILE_FLAG, required=True)
    after_copilot_parser.add_argument(CLI_REVIEW_SURFACED_FLAG, required=True)
    after_copilot_parser.add_argument(
        CLI_CLASSIFICATION_FLAG, default="absent"
    )
    after_copilot_parser.add_argument(CLI_CURRENT_HEAD_FLAG, required=True)

    after_ready_parser = all_subparsers.add_parser(COMMAND_AFTER_READY_CHECK)
    after_ready_parser.add_argument(CLI_STATE_FILE_FLAG, required=True)
    after_ready_parser.add_argument(
        CLI_CHECK_CONVERGENCE_EXIT_FLAG, required=True, type=int
    )
    after_ready_parser.add_argument(CLI_CURRENT_HEAD_FLAG, required=True)

    show_parser = all_subparsers.add_parser(COMMAND_SHOW_STATE)
    show_parser.add_argument(CLI_STATE_FILE_FLAG, required=True)

    return parser


def _dispatch_open_run(
    parsed_arguments: argparse.Namespace,
) -> tuple[dict[str, object], int]:
    return run_open_run(
        entry_skill=parsed_arguments.skill,
        has_workflow=parse_bool_flag(parsed_arguments.has_workflow),
        has_schedule_wakeup=parse_bool_flag(
            parsed_arguments.has_schedule_wakeup
        ),
        owner=parsed_arguments.owner,
        repo=parsed_arguments.repo,
        pr_number=parsed_arguments.pr_number,
        cwd_path=Path(parsed_arguments.cwd),
        state_dir=Path(parsed_arguments.state_dir),
        session_model=parsed_arguments.session_model,
        is_copilot_down=parse_bool_flag(parsed_arguments.copilot_down),
        is_bugbot_down=parse_bool_flag(parsed_arguments.bugbot_down),
        is_codex_down=parse_bool_flag(parsed_arguments.codex_down),
        is_codex_required=parse_bool_flag(parsed_arguments.codex_required),
    )


def _dispatch_after_code_review(
    parsed_arguments: argparse.Namespace,
) -> tuple[dict[str, object], int]:
    return run_after_code_review(
        state_file=Path(parsed_arguments.state_file),
        returncode=parsed_arguments.returncode,
        is_dirty_tree=parse_bool_flag(parsed_arguments.dirty_tree),
        served_command=parsed_arguments.served_command or "",
        current_head=parsed_arguments.current_head,
    )


def _dispatch_after_bugteam(
    parsed_arguments: argparse.Namespace,
) -> tuple[dict[str, object], int]:
    return run_after_bugteam(
        state_file=Path(parsed_arguments.state_file),
        is_pushed=parse_bool_flag(parsed_arguments.pushed),
        is_converged=parse_bool_flag(parsed_arguments.converged),
        current_head=parsed_arguments.current_head,
    )


def _dispatch_after_bugbot(
    parsed_arguments: argparse.Namespace,
) -> tuple[dict[str, object], int]:
    return run_after_bugbot(
        state_file=Path(parsed_arguments.state_file),
        classification=parsed_arguments.classification,
        current_head=parsed_arguments.current_head,
        is_inline_lag=parse_bool_flag(parsed_arguments.inline_lag),
    )


def _dispatch_after_codex(
    parsed_arguments: argparse.Namespace,
) -> tuple[dict[str, object], int]:
    return run_after_codex(
        state_file=Path(parsed_arguments.state_file),
        classification=parsed_arguments.classification,
        current_head=parsed_arguments.current_head,
    )


def _dispatch_after_copilot_wait(
    parsed_arguments: argparse.Namespace,
) -> tuple[dict[str, object], int]:
    return run_after_copilot_wait(
        state_file=Path(parsed_arguments.state_file),
        is_review_surfaced=parse_bool_flag(parsed_arguments.review_surfaced),
        classification=parsed_arguments.classification,
        current_head=parsed_arguments.current_head,
    )


def _dispatch_after_ready_check(
    parsed_arguments: argparse.Namespace,
) -> tuple[dict[str, object], int]:
    return run_after_ready_check(
        state_file=Path(parsed_arguments.state_file),
        check_exit=parsed_arguments.check_exit,
        current_head=parsed_arguments.current_head,
    )


def _resolve_show_state_next(all_state: Mapping[str, object]) -> str:
    pending_next = all_state.get(STATE_KEY_PENDING_NEXT)
    if isinstance(pending_next, str) and pending_next:
        return pending_next
    if all_state.get("phase") == PHASE_READY:
        return NEXT_MARK_READY
    if all_state.get("phase") == PHASE_BLOCKED:
        return NEXT_STOP_BLOCKED
    return str(all_state.get("phase"))


def _dispatch_show_state(
    parsed_arguments: argparse.Namespace,
) -> tuple[dict[str, object], int]:
    state_file = Path(parsed_arguments.state_file)
    all_state = load_state(state_file)
    all_payload = _base_ok_payload(all_state, state_file)
    next_action = _resolve_show_state_next(all_state)
    all_payload[RESULT_KEY_NEXT] = next_action
    if next_action == NEXT_RUN_CODE_REVIEW:
        all_payload[RESULT_KEY_COMMANDS] = _code_review_commands_from_state(
            all_state
        )
    elif next_action == NEXT_CHECK_READY:
        all_payload[RESULT_KEY_COMMANDS] = (
            _check_convergence_commands_from_state(all_state)
        )
    elif next_action == NEXT_RUN_BUGTEAM:
        all_payload[RESULT_KEY_COMMANDS] = _clean_comment_commands_from_state(
            all_state,
            head_sha=str(all_state.get(STATE_KEY_CODE_REVIEW_CLEAN_AT) or ""),
            served_command=str(all_state.get(STATE_KEY_SERVED_COMMAND) or ""),
        )
    elif next_action == NEXT_MARK_READY:
        all_payload[RESULT_KEY_COMMANDS] = _mark_ready_commands(all_state)
    elif next_action == NEXT_POLL_WAIT:
        all_payload[RESULT_KEY_WAIT_SECONDS] = _resolve_poll_wait_seconds(
            all_state
        )
    return all_payload, EXIT_SUCCESS


def main(all_argv: list[str]) -> int:
    """CLI entry: print one JSON control payload on stdout.

    Args:
        all_argv: Argument vector without program name.

    Returns:
        Process exit code.
    """
    parser = build_argument_parser()
    parsed_arguments = parser.parse_args(all_argv)
    dispatch_by_command = {
        COMMAND_OPEN_RUN: _dispatch_open_run,
        COMMAND_AFTER_CODE_REVIEW: _dispatch_after_code_review,
        COMMAND_AFTER_BUGTEAM: _dispatch_after_bugteam,
        COMMAND_AFTER_BUGBOT: _dispatch_after_bugbot,
        COMMAND_AFTER_CODEX: _dispatch_after_codex,
        COMMAND_AFTER_COPILOT_WAIT: _dispatch_after_copilot_wait,
        COMMAND_AFTER_READY_CHECK: _dispatch_after_ready_check,
        COMMAND_SHOW_STATE: _dispatch_show_state,
    }
    try:
        maybe_dispatch = dispatch_by_command.get(parsed_arguments.command)
        if maybe_dispatch is None:
            _emit(
                _error_payload(
                    f"unknown command: {parsed_arguments.command!r}"
                )
            )
            return EXIT_USAGE_ERROR
        all_payload, exit_code = maybe_dispatch(parsed_arguments)
        _emit(all_payload)
        return exit_code
    except ValueError as validation_error:
        _emit(_error_payload(str(validation_error)))
        return EXIT_USAGE_ERROR


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
