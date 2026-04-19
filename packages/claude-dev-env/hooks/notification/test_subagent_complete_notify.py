"""Unit tests for subagent-complete-notify Discord wiring."""

import importlib.util
import pathlib
import types
from unittest.mock import patch

HOOK_DIRECTORY = pathlib.Path(__file__).parent
MODULE_PATH = HOOK_DIRECTORY / "subagent_complete_notify.py"

FIXTURE_ACTIVITY_SECRET_ID = "fixture-activity-id-0003"
FIXTURE_TASK_DESCRIPTION = "subagent finished research task"
FIXTURE_PROJECT_NAME = "fixture-project"
NON_WINDOWS_NON_WSL_PLATFORM = "Darwin"


def load_hook_with_environment(
    environment_overrides: dict[str, str],
) -> types.ModuleType:
    module_specification = importlib.util.spec_from_file_location(
        "subagent_complete_notify_under_test",
        MODULE_PATH,
    )
    assert module_specification is not None
    assert module_specification.loader is not None
    module_under_test = importlib.util.module_from_spec(module_specification)
    with patch.dict("os.environ", environment_overrides, clear=False):
        module_specification.loader.exec_module(module_under_test)
    return module_under_test


def test_main_forwards_activity_secret_id_to_notify_discord() -> None:
    module_under_test = load_hook_with_environment(
        {"BWS_DISCORD_ACTIVITY_SECRET_ID": FIXTURE_ACTIVITY_SECRET_ID}
    )
    with (
        patch.object(
            module_under_test,
            "get_task_info_from_stdin",
            return_value=FIXTURE_TASK_DESCRIPTION,
        ),
        patch.object(
            module_under_test, "get_project_name", return_value=FIXTURE_PROJECT_NAME
        ),
        patch.object(module_under_test, "notify_ntfy"),
        patch.object(module_under_test, "notify_discord") as discord_spy,
        patch.object(module_under_test, "is_wsl", return_value=False),
        patch.object(module_under_test, "platform") as platform_stub,
    ):
        platform_stub.system.return_value = NON_WINDOWS_NON_WSL_PLATFORM
        module_under_test.main()
    assert discord_spy.call_count == 1
    call_kwargs = discord_spy.call_args.kwargs
    assert call_kwargs["webhook_secret_id"] == FIXTURE_ACTIVITY_SECRET_ID
    assert call_kwargs["title"] == FIXTURE_PROJECT_NAME
    assert call_kwargs["message"] == FIXTURE_TASK_DESCRIPTION


def test_notify_ntfy_skips_when_topic_unset() -> None:
    module_under_test = load_hook_with_environment({"CLAUDE_NTFY_TOPIC": ""})
    with patch.object(module_under_test.subprocess, "Popen") as popen_spy:
        module_under_test.notify_ntfy(title="t", message="m")
    assert popen_spy.call_count == 0


def test_main_skips_notify_discord_when_task_description_is_empty() -> None:
    module_under_test = load_hook_with_environment(
        {"BWS_DISCORD_ACTIVITY_SECRET_ID": FIXTURE_ACTIVITY_SECRET_ID}
    )
    with (
        patch.object(module_under_test, "get_task_info_from_stdin", return_value=""),
        patch.object(
            module_under_test, "get_project_name", return_value=FIXTURE_PROJECT_NAME
        ),
        patch.object(module_under_test, "notify_ntfy"),
        patch.object(module_under_test, "notify_discord") as discord_spy,
    ):
        module_under_test.main()
    assert discord_spy.call_count == 0
