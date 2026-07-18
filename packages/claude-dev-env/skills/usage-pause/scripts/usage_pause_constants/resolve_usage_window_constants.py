"""Constants for the usage-window resolver.

Groups: the OAuth usage-endpoint probe, the CLI credential file keys, the
session ingress token file environment variable, the host entrypoint
detection, the usage-response field keys, the override parse patterns, the
wakeup stage sizing, the weekly warn threshold, the result JSON keys, the
source labels, and the exit codes.
"""

from __future__ import annotations

OAUTH_USAGE_ENDPOINT_URL = "https://api.anthropic.com/api/oauth/usage"
OAUTH_BETA_HEADER_NAME = "anthropic-beta"
OAUTH_BETA_HEADER_VALUE = "oauth-2025-04-20"
AUTHORIZATION_HEADER_NAME = "Authorization"
AUTHORIZATION_BEARER_PREFIX = "Bearer "
CONTENT_TYPE_HEADER_NAME = "Content-Type"
CONTENT_TYPE_JSON = "application/json"
PROBE_TIMEOUT_SECONDS = 10

ALL_CREDENTIALS_RELATIVE_PATH_PARTS = (".claude", ".credentials.json")
CREDENTIALS_OAUTH_SECTION_KEY = "claudeAiOauth"
CREDENTIALS_ACCESS_TOKEN_KEY = "accessToken"
CREDENTIALS_EXPIRES_AT_KEY = "expiresAt"
SESSION_INGRESS_TOKEN_FILE_ENV_VAR = "CLAUDE_SESSION_INGRESS_TOKEN_FILE"
MILLISECONDS_PER_SECOND = 1000

ENTRYPOINT_ENV_VAR = "CLAUDE_CODE_ENTRYPOINT"
DESKTOP_ENTRYPOINT_VALUE = "claude-desktop"

FIVE_HOUR_BUCKET_KEY = "five_hour"
SEVEN_DAY_BUCKET_KEY = "seven_day"
UTILIZATION_KEY = "utilization"
ALL_RESETS_AT_KEYS = ("resets_at", "resetsAt")
EPOCH_MILLISECONDS_THRESHOLD = 100_000_000_000
ISO_UTC_SUFFIX = "Z"
ISO_UTC_OFFSET = "+00:00"

DURATION_PATTERN = r"^(?:(?P<hours>\d+)h)?(?:(?P<minutes>\d+)m)?$"
BARE_MINUTES_PATTERN = r"^\d+$"
CLOCK_PATTERN = r"^(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*(?P<meridiem>am|pm)?$"
MERIDIEM_PM = "pm"
MERIDIEM_AM = "am"
NOON_HOUR = 12
CLOCK_HOUR_MAXIMUM = 23
MINUTES_PER_HOUR = 60

MAXIMUM_STAGE_SECONDS = 3480
TAIL_STAGE_SECONDS = 120
MINIMUM_STAGE_SECONDS = 60

WEEKLY_UTILIZATION_WARN_THRESHOLD = 90.0

RESULT_KEY_SOURCE = "source"
RESULT_KEY_RESET_AT = "reset_at"
RESULT_KEY_SECONDS_UNTIL_RESET = "seconds_until_reset"
RESULT_KEY_STAGES_SECONDS = "stages_seconds"
RESULT_KEY_SESSION_UTILIZATION = "session_utilization"
RESULT_KEY_WEEKLY_UTILIZATION = "weekly_utilization"
RESULT_KEY_WEEKLY_RESETS_AT = "weekly_resets_at"
RESULT_KEY_WEEKLY_NEAR_CAP = "weekly_near_cap"
RESULT_KEY_ERROR = "error"

SOURCE_PROBE = "probe"
SOURCE_OVERRIDE = "override"

EXIT_CODE_RESOLVED = 0
EXIT_CODE_PROBE_UNAVAILABLE = 2

LOGGING_FORMAT = "%(levelname)s %(name)s: %(message)s"