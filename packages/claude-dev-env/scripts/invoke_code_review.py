#!/usr/bin/env python3
"""Host-aware helper that runs the built-in review slash command on opus.

Mode decision::

    session_has_usage_left=false      -> mode chain (force; primary drained)
    host=Claude, session_model=opus   -> mode in_session (skill runs slash cmd)
    host=Claude, session_model=sonnet -> mode chain (headless opus spawn)
    host=ThirdParty, any model        -> mode chain

Chain mode runs ``run_claude`` (``claude_chain_runner``) with argv from
``build_code_review_arguments`` (single-turn prompt, model opus, json output,
bypassPermissions).

cwd is the PR working tree and stdin is redirected from the empty stream so
the spawn does not wait for interactive input. Result JSON on stdout only::

    {"mode", "served_command", "returncode", "dirty_tree"}

A clean stamp requires a successful serve (``returncode == 0``, and for chain
mode a non-null ``served_command``) plus ``dirty_tree`` false. A failed chain
or config/host error leaves the tree clean but must not advance past
CODE_REVIEW — use ``is_code_review_clean_stamp_allowed``.

Import ``invoke_code_review`` for the outcome object, or run as a CLI::

    python invoke_code_review.py --cwd <dir> --session-model <alias>
        [--timeout-seconds N]
        [--session-has-usage-left true|false|unknown]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

_advisor_scripts_path = str(
    Path(__file__).resolve().parent.parent / "_shared" / "advisor" / "scripts"
)
if _advisor_scripts_path not in sys.path:
    sys.path.insert(0, _advisor_scripts_path)

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
)
from dev_env_scripts_constants.code_review_constants import (  # noqa: E402
    CLI_SESSION_HAS_USAGE_LEFT_FLAG,
    CLI_SESSION_MODEL_FLAG,
    CODE_REVIEW_MODEL_ALIAS,
    CODE_REVIEW_PROMPT,
    GIT_BINARY,
    GIT_PORCELAIN_FLAG,
    GIT_STATUS_SUBCOMMAND,
    HOST_PROFILE_ERROR_RETURNCODE,
    IN_SESSION_RETURNCODE,
    MODE_CHAIN,
    MODE_IN_SESSION,
    PERMISSION_MODE_BYPASS,
    PERMISSION_MODE_FLAG,
    RESULT_KEY_DIRTY_TREE,
    RESULT_KEY_MODE,
    RESULT_KEY_RETURNCODE,
    RESULT_KEY_SERVED_COMMAND,
    SESSION_HAS_USAGE_LEFT_FALSE,
    SESSION_HAS_USAGE_LEFT_TRUE,
    SESSION_HAS_USAGE_LEFT_UNKNOWN,
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
from tier_model_ids import detect_host_profile  # noqa: E402

_CHAIN_RUNNER_LOCK = threading.Lock()


def _chain_runner_lock() -> threading.Lock:
    """Return the module lock that serializes chain-runner stdin/cwd swaps."""
    return _CHAIN_RUNNER_LOCK


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


def decide_review_mode(
    *,
    host_profile: str,
    session_model: str,
    session_has_usage_left: bool | None = None,
) -> str:
    """Return ``in_session`` or ``chain`` from host, model, and usage probe.

    ::

        decide_review_mode(host_profile="Claude", session_model="opus")
            # ok: "in_session"
        decide_review_mode(host_profile="Claude", session_model="sonnet")
            # ok: "chain"
        decide_review_mode(host_profile="ThirdParty", session_model="opus")
            # ok: "chain"
        decide_review_mode(
            host_profile="Claude",
            session_model="opus",
            session_has_usage_left=False,
        )  # ok: "chain"

    Args:
        host_profile: Detected host profile (``Claude`` or ``ThirdParty``).
        session_model: Caller-stated session model short alias.
        session_has_usage_left: Usage-probe decision for the primary session.
            ``False`` forces chain so another chain binary can serve when the
            primary account is drained. ``True`` and ``None`` keep host/model
            rules.

    Returns:
        ``MODE_IN_SESSION`` only for Claude host on opus with usage left
        unknown or true; otherwise ``MODE_CHAIN``.
    """
    if session_has_usage_left is False:
        return MODE_CHAIN
    is_claude_host = host_profile == HOST_PROFILE_CLAUDE
    if is_claude_host and is_opus_session_model(session_model):
        return MODE_IN_SESSION
    return MODE_CHAIN


def build_code_review_arguments() -> list[str]:
    """Return the argv tokens passed to ``run_claude`` for a chain review.

    ::

        build_code_review_arguments()
            # ok: ["-p", CODE_REVIEW_PROMPT, "--model", "opus", ...]

    Returns:
        Ordered claude CLI arguments for the headless opus review slash command.
    """
    return [
        SINGLE_TURN_FLAG,
        CODE_REVIEW_PROMPT,
        MODEL_FLAG,
        CODE_REVIEW_MODEL_ALIAS,
        OUTPUT_FORMAT_FLAG,
        OUTPUT_FORMAT_JSON,
        PERMISSION_MODE_FLAG,
        PERMISSION_MODE_BYPASS,
    ]


def is_working_tree_dirty(working_directory: Path) -> bool:
    """Return True when the tree is dirty or ``git status`` fails.

    ::

        is_working_tree_dirty(clean_repo)  # ok: False
        is_working_tree_dirty(dirty_repo)  # ok: True
        is_working_tree_dirty(broken_git)  # ok: True (non-zero status)

    A non-zero ``git status`` return code must not report clean: the caller
    treats an unknown tree as dirty so a clean stamp cannot bypass the gate.

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
        True when the outcome is a successful serve that may stamp clean if
        the working tree is also clean.
    """
    if review_outcome.returncode != SUCCESSFUL_REVIEW_RETURNCODE:
        return False
    if review_outcome.mode == MODE_CHAIN and review_outcome.served_command is None:
        return False
    return True


def is_code_review_clean_stamp_allowed(review_outcome: CodeReviewOutcome) -> bool:
    """Return True when the outcome may set ``code_review_clean_at``.

    ::

        is_code_review_clean_stamp_allowed(chain_clean_ok)     # ok: True
        is_code_review_clean_stamp_allowed(chain_failed)       # ok: False
        is_code_review_clean_stamp_allowed(chain_dirty_ok)     # ok: False

    Clean stamp requires a successful serve and a clean working tree.
    ``dirty_tree`` alone is not enough: a failed chain leaves the tree clean
    and must stay in CODE_REVIEW.

    Args:
        review_outcome: Structured outcome from ``invoke_code_review``.

    Returns:
        True only when the review succeeded and ``is_dirty_tree`` is False.
    """
    if not is_successful_code_review(review_outcome):
        return False
    if review_outcome.is_dirty_tree:
        return False
    return True

def _run_claude_with_empty_stdin(
    all_claude_arguments: list[str],
    *,
    timeout_seconds: int,
    working_directory: Path,
) -> ChainInvocationOutcome:
    working_directory_path = str(working_directory)
    with _CHAIN_RUNNER_LOCK:
        previous_runner = chain_runner.chain_subprocess_runner

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
            completed_process: subprocess.CompletedProcess[str] = previous_runner(
                all_invocation_tokens,
                capture_output=True,
                text=True,
                timeout=timeout_for_run,
                check=False,
                stdin=subprocess.DEVNULL,
                cwd=working_directory_path,
            )
            return completed_process

        empty_stdin_runner: TextCapturingSubprocessRunner = _runner_with_empty_stdin
        setattr(chain_runner, "chain_subprocess_runner", empty_stdin_runner)
        try:
            return review_claude_runner(
                all_claude_arguments, timeout_seconds=timeout_seconds
            )
        finally:
            setattr(chain_runner, "chain_subprocess_runner", previous_runner)


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

def parse_session_has_usage_left_token(
    session_has_usage_left_token: str,
) -> bool | None:
    """Parse the CLI ``--session-has-usage-left`` token into a tri-state bool.

    ::

        parse_session_has_usage_left_token("true")     # ok: True
        parse_session_has_usage_left_token("false")    # ok: False
        parse_session_has_usage_left_token("unknown")  # ok: None

    Args:
        session_has_usage_left_token: One of ``true``, ``false``, or ``unknown``
            (letter case ignored).

    Returns:
        True, False, or None for the three probe outcomes.

    Raises:
        ValueError: The token is not one of the three allowed labels.
    """
    normalized_token = session_has_usage_left_token.strip().lower()
    if normalized_token == SESSION_HAS_USAGE_LEFT_TRUE:
        return True
    if normalized_token == SESSION_HAS_USAGE_LEFT_FALSE:
        return False
    if normalized_token == SESSION_HAS_USAGE_LEFT_UNKNOWN:
        return None
    raise ValueError(
        f"unsupported session-has-usage-left token: {session_has_usage_left_token!r}"
    )


def invoke_code_review(
    *,
    working_directory: Path,
    session_model: str,
    timeout_seconds: int,
    session_has_usage_left: bool | None = None,
) -> CodeReviewOutcome:
    """Run or hand off ``/code-review`` based on host profile and session model.

    Args:
        working_directory: PR working tree used as cwd for the chain spawn.
        session_model: Caller-stated session model short alias (for example
            ``opus`` or ``sonnet``).
        timeout_seconds: Timeout applied to each chain binary invocation.
        session_has_usage_left: Optional usage-probe decision. ``False`` forces
            chain mode even on Claude+opus so another chain binary can serve.

    Returns:
        Structured outcome including mode, served binary, return code, and
        whether the working tree is dirty after a chain run.
    """
    host_profile = review_host_profile_detector()
    review_mode = decide_review_mode(
        host_profile=host_profile,
        session_model=session_model,
        session_has_usage_left=session_has_usage_left,
    )
    if review_mode == MODE_IN_SESSION:
        return _in_session_outcome()
    all_claude_arguments = build_code_review_arguments()
    chain_outcome = _run_claude_with_empty_stdin(
        all_claude_arguments,
        timeout_seconds=timeout_seconds,
        working_directory=working_directory,
    )
    return _chain_outcome(chain_outcome, working_directory=working_directory)


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


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run built-in /code-review at xhigh effort on opus, host-aware."
        )
    )
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
    parser.add_argument(
        CLI_SESSION_HAS_USAGE_LEFT_FLAG,
        dest="session_has_usage_left_token",
        default=SESSION_HAS_USAGE_LEFT_UNKNOWN,
        choices=[
            SESSION_HAS_USAGE_LEFT_TRUE,
            SESSION_HAS_USAGE_LEFT_FALSE,
            SESSION_HAS_USAGE_LEFT_UNKNOWN,
        ],
        help=(
            "Usage-probe decision for the primary session. "
            "'false' forces chain mode even on Claude+opus."
        ),
    )
    return parser


def main(all_command_arguments: list[str]) -> int:
    """Run the invoker for CLI arguments and print the JSON outcome.

    ``ChainConfigurationError`` and host ``ValueError`` still emit result JSON
    on stdout (no traceback-only failure). The non-zero return code and null
    ``served_command`` block a clean stamp.

    Args:
        all_command_arguments: The argument vector after the program name.

    Returns:
        The outcome return code (``0`` for in-session; chain return code otherwise).
    """
    parser = _build_argument_parser()
    parsed_arguments = parser.parse_args(all_command_arguments)
    session_has_usage_left = parse_session_has_usage_left_token(
        parsed_arguments.session_has_usage_left_token
    )
    try:
        review_outcome = invoke_code_review(
            working_directory=parsed_arguments.working_directory,
            session_model=parsed_arguments.session_model,
            timeout_seconds=parsed_arguments.timeout_seconds,
            session_has_usage_left=session_has_usage_left,
        )
    except ChainConfigurationError:
        review_outcome = _failure_code_review_outcome(CHAIN_CONFIG_ERROR_EXIT_CODE)
    except ValueError:
        review_outcome = _failure_code_review_outcome(HOST_PROFILE_ERROR_RETURNCODE)
    encoded_payload = encode_code_review_outcome(review_outcome)
    sys.stdout.write(json.dumps(encoded_payload) + "\n")
    return review_outcome.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
