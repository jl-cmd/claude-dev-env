from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TEST_DIRECTORY = Path(__file__).resolve().parent
if str(TEST_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(TEST_DIRECTORY))

import test_automatic_advisory as support
from automatic_advisory import configuration as advisory_configuration


@pytest.mark.parametrize("field_name", ["poll_seconds", "child_timeout_seconds"])
@pytest.mark.parametrize("invalid_seconds", [float("nan"), float("inf"), float("-inf")])
def test_configuration_rejects_nonfinite_timing(
    tmp_path: Path, field_name: str, invalid_seconds: float
) -> None:
    settings_path = tmp_path / "settings.json"
    all_settings = support._valid_advisory_settings_fields(tmp_path)
    settings_path.write_text(json.dumps(all_settings), encoding="utf-8")
    valid_settings = advisory_configuration.load_advisory_settings(settings_path)
    assert valid_settings.poll_seconds == 0.25
    assert valid_settings.child_timeout_seconds == 45.5
    all_settings[field_name] = invalid_seconds
    settings_path.write_text(json.dumps(all_settings), encoding="utf-8")

    with pytest.raises(
        advisory_configuration.AdvisoryConfigurationError,
        match=f"{field_name} must be positive",
    ):
        advisory_configuration.load_advisory_settings(settings_path)


def test_poll_error_log_sits_beside_the_registration_state_file(tmp_path: Path) -> None:
    checkout_path = tmp_path / "checkout"
    checkout_path.mkdir()
    registration = support._build_registration(tmp_path, checkout_path)
    settings = support._build_settings(registration)

    assert (
        settings.poll_error_log_path
        == registration.state_path.parent / "poll-errors.log"
    )
    assert settings.poll_error_log_path.parent == settings.poll_lock_root.parent
