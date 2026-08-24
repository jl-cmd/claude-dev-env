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
FIXTURES_DIRECTORY_NAME: str = "fixtures"
JSON_SUFFIX: str = ".json"
VISIBLE_TOKENS_ROW_KEY: str = "visible_tokens"
LATENCY_MS_ROW_KEY: str = "latency_ms"
ALL_REQUIRED_ROW_KEYS: tuple[str, ...] = (
    "fixture_id",
    "fixture_band",
    "effort",
    *ALL_SCORE_ROW_KEYS,
    VISIBLE_TOKENS_ROW_KEY,
    LATENCY_MS_ROW_KEY,
    "thinking_enabled",
)
ALL_EFFORT_RANK_BY_NAME: dict[str, int] = {
    each_effort: each_index
    for each_index, each_effort in enumerate(ALL_EFFORT_LEVELS)
}
ALL_SKILL_EFFORT_LEVELS: tuple[str, ...] = ("low", "medium", "xhigh")
EVALUATION_EVIDENCE_FILENAME: str = "effort_defaults_evidence.json"
WORKFLOW_FAMILY_E_CODE_REVIEW: str = "e-code-review"
ALL_SKILL_EFFORT_FOR_EVALUATION_EFFORT: dict[str, str] = {
    "low": "low",
    "medium": "medium",
    "high": "xhigh",
    "xhigh": "xhigh",
    "max": "xhigh",
}
