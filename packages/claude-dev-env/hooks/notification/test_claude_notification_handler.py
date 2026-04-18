"""Unit tests for claude-notification-handler Discord wiring."""

import importlib.util
import pathlib
import types
from unittest.mock import patch

HOOK_DIRECTORY = pathlib.Path(__file__).parent
MODULE_PATH = HOOK_DIRECTORY / "claude_notification_handler.py"

FIXTURE_ATTENTION_SECRET_ID = "fixture-attention-id-0001"
FIXTURE_PROJECT_NAME = "fixture-project"
FIXTURE_MESSAGE = "attention required"
FIXTURE_PRIORITY = "default"
NON_WINDOWS_NON_WSL_PLATFORM = "Darwin"


def load_handler_with_environment(
    environment_overrides: dict[str, str],
) -> types.ModuleType:
    module_specification = importlib.util.spec_from_file_location(
        "claude_notification_handler_under_test",
        MODULE_PATH,
    )
    assert module_specification is not None
    assert module_specification.loader is not None
    module_under_test = importlib.util.module_from_spec(module_specification)
    with patch.dict("os.environ", environment_overrides, clear=False):
        module_specification.loader.exec_module(module_under_test)
    return module_under_test


def test_send_desktop_and_push_notification_forwards_attention_secret_id_to_notify_discord() -> (
    None
):
    module_under_test = load_handler_with_environment(
        {"BWS_DISCORD_ATTENTION_SECRET_ID": FIXTURE_ATTENTION_SECRET_ID}
    )
    with (
        patch.object(module_under_test, "notify_ntfy"),
        patch.object(module_under_test, "notify_discord") as discord_spy,
        patch.object(module_under_test, "platform") as platform_stub,
    ):
        platform_stub.system.return_value = NON_WINDOWS_NON_WSL_PLATFORM
        module_under_test.send_desktop_and_push_notification(
            project_name=FIXTURE_PROJECT_NAME,
            notification_message=FIXTURE_MESSAGE,
            ntfy_priority=FIXTURE_PRIORITY,
        )
    assert discord_spy.call_count == 1
    call_kwargs = discord_spy.call_args.kwargs
    assert call_kwargs["webhook_secret_id"] == FIXTURE_ATTENTION_SECRET_ID
    assert call_kwargs["title"] == FIXTURE_PROJECT_NAME
    assert call_kwargs["message"] == FIXTURE_MESSAGE
