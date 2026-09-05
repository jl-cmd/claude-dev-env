"""Contract tests for process-local pull request publication."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock

import pytest

_SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(_SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIRECTORY))

import pull_request

REPOSITORY = "jl-cmd/claude-dev-env"
PR_NUMBER = "2518"
PR_TITLE = "feat(skills): add guarded pull request publication"
ACCOUNT_A = "JonEcho"
ACCOUNT_B = "ReviewBot"
BODY_FILENAME = "pull-request-body.md"
LINTER_PATH = _SCRIPTS_DIRECTORY.parents[3] / "scripts/durable_post_lint.py"
COMMENT_CLI = ["comment", "--repo", REPOSITORY, "--number", PR_NUMBER, "--body-file"]
ACTION_CASES = [
    (
        [
            "create",
            "--repo",
            REPOSITORY,
            "--base",
            "main",
            "--head",
            "feature/post",
            "--title",
            PR_TITLE,
            "--body-file",
            BODY_FILENAME,
        ],
        "pr-create",
        [
            "gh",
            "pr",
            "create",
            "--draft",
            "--repo",
            REPOSITORY,
            "--base",
            "main",
            "--head",
            "feature/post",
            "--title",
            PR_TITLE,
            "--body-file",
            BODY_FILENAME,
        ],
    ),
    (
        [
            "edit",
            "--repo",
            REPOSITORY,
            "--number",
            PR_NUMBER,
            "--title",
            PR_TITLE,
            "--body-file",
            BODY_FILENAME,
        ],
        "pr-edit",
        [
            "gh",
            "pr",
            "edit",
            PR_NUMBER,
            "--repo",
            REPOSITORY,
            "--title",
            PR_TITLE,
            "--body-file",
            BODY_FILENAME,
        ],
    ),
    (
        [*COMMENT_CLI, BODY_FILENAME],
        "pr-comment",
        [
            "gh",
            "pr",
            "comment",
            PR_NUMBER,
            "--repo",
            REPOSITORY,
            "--body-file",
            BODY_FILENAME,
        ],
    ),
    (
        [
            "review",
            "--repo",
            REPOSITORY,
            "--number",
            PR_NUMBER,
            "--body-file",
            BODY_FILENAME,
        ],
        "pr-review",
        [
            "gh",
            "pr",
            "review",
            PR_NUMBER,
            "--repo",
            REPOSITORY,
            "--comment",
            "--body-file",
            BODY_FILENAME,
        ],
    ),
]


def _completion(
    all_arguments: list[str], code: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(all_arguments, code, stdout, stderr)


@pytest.fixture
def body_file(tmp_path: Path) -> Path:
    post_file = tmp_path / BODY_FILENAME
    post_file.write_text("Durable body text.", encoding="utf-8")
    return post_file


def _comment_arguments(body_file: Path) -> list[str]:
    return [*COMMENT_CLI, str(body_file)]


def _account_text(account_name: str) -> str:
    return account_name[::-1]


def _calls(command_runner: Mock) -> list[list[str]]:
    return [each_call.args[0] for each_call in command_runner.call_args_list]


def _run_comment(
    body_file: Path, command_runner: Mock, environment: dict[str, str]
) -> int:
    return pull_request.main(
        _comment_arguments(body_file),
        all_environment=environment,
        command_runner=command_runner,
    )


def _account_runner(
    *, auth_code: int = 0, auth_stdout: str, action_code: int = 0, auth_stderr: str = ""
) -> Mock:
    return Mock(
        side_effect=[
            _completion([]),
            _completion([], auth_code, auth_stdout, auth_stderr),
            _completion([], action_code),
        ]
    )


@pytest.mark.parametrize(
    ("all_cli_arguments", "linter_action", "expected_gh"), ACTION_CASES
)
def test_actions_run_exact_linter_then_gh_arguments(
    all_cli_arguments: list[str], linter_action: str, expected_gh: list[str]
) -> None:
    command_runner = Mock(side_effect=[_completion([]), _completion([])])
    exit_code = pull_request.main(
        all_cli_arguments, all_environment={}, command_runner=command_runner
    )
    title_arguments = ["--title", PR_TITLE] if "--title" in all_cli_arguments else []
    expected_linter = [
        sys.executable,
        str(LINTER_PATH),
        "--action",
        linter_action,
        *title_arguments,
        "--body-file",
        BODY_FILENAME,
    ]
    assert exit_code == 0
    assert _calls(command_runner) == [expected_linter, expected_gh]


def test_body_transport_uses_files_only(body_file: Path) -> None:
    command_runner = Mock(side_effect=[_completion([]), _completion([])])
    assert _run_comment(body_file, command_runner, {}) == 0
    for each_command in _calls(command_runner):
        assert "--body-file" in each_command
        assert "--body" not in each_command
        assert "Durable body text." not in each_command


def test_linter_failure_stops_credential_lookup_and_action(body_file: Path) -> None:
    command_runner = Mock(return_value=_completion([], 1))
    exit_code = _run_comment(
        body_file, command_runner, {"GITHUB_DEFAULT_ACCOUNT": ACCOUNT_A}
    )
    assert exit_code == 1
    assert command_runner.call_count == 1
    assert Path(_calls(command_runner)[0][1]).name == "durable_post_lint.py"


def test_account_lookup_scopes_action_environment(body_file: Path) -> None:
    account_text = _account_text(ACCOUNT_A)
    command_runner = _account_runner(auth_stdout=f"{account_text}\n")
    parent_environment = {
        "GITHUB_DEFAULT_ACCOUNT": ACCOUNT_A,
        "GITHUB_TOKEN": "parent-setting",
        "UNCHANGED": "same",
    }
    assert _run_comment(body_file, command_runner, parent_environment) == 0
    assert _calls(command_runner)[1] == ["gh", "auth", "token", "--user", ACCOUNT_A]
    action_environment = command_runner.call_args_list[2].kwargs["env"]
    assert action_environment["GH_TOKEN"] == account_text
    assert "GITHUB_TOKEN" not in action_environment
    assert action_environment["UNCHANGED"] == "same"


def test_absent_account_uses_copied_parent_environment(body_file: Path) -> None:
    command_runner = Mock(side_effect=[_completion([]), _completion([])])
    parent_environment = {"GITHUB_TOKEN": "parent-setting", "UNCHANGED": "same"}
    assert _run_comment(body_file, command_runner, parent_environment) == 0
    action_environment = command_runner.call_args_list[1].kwargs["env"]
    assert action_environment == parent_environment
    assert action_environment is not parent_environment
    assert command_runner.call_count == 2


def test_token_lookup_failure_prints_generic_safe_stderr(
    body_file: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    account_text = _account_text(ACCOUNT_A)
    command_runner = _account_runner(
        auth_code=1, auth_stdout=account_text, auth_stderr=f"unsafe {account_text}"
    )
    exit_code = _run_comment(
        body_file, command_runner, {"GITHUB_DEFAULT_ACCOUNT": ACCOUNT_A}
    )
    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err == "error: GitHub account lookup failed\n"
    assert account_text not in captured.out + captured.err
    assert command_runner.call_count == 2
    command_runner = Mock(side_effect=[_completion([]), OSError("unavailable")])
    assert (
        _run_comment(body_file, command_runner, {"GITHUB_DEFAULT_ACCOUNT": ACCOUNT_A})
        == 1
    )
    assert capsys.readouterr().err == "error: GitHub account lookup failed\n"


def test_empty_account_token_stops_before_action(
    body_file: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    command_runner = _account_runner(auth_stdout=" \n")
    exit_code = _run_comment(
        body_file, command_runner, {"GITHUB_DEFAULT_ACCOUNT": ACCOUNT_A}
    )
    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err == "error: GitHub account lookup returned no value\n"
    assert command_runner.call_count == 2


def test_action_child_results_pass_through_or_report_safely(
    body_file: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    command_runner = Mock(side_effect=[_completion([]), _completion([], 7)])
    assert _run_comment(body_file, command_runner, {}) == 7
    command_runner = Mock(side_effect=[_completion([]), OSError("unavailable")])
    assert _run_comment(body_file, command_runner, {}) == 1
    assert capsys.readouterr().err == "error: GitHub action failed\n"


def test_supplied_parent_environment_remains_unchanged(body_file: Path) -> None:
    command_runner = _account_runner(auth_stdout=_account_text(ACCOUNT_A))
    parent_environment = {
        "GITHUB_DEFAULT_ACCOUNT": ACCOUNT_A,
        "GITHUB_TOKEN": "parent-setting",
        "GH_TOKEN": "parent-setting",
    }
    original_environment = dict(parent_environment)
    assert _run_comment(body_file, command_runner, parent_environment) == 0
    assert parent_environment == original_environment


def test_process_environment_remains_unchanged(
    body_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GITHUB_DEFAULT_ACCOUNT", ACCOUNT_A)
    monkeypatch.setenv("GITHUB_TOKEN", "parent-setting")
    monkeypatch.setenv("GH_TOKEN", "parent-setting")
    original_environment = dict(os.environ)
    command_runner = _account_runner(auth_stdout=_account_text(ACCOUNT_A))
    exit_code = pull_request.main(
        _comment_arguments(body_file),
        all_environment=os.environ,
        command_runner=command_runner,
    )
    assert exit_code == 0
    assert dict(os.environ) == original_environment


def _concurrent_runner(
    all_environments: list[dict[str, str]],
    all_commands: list[list[str]],
    record_lock: threading.Lock,
) -> Callable[..., subprocess.CompletedProcess[str]]:
    def run_command(
        all_arguments: list[str], **keyword_arguments: object
    ) -> subprocess.CompletedProcess[str]:
        with record_lock:
            all_commands.append(all_arguments)
        if all_arguments[0] == sys.executable:
            return _completion(all_arguments)
        if all_arguments[:3] == ["gh", "auth", "token"]:
            if all_arguments[-1] == ACCOUNT_A:
                return _completion(all_arguments, stdout=_account_text(ACCOUNT_A))
            return _completion(all_arguments, 1)
        child_environment = keyword_arguments["env"]
        assert isinstance(child_environment, dict)
        with record_lock:
            all_environments.append(dict(child_environment))
        return _completion(all_arguments)

    return run_command


def test_concurrent_accounts_keep_tokens_isolated(body_file: Path) -> None:
    all_environments: list[dict[str, str]] = []
    all_commands: list[list[str]] = []
    command_runner = _concurrent_runner(
        all_environments, all_commands, threading.Lock()
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        first_run = executor.submit(
            pull_request.main,
            _comment_arguments(body_file),
            all_environment={"GITHUB_DEFAULT_ACCOUNT": ACCOUNT_A},
            command_runner=command_runner,
        )
        second_run = executor.submit(
            pull_request.main,
            _comment_arguments(body_file),
            all_environment={"GITHUB_DEFAULT_ACCOUNT": ACCOUNT_B},
            command_runner=command_runner,
        )
    assert {first_run.result(), second_run.result()} == {0, 1}
    assert len(all_environments) == 1
    assert all_environments[0]["GH_TOKEN"] == _account_text(ACCOUNT_A)
    assert all(
        each_command[:3] != ["gh", "auth", "switch"] for each_command in all_commands
    )


def test_token_never_reaches_captured_output(
    body_file: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    account_text = _account_text(ACCOUNT_A)
    command_runner = _account_runner(auth_stdout=f"{account_text}\n")
    assert (
        _run_comment(body_file, command_runner, {"GITHUB_DEFAULT_ACCOUNT": ACCOUNT_A})
        == 0
    )
    captured = capsys.readouterr()
    assert account_text not in captured.out + captured.err


def test_cli_rejects_inline_body(capsys: pytest.CaptureFixture[str]) -> None:
    command_runner = Mock()
    with pytest.raises(SystemExit) as raised_exit:
        pull_request.main(
            [*COMMENT_CLI[:-1], "--body", "Inline body text."],
            all_environment={},
            command_runner=command_runner,
        )
    captured = capsys.readouterr()
    assert raised_exit.value.code == 2
    assert "--body-file" in captured.err
    command_runner.assert_not_called()
