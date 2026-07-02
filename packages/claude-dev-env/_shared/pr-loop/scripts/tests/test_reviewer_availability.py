"""Direct unit tests for the unified reviewer_availability pre-check.

Every case drives the production ``main`` path through
``evaluate_reviewer_availability``. Copilot cases stub only the ``gh``
subprocess boundary inside ``copilot_quota`` (``_run_gh``), reusing the same
captured fixture ``test_copilot_quota.py`` drives. Opt-out cases set or clear
``CLAUDE_REVIEWS_DISABLED`` directly.
"""

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load_module(module_name: str) -> ModuleType:
    scripts_directory = Path(__file__).parent.parent
    if str(scripts_directory) not in sys.path:
        sys.path.insert(0, str(scripts_directory))
    module_path = scripts_directory / f"{module_name}.py"
    specification = importlib.util.spec_from_file_location(module_name, module_path)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


copilot_quota = _load_module("copilot_quota")
reviewer_availability = _load_module("reviewer_availability")

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "copilot_internal_user_jonecho.json"
AVAILABLE_USER_JSON = FIXTURE_PATH.read_text(encoding="utf-8")
FAKE_TOKEN_RESULT = (0, "ghp_faketoken_value\n")


def _exhausted_user_json() -> str:
    user = json.loads(AVAILABLE_USER_JSON)
    premium = user["quota_snapshots"]["premium_interactions"]
    premium["remaining"] = 0
    premium["quota_remaining"] = 0.0
    premium["percent_remaining"] = 0.0
    return json.dumps(user)


def _gh_stub(token_result: tuple[int, str], api_result: tuple[int, str]):
    def _fake_run_gh(
        command_arguments: list[str],
        extra_environment: dict[str, str] | None = None,
    ) -> tuple[int, str]:
        if command_arguments and command_arguments[0] == "auth":
            return token_result
        if command_arguments and command_arguments[0] == "api":
            return api_result
        raise AssertionError(f"unexpected gh command {command_arguments}")

    return _fake_run_gh


@pytest.fixture(autouse=True)
def _isolate_reviewer_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("COPILOT_QUOTA_ACCOUNT", raising=False)
    monkeypatch.delenv("CLAUDE_REVIEWS_DISABLED", raising=False)
    monkeypatch.setattr(
        reviewer_availability, "COPILOT_QUOTA_DEFAULT_ENV_FILE_PATH", tmp_path / ".env"
    )


def test_main_reports_copilot_available_when_quota_confirmed_available(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("COPILOT_QUOTA_ACCOUNT", "jonecho")
    monkeypatch.setattr(
        copilot_quota, "_run_gh", _gh_stub(FAKE_TOKEN_RESULT, (0, AVAILABLE_USER_JSON))
    )
    exit_code = reviewer_availability.main(["--reviewer", "copilot"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "running Copilot" in captured.out


def test_main_reports_copilot_down_when_opted_out_via_env(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CLAUDE_REVIEWS_DISABLED", "copilot")

    def _fail_if_called(
        command_arguments: list[str],
        extra_environment: dict[str, str] | None = None,
    ) -> tuple[int, str]:
        raise AssertionError("gh must not run once copilot is opted out")

    monkeypatch.setattr(copilot_quota, "_run_gh", _fail_if_called)
    exit_code = reviewer_availability.main(["--reviewer", "copilot"])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "CLAUDE_REVIEWS_DISABLED" in captured.err


def test_main_reports_copilot_down_when_out_of_quota(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("COPILOT_QUOTA_ACCOUNT", "jonecho")
    monkeypatch.setattr(
        copilot_quota,
        "_run_gh",
        _gh_stub(FAKE_TOKEN_RESULT, (0, _exhausted_user_json())),
    )
    exit_code = reviewer_availability.main(["--reviewer", "copilot"])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "scenario A" in captured.err


def test_main_reports_copilot_down_when_quota_api_is_down(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("COPILOT_QUOTA_ACCOUNT", "jonecho")
    monkeypatch.setattr(
        copilot_quota, "_run_gh", _gh_stub(FAKE_TOKEN_RESULT, (0, "not json at all"))
    )
    exit_code = reviewer_availability.main(["--reviewer", "copilot"])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "scenario B" in captured.err


def test_main_reports_copilot_down_when_no_account_configured(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = reviewer_availability.main(["--reviewer", "copilot"])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "scenario C" in captured.err


def test_main_reports_bugbot_available_when_not_opted_out(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = reviewer_availability.main(["--reviewer", "bugbot"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "bugbot" in captured.out


def test_main_reports_bugbot_down_when_opted_out_via_env(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CLAUDE_REVIEWS_DISABLED", "bugbot")
    exit_code = reviewer_availability.main(["--reviewer", "bugbot"])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "CLAUDE_REVIEWS_DISABLED" in captured.err
