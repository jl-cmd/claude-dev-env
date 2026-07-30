"""Named values for the Opus effort evaluation sweep."""

EVALUATION_SCHEMA_VERSION: str = "1"
THINKING_ENABLED_DEFAULT: bool = True
MINIMUM_QUALITY_HOLD_SCORE: float = 0.8
COST_LATENCY_LEVER: str = "effort"
ALL_EFFORT_LEVELS: tuple[str, ...] = ("low", "medium", "high", "xhigh", "max")
ALL_FIXTURE_BANDS: tuple[str, ...] = ("easy", "medium", "demanding")
ALL_SCORE_ROW_KEYS: tuple[str, ...] = (
    "quality_score",
    "finding_recall",
    "finding_precision",
)
ALL_REQUIRED_ROW_KEYS: tuple[str, ...] = (
    "fixture_id",
    "fixture_band",
    "effort",
    "quality_score",
    "finding_recall",
    "finding_precision",
    "visible_tokens",
    "latency_ms",
    "thinking_enabled",
)
FIXTURES_DIRECTORY_NAME: str = "fixtures"
JSON_SUFFIX: str = ".json"
VISIBLE_TOKENS_ROW_KEY: str = "visible_tokens"
LATENCY_MS_ROW_KEY: str = "latency_ms"
ALL_EFFORT_RANK_BY_NAME: dict[str, int] = {
    each_effort: each_index
    for each_index, each_effort in enumerate(ALL_EFFORT_LEVELS)
}
