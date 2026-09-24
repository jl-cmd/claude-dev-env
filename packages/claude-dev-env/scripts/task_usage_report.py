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
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import TextIO


@dataclass(frozen=True)
class ModelRates:
    input_per_million: Decimal
    write_per_million: Decimal
    read_per_million: Decimal
    output_per_million: Decimal


@dataclass(frozen=True)
class UsageEvent:
    model: str
    uncached_input_tokens: int | None
    cache_write_tokens: int | None
    cache_read_tokens: int | None
    output_tokens: int | None
    reasoning_output_tokens: int | None = None
    cost_usd: Decimal | None = None
    event_id: str | None = None


@dataclass
class TaskRuns:
    run_ids: list[str] = field(default_factory=list)
    costs: list[Decimal | None] = field(default_factory=list)
    outcomes: list[str | None] = field(default_factory=list)


def require_object(candidate: object, field_name: str) -> dict[str, object]:
    if not isinstance(candidate, dict):
        raise ValueError(f"{field_name} must be an object")
    return {
        each_key: each_entry
        for each_key, each_entry in candidate.items()
        if isinstance(each_key, str)
    }


def require_list(candidate: object, field_name: str) -> list[object]:
    if not isinstance(candidate, list):
        raise ValueError(f"{field_name} must be a list")
    return candidate


def usage_object(candidate: object) -> dict[str, object]:
    if candidate is None:
        return {}
    return require_object(candidate, "usage")


def read_count(fields: dict[str, object], field_name: str) -> int | None:
    if field_name not in fields:
        return None
    candidate = fields[field_name]
    if isinstance(candidate, bool):
        raise ValueError(f"{field_name} must be a nonnegative integer")
    if isinstance(candidate, int) and candidate >= 0:
        return candidate
    if isinstance(candidate, str) and candidate.isascii() and candidate.isdecimal():
        return int(candidate)
    raise ValueError(f"{field_name} must be a nonnegative integer")


def read_money(fields: Mapping[str, object], field_name: str) -> Decimal | None:
    if field_name not in fields or fields[field_name] is None:
        return None
    candidate = fields[field_name]
    if isinstance(candidate, bool) or not isinstance(candidate, (int, float, str)):
        raise ValueError(f"{field_name} must be a nonnegative amount")
    try:
        amount = Decimal(str(candidate))
    except InvalidOperation as error:
        raise ValueError(f"{field_name} must be a nonnegative amount") from error
    if not amount.is_finite() or amount < 0:
        raise ValueError(f"{field_name} must be a nonnegative amount")
    return amount


def safe_label(candidate: object) -> str:
    if not isinstance(candidate, str) or not candidate:
        return "unknown"
    if not candidate.isascii() or not all(
        each_character.isalnum() or each_character in "._-/"
        for each_character in candidate
    ):
        return "unknown"
    return candidate


def require_label(candidate: str, field_name: str) -> str:
    label = safe_label(candidate)
    if label == "unknown":
        raise ValueError(f"{field_name} needs a nonempty identifier")
    return label


def sum_known(all_counts: list[int | None]) -> int | None:
    if not all_counts or any(each_count is None for each_count in all_counts):
        return None
    return sum(each_count for each_count in all_counts if each_count is not None)


def sum_costs(all_costs: list[Decimal | None]) -> Decimal | None:
    if not all_costs or any(each_cost is None for each_cost in all_costs):
        return None
    return sum(
        (each_cost for each_cost in all_costs if each_cost is not None), Decimal(0)
    )


def display_money(amount: Decimal | None) -> str | None:
    if amount is None:
        return None
    return format(amount.normalize(), "f")


def parse_rate(specification: str) -> tuple[str, ModelRates]:
    model_text, separator, rate_text = specification.partition("=")
    if not separator or safe_label(model_text) == "unknown":
        raise ValueError("rate needs MODEL=INPUT,WRITE,READ,OUTPUT")
    all_rate_texts = rate_text.split(",")
    if len(all_rate_texts) != 4:
        raise ValueError("rate needs four prices per million tokens")
    rate_fields = {str(i): each_rate for i, each_rate in enumerate(all_rate_texts)}
    all_rates = [read_money(rate_fields, str(i)) for i in range(4)]
    if any(each_rate is None for each_rate in all_rates):
        raise ValueError("rate needs four prices per million tokens")
    return model_text, ModelRates(
        *[each_rate for each_rate in all_rates if each_rate is not None]
    )


def calculate_codex_cost(
    usage_event: UsageEvent, rates: ModelRates | None
) -> Decimal | None:
    if rates is None:
        return None
    all_counts = (
        usage_event.uncached_input_tokens,
        usage_event.cache_write_tokens,
        usage_event.cache_read_tokens,
        usage_event.output_tokens,
    )
    if any(each_count is None for each_count in all_counts):
        return None
    all_prices = (
        rates.input_per_million,
        rates.write_per_million,
        rates.read_per_million,
        rates.output_per_million,
    )
    return sum(
        Decimal(each_count) * each_price
        for each_count, each_price in zip(all_counts, all_prices)
        if each_count is not None
    ) / Decimal(1_000_000)


def parse_claude_usage(
    fields: dict[str, object], model: str, is_model_usage: bool
) -> UsageEvent:
    if is_model_usage:
        return UsageEvent(
            model=model,
            uncached_input_tokens=read_count(fields, "inputTokens"),
            cache_write_tokens=read_count(fields, "cacheCreationInputTokens"),
            cache_read_tokens=read_count(fields, "cacheReadInputTokens"),
            output_tokens=read_count(fields, "outputTokens"),
            cost_usd=read_money(fields, "costUSD"),
        )
    return UsageEvent(
        model=model,
        uncached_input_tokens=read_count(fields, "input_tokens"),
        cache_write_tokens=read_count(fields, "cache_creation_input_tokens"),
        cache_read_tokens=read_count(fields, "cache_read_input_tokens"),
        output_tokens=read_count(fields, "output_tokens"),
    )


def parse_claude_json(
    document: dict[str, object],
) -> tuple[list[UsageEvent], Decimal | None]:
    if document.get("type") != "result":
        raise ValueError("Claude JSON needs one result object")
    model_usage = document.get("modelUsage")
    if isinstance(model_usage, dict) and model_usage:
        all_events = [
            parse_claude_usage(
                require_object(each_usage, "model usage"), safe_label(each_model), True
            )
            for each_model, each_usage in model_usage.items()
        ]
    else:
        usage_fields = usage_object(document.get("usage"))
        all_events = [
            parse_claude_usage(usage_fields, safe_label(document.get("model")), False)
        ]
    total_cost = read_money(document, "total_cost_usd")
    return all_events, (
        total_cost
        if total_cost is not None
        else sum_costs([each_event.cost_usd for each_event in all_events])
    )


def parse_codex_usage(
    fields: dict[str, object], model: str, event_id: str | None
) -> UsageEvent:
    input_tokens = read_count(fields, "input_tokens")
    cache_read_tokens = read_count(fields, "cached_input_tokens")
    cache_write_tokens = (
        read_count(fields, "cache_write_input_tokens")
        if "cache_write_input_tokens" in fields
        else 0 if fields else None
    )
    output_tokens = read_count(fields, "output_tokens")
    reasoning_tokens = read_count(fields, "reasoning_output_tokens")
    if (
        output_tokens is not None
        and reasoning_tokens is not None
        and reasoning_tokens > output_tokens
    ):
        raise ValueError("reasoning output exceeds output tokens")
    uncached_tokens = None
    if (
        input_tokens is not None
        and cache_read_tokens is not None
        and cache_write_tokens is not None
    ):
        uncached_tokens = input_tokens - cache_read_tokens - cache_write_tokens
        if uncached_tokens < 0:
            raise ValueError("cached input exceeds input tokens")
    return UsageEvent(
        model,
        uncached_tokens,
        cache_write_tokens,
        cache_read_tokens,
        output_tokens,
        reasoning_tokens,
        event_id=event_id,
    )


def parse_codex_event(
    document: dict[str, object],
    fallback_model: str,
    rates_by_model: dict[str, ModelRates],
) -> UsageEvent | None:
    if document.get("type") != "turn.completed":
        return None
    model = safe_label(document.get("model"))
    if model == "unknown":
        model = fallback_model
    usage_fields = usage_object(document.get("usage"))
    event_id = safe_label(document.get("turn_id"))
    usage_event = parse_codex_usage(
        usage_fields, model, None if event_id == "unknown" else event_id
    )
    return UsageEvent(
        model=usage_event.model,
        uncached_input_tokens=usage_event.uncached_input_tokens,
        cache_write_tokens=usage_event.cache_write_tokens,
        cache_read_tokens=usage_event.cache_read_tokens,
        output_tokens=usage_event.output_tokens,
        reasoning_output_tokens=usage_event.reasoning_output_tokens,
        cost_usd=calculate_codex_cost(usage_event, rates_by_model.get(model)),
        event_id=usage_event.event_id,
    )


def unwrap_otel_value(candidate: object) -> object:
    if not isinstance(candidate, dict):
        return candidate
    for each_key in ("stringValue", "intValue", "doubleValue"):
        if each_key in candidate:
            return candidate[each_key]
    return candidate


def otel_attributes(document: dict[str, object]) -> dict[str, object]:
    raw_attributes = document.get("attributes", {})
    if isinstance(raw_attributes, dict):
        return {
            each_key: unwrap_otel_value(each_entry)
            for each_key, each_entry in raw_attributes.items()
        }
    all_attributes = require_list(raw_attributes, "attributes")
    attributes: dict[str, object] = {}
    for each_attribute in all_attributes:
        attribute = require_object(each_attribute, "attribute")
        attribute_key = attribute.get("key")
        if isinstance(attribute_key, str):
            attributes[attribute_key] = unwrap_otel_value(attribute.get("value"))
    return attributes


def parse_otel_event(document: dict[str, object]) -> UsageEvent | None:
    attributes = otel_attributes(document) if "attributes" in document else document
    event_name = unwrap_otel_value(document.get("body", document.get("event.name")))
    if (
        event_name not in ("claude_code.api_request", "api_request")
        and attributes.get("event.name") != "api_request"
    ):
        return None
    cost = read_money(attributes, "cost_usd")
    if cost is None:
        cost_micros = read_count(attributes, "cost_usd_micros")
        cost = (
            None if cost_micros is None else Decimal(cost_micros) / Decimal(1_000_000)
        )
    event_id = safe_label(attributes.get("request_id"))
    return UsageEvent(
        model=safe_label(attributes.get("model")),
        uncached_input_tokens=read_count(attributes, "input_tokens"),
        cache_write_tokens=read_count(attributes, "cache_creation_tokens"),
        cache_read_tokens=read_count(attributes, "cache_read_tokens"),
        output_tokens=read_count(attributes, "output_tokens"),
        cost_usd=cost,
        event_id=None if event_id == "unknown" else event_id,
    )


def require_one_otel_session(all_records: list[dict[str, object]]) -> None:
    all_session_ids: set[str] = set()
    for each_record in all_records:
        attributes = (
            otel_attributes(each_record) if "attributes" in each_record else each_record
        )
        all_session_ids.add(safe_label(attributes.get("session.id")))
    if len(all_session_ids) != 1 or "unknown" in all_session_ids:
        raise ValueError("OTel input needs one session ID across all log records")


def require_one_codex_thread(all_documents: list[dict[str, object]]) -> None:
    all_thread_starts = [
        safe_label(each_document.get("thread_id"))
        for each_document in all_documents
        if each_document.get("type") == "thread.started"
    ]
    if len(all_thread_starts) != 1 or all_thread_starts[0] == "unknown":
        raise ValueError("Codex input needs one thread.started event")


def rate_provenance(arguments: argparse.Namespace) -> tuple[str | None, str | None]:
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
    rate_source = require_label(arguments.rate_source, "rate source")
    try:
        effective_date = date.fromisoformat(arguments.rate_effective_date)
    except ValueError as error:
        raise ValueError("rate effective date needs YYYY-MM-DD") from error
    return rate_source, effective_date.isoformat()


def expand_otel_document(document: dict[str, object]) -> list[dict[str, object]]:
    if "resourceLogs" not in document:
        return [document]
    all_records: list[dict[str, object]] = []
    for each_resource in require_list(document["resourceLogs"], "resourceLogs"):
        resource = require_object(each_resource, "resource log")
        for each_scope in require_list(resource.get("scopeLogs", []), "scopeLogs"):
            scope = require_object(each_scope, "scope log")
            all_records.extend(
                require_object(each_record, "log record")
                for each_record in require_list(
                    scope.get("logRecords", []), "logRecords"
                )
            )
    return all_records


def parse_documents(stdin_text: str) -> list[dict[str, object]]:
    if not stdin_text.strip():
        raise ValueError("stdin needs vendor output")
    try:
        parsed_document = json.loads(stdin_text)
    except json.JSONDecodeError:
        return [
            require_object(json.loads(each_line), "event")
            for each_line in stdin_text.splitlines()
            if each_line.strip()
        ]
    if isinstance(parsed_document, list):
        return [
            require_object(each_document, "event") for each_document in parsed_document
        ]
    return [require_object(parsed_document, "event")]


def deduplicate_events(all_events: list[UsageEvent]) -> list[UsageEvent]:
    event_by_id: dict[str, UsageEvent] = {}
    unique_events: list[UsageEvent] = []
    for each_event in all_events:
        if each_event.event_id is None:
            unique_events.append(each_event)
            continue
        previous_event = event_by_id.get(each_event.event_id)
        if previous_event is not None and previous_event != each_event:
            raise ValueError("duplicate event ID has conflicting usage")
        if previous_event is None:
            event_by_id[each_event.event_id] = each_event
            unique_events.append(each_event)
    return unique_events


def usage_totals(all_events: list[UsageEvent]) -> dict[str, object]:
    return {
        "uncached_input_tokens": sum_known(
            [each_event.uncached_input_tokens for each_event in all_events]
        ),
        "cache_write_tokens": sum_known(
            [each_event.cache_write_tokens for each_event in all_events]
        ),
        "cache_read_tokens": sum_known(
            [each_event.cache_read_tokens for each_event in all_events]
        ),
        "output_tokens": sum_known(
            [each_event.output_tokens for each_event in all_events]
        ),
        "reasoning_output_tokens": sum_known(
            [each_event.reasoning_output_tokens for each_event in all_events]
        ),
    }


def build_run_report(
    arguments: argparse.Namespace, stdin_text: str
) -> dict[str, object]:
    all_documents = parse_documents(stdin_text)
    rate_source, rate_effective_date = rate_provenance(arguments)
    rates_by_model = dict(parse_rate(each_rate) for each_rate in arguments.rate)
    if arguments.source_format == "claude-json":
        if len(all_documents) != 1:
            raise ValueError("Claude JSON needs one result object")
        all_events, total_cost = parse_claude_json(all_documents[0])
    elif arguments.source_format == "claude-otel":
        all_records = [
            each_record
            for each_document in all_documents
            for each_record in expand_otel_document(each_document)
        ]
        require_one_otel_session(all_records)
        all_events = [
            each_event
            for each_record in all_records
            if (each_event := parse_otel_event(each_record)) is not None
        ]
        if not all_events:
            raise ValueError("OTel input needs an API request")
        all_events = deduplicate_events(all_events)
        total_cost = sum_costs([each_event.cost_usd for each_event in all_events])
    else:
        require_one_codex_thread(all_documents)
        all_events = [
            each_event
            for each_document in all_documents
            if (
                each_event := parse_codex_event(
                    each_document, safe_label(arguments.model), rates_by_model
                )
            )
            is not None
        ]
        all_events = deduplicate_events(all_events)
        total_cost = sum_costs([each_event.cost_usd for each_event in all_events])
    cost_basis = "unknown"
    if total_cost is not None:
        cost_basis = (
            "caller_rates"
            if arguments.source_format == "codex-json"
            else "provider_estimate"
        )
    return {
        "task_id": require_label(arguments.task_id, "task ID"),
        "run_id": require_label(arguments.run_id, "run ID"),
        "repository": require_label(arguments.repository, "repository"),
        "source_format": arguments.source_format,
        "outcome": arguments.outcome,
        "models": sorted({each_event.model for each_event in all_events}),
        "event_count": len(all_events),
        **usage_totals(all_events),
        "cost_usd": display_money(total_cost),
        "cost_basis": cost_basis,
        "rate_source": rate_source if cost_basis == "caller_rates" else None,
        "rate_effective_date": (
            rate_effective_date if cost_basis == "caller_rates" else None
        ),
    }


def read_summary_row(
    document: dict[str, object],
) -> tuple[tuple[str, str, str], str | None, Decimal | None]:
    repository = require_summary_label(document.get("repository"))
    task_id = require_summary_label(document.get("task_id"))
    run_id = require_summary_label(document.get("run_id"))
    outcome = document.get("outcome")
    if outcome is not None and (
        not isinstance(outcome, str) or outcome not in ("pass", "fail")
    ):
        raise ValueError("summary outcome must be pass, fail, or missing")
    return (repository, task_id, run_id), outcome, read_money(document, "cost_usd")


def require_summary_label(candidate: object) -> str:
    label = safe_label(candidate)
    if label == "unknown":
        raise ValueError("summary row needs repository, task ID, and run ID")
    return label


def summarize_run_rows(all_documents: list[dict[str, object]]) -> dict[str, object]:
    run_by_key: dict[tuple[str, str, str], tuple[str | None, Decimal | None]] = {}
    for each_document in all_documents:
        run_key, outcome, cost = read_summary_row(each_document)
        previous_run = run_by_key.get(run_key)
        if previous_run is not None and previous_run != (outcome, cost):
            raise ValueError("duplicate run ID has conflicting cost or outcome")
        run_by_key[run_key] = (outcome, cost)
    task_by_key: dict[tuple[str, str], TaskRuns] = {}
    for (repository, task_id, run_id), (outcome, cost) in sorted(run_by_key.items()):
        task_runs = task_by_key.setdefault((repository, task_id), TaskRuns())
        task_runs.run_ids.append(run_id)
        task_runs.outcomes.append(outcome)
        task_runs.costs.append(cost)
    return build_summary(task_by_key)


def build_summary(task_by_key: dict[tuple[str, str], TaskRuns]) -> dict[str, object]:
    all_tasks: list[dict[str, object]] = []
    all_costs: list[Decimal | None] = []
    passed_task_count = 0
    is_outcome_known = bool(task_by_key)
    for (repository, task_id), each_task in sorted(task_by_key.items()):
        is_task_outcome_known = all(
            each_outcome is not None for each_outcome in each_task.outcomes
        )
        is_outcome_known = is_outcome_known and is_task_outcome_known
        is_task_passed = "pass" in each_task.outcomes
        passed_task_count += int(is_task_passed and is_task_outcome_known)
        task_cost = sum_costs(each_task.costs)
        all_costs.append(task_cost)
        all_tasks.append(
            {
                "repository": repository,
                "task_id": task_id,
                "run_ids": each_task.run_ids,
                "passed": is_task_passed if is_task_outcome_known else None,
                "cost_usd": display_money(task_cost),
            }
        )
    total_cost = sum_costs(all_costs)
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
        "total_cost_usd": display_money(total_cost),
        "cost_per_passed_task_usd": display_money(cost_per_pass),
        "tasks": all_tasks,
    }


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run_parser = commands.add_parser("run", help="reduce one vendor run from stdin")
    run_parser.add_argument("--task-id", required=True)
    run_parser.add_argument("--run-id", required=True)
    run_parser.add_argument("--repository", required=True)
    run_parser.add_argument("--outcome", choices=("pass", "fail"), required=True)
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


def main(arguments: list[str] | None = None, input_stream: TextIO = sys.stdin) -> int:
    parser = create_parser()
    parsed_arguments = parser.parse_args(arguments)
    try:
        stdin_text = input_stream.read()
        if parsed_arguments.command == "run":
            report = build_run_report(parsed_arguments, stdin_text)
        else:
            report = summarize_run_rows(parse_documents(stdin_text))
    except (ValueError, json.JSONDecodeError) as error:
        sys.stderr.write(f"task usage: {error}\n")
        return 2
    sys.stdout.write(json.dumps(report, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
