"""Unit tests for notification_utils ntfy guard behavior."""

import importlib.util
import pathlib
import types
from unittest.mock import patch

HOOK_DIRECTORY = pathlib.Path(__file__).parent
MODULE_PATH = HOOK_DIRECTORY / "notification_utils.py"


def load_notification_utils_with_environment(
    environment_overrides: dict[str, str],
) -> types.ModuleType:
    module_specification = importlib.util.spec_from_file_location(
        "notification_utils_under_test",
        MODULE_PATH,
    )
    assert module_specification is not None
    assert module_specification.loader is not None
    module_under_test = importlib.util.module_from_spec(module_specification)
    with patch.dict("os.environ", environment_overrides, clear=False):
        module_specification.loader.exec_module(module_under_test)
    return module_under_test


def test_should_skip_curl_when_topic_environment_variable_is_unset() -> None:
    environment_with_topic_removed = {"NTFY_TOPIC": ""}
    module_under_test = load_notification_utils_with_environment(
        environment_with_topic_removed
    )
    with patch("subprocess.Popen") as popen_spy:
        module_under_test.notify_ntfy(title="Test", message="payload")
    assert popen_spy.call_count == 0


def test_should_invoke_curl_when_topic_environment_variable_is_set() -> None:
    environment_with_topic_set = {"NTFY_TOPIC": "private-topic-for-test"}
    module_under_test = load_notification_utils_with_environment(
        environment_with_topic_set
    )
    with patch("subprocess.Popen") as popen_spy:
        module_under_test.notify_ntfy(title="Test", message="payload")
    assert popen_spy.call_count == 1
    curl_arguments = popen_spy.call_args.args[0]
    assert "https://ntfy.sh/private-topic-for-test" in curl_arguments
