"""Direct unit tests for the copilot_quota pre-check.

Every case drives the production ``main`` / ``evaluate_copilot_quota`` path with
only the ``gh`` subprocess boundary (``_run_gh``) stubbed, fed a captured
``copilot_internal/user`` JSON fixture in the example-account shape.
"""

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load_copilot_quota_module() -> ModuleType:
    scripts_directory = Path(__file__).parent.parent
    if str(scripts_directory) not in sys.path:
        sys.path.insert(0, str(scripts_directory))
    module_path = scripts_directory / "copilot_quota.py"
    specification = importlib.util.spec_from_file_location("copilot_quota", module_path)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


copilot_quota = _load_copilot_quota_module()

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "copilot_internal_user_example.json"
AVAILABLE_USER_JSON = FIXTURE_PATH.read_text(encoding="utf-8")
FAKE_TOKEN_RESULT = (0, "ghp_faketoken_value\n")


def _exhausted_user_json() -> str:
    user = json.loads(AVAILABLE_USER_JSON)
    premium = user["quota_snapshots"]["premium_interactions"]
    premium["remaining"] = 0
    premium["quota_remaining"] = 0.0
    premium["percent_remaining"] = 0.0
    return json.dumps(user)


def _user_json_without_premium_snapshot() -> str:
    user = json.loads(AVAILABLE_USER_JSON)
    del user["quota_snapshots"]
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
def _isolate_account_sources(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("COPILOT_QUOTA_ACCOUNT", raising=False)
    monkeypatch.setattr(
        copilot_quota, "COPILOT_QUOTA_DEFAULT_ENV_FILE_PATH", tmp_path / ".env"
    )


def test_main_runs_copilot_when_premium_quota_available(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("COPILOT_QUOTA_ACCOUNT", "example-account")
    monkeypatch.setattr(
        copilot_quota,
        "_run_gh",
        _gh_stub(FAKE_TOKEN_RESULT, (0, AVAILABLE_USER_JSON)),
    )
    exit_code = copilot_quota.main([])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "running Copilot" in captured.out
    assert "6817" in captured.out


def test_main_exits_out_of_quota_when_premium_exhausted(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("COPILOT_QUOTA_ACCOUNT", "example-account")
    monkeypatch.setattr(
        copilot_quota,
        "_run_gh",
        _gh_stub(FAKE_TOKEN_RESULT, (0, _exhausted_user_json())),
    )
    exit_code = copilot_quota.main([])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "scenario A" in captured.err


def test_main_exits_api_down_on_non_json_response(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("COPILOT_QUOTA_ACCOUNT", "example-account")
    monkeypatch.setattr(
        copilot_quota,
        "_run_gh",
        _gh_stub(FAKE_TOKEN_RESULT, (0, "not json at all")),
    )
    exit_code = copilot_quota.main([])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "scenario B" in captured.err


def test_main_exits_api_down_on_missing_premium_snapshot(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("COPILOT_QUOTA_ACCOUNT", "example-account")
    monkeypatch.setattr(
        copilot_quota,
        "_run_gh",
        _gh_stub(FAKE_TOKEN_RESULT, (0, _user_json_without_premium_snapshot())),
    )
    exit_code = copilot_quota.main([])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "scenario B" in captured.err


def test_main_exits_api_down_when_gh_token_unresolved(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("COPILOT_QUOTA_ACCOUNT", "example-account")
    monkeypatch.setattr(
        copilot_quota,
        "_run_gh",
        _gh_stub((1, ""), (0, AVAILABLE_USER_JSON)),
    )
    exit_code = copilot_quota.main([])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "scenario B" in captured.err


def test_main_exits_no_config_and_names_env_path_and_key(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _fail_if_called(
        command_arguments: list[str],
        extra_environment: dict[str, str] | None = None,
    ) -> tuple[int, str]:
        raise AssertionError("gh must not run when no account is configured")

    monkeypatch.setattr(copilot_quota, "_run_gh", _fail_if_called)
    exit_code = copilot_quota.main([])
    captured = capsys.readouterr()
    assert exit_code == 3
    assert "scenario C" in captured.err
    assert "COPILOT_QUOTA_ACCOUNT" in captured.err
    assert ".env" in captured.err


@pytest.mark.parametrize(
    ("api_result", "expected_exit_code", "expected_scenario"),
    [
        ((0, _exhausted_user_json()), 1, "scenario A"),
        ((0, "not json at all"), 2, "scenario B"),
    ],
)
def test_every_gh_backed_skip_writes_a_log_line_naming_the_scenario(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    api_result: tuple[int, str],
    expected_exit_code: int,
    expected_scenario: str,
) -> None:
    monkeypatch.setenv("COPILOT_QUOTA_ACCOUNT", "example-account")
    monkeypatch.setattr(
        copilot_quota, "_run_gh", _gh_stub(FAKE_TOKEN_RESULT, api_result)
    )
    exit_code = copilot_quota.main([])
    captured = capsys.readouterr()
    assert exit_code == expected_exit_code
    assert captured.out == ""
    assert expected_scenario in captured.err
    assert captured.err.strip() != ""


def test_cli_account_takes_precedence_over_env_var(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("COPILOT_QUOTA_ACCOUNT", "env-user")
    accounts_seen: list[str] = []

    def _fake_run_gh(
        command_arguments: list[str],
        extra_environment: dict[str, str] | None = None,
    ) -> tuple[int, str]:
        if command_arguments[0] == "auth":
            accounts_seen.append(command_arguments[-1])
            return FAKE_TOKEN_RESULT
        return (0, AVAILABLE_USER_JSON)

    monkeypatch.setattr(copilot_quota, "_run_gh", _fake_run_gh)
    decision = copilot_quota.evaluate_copilot_quota(
        cli_account="cli-user", env_file_path=tmp_path / ".env"
    )
    assert decision.exit_code == 0
    assert accounts_seen == ["cli-user"]


def test_account_resolves_from_env_file_when_flag_and_env_absent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# local copilot quota account\nCOPILOT_QUOTA_ACCOUNT=file-user\n",
        encoding="utf-8",
    )
    accounts_seen: list[str] = []

    def _fake_run_gh(
        command_arguments: list[str],
        extra_environment: dict[str, str] | None = None,
    ) -> tuple[int, str]:
        if command_arguments[0] == "auth":
            accounts_seen.append(command_arguments[-1])
            return FAKE_TOKEN_RESULT
        return (0, AVAILABLE_USER_JSON)

    monkeypatch.setattr(copilot_quota, "_run_gh", _fake_run_gh)
    decision = copilot_quota.evaluate_copilot_quota(
        cli_account=None, env_file_path=env_file
    )
    assert decision.exit_code == 0
    assert accounts_seen == ["file-user"]
