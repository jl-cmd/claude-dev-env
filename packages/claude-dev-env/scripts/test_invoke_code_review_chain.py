"""Chain-invocation argv assembly, empty stdin, and working directory."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

try:
    import invoke_code_review as invoker
    from _code_review_test_support import (
        FIXTURE_SESSION_OPUS,
        FIXTURE_SESSION_SONNET,
        HOST_PROFILE_THIRD_PARTY,
        claude_served,
        init_git_repository,
        install_seams,
        run_review,
    )
    from dev_env_scripts_constants.code_review_constants import (
        CODE_REVIEW_MODEL_ALIAS,
        DEFAULT_CODE_REVIEW_EFFORT,
        PERMISSION_MODE_BYPASS,
        PERMISSION_MODE_FLAG,
    )
    from dev_env_scripts_constants.grok_worker_constants import (
        MODEL_FLAG,
        OUTPUT_FORMAT_FLAG,
        OUTPUT_FORMAT_JSON,
        SINGLE_TURN_FLAG,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import invoke_code_review as invoker
    from _code_review_test_support import (
        FIXTURE_SESSION_OPUS,
        FIXTURE_SESSION_SONNET,
        HOST_PROFILE_THIRD_PARTY,
        claude_served,
        init_git_repository,
        install_seams,
        run_review,
    )
    from dev_env_scripts_constants.code_review_constants import (
        CODE_REVIEW_MODEL_ALIAS,
        DEFAULT_CODE_REVIEW_EFFORT,
        PERMISSION_MODE_BYPASS,
        PERMISSION_MODE_FLAG,
    )
    from dev_env_scripts_constants.grok_worker_constants import (
        MODEL_FLAG,
        OUTPUT_FORMAT_FLAG,
        OUTPUT_FORMAT_JSON,
        SINGLE_TURN_FLAG,
    )


def test_chain_argv_assembly(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    working_directory = init_git_repository(tmp_path / "repo")
    call_log = install_seams(
        monkeypatch,
        host_profile=HOST_PROFILE_THIRD_PARTY,
        claude_outcome=claude_served(),
        working_directory=working_directory,
    )

    run_review(working_directory, session_model=FIXTURE_SESSION_SONNET)

    assert call_log.claude_arguments == [
        SINGLE_TURN_FLAG,
        invoker.build_code_review_prompt(DEFAULT_CODE_REVIEW_EFFORT),
        MODEL_FLAG,
        CODE_REVIEW_MODEL_ALIAS,
        OUTPUT_FORMAT_FLAG,
        OUTPUT_FORMAT_JSON,
        PERMISSION_MODE_FLAG,
        PERMISSION_MODE_BYPASS,
    ]


def test_chain_redirects_empty_stdin_and_sets_cwd(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    working_directory = init_git_repository(tmp_path / "repo")
    call_log = install_seams(
        monkeypatch,
        host_profile=HOST_PROFILE_THIRD_PARTY,
        claude_outcome=claude_served(),
        working_directory=working_directory,
    )

    run_review(working_directory, session_model=FIXTURE_SESSION_OPUS)

    assert call_log.is_stdin_empty is True
    assert call_log.claude_working_directory == working_directory
