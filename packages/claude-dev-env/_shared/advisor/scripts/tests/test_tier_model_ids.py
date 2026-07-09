"""Behavioral tests for ladder-tier to CLI model-ID resolution."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load_tier_model_ids_module() -> ModuleType:
    scripts_root = Path(__file__).parent.parent
    constants_root = scripts_root / "config"
    sys.path.insert(0, str(constants_root))
    module_path = scripts_root / "tier_model_ids.py"
    specification = importlib.util.spec_from_file_location(
        "tier_model_ids", module_path
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


tier_model_ids = _load_tier_model_ids_module()
resolve_cli_model_id = tier_model_ids.resolve_cli_model_id

from advisor_scripts_constants.model_tier_run_validator_constants import (  # noqa: E402
    ADVISOR_SENDMESSAGE_REPLY_WAIT_SECONDS,
    ALL_CLI_MODEL_ID_BY_TIER,
)


@pytest.mark.parametrize(
    ("tier_name", "expected_model_id"),
    [
        ("Fable", "fable"),
        ("Opus", "opus"),
        ("Sonnet", "sonnet"),
        ("Haiku", "haiku"),
        ("fable", "fable"),
        ("OPUS", "opus"),
        ("sonnet", "sonnet"),
        ("hAiKu", "haiku"),
    ],
)
def test_resolve_cli_model_id_maps_known_tiers(
    tier_name: str,
    expected_model_id: str,
) -> None:
    assert resolve_cli_model_id(tier_name) == expected_model_id


def test_resolve_cli_model_id_rejects_unknown_tier() -> None:
    with pytest.raises(ValueError, match="not a known model tier"):
        resolve_cli_model_id("Titan")


def test_sendmessage_reply_wait_is_positive_two_minute_bound() -> None:
    assert ADVISOR_SENDMESSAGE_REPLY_WAIT_SECONDS > 0
    assert ADVISOR_SENDMESSAGE_REPLY_WAIT_SECONDS == 120


def test_cli_model_id_map_covers_every_ladder_alias() -> None:
    assert ALL_CLI_MODEL_ID_BY_TIER == {
        "Fable": "fable",
        "Opus": "opus",
        "Sonnet": "sonnet",
        "Haiku": "haiku",
    }
