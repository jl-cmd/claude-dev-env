#!/usr/bin/env python3
"""Host-aware helper that runs the built-in review slash command on opus.

Mode decision::

    host=Claude, session_model=opus  -> mode in_session (skill runs slash cmd)
    host=Claude, session_model=sonnet -> mode chain (headless opus spawn)
    host=ThirdParty, any model        -> mode chain

Chain mode runs ``run_claude`` with argv from ``build_code_review_arguments``
(single-turn prompt, model opus, json output, and the permission mode this
caller is allowed to ask the review binary for).

cwd is the PR working tree and stdin is redirected from the empty stream so
the spawn does not wait for interactive input. Result JSON on stdout only::

    {"mode", "served_command", "returncode", "dirty_tree"}

Import ``invoke_code_review`` for the outcome object, or run as a CLI::

    python invoke_code_review.py --cwd <dir> --session-model <alias>
        [--timeout-seconds N] [effort]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

_scripts_directory_path = Path(__file__).resolve().parent
_scripts_directory = str(_scripts_directory_path)
sys.path[:] = [
    each_existing_entry
    for each_existing_entry in sys.path
    if each_existing_entry != _scripts_directory
]
sys.path[:0] = [_scripts_directory]

_advisor_scripts_path = str(
    _scripts_directory_path.parent / "_shared" / "advisor" / "scripts"
)
sys.path[:] = [
    each_existing_entry
    for each_existing_entry in sys.path
    if each_existing_entry != _advisor_scripts_path
]
sys.path[:0] = [_advisor_scripts_path]

from tier_model_ids import detect_host_profile  # noqa: E402
from advisor_scripts_constants.model_tier_run_validator_constants import (  # noqa: E402
    HOST_PROFILE_CLAUDE,
)
import claude_chain_runner as chain_runner  # noqa: E402
from claude_chain_runner import (  # noqa: E402
    ChainConfigurationError,
    ChainInvocationOutcome,
    run_claude,
)
from dev_env_scripts_constants.claude_chain_constants import (  # noqa: E402
    CHAIN_CONFIG_ERROR_EXIT_CODE,
    collect_forwarded_text_codec,
)
from dev_env_scripts_constants.code_review_constants import (  # noqa: E402
    ALL_EFFORT_TOKENS_IN_ASCENDING_ORDER,
    CLI_EFFORT_HELP,
    CLI_EFFORT_METAVAR,
    CLI_SESSION_MODEL_FLAG,
    CODE_REVIEW_FIX_FLAG,
    CODE_REVIEW_MODEL_ALIAS,
    CODE_REVIEW_SLASH_COMMAND,
    DEFAULT_CODE_REVIEW_EFFORT,
    EFFORT_TOKEN_LIST_SEPARATOR,
    GIT_BINARY,
    GIT_PORCELAIN_FLAG,
    GIT_STATUS_SUBCOMMAND,
    HOST_PROFILE_ERROR_RETURNCODE,
    IN_SESSION_RETURNCODE,
    INVALID_EFFORT_MESSAGE,
    INVALID_EFFORT_RETURNCODE,
    MODE_CHAIN,
    MODE_IN_SESSION,
    REVIEW_PERMISSION_MODE as PERMISSION_MODE_BYPASS,
    PERMISSION_MODE_FLAG,
    RESULT_KEY_DIRTY_TREE,
    RESULT_KEY_MODE,
    RESULT_KEY_RETURNCODE,
    RESULT_KEY_SERVED_COMMAND,
    SUCCESSFUL_REVIEW_RETURNCODE,
)
from dev_env_scripts_constants.grok_worker_constants import (  # noqa: E402
    CLI_TIMEOUT_FLAG,
    CWD_FLAG,
    MODEL_FLAG,
    OUTPUT_FORMAT_FLAG,
    OUTPUT_FORMAT_JSON,
    SINGLE_TURN_FLAG,
)
from dev_env_scripts_constants.timing import (  # noqa: E402
    DEFAULT_CODE_REVIEW_TIMEOUT_SECONDS,
)


@dataclass(frozen=True)
class CodeReviewOutcome:
    """Outcome of a host-aware code-review invocation.

    ``mode`` is ``in_session`` when the skill should run the slash command
    itself, or ``chain`` when a headless spawn already ran. ``served_command``
    names the chain binary that served a chain run, or ``None`` otherwise.
    ``is_dirty_tree`` is True when ``git status --porcelain`` is non-empty
    after a chain run (fixes applied).
    """

    mode: str
    served_command: str | None
    returncode: int
    is_dirty_tree: bool


review_claude_runner = run_claude
review_host_profile_detector = detect_host_profile
review_git_status_runner = subprocess.run

TextCapturingSubprocessRunner = Callable[
    ...,
    subprocess.CompletedProcess[str],
]


def is_opus_session_model(session_model: str) -> bool:
    """Return True when *session_model* is the opus short alias (any letter case).

    ::

        is_opus_session_model("opus")   # ok: True
        is_opus_session_model("Opus")   # ok: True
        is_opus_session_model("sonnet") # ok: False

    Args:
        session_model: Caller-stated session model short alias.

    Returns:
        True when the normalized alias matches the code-review model pin.
    """
    return session_model.strip().lower() == CODE_REVIEW_MODEL_ALIAS


def decide_review_mode(*, host_profile: str, session_model: str) -> str:
    """Return ``in_session`` or ``chain`` from host profile and session model.

    ::

        decide_review_mode(host_profile="Claude", session_model="opus")
            # ok: "in_session"
        decide_review_mode(host_profile="Claude", session_model="sonnet")
            # ok: "chain"

    Args:
        host_profile: Detected host profile (``Claude`` or ``ThirdParty``).
        session_model: Caller-stated session model short alias.

    Returns:
        ``MODE_IN_SESSION`` only for Claude host on opus; otherwise ``MODE_CHAIN``.
    """
    is_claude_host = host_profile == HOST_PROFILE_CLAUDE
    if is_claude_host and is_opus_session_model(session_model):
        return MODE_IN_SESSION
    return MODE_CHAIN


def build_code_review_prompt(effort: str) -> str:
    """Build the single-turn slash-command prompt for the given effort.

    ::

        build_code_review_prompt("low")   # ok: "/code-review low --fix"
        build_code_review_prompt("xhigh") # ok: "/code-review xhigh --fix"

    Args:
        effort: A validated effort token from the ascending order tuple.

    Returns:
        The ``/code-review <effort> --fix`` prompt string.
    """
    return f"{CODE_REVIEW_SLASH_COMMAND} {effort} {CODE_REVIEW_FIX_FLAG}"


def build_code_review_arguments(
    effort: str = DEFAULT_CODE_REVIEW_EFFORT,
) -> list[str]:
    """Return the argv tokens passed to ``run_claude`` for a chain review.

    ::

        build_code_review_arguments("high")
            # ok: ["-p", "/code-review high --fix", "--model", "opus", ...]

    Args:
        effort: Effort token embedded in the slash-command prompt.

    Returns:
        Ordered claude CLI arguments for the headless opus review slash command.
    """
    return [
        SINGLE_TURN_FLAG,
        build_code_review_prompt(effort),
        MODEL_FLAG,
        CODE_REVIEW_MODEL_ALIAS,
        OUTPUT_FORMAT_FLAG,
        OUTPUT_FORMAT_JSON,
        PERMISSION_MODE_FLAG,
        PERMISSION_MODE_BYPASS,
    ]


def validate_effort_token(effort: str) -> str | None:
    """Return an error message when *effort* is unknown or unsupported.

    ::

        validate_effort_token("low")    # ok: None
        validate_effort_token("ultra")  # flag: error mentioning ultra
        validate_effort_token("bogus")  # flag: error listing allowed tokens

    Args:
        effort: Caller-supplied effort token.

    Returns:
        None when the token is allowed; otherwise a human-readable error.
    """
    if effort in ALL_EFFORT_TOKENS_IN_ASCENDING_ORDER:
        return None
    allowed_tokens = EFFORT_TOKEN_LIST_SEPARATOR.join(
        ALL_EFFORT_TOKENS_IN_ASCENDING_ORDER
    )
    return INVALID_EFFORT_MESSAGE.format(effort=effort, allowed=allowed_tokens)


def is_working_tree_dirty(working_directory: Path) -> bool:
    """Return True when the tree is dirty or ``git status`` fails.

    ::

        is_working_tree_dirty(clean_repo)  # ok: False
        is_working_tree_dirty(dirty_repo)  # ok: True
        is_working_tree_dirty(broken_git)  # ok: True (non-zero status)

    A non-zero ``git status`` return code reports a dirty tree.

    Args:
        working_directory: Git working tree to inspect.

    Returns:
        True when porcelain output is non-empty, or when git status exits
        non-zero.
    """
    completion = review_git_status_runner(
        [GIT_BINARY, GIT_STATUS_SUBCOMMAND, GIT_PORCELAIN_FLAG],
        cwd=str(working_directory),
        capture_output=True,
        text=True,
        check=False,
    )
    if completion.returncode != 0:
        return True
    return bool(completion.stdout.strip())


def is_successful_code_review(review_outcome: CodeReviewOutcome) -> bool:
    """Return True when the invocation completed a successful review serve.

    ::

        is_successful_code_review(in_session_ok)   # ok: True
        is_successful_code_review(chain_served)    # ok: True
        is_successful_code_review(chain_failed)    # ok: False

    Success requires ``returncode == 0``. Chain mode also requires a non-null
    ``served_command``. In-session mode hands the slash command to the skill,
    so ``served_command`` stays null by design.

    Args:
        review_outcome: Structured outcome from ``invoke_code_review``.

    Returns:
        True when the outcome is a successful review serve.
    """
    if review_outcome.returncode != SUCCESSFUL_REVIEW_RETURNCODE:
        return False
    if review_outcome.mode == MODE_CHAIN and review_outcome.served_command is None:
        return False
    return True


def _run_claude_with_empty_stdin(
    all_claude_arguments: list[str],
    *,
    timeout_seconds: int,
    working_directory: Path,
) -> ChainInvocationOutcome:
    working_directory_path = str(working_directory)

    def _runner_with_empty_stdin(
        all_invocation_tokens: Sequence[str],
        *all_positionals: object,
        **all_keywords: object,
    ) -> subprocess.CompletedProcess[str]:
        del all_positionals
        maybe_timeout = all_keywords.get("timeout")
        timeout_for_run: float | None
        if isinstance(maybe_timeout, (int, float)):
            timeout_for_run = float(maybe_timeout)
        else:
            timeout_for_run = None
        forwarded_text_codec = collect_forwarded_text_codec(all_keywords)
        completed_process: subprocess.CompletedProcess[str] = previous_runner(
            all_invocation_tokens,
            capture_output=True,
            text=True,
            timeout=timeout_for_run,
            check=False,
            stdin=subprocess.DEVNULL,
            cwd=working_directory_path,
            **forwarded_text_codec,
        )
        return completed_process

    empty_stdin_runner: TextCapturingSubprocessRunner = _runner_with_empty_stdin
    with chain_runner.override_chain_subprocess_runner(
        empty_stdin_runner
    ) as previous_runner:
        return review_claude_runner(
            all_claude_arguments, timeout_seconds=timeout_seconds
        )


def _in_session_outcome() -> CodeReviewOutcome:
    return CodeReviewOutcome(
        mode=MODE_IN_SESSION,
        served_command=None,
        returncode=IN_SESSION_RETURNCODE,
        is_dirty_tree=False,
    )


def _chain_outcome(
    chain_outcome: ChainInvocationOutcome,
    *,
    working_directory: Path,
) -> CodeReviewOutcome:
    return CodeReviewOutcome(
        mode=MODE_CHAIN,
        served_command=chain_outcome.served_command,
        returncode=chain_outcome.returncode,
        is_dirty_tree=is_working_tree_dirty(working_directory),
    )


def _failure_code_review_outcome(returncode: int) -> CodeReviewOutcome:
    return CodeReviewOutcome(
        mode=MODE_CHAIN,
        served_command=None,
        returncode=returncode,
        is_dirty_tree=False,
    )


def _run_chain_review(
    *,
    working_directory: Path,
    timeout_seconds: int,
    effort: str,
) -> CodeReviewOutcome:
    all_claude_arguments = build_code_review_arguments(effort)
    chain_outcome = _run_claude_with_empty_stdin(
        all_claude_arguments,
        timeout_seconds=timeout_seconds,
        working_directory=working_directory,
    )
    if chain_outcome.returncode != SUCCESSFUL_REVIEW_RETURNCODE and chain_outcome.stderr:
        sys.stderr.write(chain_outcome.stderr.strip() + "\n")
    return _chain_outcome(chain_outcome, working_directory=working_directory)


def invoke_code_review(
    *,
    working_directory: Path,
    session_model: str,
    timeout_seconds: int,
    effort: str = DEFAULT_CODE_REVIEW_EFFORT,
) -> CodeReviewOutcome:
    """Run or hand off ``/code-review`` based on host profile and session model.

    ::

        Claude + opus  -> in_session (no spawn)
        any host with sonnet -> chain (headless spawn)

    Args:
        working_directory: PR working tree used as cwd for the chain spawn.
        session_model: Caller-stated session model short alias.
        timeout_seconds: Timeout applied to each chain binary invocation.
        effort: Effort token embedded in the ``/code-review`` prompt.

    Returns:
        Structured outcome including mode, served binary, return code, and
        whether the working tree is dirty after a chain run.
    """
    host_profile = review_host_profile_detector()
    review_mode = decide_review_mode(
        host_profile=host_profile,
        session_model=session_model,
    )
    if review_mode == MODE_IN_SESSION:
        return _in_session_outcome()
    return _run_chain_review(
        working_directory=working_directory,
        timeout_seconds=timeout_seconds,
        effort=effort,
    )


def encode_code_review_outcome(
    review_outcome: CodeReviewOutcome,
) -> dict[str, object]:
    """Encode a code-review outcome as the JSON-serializable payload.

    Args:
        review_outcome: The invoker outcome to encode.

    Returns:
        A plain dict matching the CLI JSON shape.
    """
    return {
        RESULT_KEY_MODE: review_outcome.mode,
        RESULT_KEY_SERVED_COMMAND: review_outcome.served_command,
        RESULT_KEY_RETURNCODE: review_outcome.returncode,
        RESULT_KEY_DIRTY_TREE: review_outcome.is_dirty_tree,
    }


def _add_review_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        CWD_FLAG,
        dest="working_directory",
        required=True,
        type=Path,
        help="PR working tree used as cwd for the chain spawn.",
    )
    parser.add_argument(
        CLI_SESSION_MODEL_FLAG,
        dest="session_model",
        required=True,
        help="Caller session model short alias (for example opus or sonnet).",
    )
    parser.add_argument(
        CLI_TIMEOUT_FLAG,
        dest="timeout_seconds",
        type=int,
        default=DEFAULT_CODE_REVIEW_TIMEOUT_SECONDS,
        help="Timeout in seconds applied to each chain binary invocation.",
    )


def _add_effort_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        CLI_EFFORT_METAVAR,
        nargs="?",
        default=DEFAULT_CODE_REVIEW_EFFORT,
        help=CLI_EFFORT_HELP,
    )


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run built-in /code-review at a chosen effort on opus, host-aware."
        )
    )
    _add_review_arguments(parser)
    _add_effort_argument(parser)
    return parser


def _emit_invalid_effort_and_exit_code(effort: str) -> int:
    error_message = validate_effort_token(effort)
    if error_message is None:
        return SUCCESSFUL_REVIEW_RETURNCODE
    sys.stderr.write(error_message + "\n")
    return INVALID_EFFORT_RETURNCODE


def _run_plain_review_cli(*, parsed_arguments: argparse.Namespace, effort: str) -> int:
    try:
        review_outcome = invoke_code_review(
            working_directory=parsed_arguments.working_directory,
            session_model=parsed_arguments.session_model,
            timeout_seconds=parsed_arguments.timeout_seconds,
            effort=effort,
        )
    except ChainConfigurationError:
        review_outcome = _failure_code_review_outcome(CHAIN_CONFIG_ERROR_EXIT_CODE)
    except ValueError:
        review_outcome = _failure_code_review_outcome(HOST_PROFILE_ERROR_RETURNCODE)
    sys.stdout.write(json.dumps(encode_code_review_outcome(review_outcome)) + "\n")
    return review_outcome.returncode


def main(all_command_arguments: list[str]) -> int:
    """Run the invoker for CLI arguments and print the JSON outcome.

    An unknown or ``ultra`` effort exits non-zero before any review runs.

    Args:
        all_command_arguments: The argument vector after the program name.

    Returns:
        The outcome return code (``0`` for in-session; chain return code
        otherwise; non-zero when effort is invalid or minting fails to converge).
    """
    parser = _build_argument_parser()
    parsed_arguments = parser.parse_args(all_command_arguments)
    effort_token = str(parsed_arguments.effort)
    invalid_effort_exit_code = _emit_invalid_effort_and_exit_code(effort_token)
    if invalid_effort_exit_code != SUCCESSFUL_REVIEW_RETURNCODE:
        return invalid_effort_exit_code
    return _run_plain_review_cli(parsed_arguments=parsed_arguments, effort=effort_token)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
