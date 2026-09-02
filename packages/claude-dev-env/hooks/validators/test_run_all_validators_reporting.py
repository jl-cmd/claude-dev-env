"""Tests for the run report run_all_validators renders after a full run.

Timing metrics and the version header are the two pieces of that report. They
moved out of test_run_all_validators.py so the paired file keeps room for the
gate behavior it exists to pin.
"""

import pytest

from .run_all_validators import (
    add_timing,
    build_json_output,
    create_timing_metrics,
    format_timing_report,
    print_header,
)


class TestTimingMetrics:
    def test_create_timing_metrics_empty(self) -> None:
        metrics = create_timing_metrics({})
        assert metrics.total_seconds == 0.0
        assert metrics.validator_times == {}

    def test_create_timing_metrics_with_data(self) -> None:
        timings = {"Validator A": 1.5, "Validator B": 2.0}
        metrics = create_timing_metrics(timings)
        assert metrics.total_seconds == 3.5
        assert metrics.validator_times == timings

    def test_add_timing_returns_new_instance(self) -> None:
        metrics1 = create_timing_metrics({})
        metrics2 = add_timing(metrics1, "Test", 1.5)

        assert metrics1.total_seconds == 0.0
        assert metrics2.total_seconds == 1.5
        assert "Test" not in metrics1.validator_times
        assert metrics2.validator_times["Test"] == 1.5

    def test_format_report_includes_all_timings(self) -> None:
        metrics = create_timing_metrics({"Fast": 0.1, "Slow": 2.5})
        report = format_timing_report(metrics)

        assert "Fast" in report
        assert "Slow" in report
        assert "2.6" in report


class TestVersionHeader:
    def test_print_header_includes_version(self, capsys: pytest.CaptureFixture[str]) -> None:
        print_header()
        captured = capsys.readouterr()

        assert "PRE-PUSH VALIDATOR RESULTS" in captured.out
        assert "(v" in captured.out

    def test_build_json_output_includes_version(self) -> None:
        json_output = build_json_output(
            results=[],
            metrics=create_timing_metrics({}),
            include_timing=False,
        )

        assert "version" in json_output
        assert "timestamp" in json_output
        assert isinstance(json_output["version"], str)
