"""Behavior tests for the effort evaluation harness."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
_CONSTANTS_PARENT = _SCRIPTS_DIRECTORY / "config"
for each_path in (_SCRIPTS_DIRECTORY, _CONSTANTS_PARENT):
    path_text = str(each_path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from e_code_review_effort_constants import (  # noqa: E402
    ALL_EFFORT_LEVELS,
    ALL_FIXTURE_BANDS,
    MINIMUM_QUALITY_HOLD_SCORE,
    THINKING_ENABLED_DEFAULT,
)
from effort_evaluation import (  # noqa: E402
    build_synthetic_row,
    fixtures_directory,
    load_fixtures,
    quality_holds,
    recommend_effort_by_band,
    validate_evaluation_row,
)


def test_fixtures_directory_points_at_frozen_json() -> None:
    directory = fixtures_directory()
    assert directory.is_dir()
    assert directory.name == "fixtures"
    assert (directory / "easy.json").is_file()


def test_loads_three_frozen_fixture_bands() -> None:
    all_fixtures = load_fixtures()
    assert len(all_fixtures) == len(ALL_FIXTURE_BANDS)
    bands = {str(each_fixture["band"]) for each_fixture in all_fixtures}
    assert bands == set(ALL_FIXTURE_BANDS)
    for each_fixture in all_fixtures:
        assert each_fixture["fixture_id"]
        assert isinstance(each_fixture["seeded_findings"], list)
        assert len(each_fixture["seeded_findings"]) >= 1


def test_validate_row_accepts_complete_row_and_rejects_thinking_off() -> None:
    good_row = build_synthetic_row(
        fixture_id="easy-comment-preservation",
        fixture_band="easy",
        effort="low",
        quality_score=0.9,
        finding_recall=1.0,
        finding_precision=1.0,
        visible_tokens=1200,
        latency_ms=4000,
    )
    assert validate_evaluation_row(good_row) == []
    assert good_row["thinking_enabled"] is THINKING_ENABLED_DEFAULT
    bad_row = dict(good_row)
    bad_row["thinking_enabled"] = False
    problems = validate_evaluation_row(bad_row)
    assert any("thinking_enabled" in each_problem for each_problem in problems)


def test_recommend_picks_lowest_effort_that_holds_quality() -> None:
    all_rows = [
        build_synthetic_row("easy-a", "easy", "low", 0.5, 0.5, 0.5, 100, 1000),
        build_synthetic_row("easy-a", "easy", "medium", 0.95, 0.95, 0.95, 200, 2000),
        build_synthetic_row("easy-a", "easy", "xhigh", 0.99, 0.99, 0.99, 400, 5000),
        build_synthetic_row("medium-a", "medium", "high", 0.9, 0.9, 0.9, 300, 3000),
        build_synthetic_row(
            "demanding-a", "demanding", "max", 0.85, 0.85, 0.85, 800, 9000
        ),
    ]
    for each_row in all_rows:
        assert validate_evaluation_row(each_row) == []
    recommendation = recommend_effort_by_band(all_rows)
    by_band = recommendation["recommendation_by_band"]
    assert isinstance(by_band, dict)
    assert by_band["easy"]["recommended_effort"] == "medium"
    assert by_band["easy"]["cited_row"]["effort"] == "medium"
    assert by_band["medium"]["recommended_effort"] == "high"
    assert by_band["demanding"]["recommended_effort"] == "max"
    assert recommendation["thinking_enabled"] is True
    assert recommendation["cost_latency_lever"] == "effort"
    assert recommendation["defaults_unchanged"] is True


def test_recommend_blocks_band_without_holding_row() -> None:
    all_rows = [
        build_synthetic_row("easy-a", "easy", "low", 0.1, 0.1, 0.1, 50, 500),
    ]
    recommendation = recommend_effort_by_band(all_rows)
    easy = recommendation["recommendation_by_band"]["easy"]
    assert easy["recommended_effort"] is None
    assert easy["cited_row"] is None
    assert "quality floor" in str(easy["blocker"])


def test_quality_holds_uses_named_floor() -> None:
    holding = build_synthetic_row(
        "x", "easy", "low", MINIMUM_QUALITY_HOLD_SCORE, 1.0, 1.0, 1, 1
    )
    failing = build_synthetic_row(
        "x", "easy", "low", MINIMUM_QUALITY_HOLD_SCORE - 0.01, 1.0, 1.0, 1, 1
    )
    assert quality_holds(holding) is True
    assert quality_holds(failing) is False


def test_effort_levels_cover_cli_set() -> None:
    assert "low" in ALL_EFFORT_LEVELS
    assert "max" in ALL_EFFORT_LEVELS
    assert len(ALL_EFFORT_LEVELS) == 5
