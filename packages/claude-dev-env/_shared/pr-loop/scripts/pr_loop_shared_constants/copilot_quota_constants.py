"""Configuration constants for the Copilot premium-request quota pre-check."""

from __future__ import annotations

from pathlib import Path

COPILOT_QUOTA_ACCOUNT_ENV_VAR_NAME: str = "COPILOT_QUOTA_ACCOUNT"
GH_TOKEN_ENV_VAR_NAME: str = "GH_TOKEN"
COPILOT_INTERNAL_USER_API_PATH: str = "copilot_internal/user"

QUOTA_SNAPSHOTS_FIELD_NAME: str = "quota_snapshots"
PREMIUM_INTERACTIONS_FIELD_NAME: str = "premium_interactions"
PREMIUM_UNLIMITED_FIELD_NAME: str = "unlimited"
PREMIUM_REMAINING_FIELD_NAME: str = "remaining"
PREMIUM_OVERAGE_PERMITTED_FIELD_NAME: str = "overage_permitted"
PREMIUM_ENTITLEMENT_FIELD_NAME: str = "entitlement"
PREMIUM_PERCENT_REMAINING_FIELD_NAME: str = "percent_remaining"

EXIT_CODE_QUOTA_AVAILABLE: int = 0
EXIT_CODE_OUT_OF_QUOTA: int = 1
EXIT_CODE_QUOTA_API_DOWN: int = 2
EXIT_CODE_NO_ACCOUNT_CONFIGURED: int = 3

COPILOT_QUOTA_DEFAULT_ENV_FILE_PATH: Path = Path(__file__).resolve().parents[4] / ".env"
