"""Behavioral tests for ladder-tier to CLI model-alias resolution."""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load_tier_model_ids_module() -> ModuleType:
    scripts_root = Path(__file__).parent.parent
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
canonical_tier_name = tier_model_ids.canonical_tier_name
detect_host_profile = tier_model_ids.detect_host_profile
constants_root = Path(__file__).parent.parent / "config"
if str(constants_root) not in sys.path:
    sys.path.insert(0, str(constants_root))

from advisor_scripts_constants.model_tier_run_validator_constants import (  # noqa: E402
    ADVISOR_SENDMESSAGE_REPLY_WAIT_SECONDS,
    ALL_CLI_MODEL_ID_BY_TIER,
    ALL_KNOWN_TIER_NAMES,
    ALL_MODEL_TIERS,
    HOST_PROFILE_CLAUDE,
    HOST_PROFILE_THIRD_PARTY,
    THIRD_PARTY_MODEL_TIER,
)

SCRIPTS_ROOT = Path(__file__).parent.parent
DOCUMENTED_RESOLVE_ONE_LINER = (
    "from tier_model_ids import resolve_cli_model_id; "
    "print(resolve_cli_model_id('Opus'))"
)


@pytest.mark.parametrize(
    ("tier_name", "expected_model_alias"),
    [
        ("Fable", "fable"),
        ("Opus", "opus"),
        ("Sonnet", "sonnet"),
        ("Haiku", "haiku"),
        ("ThirdParty", "third-party"),
        ("fable", "fable"),
        ("OPUS", "opus"),
        ("sonnet", "sonnet"),
        ("hAiKu", "haiku"),
        ("thirdparty", "third-party"),
        (" THIRDPARTY ", "third-party"),
        (" Opus ", "opus"),
        ("\thaiku\n", "haiku"),
    ],
)
def test_resolve_cli_model_id_maps_known_tiers(
    tier_name: str,
    expected_model_alias: str,
) -> None:
    assert resolve_cli_model_id(tier_name) == expected_model_alias


def test_resolve_cli_model_id_rejects_unknown_tier() -> None:
    with pytest.raises(ValueError, match="not a known model tier"):
        resolve_cli_model_id("Titan")


def test_resolve_cli_model_id_rejects_empty_string() -> None:
    with pytest.raises(ValueError, match="not a known model tier"):
        resolve_cli_model_id("")


def test_resolve_cli_model_id_rejects_whitespace_only() -> None:
    with pytest.raises(ValueError, match="not a known model tier"):
        resolve_cli_model_id("   ")


def test_sendmessage_reply_wait_is_positive_bound() -> None:
    assert ADVISOR_SENDMESSAGE_REPLY_WAIT_SECONDS > 0
    assert ADVISOR_SENDMESSAGE_REPLY_WAIT_SECONDS == 120


def test_cli_model_alias_map_keys_match_known_tiers() -> None:
    assert set(ALL_CLI_MODEL_ID_BY_TIER) == set(ALL_KNOWN_TIER_NAMES)
    assert set(ALL_MODEL_TIERS).issubset(set(ALL_KNOWN_TIER_NAMES))
    assert THIRD_PARTY_MODEL_TIER in ALL_KNOWN_TIER_NAMES
    assert THIRD_PARTY_MODEL_TIER not in ALL_MODEL_TIERS
    assert all(
        ALL_CLI_MODEL_ID_BY_TIER[each_tier] for each_tier in ALL_KNOWN_TIER_NAMES
    )


def test_canonical_tier_name_strips_and_normalizes() -> None:
    assert canonical_tier_name(" opus ") == "Opus"
    assert canonical_tier_name("thirdparty") == "ThirdParty"
    assert canonical_tier_name("") is None
    assert canonical_tier_name("Titan") is None


def test_detect_host_profile_defaults_to_claude() -> None:
    assert detect_host_profile(setting_by_name={}) == HOST_PROFILE_CLAUDE


@pytest.mark.parametrize(
    "truthy_value",
    ["1", "true", "TRUE", "yes", "YES", "on", "On"],
)
def test_detect_host_profile_reads_third_party_truthy_values(
    truthy_value: str,
) -> None:
    assert (
        detect_host_profile(setting_by_name={"THIRD_PARTY": truthy_value})
        == HOST_PROFILE_THIRD_PARTY
    )


def test_detect_host_profile_reads_third_party_flag() -> None:
    assert (
        detect_host_profile(setting_by_name={"THIRD_PARTY": "0"})
        == HOST_PROFILE_CLAUDE
    )
    assert (
        detect_host_profile(setting_by_name={"THIRD_PARTY": "false"})
        == HOST_PROFILE_CLAUDE
    )


def test_detect_host_profile_reads_explicit_override() -> None:
    assert (
        detect_host_profile(setting_by_name={"ADVISOR_HOST_PROFILE": "ThirdParty"})
        == HOST_PROFILE_THIRD_PARTY
    )
    assert (
        detect_host_profile(setting_by_name={"ADVISOR_HOST_PROFILE": "claude"})
        == HOST_PROFILE_CLAUDE
    )
    assert (
        detect_host_profile(
            setting_by_name={"ADVISOR_HOST_PROFILE": "Claude", "THIRD_PARTY": "1"}
        )
        == HOST_PROFILE_CLAUDE
    )


def test_detect_host_profile_rejects_unknown_explicit_value() -> None:
    with pytest.raises(ValueError, match="not a known profile"):
        detect_host_profile(setting_by_name={"ADVISOR_HOST_PROFILE": "Titan"})


def test_documented_resolve_one_liner_runs_without_prior_path_pollution() -> None:
    clean_environment = {
        each_key: each_value
        for each_key, each_value in os.environ.items()
        if each_key.upper() != "PYTHONPATH"
    }
    clean_environment["PYTHONPATH"] = ""
    completed_process = subprocess.run(
        [sys.executable, "-c", DOCUMENTED_RESOLVE_ONE_LINER],
        cwd=str(SCRIPTS_ROOT),
        capture_output=True,
        text=True,
        env=clean_environment,
        check=False,
    )
    assert completed_process.returncode == 0, completed_process.stderr
    assert completed_process.stdout.strip() == "opus"
