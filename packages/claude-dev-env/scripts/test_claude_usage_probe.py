"""Unit tests for the Claude session usage probe wrapper."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import claude_usage_probe as usage_probe  # noqa: E402
from dev_env_scripts_constants.claude_usage_probe_constants import (  # noqa: E402
    EXIT_CODE_PROBE_REPORT,
    RESULT_KEY_PROBE_OK,
    RESULT_KEY_SESSION_HAS_USAGE_LEFT,
    RESULT_KEY_SESSION_UTILIZATION,
    RESULT_KEY_SOURCE,
    RESULT_KEY_WEEKLY_NEAR_CAP,
    RESULT_KEY_WEEKLY_UTILIZATION,
    SESSION_UTILIZATION_NO_USAGE_THRESHOLD,
    SOURCE_UNAVAILABLE,
)

FIXTURE_SOURCE_PROBE = "probe"
FIXTURE_SESSION_UTILIZATION_AVAILABLE = 42.0
FIXTURE_SESSION_UTILIZATION_DRAINED = 100.0
FIXTURE_SESSION_UTILIZATION_NEAR_DRAINED = 99.0
FIXTURE_WEEKLY_UTILIZATION = 63.0
FIXTURE_RESOLVER_RETURNCODE_OK = 0
FIXTURE_RESOLVER_RETURNCODE_FAIL = 2


def _completed_process(
    *,
    returncode: int,
    stdout: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["python", "resolve_usage_window.py"],
        returncode=returncode,
        stdout=stdout,
        stderr="",
    )


def _resolver_stdout(
    *,
    session_utilization: float | None,
    weekly_utilization: float | None = FIXTURE_WEEKLY_UTILIZATION,
    weekly_near_cap: bool = False,
    source: str = FIXTURE_SOURCE_PROBE,
) -> str:
    return json.dumps(
        {
            RESULT_KEY_SESSION_UTILIZATION: session_utilization,
            RESULT_KEY_WEEKLY_UTILIZATION: weekly_utilization,
            RESULT_KEY_WEEKLY_NEAR_CAP: weekly_near_cap,
            RESULT_KEY_SOURCE: source,
        }
    )


@pytest.mark.parametrize(
    ("session_utilization", "expected_has_usage_left"),
    [
        (FIXTURE_SESSION_UTILIZATION_AVAILABLE, True),
        (FIXTURE_SESSION_UTILIZATION_NEAR_DRAINED, True),
        (FIXTURE_SESSION_UTILIZATION_DRAINED, False),
        (SESSION_UTILIZATION_NO_USAGE_THRESHOLD + 1.0, False),
        (None, None),
    ],
)
def test_session_has_usage_left_from_utilization(
    session_utilization: float | None,
    expected_has_usage_left: bool | None,
) -> None:
    assert (
        usage_probe.session_has_usage_left_from_utilization(session_utilization)
        is expected_has_usage_left
    )


@pytest.mark.parametrize(
    ("session_has_usage_left", "expected_should_force_chain"),
    [
        (False, True),
        (True, False),
        (None, False),
    ],
)
def test_should_force_chain_mode(
    session_has_usage_left: bool | None,
    expected_should_force_chain: bool,
) -> None:
    assert (
        usage_probe.should_force_chain_mode(session_has_usage_left)
        is expected_should_force_chain
    )


def test_build_usage_probe_report_available() -> None:
    probe_report = usage_probe.build_usage_probe_report(
        session_utilization=FIXTURE_SESSION_UTILIZATION_AVAILABLE,
        weekly_utilization=FIXTURE_WEEKLY_UTILIZATION,
        weekly_near_cap=False,
        source=FIXTURE_SOURCE_PROBE,
    )
    assert probe_report == usage_probe.ClaudeUsageProbeReport(
        session_utilization=FIXTURE_SESSION_UTILIZATION_AVAILABLE,
        weekly_utilization=FIXTURE_WEEKLY_UTILIZATION,
        weekly_near_cap=False,
        session_has_usage_left=True,
        source=FIXTURE_SOURCE_PROBE,
        probe_ok=True,
    )


def test_build_usage_probe_report_drained() -> None:
    probe_report = usage_probe.build_usage_probe_report(
        session_utilization=FIXTURE_SESSION_UTILIZATION_DRAINED,
        weekly_utilization=FIXTURE_WEEKLY_UTILIZATION,
        weekly_near_cap=False,
        source=FIXTURE_SOURCE_PROBE,
    )
    assert probe_report.session_has_usage_left is False
    assert probe_report.probe_ok is True


def test_build_usage_probe_report_null_session_meter() -> None:
    probe_report = usage_probe.build_usage_probe_report(
        session_utilization=None,
        weekly_utilization=None,
        weekly_near_cap=None,
        source=FIXTURE_SOURCE_PROBE,
    )
    assert probe_report.session_has_usage_left is None
    assert probe_report.probe_ok is True


def test_build_unavailable_usage_probe_report() -> None:
    probe_report = usage_probe.build_unavailable_usage_probe_report()
    assert probe_report == usage_probe.ClaudeUsageProbeReport(
        session_utilization=None,
        weekly_utilization=None,
        weekly_near_cap=None,
        session_has_usage_left=None,
        source=SOURCE_UNAVAILABLE,
        probe_ok=False,
    )


def test_probe_claude_usage_maps_successful_resolver_stdout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolver_stdout = _resolver_stdout(
        session_utilization=FIXTURE_SESSION_UTILIZATION_AVAILABLE
    )

    def _fake_runner(
        all_invocation_tokens: list[str],
        **all_keywords: object,
    ) -> subprocess.CompletedProcess[str]:
        del all_invocation_tokens, all_keywords
        return _completed_process(
            returncode=FIXTURE_RESOLVER_RETURNCODE_OK,
            stdout=resolver_stdout,
        )

    monkeypatch.setattr(usage_probe, "usage_probe_subprocess_runner", _fake_runner)
    monkeypatch.setattr(
        usage_probe,
        "usage_probe_resolve_script_path",
        Path(__file__),
    )
    probe_report = usage_probe.probe_claude_usage()
    assert probe_report.probe_ok is True
    assert probe_report.session_has_usage_left is True
    assert probe_report.session_utilization == FIXTURE_SESSION_UTILIZATION_AVAILABLE


def test_probe_claude_usage_unavailable_on_non_zero_resolver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_runner(
        all_invocation_tokens: list[str],
        **all_keywords: object,
    ) -> subprocess.CompletedProcess[str]:
        del all_invocation_tokens, all_keywords
        return _completed_process(
            returncode=FIXTURE_RESOLVER_RETURNCODE_FAIL,
            stdout=json.dumps({"error": "no token"}),
        )

    monkeypatch.setattr(usage_probe, "usage_probe_subprocess_runner", _fake_runner)
    monkeypatch.setattr(
        usage_probe,
        "usage_probe_resolve_script_path",
        Path(__file__),
    )
    probe_report = usage_probe.probe_claude_usage()
    assert probe_report.probe_ok is False
    assert probe_report.source == SOURCE_UNAVAILABLE


def test_probe_claude_usage_unavailable_when_script_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    missing_script_path = tmp_path / "missing_resolve_usage_window.py"
    monkeypatch.setattr(
        usage_probe,
        "usage_probe_resolve_script_path",
        missing_script_path,
    )
    probe_report = usage_probe.probe_claude_usage()
    assert probe_report.probe_ok is False


def test_probe_claude_usage_unavailable_on_timeout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    resolve_usage_window_path = tmp_path / "resolve_usage_window.py"
    resolve_usage_window_path.write_text("# stub\n", encoding="utf-8")

    def _timeout_runner(
        all_invocation_tokens: list[str],
        **all_keywords: object,
    ) -> subprocess.CompletedProcess[str]:
        del all_invocation_tokens, all_keywords
        raise subprocess.TimeoutExpired(cmd="resolve", timeout=1)

    monkeypatch.setattr(usage_probe, "usage_probe_subprocess_runner", _timeout_runner)
    monkeypatch.setattr(
        usage_probe,
        "usage_probe_resolve_script_path",
        resolve_usage_window_path,
    )
    probe_report = usage_probe.probe_claude_usage()
    assert probe_report.probe_ok is False


@pytest.mark.parametrize(
    "resolver_payload",
    [
        {RESULT_KEY_SESSION_UTILIZATION: 5, RESULT_KEY_WEEKLY_UTILIZATION: 10},
        {RESULT_KEY_SESSION_UTILIZATION: 5, RESULT_KEY_SOURCE: 7},
        {RESULT_KEY_SESSION_UTILIZATION: 5, RESULT_KEY_SOURCE: ""},
    ],
)
def test_probe_reports_unavailable_when_source_is_not_a_label(
    monkeypatch: pytest.MonkeyPatch,
    resolver_payload: dict[str, object],
) -> None:
    """probe_ok true must never pair with the unavailable source label."""

    def _fake_runner(
        all_invocation_tokens: list[str],
        **all_keywords: object,
    ) -> subprocess.CompletedProcess[str]:
        del all_invocation_tokens, all_keywords
        return _completed_process(
            returncode=FIXTURE_RESOLVER_RETURNCODE_OK,
            stdout=json.dumps(resolver_payload),
        )

    monkeypatch.setattr(usage_probe, "usage_probe_subprocess_runner", _fake_runner)
    monkeypatch.setattr(
        usage_probe,
        "usage_probe_resolve_script_path",
        Path(__file__),
    )
    probe_report = usage_probe.probe_claude_usage()
    assert probe_report.probe_ok is False
    assert probe_report.source == SOURCE_UNAVAILABLE
    assert probe_report.session_utilization is None


def test_probe_reports_unavailable_on_non_dict_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_runner(
        all_invocation_tokens: list[str],
        **all_keywords: object,
    ) -> subprocess.CompletedProcess[str]:
        del all_invocation_tokens, all_keywords
        return _completed_process(
            returncode=FIXTURE_RESOLVER_RETURNCODE_OK,
            stdout=json.dumps([1, 2, 3]),
        )

    monkeypatch.setattr(usage_probe, "usage_probe_subprocess_runner", _fake_runner)
    monkeypatch.setattr(
        usage_probe,
        "usage_probe_resolve_script_path",
        Path(__file__),
    )
    assert usage_probe.probe_claude_usage().probe_ok is False


def test_locate_resolve_usage_window_script_prefers_checkout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    package_root = tmp_path / "claude-dev-env"
    checkout_script_path = (
        package_root
        / "skills"
        / "usage-pause"
        / "scripts"
        / "resolve_usage_window.py"
    )
    checkout_script_path.parent.mkdir(parents=True)
    checkout_script_path.write_text("# checkout\n", encoding="utf-8")
    home_directory = tmp_path / "home"
    installed_script_path = (
        home_directory
        / ".claude"
        / "skills"
        / "usage-pause"
        / "scripts"
        / "resolve_usage_window.py"
    )
    installed_script_path.parent.mkdir(parents=True)
    installed_script_path.write_text("# installed\n", encoding="utf-8")

    monkeypatch.setattr(usage_probe, "usage_probe_package_root", package_root)
    monkeypatch.setattr(usage_probe, "usage_probe_home_directory", home_directory)
    located_script_path = usage_probe.locate_resolve_usage_window_script()
    assert located_script_path == checkout_script_path


def test_locate_resolve_usage_window_script_falls_back_to_install(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    package_root = tmp_path / "claude-dev-env"
    package_root.mkdir()
    home_directory = tmp_path / "home"
    installed_script_path = (
        home_directory
        / ".claude"
        / "skills"
        / "usage-pause"
        / "scripts"
        / "resolve_usage_window.py"
    )
    installed_script_path.parent.mkdir(parents=True)
    installed_script_path.write_text("# installed\n", encoding="utf-8")

    monkeypatch.setattr(usage_probe, "usage_probe_package_root", package_root)
    monkeypatch.setattr(usage_probe, "usage_probe_home_directory", home_directory)
    located_script_path = usage_probe.locate_resolve_usage_window_script()
    assert located_script_path == installed_script_path


def test_main_writes_report_and_exits_zero(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    expected_report = usage_probe.build_usage_probe_report(
        session_utilization=FIXTURE_SESSION_UTILIZATION_AVAILABLE,
        weekly_utilization=FIXTURE_WEEKLY_UTILIZATION,
        weekly_near_cap=False,
        source=FIXTURE_SOURCE_PROBE,
    )
    monkeypatch.setattr(
        usage_probe,
        "probe_claude_usage",
        lambda: expected_report,
    )
    exit_code = usage_probe.main([])
    captured_stdout = capsys.readouterr().out
    assert exit_code == EXIT_CODE_PROBE_REPORT
    assert json.loads(captured_stdout) == {
        RESULT_KEY_SESSION_UTILIZATION: FIXTURE_SESSION_UTILIZATION_AVAILABLE,
        RESULT_KEY_WEEKLY_UTILIZATION: FIXTURE_WEEKLY_UTILIZATION,
        RESULT_KEY_WEEKLY_NEAR_CAP: False,
        RESULT_KEY_SESSION_HAS_USAGE_LEFT: True,
        RESULT_KEY_SOURCE: FIXTURE_SOURCE_PROBE,
        RESULT_KEY_PROBE_OK: True,
    }


def test_encode_usage_probe_report_is_one_json_line() -> None:
    probe_report = usage_probe.build_unavailable_usage_probe_report()
    encoded_report = usage_probe.encode_usage_probe_report(probe_report)
    assert encoded_report.endswith("\n")
    assert json.loads(encoded_report) == {
        RESULT_KEY_SESSION_UTILIZATION: None,
        RESULT_KEY_WEEKLY_UTILIZATION: None,
        RESULT_KEY_WEEKLY_NEAR_CAP: None,
        RESULT_KEY_SESSION_HAS_USAGE_LEFT: None,
        RESULT_KEY_SOURCE: SOURCE_UNAVAILABLE,
        RESULT_KEY_PROBE_OK: False,
    }
