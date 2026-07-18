#!/usr/bin/env python3
"""Host-aware helper that runs the built-in review slash command on opus.

Mode decision::

    host=Claude, session_model=opus  -> mode in_session (skill runs slash cmd)
    host=Claude, session_model=sonnet -> mode chain (headless opus spawn)
    host=ThirdParty, any model        -> mode chain

Chain mode runs ``run_claude`` with argv from ``build_code_review_arguments``
(single-turn prompt, model opus, json output, bypassPermissions).

cwd is the PR working tree and stdin is redirected from the empty stream so
the spawn does not wait for interactive input. Result JSON on stdout only::

    {"mode", "served_command", "returncode", "dirty_tree"}

``--record-stamp`` forces chain mode, loops a capped number of review passes,
and mints a clean stamp only when a pass exits 0 with a stable surface hash.

Import ``invoke_code_review`` for the outcome object, or run as a CLI::

    python invoke_code_review.py --cwd <dir> --session-model <alias>
        [--timeout-seconds N] [--record-stamp] [effort]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

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
    ALL_EFFORT_TOKENS_IN_ASCENDING_ORDER,
    CLI_EFFORT_HELP,
    CLI_EFFORT_METAVAR,
    CLI_RECORD_STAMP_HELP,
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
    MAXIMUM_STAMP_MINT_PASSES,
    MODE_CHAIN,
    MODE_IN_SESSION,
    PERMISSION_MODE_BYPASS,
    PERMISSION_MODE_FLAG,
    RECORD_STAMP_FLAG,
    RESULT_KEY_BOUND_HASH,
    RESULT_KEY_DIRTY_TREE,
    RESULT_KEY_MODE,
    RESULT_KEY_PASS_COUNT,
    RESULT_KEY_RETURNCODE,
    RESULT_KEY_SERVED_COMMAND,
    RESULT_KEY_STAMP_MINTED,
    STAMP_DID_NOT_CONVERGE_MESSAGE,
    STAMP_DID_NOT_CONVERGE_RETURNCODE,
    STAMP_STORE_IMPORT_FAILURE_MESSAGE,
    STAMP_STORE_LIVE_SURFACE_HASH_NAME,
    STAMP_STORE_MODULE_FILE_NAME,
    STAMP_STORE_MODULE_NAME,
    STAMP_STORE_RECORD_CLEAN_STAMP_NAME,
    STAMP_STORE_RESOLVE_REPO_ROOT_NAME,
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


@dataclass(frozen=True)
class StampMintOutcome:
    """Outcome of a ``--record-stamp`` minting run.

    ::

        stable rc 0 pass  -> is_stamp_minted True, bound_hash set
        cap hit / unstable -> is_stamp_minted False, non-zero returncode

    The attributes carry the last review, whether a stamp was minted, the pass
    count, and the surface hash the stamp was bound to when minted.
    """

    review_outcome: CodeReviewOutcome
    is_stamp_minted: bool
    pass_count: int
    bound_hash: str | None


review_claude_runner = run_claude
review_host_profile_detector = detect_host_profile
review_git_status_runner = subprocess.run

TextCapturingSubprocessRunner = Callable[
    ...,
    subprocess.CompletedProcess[str],
]


def _stamp_store_file_path() -> Path:
    """Return the stamp store module path in the sibling hooks/blocking tree."""
    blocking_directory = Path(__file__).resolve().parent.parent / "hooks" / "blocking"
    return blocking_directory / STAMP_STORE_MODULE_FILE_NAME


def _load_store_from_spec(store_file_path: Path) -> ModuleType:
    """Import the stamp store from *store_file_path*, re-raising a missing dep."""
    blocking_directory_string = str(store_file_path.parent)
    if blocking_directory_string not in sys.path:
        sys.path.insert(0, blocking_directory_string)
    module_spec = importlib.util.spec_from_file_location(
        STAMP_STORE_MODULE_NAME, store_file_path
    )
    if module_spec is None or module_spec.loader is None:
        raise ModuleNotFoundError(
            f"could not create import spec for {store_file_path}",
            name=STAMP_STORE_MODULE_NAME,
        )
    store_module = importlib.util.module_from_spec(module_spec)
    sys.modules[STAMP_STORE_MODULE_NAME] = store_module
    try:
        module_spec.loader.exec_module(store_module)
    except ModuleNotFoundError:
        del sys.modules[STAMP_STORE_MODULE_NAME]
        raise
    return store_module


def load_code_review_stamp_store() -> ModuleType:
    """Import the stamp store module from the installed or repo hooks tree.

    ::

        code_review_stamp_store.py present -> module with record_clean_stamp
        module file missing                -> ModuleNotFoundError (loud)

    A genuine missing dependency of the store still raises rather than being
    swallowed, so ``--record-stamp`` fails loudly when it cannot mint.

    Returns:
        The loaded ``code_review_stamp_store`` module.

    Raises:
        ModuleNotFoundError: When the store file is absent or a real import
            dependency of the store is missing.
    """
    store_file_path = _stamp_store_file_path()
    if not store_file_path.is_file():
        raise ModuleNotFoundError(
            f"code review stamp store not found at {store_file_path}",
            name=STAMP_STORE_MODULE_NAME,
        )
    cached_module = sys.modules.get(STAMP_STORE_MODULE_NAME)
    if cached_module is not None:
        return cached_module
    return _load_store_from_spec(store_file_path)


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
    return _chain_outcome(chain_outcome, working_directory=working_directory)


def invoke_code_review(
    *,
    working_directory: Path,
    session_model: str,
    timeout_seconds: int,
    effort: str = DEFAULT_CODE_REVIEW_EFFORT,
    is_force_chain: bool = False,
) -> CodeReviewOutcome:
    """Run or hand off ``/code-review`` based on host profile and session model.

    ::

        Claude + opus, is_force_chain False -> in_session (no spawn)
        Claude + opus, is_force_chain True  -> chain (headless spawn)
        any host with sonnet                -> chain

    Args:
        working_directory: PR working tree used as cwd for the chain spawn.
        session_model: Caller-stated session model short alias.
        timeout_seconds: Timeout applied to each chain binary invocation.
        effort: Effort token embedded in the ``/code-review`` prompt.
        is_force_chain: When True, always spawn chain mode (used by
            ``--record-stamp`` so the invoker observes the review).

    Returns:
        Structured outcome including mode, served binary, return code, and
        whether the working tree is dirty after a chain run.
    """
    if is_force_chain:
        return _run_chain_review(
            working_directory=working_directory,
            timeout_seconds=timeout_seconds,
            effort=effort,
        )
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


def _surface_hash_before_and_after_are_stable(
    before_hash: str | None,
    after_hash: str | None,
) -> bool:
    if before_hash is None:
        return False
    if after_hash is None:
        return False
    return before_hash == after_hash


def _mint_stamp_for_stable_pass(
    *,
    store_module: ModuleType,
    working_directory: Path,
    surface_hash: str,
    effort: str,
) -> bool:
    resolve_repo_root = getattr(store_module, STAMP_STORE_RESOLVE_REPO_ROOT_NAME)
    record_clean_stamp = getattr(store_module, STAMP_STORE_RECORD_CLEAN_STAMP_NAME)
    repo_root = resolve_repo_root(str(working_directory))
    if repo_root is None:
        return False
    record_clean_stamp(repo_root, surface_hash, effort)
    return True


def _mint_outcome_when_stable_clean(
    *,
    store_module: ModuleType,
    working_directory: Path,
    effort: str,
    pass_number: int,
    before_hash: str,
    review_outcome: CodeReviewOutcome,
) -> StampMintOutcome | None:
    is_minted = _mint_stamp_for_stable_pass(
        store_module=store_module,
        working_directory=working_directory,
        surface_hash=before_hash,
        effort=effort,
    )
    if not is_minted:
        return None
    return StampMintOutcome(
        review_outcome=review_outcome,
        is_stamp_minted=True,
        pass_count=pass_number,
        bound_hash=before_hash,
    )


def _unminted_pass_outcome(
    review_outcome: CodeReviewOutcome, pass_number: int
) -> StampMintOutcome:
    return StampMintOutcome(
        review_outcome=review_outcome,
        is_stamp_minted=False,
        pass_count=pass_number,
        bound_hash=None,
    )


def _stamp_outcome_for_pass(
    *,
    store_module: ModuleType,
    working_directory: Path,
    effort: str,
    pass_number: int,
    before_hash: str | None,
    after_hash: str | None,
    review_outcome: CodeReviewOutcome,
) -> StampMintOutcome | None:
    is_stable = _surface_hash_before_and_after_are_stable(before_hash, after_hash)
    is_successful = is_successful_code_review(review_outcome)
    is_empty_surface = before_hash is None and after_hash is None
    if is_successful and is_empty_surface:
        return _unminted_pass_outcome(review_outcome, pass_number)
    if is_successful and is_stable and before_hash is not None:
        minted = _mint_outcome_when_stable_clean(
            store_module=store_module,
            working_directory=working_directory,
            effort=effort,
            pass_number=pass_number,
            before_hash=before_hash,
            review_outcome=review_outcome,
        )
        if minted is not None:
            return minted
    if is_stable:
        return _unminted_pass_outcome(review_outcome, pass_number)
    return None


def _run_one_stamp_mint_pass(
    *,
    store_module: ModuleType,
    live_surface_hash: Callable[..., str | None],
    working_directory: Path,
    timeout_seconds: int,
    effort: str,
    pass_number: int,
) -> tuple[CodeReviewOutcome, StampMintOutcome | None]:
    before_hash = live_surface_hash(str(working_directory))
    review_outcome = invoke_code_review(
        working_directory=working_directory,
        session_model=CODE_REVIEW_MODEL_ALIAS,
        timeout_seconds=timeout_seconds,
        effort=effort,
        is_force_chain=True,
    )
    after_hash = live_surface_hash(str(working_directory))
    maybe_outcome = _stamp_outcome_for_pass(
        store_module=store_module,
        working_directory=working_directory,
        effort=effort,
        pass_number=pass_number,
        before_hash=before_hash,
        after_hash=after_hash,
        review_outcome=review_outcome,
    )
    return review_outcome, maybe_outcome


def _iterate_stamp_mint_passes(
    *,
    store_module: ModuleType,
    live_surface_hash: Callable[..., str | None],
    working_directory: Path,
    timeout_seconds: int,
    effort: str,
    maximum_passes: int,
) -> StampMintOutcome:
    last_review_outcome = _failure_code_review_outcome(
        STAMP_DID_NOT_CONVERGE_RETURNCODE
    )
    for each_pass_number in range(1, maximum_passes + 1):
        last_review_outcome, maybe_mint_outcome = _run_one_stamp_mint_pass(
            store_module=store_module,
            live_surface_hash=live_surface_hash,
            working_directory=working_directory,
            timeout_seconds=timeout_seconds,
            effort=effort,
            pass_number=each_pass_number,
        )
        if maybe_mint_outcome is not None:
            return maybe_mint_outcome
    return _unminted_pass_outcome(last_review_outcome, maximum_passes)


def invoke_code_review_and_record_stamp(
    *,
    working_directory: Path,
    session_model: str,
    timeout_seconds: int,
    effort: str,
    maximum_passes: int = MAXIMUM_STAMP_MINT_PASSES,
) -> StampMintOutcome:
    """Force chain review passes until the surface is stable, then mint a stamp.

    Args:
        working_directory: PR working tree used as cwd for each chain spawn.
        session_model: Session model short alias (unused; chain mode forced).
        timeout_seconds: Timeout applied to each chain binary invocation.
        effort: Effort token the clean review records on the stamp.
        maximum_passes: Hard cap on review passes before giving up.

    Returns:
        A StampMintOutcome for the last review and whether a stamp was minted.
    """
    del session_model
    store_module = load_code_review_stamp_store()
    return _iterate_stamp_mint_passes(
        store_module=store_module,
        live_surface_hash=getattr(store_module, STAMP_STORE_LIVE_SURFACE_HASH_NAME),
        working_directory=working_directory,
        timeout_seconds=timeout_seconds,
        effort=effort,
        maximum_passes=maximum_passes,
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


def encode_stamp_mint_outcome(
    mint_outcome: StampMintOutcome,
) -> dict[str, object]:
    """Encode a stamp-mint outcome as the JSON-serializable payload.

    Args:
        mint_outcome: The ``--record-stamp`` outcome to encode.

    Returns:
        A plain dict with the review fields plus mint metadata.
    """
    encoded_payload = encode_code_review_outcome(mint_outcome.review_outcome)
    encoded_payload[RESULT_KEY_STAMP_MINTED] = mint_outcome.is_stamp_minted
    encoded_payload[RESULT_KEY_PASS_COUNT] = mint_outcome.pass_count
    encoded_payload[RESULT_KEY_BOUND_HASH] = mint_outcome.bound_hash
    if not mint_outcome.is_stamp_minted:
        if mint_outcome.pass_count >= MAXIMUM_STAMP_MINT_PASSES:
            encoded_payload[RESULT_KEY_RETURNCODE] = STAMP_DID_NOT_CONVERGE_RETURNCODE
    return encoded_payload


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


def _add_stamp_and_effort_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        RECORD_STAMP_FLAG,
        dest="is_record_stamp",
        action="store_true",
        help=CLI_RECORD_STAMP_HELP,
    )
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
    _add_stamp_and_effort_arguments(parser)
    return parser


def _emit_invalid_effort_and_exit_code(effort: str) -> int:
    error_message = validate_effort_token(effort)
    if error_message is None:
        return SUCCESSFUL_REVIEW_RETURNCODE
    sys.stderr.write(error_message + "\n")
    return INVALID_EFFORT_RETURNCODE


def _import_failure_payload() -> dict[str, object]:
    failure_outcome = _failure_code_review_outcome(INVALID_EFFORT_RETURNCODE)
    encoded_payload = encode_code_review_outcome(failure_outcome)
    encoded_payload[RESULT_KEY_STAMP_MINTED] = False
    encoded_payload[RESULT_KEY_PASS_COUNT] = 0
    encoded_payload[RESULT_KEY_BOUND_HASH] = None
    return encoded_payload


def _no_mint_outcome(returncode: int) -> StampMintOutcome:
    return StampMintOutcome(
        review_outcome=_failure_code_review_outcome(returncode),
        is_stamp_minted=False,
        pass_count=0,
        bound_hash=None,
    )


def _mint_or_config_outcome(
    *,
    working_directory: Path,
    session_model: str,
    timeout_seconds: int,
    effort: str,
) -> StampMintOutcome:
    try:
        return invoke_code_review_and_record_stamp(
            working_directory=working_directory,
            session_model=session_model,
            timeout_seconds=timeout_seconds,
            effort=effort,
        )
    except ChainConfigurationError:
        return _no_mint_outcome(CHAIN_CONFIG_ERROR_EXIT_CODE)
    except ValueError:
        return _no_mint_outcome(HOST_PROFILE_ERROR_RETURNCODE)


def _emit_import_failure(import_error: ModuleNotFoundError) -> int:
    sys.stderr.write(
        STAMP_STORE_IMPORT_FAILURE_MESSAGE.format(error=import_error) + "\n"
    )
    sys.stdout.write(json.dumps(_import_failure_payload()) + "\n")
    return INVALID_EFFORT_RETURNCODE


def _record_stamp_exit_code(mint_outcome: StampMintOutcome) -> int:
    if mint_outcome.is_stamp_minted:
        return mint_outcome.review_outcome.returncode
    if mint_outcome.pass_count >= MAXIMUM_STAMP_MINT_PASSES:
        return STAMP_DID_NOT_CONVERGE_RETURNCODE
    return mint_outcome.review_outcome.returncode


def _emit_mint_outcome(mint_outcome: StampMintOutcome) -> int:
    encoded_payload = encode_stamp_mint_outcome(mint_outcome)
    did_not_converge = (
        not mint_outcome.is_stamp_minted
        and mint_outcome.pass_count >= MAXIMUM_STAMP_MINT_PASSES
    )
    if did_not_converge:
        sys.stderr.write(
            STAMP_DID_NOT_CONVERGE_MESSAGE.format(pass_count=mint_outcome.pass_count)
            + "\n"
        )
    sys.stdout.write(json.dumps(encoded_payload) + "\n")
    return _record_stamp_exit_code(mint_outcome)


def _run_record_stamp_cli(
    *,
    working_directory: Path,
    session_model: str,
    timeout_seconds: int,
    effort: str,
) -> int:
    try:
        mint_outcome = _mint_or_config_outcome(
            working_directory=working_directory,
            session_model=session_model,
            timeout_seconds=timeout_seconds,
            effort=effort,
        )
    except ModuleNotFoundError as import_error:
        return _emit_import_failure(import_error)
    return _emit_mint_outcome(mint_outcome)


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

    ``--record-stamp`` forces chain mode and mints only on a surface-stable
    returncode-0 pass; an unknown or ``ultra`` effort exits non-zero before any
    review runs.

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
    if parsed_arguments.is_record_stamp:
        return _run_record_stamp_cli(
            working_directory=parsed_arguments.working_directory,
            session_model=parsed_arguments.session_model,
            timeout_seconds=parsed_arguments.timeout_seconds,
            effort=effort_token,
        )
    return _run_plain_review_cli(parsed_arguments=parsed_arguments, effort=effort_token)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
