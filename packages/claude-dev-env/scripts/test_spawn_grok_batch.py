"""Behavioral tests for the grok batch launcher and report collector.

Subprocess seams are swapped; no live grok calls run in this suite.
"""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import spawn_grok_batch as batch  # noqa: E402
from dev_env_scripts_constants.grok_worker_constants import (  # noqa: E402
    BUILD_PROFILE_PROMPT_HEADER,
    CLASSIFICATION_ERROR,
    CLASSIFICATION_OK,
    CLASSIFICATION_USAGE_LIMIT,
    DEBUG_FILE_FLAG,
    DEFAULT_ROLE,
    DEFAULT_WORKER_MAX_TURNS,
    DEFAULT_WORKER_TIMEOUT_SECONDS,
    DISABLE_WEB_SEARCH_FLAG,
    DISALLOWED_TOOLS_FLAG,
    LEADER_SOCKET_FILENAME_PREFIX,
    LEADER_SOCKET_FILENAME_SUFFIX,
    OUTPUT_FILENAME_PREFIX,
    PROMPT_FILENAME_PREFIX,
    READONLY_DISALLOWED_TOOLS_VALUE,
    READONLY_PROFILE_PROMPT_HEADER,
    REASON_GROK_BINARY_MISSING,
    SUMMARY_CLASSIFICATION_KEY,
    SUMMARY_IS_OK_KEY,
    SUMMARY_IS_PREFLIGHT_USABLE_KEY,
    SUMMARY_LEADER_SOCKET_KEY,
    SUMMARY_OUTPUT_FILE_KEY,
    SUMMARY_PREFLIGHT_REASON_KEY,
    SUMMARY_PROMPT_FILE_KEY,
    SUMMARY_REPORT_TEXT_KEY,
    SUMMARY_RETURNCODE_KEY,
    SUMMARY_ROLE_NAME_KEY,
    SUMMARY_TOOL_PROFILE_KEY,
    SUMMARY_WORKERS_KEY,
    TOOL_PROFILE_BUILD,
    TOOL_PROFILE_READONLY,
    UTF8_ENCODING,
    WORKER_SPEC_MAX_TURNS_KEY,
    WORKER_SPEC_TIMEOUT_KEY,
)
from dev_env_scripts_constants.timing import WORKER_STAGGER_SECONDS  # noqa: E402
from grok_headless_runner import GrokRunnerOutcome  # noqa: E402
from grok_worker_preflight import PreflightOutcome  # noqa: E402

FIXTURE_REPORT_TEXT = '{"status":"done","role":"investigator"}'
FIXTURE_USAGE_LIMIT_TEXT = "rate limit exceeded (HTTP 429): quota exceeded"


def _write_prompt_parts(
    tmp_path: Path, *, role_marker: str = "investigator"
) -> tuple[Path, Path]:
    header_part = tmp_path / f"role-header-{role_marker}.txt"
    body_part = tmp_path / f"assignment-body-{role_marker}.txt"
    header_part.write_text(
        f"Role: investigator\nrole-marker:{role_marker}",
        encoding=UTF8_ENCODING,
    )
    body_part.write_text("Inspect the package layout.", encoding=UTF8_ENCODING)
    return header_part, body_part


def _worker_payload(
    *,
    role_name: str,
    all_prompt_parts: list[str],
    working_directory: Path,
    tool_profile: str,
    timeout_seconds: int = 30,
    is_repo_only: bool = False,
) -> dict[str, object]:
    return {
        "role_name": role_name,
        "prompt_parts": all_prompt_parts,
        "cwd": str(working_directory),
        "tool_profile": tool_profile,
        "timeout_seconds": timeout_seconds,
        "is_repo_only": is_repo_only,
    }


def _write_batch_spec(
    tmp_path: Path,
    *,
    all_worker_payloads: list[dict[str, object]],
    role: str = DEFAULT_ROLE,
    should_ping: bool = False,
) -> Path:
    specification_path = tmp_path / "batch-spec.json"
    specification_path.write_text(
        json.dumps(
            {
                "role": role,
                "should_ping": should_ping,
                "workers": all_worker_payloads,
            }
        ),
        encoding=UTF8_ENCODING,
    )
    return specification_path


class _RunnerRecorder:
    def __init__(self, outcome_by_role_name: dict[str, GrokRunnerOutcome]) -> None:
        self.outcome_by_role_name = dict(outcome_by_role_name)
        self.all_keyword_arguments: list[dict[str, object]] = []
        self._lock = threading.Lock()

    def __call__(self, **keyword_arguments: object) -> GrokRunnerOutcome:
        with self._lock:
            self.all_keyword_arguments.append(dict(keyword_arguments))
        prompt_file = keyword_arguments["prompt_file"]
        assert isinstance(prompt_file, Path)
        prompt_text = prompt_file.read_text(encoding=UTF8_ENCODING)
        for each_role_name, each_outcome in self.outcome_by_role_name.items():
            marker = f"role-marker:{each_role_name}"
            if marker in prompt_text:
                return each_outcome
        raise AssertionError(f"no outcome mapped for prompt: {prompt_text!r}")


def _ok_outcome(report_text: str = FIXTURE_REPORT_TEXT) -> GrokRunnerOutcome:
    return GrokRunnerOutcome(
        is_ok=True,
        returncode=0,
        classification=CLASSIFICATION_OK,
        stdout=report_text,
        stderr="",
    )


def _usage_limit_outcome() -> GrokRunnerOutcome:
    return GrokRunnerOutcome(
        is_ok=False,
        returncode=1,
        classification=CLASSIFICATION_USAGE_LIMIT,
        stdout="",
        stderr=FIXTURE_USAGE_LIMIT_TEXT,
    )


def test_assemble_worker_prompt_joins_parts_with_profile_header(
    tmp_path: Path,
) -> None:
    header_part, body_part = _write_prompt_parts(tmp_path)

    build_prompt = batch.assemble_worker_prompt(
        all_prompt_part_paths=(header_part, body_part),
        tool_profile=TOOL_PROFILE_BUILD,
    )
    readonly_prompt = batch.assemble_worker_prompt(
        all_prompt_part_paths=(header_part, body_part),
        tool_profile=TOOL_PROFILE_READONLY,
    )

    assert build_prompt.startswith(BUILD_PROFILE_PROMPT_HEADER)
    assert "Role: investigator" in build_prompt
    assert "Inspect the package layout." in build_prompt
    assert "Never commit, push, or call gh." in build_prompt
    assert readonly_prompt.startswith(READONLY_PROFILE_PROMPT_HEADER)
    assert "Do not write, edit, or run shell commands." in readonly_prompt


def test_tool_profile_arguments_differ_for_readonly_and_build(
    tmp_path: Path,
) -> None:
    debug_file = tmp_path / "debug.log"

    readonly_arguments = batch.build_tool_profile_arguments(
        tool_profile=TOOL_PROFILE_READONLY,
        is_repo_only=True,
        debug_file=debug_file,
    )
    build_arguments = batch.build_tool_profile_arguments(
        tool_profile=TOOL_PROFILE_BUILD,
        is_repo_only=False,
        debug_file=debug_file,
    )

    assert DISALLOWED_TOOLS_FLAG in readonly_arguments
    assert READONLY_DISALLOWED_TOOLS_VALUE in readonly_arguments
    assert DISABLE_WEB_SEARCH_FLAG in readonly_arguments
    assert DEBUG_FILE_FLAG in readonly_arguments
    assert str(debug_file) in readonly_arguments
    assert DISALLOWED_TOOLS_FLAG not in build_arguments
    assert DISABLE_WEB_SEARCH_FLAG not in build_arguments
    assert DEBUG_FILE_FLAG in build_arguments


def test_unique_socket_and_output_paths_per_worker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    header_a, body_a = _write_prompt_parts(tmp_path, role_marker="worker-a")
    header_b, body_b = _write_prompt_parts(tmp_path, role_marker="worker-b")
    working_directory = tmp_path / "project"
    working_directory.mkdir()
    run_state_directory = tmp_path / "run-state"
    specification_path = _write_batch_spec(
        tmp_path,
        all_worker_payloads=[
            _worker_payload(
                role_name="worker-a",
                all_prompt_parts=[str(header_a), str(body_a)],
                working_directory=working_directory,
                tool_profile=TOOL_PROFILE_READONLY,
            ),
            _worker_payload(
                role_name="worker-b",
                all_prompt_parts=[str(header_b), str(body_b)],
                working_directory=working_directory,
                tool_profile=TOOL_PROFILE_BUILD,
            ),
        ],
    )
    batch_spec = batch.load_batch_spec(specification_path)
    recorder = _RunnerRecorder(
        {
            "worker-a": _ok_outcome("a"),
            "worker-b": _ok_outcome("b"),
        }
    )
    monkeypatch.setattr(
        batch, "batch_preflight", lambda **_kwargs: PreflightOutcome(True, None)
    )
    monkeypatch.setattr(batch, "batch_headless_runner", recorder)
    monkeypatch.setattr(batch, "batch_sleep", lambda _seconds: None)

    batch_summary = batch.run_grok_batch(
        batch_spec=batch_spec,
        run_state_directory=run_state_directory,
    )

    assert len(batch_summary.all_worker_reports) == 2
    first_report = batch_summary.all_worker_reports[0]
    second_report = batch_summary.all_worker_reports[1]
    assert first_report.leader_socket != second_report.leader_socket
    assert first_report.report_path != second_report.report_path
    assert first_report.prompt_path != second_report.prompt_path
    assert Path(first_report.leader_socket).parent == run_state_directory
    assert Path(first_report.report_path).parent == run_state_directory
    assert Path(first_report.leader_socket).name.startswith(
        LEADER_SOCKET_FILENAME_PREFIX
    )
    assert Path(first_report.leader_socket).name.endswith(
        LEADER_SOCKET_FILENAME_SUFFIX
    )
    assert Path(first_report.report_path).name.startswith(OUTPUT_FILENAME_PREFIX)
    assert Path(first_report.prompt_path).name.startswith(PROMPT_FILENAME_PREFIX)
    all_socket_arguments = {
        each_kwargs["leader_socket_path"]
        for each_kwargs in recorder.all_keyword_arguments
    }
    assert len(all_socket_arguments) == 2


def test_stagger_ordering_uses_index_times_stagger_seconds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    working_directory = tmp_path / "project"
    working_directory.mkdir()
    run_state_directory = tmp_path / "run-state"
    all_worker_payloads: list[dict[str, object]] = []
    outcome_by_role_name: dict[str, GrokRunnerOutcome] = {}
    for each_index in range(3):
        role_name = f"worker-{each_index}"
        header_part, body_part = _write_prompt_parts(
            tmp_path, role_marker=role_name
        )
        all_worker_payloads.append(
            _worker_payload(
                role_name=role_name,
                all_prompt_parts=[str(header_part), str(body_part)],
                working_directory=working_directory,
                tool_profile=TOOL_PROFILE_BUILD,
            )
        )
        outcome_by_role_name[role_name] = _ok_outcome(str(each_index))
    specification_path = _write_batch_spec(
        tmp_path, all_worker_payloads=all_worker_payloads
    )
    batch_spec = batch.load_batch_spec(specification_path)
    recorder = _RunnerRecorder(outcome_by_role_name)
    all_sleep_seconds: list[int] = []
    sleep_lock = threading.Lock()

    def _record_sleep(delay_seconds: float) -> None:
        with sleep_lock:
            all_sleep_seconds.append(int(delay_seconds))

    monkeypatch.setattr(
        batch, "batch_preflight", lambda **_kwargs: PreflightOutcome(True, None)
    )
    monkeypatch.setattr(batch, "batch_headless_runner", recorder)
    monkeypatch.setattr(batch, "batch_sleep", _record_sleep)

    batch.run_grok_batch(
        batch_spec=batch_spec,
        run_state_directory=run_state_directory,
    )

    assert sorted(all_sleep_seconds) == [
        0,
        WORKER_STAGGER_SECONDS,
        WORKER_STAGGER_SECONDS * 2,
    ]
    assert WORKER_STAGGER_SECONDS == 15


def test_tool_profile_argv_passed_to_runner(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    header_ro, body_ro = _write_prompt_parts(tmp_path, role_marker="readonly-worker")
    header_build, body_build = _write_prompt_parts(
        tmp_path, role_marker="build-worker"
    )
    working_directory = tmp_path / "project"
    working_directory.mkdir()
    run_state_directory = tmp_path / "run-state"
    specification_path = _write_batch_spec(
        tmp_path,
        all_worker_payloads=[
            _worker_payload(
                role_name="readonly-worker",
                all_prompt_parts=[str(header_ro), str(body_ro)],
                working_directory=working_directory,
                tool_profile=TOOL_PROFILE_READONLY,
                is_repo_only=True,
            ),
            _worker_payload(
                role_name="build-worker",
                all_prompt_parts=[str(header_build), str(body_build)],
                working_directory=working_directory,
                tool_profile=TOOL_PROFILE_BUILD,
            ),
        ],
    )
    batch_spec = batch.load_batch_spec(specification_path)
    recorder = _RunnerRecorder(
        {
            "readonly-worker": _ok_outcome("ro"),
            "build-worker": _ok_outcome("build"),
        }
    )
    monkeypatch.setattr(
        batch, "batch_preflight", lambda **_kwargs: PreflightOutcome(True, None)
    )
    monkeypatch.setattr(batch, "batch_headless_runner", recorder)
    monkeypatch.setattr(batch, "batch_sleep", lambda _seconds: None)

    batch.run_grok_batch(
        batch_spec=batch_spec,
        run_state_directory=run_state_directory,
    )

    all_extra_arguments = [
        each_kwargs["all_extra_arguments"]
        for each_kwargs in recorder.all_keyword_arguments
    ]
    readonly_extra = next(
        each_extra
        for each_extra in all_extra_arguments
        if isinstance(each_extra, tuple) and DISALLOWED_TOOLS_FLAG in each_extra
    )
    build_extra = next(
        each_extra
        for each_extra in all_extra_arguments
        if isinstance(each_extra, tuple) and DISALLOWED_TOOLS_FLAG not in each_extra
    )
    assert READONLY_DISALLOWED_TOOLS_VALUE in readonly_extra
    assert DISABLE_WEB_SEARCH_FLAG in readonly_extra
    assert DISABLE_WEB_SEARCH_FLAG not in build_extra
    assert DEBUG_FILE_FLAG in readonly_extra
    assert DEBUG_FILE_FLAG in build_extra


def test_batch_summary_as_dict_shape_and_report_collection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    header_ok, body_ok = _write_prompt_parts(tmp_path, role_marker="ok-worker")
    header_limited, body_limited = _write_prompt_parts(
        tmp_path, role_marker="limited-worker"
    )
    working_directory = tmp_path / "project"
    working_directory.mkdir()
    run_state_directory = tmp_path / "run-state"
    specification_path = _write_batch_spec(
        tmp_path,
        all_worker_payloads=[
            _worker_payload(
                role_name="ok-worker",
                all_prompt_parts=[str(header_ok), str(body_ok)],
                working_directory=working_directory,
                tool_profile=TOOL_PROFILE_BUILD,
            ),
            _worker_payload(
                role_name="limited-worker",
                all_prompt_parts=[str(header_limited), str(body_limited)],
                working_directory=working_directory,
                tool_profile=TOOL_PROFILE_READONLY,
            ),
        ],
    )
    batch_spec = batch.load_batch_spec(specification_path)
    recorder = _RunnerRecorder(
        {
            "ok-worker": _ok_outcome(),
            "limited-worker": _usage_limit_outcome(),
        }
    )
    monkeypatch.setattr(
        batch, "batch_preflight", lambda **_kwargs: PreflightOutcome(True, None)
    )
    monkeypatch.setattr(batch, "batch_headless_runner", recorder)
    monkeypatch.setattr(batch, "batch_sleep", lambda _seconds: None)

    batch_summary = batch.run_grok_batch(
        batch_spec=batch_spec,
        run_state_directory=run_state_directory,
    )
    summary_payload = batch.batch_summary_as_dict(batch_summary)

    assert summary_payload[SUMMARY_IS_PREFLIGHT_USABLE_KEY] is True
    assert summary_payload[SUMMARY_PREFLIGHT_REASON_KEY] is None
    all_worker_payloads = summary_payload[SUMMARY_WORKERS_KEY]
    assert isinstance(all_worker_payloads, list)
    assert len(all_worker_payloads) == 2
    first_payload = all_worker_payloads[0]
    second_payload = all_worker_payloads[1]
    assert first_payload[SUMMARY_ROLE_NAME_KEY] == "ok-worker"
    assert first_payload[SUMMARY_RETURNCODE_KEY] == 0
    assert first_payload[SUMMARY_CLASSIFICATION_KEY] == CLASSIFICATION_OK
    assert first_payload[SUMMARY_IS_OK_KEY] is True
    assert first_payload[SUMMARY_REPORT_TEXT_KEY] == FIXTURE_REPORT_TEXT
    assert first_payload[SUMMARY_TOOL_PROFILE_KEY] == TOOL_PROFILE_BUILD
    assert SUMMARY_OUTPUT_FILE_KEY in first_payload
    assert SUMMARY_LEADER_SOCKET_KEY in first_payload
    assert SUMMARY_PROMPT_FILE_KEY in first_payload
    assert second_payload[SUMMARY_ROLE_NAME_KEY] == "limited-worker"
    assert second_payload[SUMMARY_CLASSIFICATION_KEY] == CLASSIFICATION_USAGE_LIMIT
    assert second_payload[SUMMARY_IS_OK_KEY] is False
    assert second_payload[SUMMARY_REPORT_TEXT_KEY] == FIXTURE_USAGE_LIMIT_TEXT
    assert Path(str(first_payload[SUMMARY_OUTPUT_FILE_KEY])).is_file()
    assert (
        Path(str(first_payload[SUMMARY_OUTPUT_FILE_KEY])).read_text(
            encoding=UTF8_ENCODING
        )
        == FIXTURE_REPORT_TEXT
    )


def test_preflight_fallthrough_skips_workers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    header_part, body_part = _write_prompt_parts(
        tmp_path, role_marker="never-launched"
    )
    working_directory = tmp_path / "project"
    working_directory.mkdir()
    run_state_directory = tmp_path / "run-state"
    specification_path = _write_batch_spec(
        tmp_path,
        all_worker_payloads=[
            _worker_payload(
                role_name="never-launched",
                all_prompt_parts=[str(header_part), str(body_part)],
                working_directory=working_directory,
                tool_profile=TOOL_PROFILE_BUILD,
            )
        ],
    )
    batch_spec = batch.load_batch_spec(specification_path)
    recorder = _RunnerRecorder({})
    monkeypatch.setattr(
        batch,
        "batch_preflight",
        lambda **_kwargs: PreflightOutcome(False, REASON_GROK_BINARY_MISSING),
    )
    monkeypatch.setattr(batch, "batch_headless_runner", recorder)
    monkeypatch.setattr(batch, "batch_sleep", lambda _seconds: None)

    batch_summary = batch.run_grok_batch(
        batch_spec=batch_spec,
        run_state_directory=run_state_directory,
    )
    summary_payload = batch.batch_summary_as_dict(batch_summary)

    assert batch_summary.is_preflight_usable is False
    assert batch_summary.preflight_reason == REASON_GROK_BINARY_MISSING
    assert batch_summary.all_worker_reports == ()
    assert recorder.all_keyword_arguments == []
    assert summary_payload[SUMMARY_IS_PREFLIGHT_USABLE_KEY] is False
    assert summary_payload[SUMMARY_PREFLIGHT_REASON_KEY] == REASON_GROK_BINARY_MISSING
    assert summary_payload[SUMMARY_WORKERS_KEY] == []


def test_main_prints_summary_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    header_part, body_part = _write_prompt_parts(tmp_path, role_marker="cli-worker")
    working_directory = tmp_path / "project"
    working_directory.mkdir()
    run_state_directory = tmp_path / "run-state"
    specification_path = _write_batch_spec(
        tmp_path,
        all_worker_payloads=[
            _worker_payload(
                role_name="cli-worker",
                all_prompt_parts=[str(header_part), str(body_part)],
                working_directory=working_directory,
                tool_profile=TOOL_PROFILE_BUILD,
            )
        ],
    )
    recorder = _RunnerRecorder({"cli-worker": _ok_outcome()})
    monkeypatch.setattr(
        batch, "batch_preflight", lambda **_kwargs: PreflightOutcome(True, None)
    )
    monkeypatch.setattr(batch, "batch_headless_runner", recorder)
    monkeypatch.setattr(batch, "batch_sleep", lambda _seconds: None)

    exit_code = batch.main(
        [
            "--spec",
            str(specification_path),
            "--run-temp-dir",
            str(run_state_directory),
        ]
    )

    captured = capsys.readouterr()
    summary_payload = json.loads(captured.out)
    assert exit_code == 0
    assert summary_payload[SUMMARY_IS_PREFLIGHT_USABLE_KEY] is True
    assert len(summary_payload[SUMMARY_WORKERS_KEY]) == 1
    assert (
        summary_payload[SUMMARY_WORKERS_KEY][0][SUMMARY_ROLE_NAME_KEY] == "cli-worker"
    )


def test_worker_exception_preserves_partial_summary_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    header_good, body_good = _write_prompt_parts(tmp_path, role_marker="good-worker")
    working_directory = tmp_path / "project"
    working_directory.mkdir()
    run_state_directory = tmp_path / "run-state"
    missing_prompt_part = tmp_path / "does-not-exist-prompt.txt"
    specification_path = _write_batch_spec(
        tmp_path,
        all_worker_payloads=[
            _worker_payload(
                role_name="good-worker",
                all_prompt_parts=[str(header_good), str(body_good)],
                working_directory=working_directory,
                tool_profile=TOOL_PROFILE_BUILD,
            ),
            _worker_payload(
                role_name="broken-worker",
                all_prompt_parts=[str(missing_prompt_part)],
                working_directory=working_directory,
                tool_profile=TOOL_PROFILE_BUILD,
            ),
        ],
    )
    recorder = _RunnerRecorder({"good-worker": _ok_outcome()})
    monkeypatch.setattr(
        batch, "batch_preflight", lambda **_kwargs: PreflightOutcome(True, None)
    )
    monkeypatch.setattr(batch, "batch_headless_runner", recorder)
    monkeypatch.setattr(batch, "batch_sleep", lambda _seconds: None)

    exit_code = batch.main(
        [
            "--spec",
            str(specification_path),
            "--run-temp-dir",
            str(run_state_directory),
        ]
    )

    captured = capsys.readouterr()
    summary_payload = json.loads(captured.out)
    all_worker_payloads = summary_payload[SUMMARY_WORKERS_KEY]
    assert exit_code == 1
    assert isinstance(all_worker_payloads, list)
    assert len(all_worker_payloads) == 2
    report_by_role_name = {
        each_payload[SUMMARY_ROLE_NAME_KEY]: each_payload
        for each_payload in all_worker_payloads
    }
    good_payload = report_by_role_name["good-worker"]
    broken_payload = report_by_role_name["broken-worker"]
    assert good_payload[SUMMARY_IS_OK_KEY] is True
    assert good_payload[SUMMARY_CLASSIFICATION_KEY] == CLASSIFICATION_OK
    assert good_payload[SUMMARY_REPORT_TEXT_KEY] == FIXTURE_REPORT_TEXT
    assert broken_payload[SUMMARY_IS_OK_KEY] is False
    assert broken_payload[SUMMARY_CLASSIFICATION_KEY] == CLASSIFICATION_ERROR
    assert broken_payload[SUMMARY_REPORT_TEXT_KEY]
    assert len(recorder.all_keyword_arguments) == 1


def test_require_int_rejects_bool() -> None:
    with pytest.raises(ValueError, match="timeout_seconds"):
        batch._require_int(True, WORKER_SPEC_TIMEOUT_KEY)
    assert batch._require_int(600, WORKER_SPEC_TIMEOUT_KEY) == 600


def test_load_batch_spec_rejects_boolean_timeout(tmp_path: Path) -> None:
    header_part, body_part = _write_prompt_parts(tmp_path)
    working_directory = tmp_path / "project"
    working_directory.mkdir()
    worker_payload = _worker_payload(
        role_name="bool-timeout-worker",
        all_prompt_parts=[str(header_part), str(body_part)],
        working_directory=working_directory,
        tool_profile=TOOL_PROFILE_BUILD,
    )
    worker_payload[WORKER_SPEC_TIMEOUT_KEY] = True
    specification_path = _write_batch_spec(
        tmp_path, all_worker_payloads=[worker_payload]
    )

    with pytest.raises(ValueError, match=WORKER_SPEC_TIMEOUT_KEY):
        batch.load_batch_spec(specification_path)


def test_load_batch_spec_missing_worker_keys_raise_value_error(
    tmp_path: Path,
) -> None:
    specification_path = tmp_path / "empty-worker-spec.json"
    specification_path.write_text(
        json.dumps(
            {
                "role": "x",
                "should_ping": False,
                "workers": [{}],
            }
        ),
        encoding=UTF8_ENCODING,
    )

    with pytest.raises(ValueError) as raised_error:
        batch.load_batch_spec(specification_path)

    assert not isinstance(raised_error.value, KeyError)
    assert "role_name" in str(raised_error.value).lower() or "missing" in str(
        raised_error.value
    ).lower() or "must be" in str(raised_error.value).lower()


def test_load_batch_spec_rejects_non_positive_timeout_and_max_turns(
    tmp_path: Path,
) -> None:
    header_part, body_part = _write_prompt_parts(tmp_path)
    working_directory = tmp_path / "project"
    working_directory.mkdir()

    zero_timeout_dir = tmp_path / "zero-timeout"
    zero_timeout_dir.mkdir()
    zero_timeout_payload = _worker_payload(
        role_name="zero-timeout",
        all_prompt_parts=[str(header_part), str(body_part)],
        working_directory=working_directory,
        tool_profile=TOOL_PROFILE_BUILD,
        timeout_seconds=0,
    )
    zero_timeout_path = _write_batch_spec(
        zero_timeout_dir,
        all_worker_payloads=[zero_timeout_payload],
    )
    with pytest.raises(ValueError, match=WORKER_SPEC_TIMEOUT_KEY):
        batch.load_batch_spec(zero_timeout_path)

    negative_turns_dir = tmp_path / "negative-turns"
    negative_turns_dir.mkdir()
    negative_turns_payload = _worker_payload(
        role_name="negative-turns",
        all_prompt_parts=[str(header_part), str(body_part)],
        working_directory=working_directory,
        tool_profile=TOOL_PROFILE_BUILD,
    )
    negative_turns_payload[WORKER_SPEC_MAX_TURNS_KEY] = -1
    negative_turns_path = _write_batch_spec(
        negative_turns_dir,
        all_worker_payloads=[negative_turns_payload],
    )
    with pytest.raises(ValueError, match=WORKER_SPEC_MAX_TURNS_KEY):
        batch.load_batch_spec(negative_turns_path)


def test_load_batch_spec_accepts_default_timeout_and_max_turns(
    tmp_path: Path,
) -> None:
    header_part, body_part = _write_prompt_parts(tmp_path)
    working_directory = tmp_path / "project"
    working_directory.mkdir()
    worker_payload = {
        "role_name": "defaults-worker",
        "prompt_parts": [str(header_part), str(body_part)],
        "cwd": str(working_directory),
        "tool_profile": TOOL_PROFILE_BUILD,
    }
    specification_path = _write_batch_spec(
        tmp_path, all_worker_payloads=[worker_payload]
    )

    batch_spec = batch.load_batch_spec(specification_path)

    assert len(batch_spec.all_workers) == 1
    assert batch_spec.all_workers[0].timeout_seconds == DEFAULT_WORKER_TIMEOUT_SECONDS
    assert batch_spec.all_workers[0].max_turns == DEFAULT_WORKER_MAX_TURNS
