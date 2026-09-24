"""Reduce vendor usage events to task costs without retaining event content.

::

    claude -p --output-format json ... | python task_usage_report.py run \
        --task-id task-1 --run-id run-1 --repository team/project \
        --outcome pass --source-format claude-json

    cat run-rows.jsonl | python task_usage_report.py summary

Each resumed invocation needs a new run ID under the same task ID.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum

from task_usage_events import (
    ModelRates,
    UsageEvent,
    UsageReportRunFatal,
    _cost_basis,
    _display_money,
    _parse_claude_json,
    _parse_codex_event,
    _parse_otel_event,
    _parse_rate,
    _read_money,
    _require_label,
    _require_list,
    _require_object,
    _require_one_codex_thread,
    _require_one_otel_session,
    _safe_label,
    _sum_costs,
    _sum_known,
)


@dataclass
class TaskRuns:
    run_ids: list[str] = field(default_factory=list)
    costs: list[Decimal | None] = field(default_factory=list)
    outcomes: list[str | None] = field(default_factory=list)


class RunOutcome(str, Enum):
    PASS = "pass"
    FAIL = "fail"


def _rate_provenance(arguments: argparse.Namespace) -> tuple[str | None, str | None]:
    if not arguments.rate:
        if arguments.rate_source or arguments.rate_effective_date:
            raise ValueError("rate source and date need a rate")
        return None, None
    if (
        arguments.source_format != "codex-json"
        or not arguments.rate_source
        or not arguments.rate_effective_date
    ):
        raise ValueError("Codex rates need a source and effective date")
    rate_source = _require_label(arguments.rate_source, "rate source")
    try:
        effective_date = date.fromisoformat(arguments.rate_effective_date)
    except ValueError as error:
        raise ValueError("rate effective date needs YYYY-MM-DD") from error
    return rate_source, effective_date.isoformat()


def _expand_otel_document(
    all_document_fields: dict[str, object],
) -> list[dict[str, object]]:
    if "resourceLogs" not in all_document_fields:
        return [all_document_fields]
    all_records: list[dict[str, object]] = []
    for each_resource in _require_list(
        all_document_fields["resourceLogs"], "resourceLogs"
    ):
        resource = _require_object(each_resource, "resource log")
        for each_scope in _require_list(resource.get("scopeLogs", []), "scopeLogs"):
            scope = _require_object(each_scope, "scope log")
            all_records.extend(
                _require_object(each_record, "log record")
                for each_record in _require_list(
                    scope.get("logRecords", []), "logRecords"
                )
            )
    return all_records


def _parse_documents(stdin_text: str) -> list[dict[str, object]]:
    if not stdin_text.strip():
        raise ValueError("stdin needs vendor output")
    try:
        parsed_document = json.loads(stdin_text)
    except json.JSONDecodeError:
        return [
            _require_object(json.loads(each_line), "event")
            for each_line in stdin_text.splitlines()
            if each_line.strip()
        ]
    if isinstance(parsed_document, list):
        return [
            _require_object(each_document, "event") for each_document in parsed_document
        ]
    return [_require_object(parsed_document, "event")]


def _deduplicate_events(all_events: list[UsageEvent]) -> list[UsageEvent]:
    event_by_id: dict[str, UsageEvent] = {}
    unique_events: list[UsageEvent] = []
    for each_event in all_events:
        if each_event.event_id is None:
            unique_events.append(each_event)
            continue
        previous_event = event_by_id.get(each_event.event_id)
        if previous_event is not None and previous_event != each_event:
            raise UsageReportRunFatal("duplicate event ID has conflicting usage")
        if previous_event is None:
            event_by_id[each_event.event_id] = each_event
            unique_events.append(each_event)
    return unique_events


def _usage_totals(all_events: list[UsageEvent]) -> dict[str, object]:
    return {
        "uncached_input_tokens": _sum_known(
            [each_event.uncached_input_tokens for each_event in all_events]
        ),
        "cache_write_tokens": _sum_known(
            [each_event.cache_write_tokens for each_event in all_events]
        ),
        "cache_read_tokens": _sum_known(
            [each_event.cache_read_tokens for each_event in all_events]
        ),
        "output_tokens": _sum_known(
            [each_event.generated_tokens for each_event in all_events]
        ),
        "reasoning_output_tokens": _sum_known(
            [each_event.reasoning_generated_tokens for each_event in all_events]
        ),
    }


def _collect_claude_events(
    all_documents: list[dict[str, object]],
) -> tuple[list[UsageEvent], Decimal | None]:
    if len(all_documents) != 1:
        raise ValueError("Claude JSON needs one result object")
    return _parse_claude_json(all_documents[0])


def _collect_otel_events(
    all_documents: list[dict[str, object]],
) -> tuple[list[UsageEvent], Decimal | None]:
    all_records = [
        each_record
        for each_document in all_documents
        for each_record in _expand_otel_document(each_document)
    ]
    _require_one_otel_session(all_records)
    all_events = [
        each_event
        for each_record in all_records
        if (each_event := _parse_otel_event(each_record)) is not None
    ]
    if not all_events:
        raise ValueError("OTel input needs an API request")
    unique_events = _deduplicate_events(all_events)
    return unique_events, _sum_costs(
        [each_event.cost_usd for each_event in unique_events]
    )


def _collect_codex_events(
    all_documents: list[dict[str, object]],
    fallback_model: str,
    rates_by_model: dict[str, ModelRates],
) -> tuple[list[UsageEvent], Decimal | None]:
    _require_one_codex_thread(all_documents)
    all_events = [
        each_event
        for each_document in all_documents
        if (
            each_event := _parse_codex_event(
                each_document, fallback_model, rates_by_model
            )
        )
        is not None
    ]
    unique_events = _deduplicate_events(all_events)
    return unique_events, _sum_costs(
        [each_event.cost_usd for each_event in unique_events]
    )


def _collect_run_events(
    arguments: argparse.Namespace,
    all_documents: list[dict[str, object]],
    rates_by_model: dict[str, ModelRates],
) -> tuple[list[UsageEvent], Decimal | None]:
    if arguments.source_format == "claude-json":
        return _collect_claude_events(all_documents)
    if arguments.source_format == "claude-otel":
        return _collect_otel_events(all_documents)
    return _collect_codex_events(
        all_documents, _safe_label(arguments.model), rates_by_model
    )


def _build_run_report(
    arguments: argparse.Namespace, stdin_text: str
) -> dict[str, object]:
    all_documents = _parse_documents(stdin_text)
    rate_source, rate_effective_date = _rate_provenance(arguments)
    rates_by_model = dict(_parse_rate(each_rate) for each_rate in arguments.rate)
    all_events, total_cost = _collect_run_events(
        arguments, all_documents, rates_by_model
    )
    cost_basis = _cost_basis(arguments.source_format, total_cost)
    return {
        "task_id": _require_label(arguments.task_id, "task ID"),
        "run_id": _require_label(arguments.run_id, "run ID"),
        "repository": _require_label(arguments.repository, "repository"),
        "source_format": arguments.source_format,
        "outcome": arguments.outcome,
        "models": sorted({each_event.model for each_event in all_events}),
        "event_count": len(all_events),
        **_usage_totals(all_events),
        "cost_usd": _display_money(total_cost),
        "cost_basis": cost_basis,
        "rate_source": rate_source if cost_basis == "caller_rates" else None,
        "rate_effective_date": (
            rate_effective_date if cost_basis == "caller_rates" else None
        ),
    }


def _read_summary_row(
    all_document_fields: dict[str, object],
) -> tuple[tuple[str, str, str], str | None, Decimal | None]:
    repository = _require_summary_label(all_document_fields.get("repository"))
    task_id = _require_summary_label(all_document_fields.get("task_id"))
    run_id = _require_summary_label(all_document_fields.get("run_id"))
    outcome = all_document_fields.get("outcome")
    if outcome is not None and (
        not isinstance(outcome, str)
        or outcome not in tuple(each_outcome.value for each_outcome in RunOutcome)
    ):
        raise ValueError("summary outcome must be pass, fail, or missing")
    return (
        (repository, task_id, run_id),
        outcome,
        _read_money(all_document_fields, "cost_usd"),
    )


def _require_summary_label(candidate: object) -> str:
    label = _safe_label(candidate)
    if label == "unknown":
        raise ValueError("summary row needs repository, task ID, and run ID")
    return label


def _summarize_run_rows(all_documents: list[dict[str, object]]) -> dict[str, object]:
    run_by_key: dict[tuple[str, str, str], tuple[str | None, Decimal | None]] = {}
    for each_document in all_documents:
        run_key, outcome, cost = _read_summary_row(each_document)
        previous_run = run_by_key.get(run_key)
        if previous_run is not None and previous_run != (outcome, cost):
            raise UsageReportRunFatal(
                "duplicate run ID has conflicting cost or outcome"
            )
        run_by_key[run_key] = (outcome, cost)
    task_by_key: dict[tuple[str, str], TaskRuns] = {}
    for (each_repository, each_task_id, each_run_id), (
        each_outcome,
        each_cost,
    ) in sorted(run_by_key.items()):
        task_runs = task_by_key.setdefault((each_repository, each_task_id), TaskRuns())
        task_runs.run_ids.append(each_run_id)
        task_runs.outcomes.append(each_outcome)
        task_runs.costs.append(each_cost)
    return _build_summary(task_by_key)


def _task_summary_row(
    repository: str, task_id: str, task_runs: TaskRuns
) -> tuple[dict[str, object], Decimal | None, bool | None]:
    is_outcome_known = all(
        each_outcome is not None for each_outcome in task_runs.outcomes
    )
    is_task_passed = RunOutcome.PASS.value in task_runs.outcomes
    task_cost = _sum_costs(task_runs.costs)
    return (
        {
            "repository": repository,
            "task_id": task_id,
            "run_ids": task_runs.run_ids,
            "passed": is_task_passed if is_outcome_known else None,
            "cost_usd": _display_money(task_cost),
        },
        task_cost,
        is_task_passed if is_outcome_known else None,
    )


def _build_summary(task_by_key: dict[tuple[str, str], TaskRuns]) -> dict[str, object]:
    all_tasks: list[dict[str, object]] = []
    all_costs: list[Decimal | None] = []
    passed_task_count = 0
    is_outcome_known = bool(task_by_key)
    for (each_repository, each_task_id), each_task in sorted(task_by_key.items()):
        task_row, task_cost, is_task_passed = _task_summary_row(
            each_repository, each_task_id, each_task
        )
        is_outcome_known = is_outcome_known and is_task_passed is not None
        passed_task_count += int(bool(is_task_passed))
        all_costs.append(task_cost)
        all_tasks.append(task_row)
    total_cost = _sum_costs(all_costs)
    is_complete = is_outcome_known and total_cost is not None and passed_task_count > 0
    cost_per_pass = (
        total_cost / passed_task_count
        if is_complete and total_cost is not None
        else None
    )
    return {
        "status": "known" if is_complete else "unknown",
        "task_count": len(all_tasks),
        "passed_task_count": passed_task_count if is_outcome_known else None,
        "total_cost_usd": _display_money(total_cost),
        "cost_per_passed_task_usd": _display_money(cost_per_pass),
        "tasks": all_tasks,
    }


def _create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run_parser = commands.add_parser("run", help="reduce one vendor run from stdin")
    run_parser.add_argument("--task-id", required=True)
    run_parser.add_argument("--run-id", required=True)
    run_parser.add_argument("--repository", required=True)
    run_parser.add_argument(
        "--outcome",
        choices=tuple(each_outcome.value for each_outcome in RunOutcome),
        required=True,
    )
    run_parser.add_argument(
        "--source-format",
        choices=("claude-json", "claude-otel", "codex-json"),
        required=True,
    )
    run_parser.add_argument("--model", help="Codex model when turn events omit it")
    run_parser.add_argument(
        "--rate", action="append", default=[], metavar="MODEL=INPUT,WRITE,READ,OUTPUT"
    )
    run_parser.add_argument("--rate-source", help="source for caller-supplied prices")
    run_parser.add_argument(
        "--rate-effective-date", help="date for caller-supplied prices"
    )
    commands.add_parser("summary", help="group run reports from stdin")
    return parser


def _main() -> int:
    parser = _create_parser()
    parsed_arguments = parser.parse_args()
    try:
        stdin_text = sys.stdin.read()
        if parsed_arguments.command == "run":
            report = _build_run_report(parsed_arguments, stdin_text)
        else:
            report = _summarize_run_rows(_parse_documents(stdin_text))
    except (ValueError, json.JSONDecodeError) as error:
        sys.stderr.write(f"invalid input: {error}\n")
        return 2
    sys.stdout.write(json.dumps(report, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
