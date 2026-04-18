"""Unit tests for attention-needed-notify Discord wiring."""

import importlib.util
import io
import pathlib
import types
from unittest.mock import patch

HOOK_DIRECTORY = pathlib.Path(__file__).parent
MODULE_PATH = HOOK_DIRECTORY / "attention_needed_notify.py"

FIXTURE_ATTENTION_SECRET_ID = "fixture-attention-id-0002"
NON_WINDOWS_NON_WSL_PLATFORM = "Darwin"
EMPTY_HOOK_INPUT_JSON = "{}"


def load_hook_with_environment(
    environment_overrides: dict[str, str],
) -> types.ModuleType:
    module_specification = importlib.util.spec_from_file_location(
        "attention_needed_notify_under_test",
        MODULE_PATH,
    )
    assert module_specification is not None
    assert module_specification.loader is not None
    module_under_test = importlib.util.module_from_spec(module_specification)
    with patch.dict("os.environ", environment_overrides, clear=False):
        module_specification.loader.exec_module(module_under_test)
    return module_under_test


def test_main_forwards_attention_secret_id_to_notify_discord() -> None:
    module_under_test = load_hook_with_environment(
        {"BWS_DISCORD_ATTENTION_SECRET_ID": FIXTURE_ATTENTION_SECRET_ID}
    )
    with (
        patch.object(module_under_test, "notify_ntfy"),
        patch.object(module_under_test, "notify_discord") as discord_spy,
        patch.object(module_under_test, "is_wsl", return_value=False),
        patch.object(module_under_test, "platform") as platform_stub,
        patch("sys.stdin", io.StringIO(EMPTY_HOOK_INPUT_JSON)),
    ):
        platform_stub.system.return_value = NON_WINDOWS_NON_WSL_PLATFORM
        module_under_test.main()
    assert discord_spy.call_count == 1
    call_kwargs = discord_spy.call_args.kwargs
    assert call_kwargs["webhook_secret_id"] == FIXTURE_ATTENTION_SECRET_ID
