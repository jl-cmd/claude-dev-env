"""Tests for cluster_recurrences — signature grouping and timing regressions."""

import io
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

_script_directory = str(Path(__file__).resolve().parent)
if _script_directory not in sys.path:
    sys.path.insert(0, _script_directory)

from cluster_recurrences import (  # noqa: E402
    TimingSample,
    detect_timing_regressions,
    main,
    normalize_signature,
    recency_weight,
    rank_signature_clusters,
)
from collect_log_window import LogRecord  # noqa: E402


def _record(timestamp: datetime, message: str) -> LogRecord:
    return LogRecord(
        timestamp=timestamp, source="a_hook", level="block", message=message
    )


class TestNormalizeSignature:
    def test_two_messages_differing_only_in_numbers_share_a_signature(self) -> None:
        first = normalize_signature("blocked at line 12 with 3 issues")
        second = normalize_signature("blocked at line 348 with 9 issues")
        assert first == second

    def test_messages_differing_only_in_a_path_share_a_signature(self) -> None:
        first = normalize_signature(r"cannot read C:\a\b\one.py right now")
        second = normalize_signature(r"cannot read C:\x\y\two.py right now")
        assert first == second

    def test_messages_differing_only_in_a_hash_share_a_signature(self) -> None:
        first = normalize_signature("commit a1b2c3d failed to apply")
        second = normalize_signature("commit deadbeef failed to apply")
        assert first == second

    def test_distinct_messages_keep_distinct_signatures(self) -> None:
        assert normalize_signature("heavy word detected") != normalize_signature(
            "missing type hint"
        )


class TestRecencyWeight:
    def test_a_fresh_record_weighs_about_one(self) -> None:
        now = datetime(2026, 7, 3, 12, 0, 0)
        weight = recency_weight(now, now)
        assert abs(weight - 1.0) < 0.001

    def test_a_record_one_half_life_old_weighs_about_the_decay_base(self) -> None:
        now = datetime(2026, 7, 3, 12, 0, 0)
        one_half_life_ago = now - timedelta(hours=24)
        weight = recency_weight(one_half_life_ago, now)
        assert abs(weight - 0.5) < 0.001

    def test_a_future_record_is_clamped_to_at_most_one(self) -> None:
        now = datetime(2026, 7, 3, 12, 0, 0)
        one_hour_ahead = now + timedelta(hours=1)
        weight = recency_weight(one_hour_ahead, now)
        assert abs(weight - 1.0) < 0.001


class TestRankSignatureClusters:
    def test_the_most_frequent_recent_signature_ranks_first(self) -> None:
        now = datetime(2026, 7, 3, 12, 0, 0)
        records = [
            _record(now - timedelta(hours=1), "blocked at line 1"),
            _record(now - timedelta(hours=2), "blocked at line 2"),
            _record(now - timedelta(hours=1), "blocked at line 3"),
            _record(now - timedelta(hours=200), "a rare stale failure"),
        ]
        clusters = rank_signature_clusters(records, now)
        assert clusters[0].count == 3
        assert clusters[0].signature == normalize_signature("blocked at line 1")

    def test_each_distinct_signature_becomes_one_cluster(self) -> None:
        now = datetime(2026, 7, 3, 12, 0, 0)
        records = [
            _record(now, "heavy word here"),
            _record(now, "missing type hint"),
        ]
        clusters = rank_signature_clusters(records, now)
        assert len(clusters) == 2


class TestDetectTimingRegressions:
    def test_flags_an_operation_whose_recent_runs_are_slower(self) -> None:
        base = datetime(2026, 7, 3, 0, 0, 0)
        samples = [
            TimingSample("extract", base + timedelta(minutes=1), 100.0),
            TimingSample("extract", base + timedelta(minutes=2), 110.0),
            TimingSample("extract", base + timedelta(minutes=3), 105.0),
            TimingSample("extract", base + timedelta(minutes=40), 300.0),
            TimingSample("extract", base + timedelta(minutes=41), 320.0),
            TimingSample("extract", base + timedelta(minutes=42), 310.0),
        ]
        regressions = detect_timing_regressions(samples)
        assert len(regressions) == 1
        assert regressions[0].operation == "extract"
        assert regressions[0].ratio > 1.5

    def test_ignores_a_steady_operation(self) -> None:
        base = datetime(2026, 7, 3, 0, 0, 0)
        samples = [
            TimingSample("steady", base + timedelta(minutes=each_minute_offset), 100.0)
            for each_minute_offset in range(6)
        ]
        assert detect_timing_regressions(samples) == []

    def test_ignores_an_operation_with_too_few_samples(self) -> None:
        base = datetime(2026, 7, 3, 0, 0, 0)
        samples = [
            TimingSample("sparse", base + timedelta(minutes=1), 100.0),
            TimingSample("sparse", base + timedelta(minutes=2), 900.0),
        ]
        assert detect_timing_regressions(samples) == []


class TestMain:
    def test_rejects_non_json_stdin(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(sys, "stdin", io.StringIO("not json"))
        exit_code = main()
        captured = capsys.readouterr()
        assert exit_code == 1
        assert "not valid JSON" in captured.err

    def test_rejects_a_non_list_payload(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(sys, "stdin", io.StringIO('{"not": "a list"}'))
        exit_code = main()
        captured = capsys.readouterr()
        assert exit_code == 1
        assert "must be a list" in captured.err

    def test_rejects_a_malformed_record(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(sys, "stdin", io.StringIO('[{"missing": "fields"}]'))
        exit_code = main()
        captured = capsys.readouterr()
        assert exit_code == 1
        assert "malformed record" in captured.err
