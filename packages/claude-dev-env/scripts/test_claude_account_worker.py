from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from claude_account_worker import AccountSelection, run_worker
from dev_env_scripts_constants.claude_account_worker_constants import (
    CHOICE_MAIN,
    CHOICE_SECOND,
    CHOICE_WAIT,
    CLAUDE_CONFIG_DIR_ENV_VAR,
    STDOUT_TAIL_CHARACTER_LIMIT,
    TIMEOUT_EXIT_CODE,
    WAIT_EXIT_CODE,
)


class FakeProcess:
    def __init__(
        self,
        *,
        stdout: str = '{"result":"ready","is_error":false}',
        returncode: int = 0,
        timeout_first: bool = False,
        timeout_output: str = "",
        drain_timeout_count: int = 0,
    ) -> None:
        self.stdout = stdout
        self.returncode = returncode
        self.timeout_first = timeout_first
        self.timeout_output = timeout_output
        self.drain_timeout_count = drain_timeout_count
        self.pid = 42
        self.communicate_calls: list[tuple[str | None, float | None]] = []
        self.terminated = False

    def communicate(
        self,
        input: str | None = None,
        timeout: float | None = None,
    ) -> tuple[str, str]:
        self.communicate_calls.append((input, timeout))
        if self.timeout_first and len(self.communicate_calls) == 1:
            raise subprocess.TimeoutExpired(
                cmd="claude",
                timeout=timeout,
                output=self.timeout_output,
            )
        if self.drain_timeout_count:
            self.drain_timeout_count -= 1
            raise subprocess.TimeoutExpired(
                cmd="claude",
                timeout=timeout,
                output=self.timeout_output,
            )
        return self.stdout, ""

    def poll(self) -> int | None:
        return self.returncode if self.terminated else None

    def kill(self) -> None:
        self.terminated = True
        self.returncode = -9


def _selection(
    account: str,
    *,
    config_dir: Path | None = None,
    reason: str = "selected by test",
) -> AccountSelection:
    return AccountSelection(account=account, config_dir=config_dir, reason=reason)


def _make_runner(
    process: FakeProcess,
    captured: dict[str, Any],
) -> Callable[..., FakeProcess]:
    def run(arguments: list[str], **options: Any) -> FakeProcess:
        captured["arguments"] = arguments
        captured.update(options)
        return process

    return run


def _run_worker(
    tmp_path: Path,
    *,
    selection: AccountSelection,
    process: FakeProcess,
    parent_environment: dict[str, str] | None = None,
    process_terminator: Callable[[FakeProcess], None] | None = None,
    model: str | None = None,
    permission_mode: str = "auto",
) -> tuple[int, dict[str, Any], dict[str, Any]]:
    prompt_file = tmp_path / "brief.md"
    prompt_file.write_text("standalone brief", encoding="utf-8")
    report_file = tmp_path / "report.json"
    captured: dict[str, Any] = {}
    runner = _make_runner(process, captured)
    options: dict[str, Any] = {
        "prompt_file": prompt_file,
        "cwd": tmp_path,
        "report_file": report_file,
        "model": model,
        "permission_mode": permission_mode,
        "decision_selector": lambda: selection,
        "process_factory": runner,
        "parent_environment": (
            {"KEEP_ME": "present"}
            if parent_environment is None
            else parent_environment
        ),
        "binary_resolver": lambda _: "claude.exe",
        "monotonic_clock": lambda: 1.0,
    }
    if process_terminator is not None:
        options["process_terminator"] = process_terminator
    exit_code = run_worker(**options)
    return exit_code, json.loads(report_file.read_text(encoding="utf-8")), captured


def test_should_set_second_profile_and_pass_parent_environment(
    tmp_path: Path,
) -> None:
    profile_dir = tmp_path / "second-profile"
    process = FakeProcess()
    exit_code, report, captured = _run_worker(
        tmp_path,
        selection=_selection(CHOICE_SECOND, config_dir=profile_dir),
        process=process,
        parent_environment={
            CLAUDE_CONFIG_DIR_ENV_VAR: "inherited-profile",
            "KEEP_ME": "present",
        },
        model="sonnet",
        permission_mode="plan",
    )

    assert exit_code == 0
    assert report["account"] == CHOICE_SECOND
    assert captured["env"][CLAUDE_CONFIG_DIR_ENV_VAR] == str(profile_dir)
    assert captured["env"]["KEEP_ME"] == "present"
    assert captured["arguments"] == [
        "claude.exe",
        "-p",
        "--output-format",
        "json",
        "--permission-mode",
        "plan",
        "--model",
        "sonnet",
    ]
    assert captured["cwd"] == str(tmp_path)
    assert process.communicate_calls[0][0] == "standalone brief"


def test_should_remove_inherited_profile_for_main_account(tmp_path: Path) -> None:
    process = FakeProcess()
    exit_code, report, captured = _run_worker(
        tmp_path,
        selection=_selection(CHOICE_MAIN, config_dir=tmp_path / "main-profile"),
        process=process,
        parent_environment={
            CLAUDE_CONFIG_DIR_ENV_VAR: "inherited-profile",
            "KEEP_ME": "present",
        },
    )

    assert exit_code == 0
    assert report["account"] == CHOICE_MAIN
    assert CLAUDE_CONFIG_DIR_ENV_VAR not in captured["env"]
    assert captured["env"]["KEEP_ME"] == "present"


def test_should_write_wait_reason_and_start_no_process(tmp_path: Path) -> None:
    report_file = tmp_path / "wait-report.json"
    process_started = False

    def forbidden_runner(*_: Any, **__: Any) -> FakeProcess:
        nonlocal process_started
        process_started = True
        raise AssertionError("wait must not start a process")

    exit_code = run_worker(
        prompt_file=tmp_path / "missing-brief.md",
        cwd=tmp_path,
        report_file=report_file,
        decision_selector=lambda: _selection(
            CHOICE_WAIT,
            reason="second account resets at 2026-09-24T12:00:00Z",
        ),
        process_factory=forbidden_runner,
        binary_resolver=lambda _: (_ for _ in ()).throw(
            AssertionError("wait must not resolve a binary")
        ),
    )
    report = json.loads(report_file.read_text(encoding="utf-8"))

    assert exit_code == WAIT_EXIT_CODE
    assert process_started is False
    assert report["account"] == CHOICE_WAIT
    assert report["reason"] == "second account resets at 2026-09-24T12:00:00Z"
    assert report["is_error"] is True


def test_should_kill_child_on_timeout_and_exit_124(tmp_path: Path) -> None:
    process = FakeProcess(
        stdout='{"result":"partial"}',
        returncode=-9,
        timeout_first=True,
        timeout_output='{"result":"partial"}',
    )
    termination_calls: list[FakeProcess] = []
    exit_code, report, _ = _run_worker(
        tmp_path,
        selection=_selection(CHOICE_SECOND, config_dir=tmp_path / "profile"),
        process=process,
        process_terminator=lambda child: termination_calls.append(child),
    )

    assert exit_code == TIMEOUT_EXIT_CODE
    assert termination_calls == [process]
    assert len(process.communicate_calls) == 2
    assert report["exit_code"] == TIMEOUT_EXIT_CODE
    assert report["is_error"] is True


def test_should_copy_parsed_result_into_report(tmp_path: Path) -> None:
    process = FakeProcess(stdout='{"result":"ready","is_error":false}')
    exit_code, report, _ = _run_worker(
        tmp_path,
        selection=_selection(CHOICE_SECOND, config_dir=tmp_path / "profile"),
        process=process,
    )

    assert exit_code == 0
    assert report["result"] == "ready"
    assert report["is_error"] is False


def test_should_write_raw_stdout_tail_when_output_is_not_json(tmp_path: Path) -> None:
    stdout_text = "x" * (STDOUT_TAIL_CHARACTER_LIMIT - 4) + "tail"
    process = FakeProcess(stdout=stdout_text)
    exit_code, report, _ = _run_worker(
        tmp_path,
        selection=_selection(CHOICE_SECOND, config_dir=tmp_path / "profile"),
        process=process,
    )

    assert exit_code == 0
    assert report["result"] == stdout_text[-STDOUT_TAIL_CHARACTER_LIMIT:]
    assert report["is_error"] is True


def test_should_preserve_child_exit_code_three_for_selected_account(
    tmp_path: Path,
) -> None:
    process = FakeProcess(returncode=3)
    exit_code, report, _ = _run_worker(
        tmp_path,
        selection=_selection(CHOICE_SECOND, config_dir=tmp_path / "profile"),
        process=process,
    )

    assert exit_code == 3
    assert report["account"] == CHOICE_SECOND
    assert report["exit_code"] == 3
    assert report["is_error"] is True


def test_should_keep_claude_json_error_flag(tmp_path: Path) -> None:
    process = FakeProcess(stdout='{"result":"failed","is_error":true}')
    exit_code, report, _ = _run_worker(
        tmp_path,
        selection=_selection(CHOICE_SECOND, config_dir=tmp_path / "profile"),
        process=process,
    )

    assert exit_code == 0
    assert report["result"] == "failed"
    assert report["is_error"] is True
