"""Check task usage reporting through its command line interface."""

from __future__ import annotations

import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).with_name("task_usage_report.py")
CODEX_STREAM_FIXTURE = (
    Path(__file__).resolve().parent.parent
    / "_shared"
    / "pr-loop"
    / "scripts"
    / "fixtures"
    / "success_stream_v0.144.3.jsonl"
)
RUN_ARGUMENTS = [
    "run",
    "--task-id",
    "task-7",
    "--run-id",
    "run-1",
    "--repository",
    "team/project",
    "--outcome",
    "pass",
]


def invoke_cli(
    arguments: list[str], stdin_text: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *arguments],
        input=stdin_text,
        capture_output=True,
        text=True,
        check=False,
    )


def report_for(source_format: str, source_payload: object) -> dict[str, object]:
    if source_format == "codex-json":
        stdin_text = "\n".join(
            map(
                json.dumps,
                [{"type": "thread.started", "thread_id": "thread-1"}, source_payload],
            )
        )
    else:
        stdin_text = json.dumps(source_payload)
    completed = invoke_cli(
        [*RUN_ARGUMENTS, "--source-format", source_format], stdin_text
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def test_claude_json_emits_only_allowlisted_fields_and_uses_model_usage_once() -> None:
    source_payload = {
        "type": "result",
        "result": "SECRET_PROMPT_AND_ANSWER",
        "session_id": "SECRET_SESSION",
        "total_cost_usd": 0.125,
        "usage": {
            "input_tokens": 17,
            "cache_creation_input_tokens": 11,
            "cache_read_input_tokens": 31,
            "output_tokens": 7,
        },
        "modelUsage": {
            "claude-opus": {
                "inputTokens": 17,
                "cacheCreationInputTokens": 11,
                "cacheReadInputTokens": 31,
                "outputTokens": 7,
                "costUSD": 0.125,
            }
        },
    }
    report = report_for("claude-json", source_payload)
    serialized_report = json.dumps(report)
    assert "SECRET_PROMPT_AND_ANSWER" not in serialized_report
    assert "SECRET_SESSION" not in serialized_report
    assert report["uncached_input_tokens"] == 17
    assert report["cache_write_tokens"] == 11
    assert report["cache_read_tokens"] == 31
    assert report["output_tokens"] == 7
    assert report["cost_usd"] == "0.125"
    assert report["cost_basis"] == "provider_estimate"
    assert report["models"] == ["claude-opus"]
    assert report["event_count"] == 1


def test_claude_json_keeps_missing_usage_unknown() -> None:
    report = report_for(
        "claude-json", {"type": "result", "total_cost_usd": 0.03, "result": "secret"}
    )
    assert report["uncached_input_tokens"] is None
    assert report["cache_write_tokens"] is None
    assert report["cost_usd"] == "0.03"


def test_claude_otel_deduplicates_request_ids_and_keeps_models_separate() -> None:
    first_event = {
        "body": "claude_code.api_request",
        "attributes": {
            "request_id": "request-1",
            "session.id": "session-1",
            "model": "claude-opus",
            "input_tokens": 2,
            "cache_creation_tokens": 3,
            "cache_read_tokens": 5,
            "output_tokens": 7,
            "cost_usd_micros": 12_500,
            "prompt": "SECRET_PROMPT",
        },
    }
    second_event = {
        "body": "claude_code.api_request",
        "attributes": {
            "request_id": "request-2",
            "session.id": "session-1",
            "model": "claude-sonnet",
            "input_tokens": 11,
            "cache_creation_tokens": 13,
            "cache_read_tokens": 17,
            "output_tokens": 19,
            "cost_usd": 0.0375,
        },
    }
    stdin_text = "\n".join(map(json.dumps, [first_event, first_event, second_event]))
    completed = invoke_cli(
        [*RUN_ARGUMENTS, "--source-format", "claude-otel"], stdin_text
    )
    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["event_count"] == 2
    assert report["uncached_input_tokens"] == 13
    assert report["cache_write_tokens"] == 16
    assert report["cache_read_tokens"] == 22
    assert report["output_tokens"] == 26
    assert Decimal(report["cost_usd"]) == Decimal("0.0500")
    assert report["models"] == ["claude-opus", "claude-sonnet"]
    assert "SECRET_PROMPT" not in completed.stdout


def test_claude_otel_accepts_typed_attributes_and_ignores_other_events() -> None:
    source_payload = {
        "resourceLogs": [
            {
                "scopeLogs": [
                    {
                        "logRecords": [
                            {
                                "body": {"stringValue": "claude_code.user_prompt"},
                                "attributes": [
                                    {
                                        "key": "session.id",
                                        "value": {"stringValue": "session-1"},
                                    },
                                    {
                                        "key": "prompt",
                                        "value": {"stringValue": "SECRET_PROMPT"},
                                    },
                                ],
                            },
                            {
                                "body": {"stringValue": "claude_code.api_request"},
                                "attributes": [
                                    {
                                        "key": "request_id",
                                        "value": {"stringValue": "r1"},
                                    },
                                    {"key": "model", "value": {"stringValue": "opus"}},
                                    {
                                        "key": "session.id",
                                        "value": {"stringValue": "session-1"},
                                    },
                                    {"key": "input_tokens", "value": {"intValue": "4"}},
                                    {
                                        "key": "cache_creation_tokens",
                                        "value": {"intValue": "0"},
                                    },
                                    {
                                        "key": "cache_read_tokens",
                                        "value": {"intValue": "8"},
                                    },
                                    {
                                        "key": "output_tokens",
                                        "value": {"intValue": "2"},
                                    },
                                ],
                            },
                        ]
                    }
                ]
            }
        ]
    }
    report = report_for("claude-otel", source_payload)
    assert report["event_count"] == 1
    assert report["uncached_input_tokens"] == 4
    assert report["cache_read_tokens"] == 8
    assert report["cost_usd"] is None
    assert "SECRET_PROMPT" not in json.dumps(report)
    assert "session-1" not in json.dumps(report)


def test_codex_uses_cached_and_reasoning_counts_as_subsets() -> None:
    source_payload = [
        {"type": "thread.started", "thread_id": "SECRET_THREAD"},
        {
            "type": "turn.completed",
            "turn_id": "turn-1",
            "model": "gpt-x",
            "usage": {
                "input_tokens": 100,
                "cached_input_tokens": 20,
                "cache_write_input_tokens": 5,
                "output_tokens": 30,
                "reasoning_output_tokens": 10,
            },
            "text": "SECRET_ANSWER",
        },
    ]
    stdin_text = "\n".join(map(json.dumps, source_payload))
    completed = invoke_cli(
        [
            *RUN_ARGUMENTS,
            "--source-format",
            "codex-json",
            "--rate",
            "gpt-x=1,2,0.1,4",
            "--rate-source",
            "vendor-price-card",
            "--rate-effective-date",
            "2026-09-24",
        ],
        stdin_text,
    )
    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["uncached_input_tokens"] == 75
    assert report["cache_write_tokens"] == 5
    assert report["cache_read_tokens"] == 20
    assert report["output_tokens"] == 30
    assert report["reasoning_output_tokens"] == 10
    assert report["cost_usd"] == "0.000207"
    assert report["cost_basis"] == "caller_rates"
    assert report["rate_source"] == "vendor-price-card"
    assert report["rate_effective_date"] == "2026-09-24"
    assert "SECRET_THREAD" not in completed.stdout
    assert "SECRET_ANSWER" not in completed.stdout


def test_codex_deduplicates_turn_ids_and_requires_rates_for_cost() -> None:
    turn_event = {
        "type": "turn.completed",
        "turn_id": "turn-1",
        "usage": {
            "input_tokens": 20,
            "cached_input_tokens": 5,
            "cache_write_input_tokens": 0,
            "output_tokens": 3,
        },
    }
    stdin_text = "\n".join(
        map(
            json.dumps,
            [
                {"type": "thread.started", "thread_id": "thread-1"},
                turn_event,
                turn_event,
            ],
        )
    )
    completed = invoke_cli(
        [*RUN_ARGUMENTS, "--source-format", "codex-json"], stdin_text
    )
    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["event_count"] == 1
    assert report["uncached_input_tokens"] == 15
    assert report["cost_usd"] is None
    assert report["cost_basis"] == "unknown"


def test_codex_missing_usage_does_not_become_zero() -> None:
    report = report_for("codex-json", {"type": "turn.completed"})
    assert report["event_count"] == 1
    assert report["uncached_input_tokens"] is None
    assert report["output_tokens"] is None
    assert report["cost_usd"] is None


@pytest.mark.parametrize("bad_count", [-1, 1.5, "oops", None, True])
def test_malformed_numeric_usage_fails_without_echoing_event(bad_count: object) -> None:
    source_payload = {
        "type": "turn.completed",
        "usage": {
            "input_tokens": bad_count,
            "cached_input_tokens": 0,
            "cache_write_input_tokens": 0,
            "output_tokens": 1,
        },
        "text": "SECRET_ANSWER",
    }
    completed = invoke_cli(
        [*RUN_ARGUMENTS, "--source-format", "codex-json"],
        "\n".join(
            map(
                json.dumps,
                [{"type": "thread.started", "thread_id": "thread-1"}, source_payload],
            )
        ),
    )
    assert completed.returncode != 0
    assert completed.stdout == ""
    assert "SECRET_ANSWER" not in completed.stderr


def test_codex_rejects_cached_input_exceeding_total_input() -> None:
    source_payload = {
        "type": "turn.completed",
        "usage": {
            "input_tokens": 10,
            "cached_input_tokens": 11,
            "cache_write_input_tokens": 0,
            "output_tokens": 1,
        },
    }
    completed = invoke_cli(
        [*RUN_ARGUMENTS, "--source-format", "codex-json"],
        "\n".join(
            map(
                json.dumps,
                [{"type": "thread.started", "thread_id": "thread-1"}, source_payload],
            )
        ),
    )
    assert completed.returncode != 0


def test_summary_groups_resumed_runs_and_includes_failed_attempt_cost() -> None:
    first_report = {
        "task_id": "task-7",
        "run_id": "run-1",
        "repository": "team/project",
        "outcome": "fail",
        "cost_usd": "0.20",
    }
    second_report = {
        "task_id": "task-7",
        "run_id": "run-2",
        "repository": "team/project",
        "outcome": "pass",
        "cost_usd": "0.30",
    }
    stdin_text = "\n".join(map(json.dumps, [first_report, second_report]))
    completed = invoke_cli(["summary"], stdin_text)
    assert completed.returncode == 0, completed.stderr
    summary = json.loads(completed.stdout)
    assert summary["task_count"] == 1
    assert summary["passed_task_count"] == 1
    assert Decimal(summary["total_cost_usd"]) == Decimal("0.50")
    assert Decimal(summary["cost_per_passed_task_usd"]) == Decimal("0.50")
    assert summary["tasks"][0]["run_ids"] == ["run-1", "run-2"]


@pytest.mark.parametrize("missing_field", ["cost_usd", "outcome"])
def test_summary_marks_missing_cost_or_outcome_unknown(missing_field: str) -> None:
    source_report = {
        "task_id": "task-7",
        "run_id": "run-1",
        "repository": "team/project",
        "outcome": "pass",
        "cost_usd": "0.20",
    }
    del source_report[missing_field]
    completed = invoke_cli(["summary"], json.dumps(source_report))
    assert completed.returncode == 0, completed.stderr
    summary = json.loads(completed.stdout)
    assert summary["cost_per_passed_task_usd"] is None
    assert summary["status"] == "unknown"


def test_summary_deduplicates_identical_run_rows() -> None:
    source_report = {
        "task_id": "task-7",
        "run_id": "run-1",
        "repository": "team/project",
        "outcome": "pass",
        "cost_usd": "0.20",
    }
    completed = invoke_cli(
        ["summary"], "\n".join(map(json.dumps, [source_report, source_report]))
    )
    assert completed.returncode == 0, completed.stderr
    summary = json.loads(completed.stdout)
    assert Decimal(summary["total_cost_usd"]) == Decimal("0.20")
    assert summary["tasks"][0]["run_ids"] == ["run-1"]


def test_claude_otel_accepts_flat_event_attributes() -> None:
    source_payload = {
        "event.name": "api_request",
        "session.id": "session-1",
        "model": "claude-sonnet",
        "input_tokens": 4,
        "cache_creation_tokens": 2,
        "cache_read_tokens": 3,
        "output_tokens": 1,
        "cost_usd": 0.002,
    }
    report = report_for("claude-otel", source_payload)
    assert report["uncached_input_tokens"] == 4
    assert report["cache_write_tokens"] == 2
    assert report["cost_usd"] == "0.002"


def test_codex_mixed_models_need_each_models_rate() -> None:
    all_events = [
        {
            "type": "turn.completed",
            "turn_id": f"turn-{each_index}",
            "model": each_model,
            "usage": {
                "input_tokens": 1_000_000,
                "cached_input_tokens": 0,
                "cache_write_input_tokens": 0,
                "output_tokens": 0,
            },
        }
        for each_index, each_model in enumerate(("gpt-small", "gpt-large"))
    ]
    stdin_text = "\n".join(
        map(
            json.dumps,
            [{"type": "thread.started", "thread_id": "thread-1"}, *all_events],
        )
    )
    base_arguments = [*RUN_ARGUMENTS, "--source-format", "codex-json"]
    rate_provenance = [
        "--rate-source",
        "vendor-price-card",
        "--rate-effective-date",
        "2026-09-24",
    ]
    partial = invoke_cli(
        [*base_arguments, "--rate", "gpt-small=1,0,0,0", *rate_provenance],
        stdin_text,
    )
    complete = invoke_cli(
        [
            *base_arguments,
            "--rate",
            "gpt-small=1,0,0,0",
            "--rate",
            "gpt-large=3,0,0,0",
            *rate_provenance,
        ],
        stdin_text,
    )
    assert partial.returncode == 0, partial.stderr
    assert complete.returncode == 0, complete.stderr
    assert json.loads(partial.stdout)["cost_usd"] is None
    complete_report = json.loads(complete.stdout)
    assert complete_report["cost_usd"] == "4"
    assert complete_report["models"] == ["gpt-large", "gpt-small"]


def test_otel_rejects_mixed_sessions_without_leaking_identifiers() -> None:
    all_events = [
        {
            "body": "claude_code.api_request",
            "attributes": {
                "session.id": each_session,
                "request_id": f"request-{each_index}",
                "model": "claude-opus",
                "input_tokens": 1,
                "cache_creation_tokens": 0,
                "cache_read_tokens": 0,
                "output_tokens": 1,
                "cost_usd": 0.01,
            },
        }
        for each_index, each_session in enumerate(
            ("SECRET_SESSION_A", "SECRET_SESSION_B")
        )
    ]
    completed = invoke_cli(
        [*RUN_ARGUMENTS, "--source-format", "claude-otel"],
        "\n".join(map(json.dumps, all_events)),
    )
    assert completed.returncode != 0
    assert completed.stdout == ""
    assert "SECRET_SESSION" not in completed.stderr


def test_otel_rejects_non_api_record_from_another_session() -> None:
    all_records = [
        {
            "body": "claude_code.api_request",
            "attributes": {"session.id": "SECRET_SESSION_A"},
        },
        {
            "body": "claude_code.user_prompt",
            "attributes": {
                "session.id": "SECRET_SESSION_B",
                "prompt": "SECRET_PROMPT",
            },
        },
    ]
    completed = invoke_cli(
        [*RUN_ARGUMENTS, "--source-format", "claude-otel"], json.dumps(all_records)
    )
    assert completed.returncode != 0
    assert completed.stdout == ""
    assert "one session ID" in completed.stderr
    assert "SECRET_SESSION" not in completed.stderr
    assert "SECRET_PROMPT" not in completed.stderr


def test_otel_rejects_capture_without_api_request() -> None:
    source_payload = {
        "body": "claude_code.user_prompt",
        "attributes": {"session.id": "session-1"},
    }
    completed = invoke_cli(
        [*RUN_ARGUMENTS, "--source-format", "claude-otel"], json.dumps(source_payload)
    )
    assert completed.returncode != 0
    assert completed.stdout == ""


def test_codex_rejects_concatenated_threads() -> None:
    all_events = [
        {"type": "thread.started", "thread_id": "thread-1"},
        {"type": "turn.completed", "usage": {"input_tokens": 1}},
        {"type": "thread.started", "thread_id": "thread-2"},
        {"type": "turn.completed", "usage": {"input_tokens": 1}},
    ]
    completed = invoke_cli(
        [*RUN_ARGUMENTS, "--source-format", "codex-json"],
        "\n".join(map(json.dumps, all_events)),
    )
    assert completed.returncode != 0
    assert completed.stdout == ""


def test_codex_rate_requires_source_and_effective_date() -> None:
    all_events = [
        {"type": "thread.started", "thread_id": "thread-1"},
        {
            "type": "turn.completed",
            "model": "gpt-x",
            "usage": {
                "input_tokens": 1,
                "cached_input_tokens": 0,
                "cache_write_input_tokens": 0,
                "output_tokens": 1,
            },
        },
    ]
    completed = invoke_cli(
        [*RUN_ARGUMENTS, "--source-format", "codex-json", "--rate", "gpt-x=1,0,0,1"],
        "\n".join(map(json.dumps, all_events)),
    )
    assert completed.returncode != 0
    assert completed.stdout == ""


def test_codex_fixture_without_cache_write_field_uses_zero_write_cost() -> None:
    completed = invoke_cli(
        [
            *RUN_ARGUMENTS,
            "--source-format",
            "codex-json",
            "--model",
            "gpt-x",
            "--rate",
            "gpt-x=1,2,0.1,4",
            "--rate-source",
            "vendor-price-card",
            "--rate-effective-date",
            "2026-09-24",
        ],
        CODEX_STREAM_FIXTURE.read_text(encoding="utf-8"),
    )
    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["uncached_input_tokens"] == 12
    assert report["cache_write_tokens"] == 0
    assert report["cache_read_tokens"] == 0
    assert report["output_tokens"] == 6
    assert report["cost_usd"] == "0.000036"
    assert report["cost_basis"] == "caller_rates"
