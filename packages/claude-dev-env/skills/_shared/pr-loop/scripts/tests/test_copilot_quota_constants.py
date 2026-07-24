"""Tests for copilot_quota_constants.py extracted constant set."""

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_constants_module() -> ModuleType:
    module_path = (
        Path(__file__).parent.parent
        / "pr_loop_shared_constants"
        / "copilot_quota_constants.py"
    )
    specification = importlib.util.spec_from_file_location(
        "pr_loop_shared_constants.copilot_quota_constants", module_path
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


constants_module = _load_constants_module()


def test_copilot_quota_account_env_var_name() -> None:
    assert (
        constants_module.COPILOT_QUOTA_ACCOUNT_ENV_VAR_NAME == "COPILOT_QUOTA_ACCOUNT"
    )


def test_gh_token_env_var_name() -> None:
    assert constants_module.GH_TOKEN_ENV_VAR_NAME == "GH_TOKEN"


def test_copilot_internal_user_api_path() -> None:
    assert constants_module.COPILOT_INTERNAL_USER_API_PATH == "copilot_internal/user"


def test_premium_interactions_gating_field_names() -> None:
    assert constants_module.QUOTA_SNAPSHOTS_FIELD_NAME == "quota_snapshots"
    assert constants_module.PREMIUM_INTERACTIONS_FIELD_NAME == "premium_interactions"
    assert constants_module.PREMIUM_UNLIMITED_FIELD_NAME == "unlimited"
    assert constants_module.PREMIUM_REMAINING_FIELD_NAME == "remaining"
    assert constants_module.PREMIUM_OVERAGE_PERMITTED_FIELD_NAME == "overage_permitted"


def test_exit_codes_are_the_four_distinct_scenarios() -> None:
    all_exit_codes = (
        constants_module.EXIT_CODE_QUOTA_AVAILABLE,
        constants_module.EXIT_CODE_OUT_OF_QUOTA,
        constants_module.EXIT_CODE_QUOTA_API_DOWN,
        constants_module.EXIT_CODE_NO_ACCOUNT_CONFIGURED,
    )
    assert all_exit_codes == (0, 1, 2, 3)
    assert len(set(all_exit_codes)) == len(all_exit_codes)


def test_default_env_file_path_sits_at_the_package_root() -> None:
    default_env_file_path = constants_module.COPILOT_QUOTA_DEFAULT_ENV_FILE_PATH
    assert default_env_file_path.name == ".env"
    assert default_env_file_path.parent.name == "claude-dev-env"
