"""Parse vendor usage events and compute token costs for task reports."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import fields as dataclass_fields
from decimal import Decimal, InvalidOperation


class UsageReportRunFatal(ValueError):
    """Stop a report when its input cannot be used safely."""


@dataclass(frozen=True)
class ModelRates:
    input_per_million: Decimal
    write_per_million: Decimal
    read_per_million: Decimal
    generated_per_million: Decimal


@dataclass(frozen=True)
class UsageEvent:
    model: str
    uncached_input_tokens: int | None
    cache_write_tokens: int | None
    cache_read_tokens: int | None
    generated_tokens: int | None
    reasoning_generated_tokens: int | None = None
    cost_usd: Decimal | None = None
    event_id: str | None = None


def _require_object(candidate: object, field_name: str) -> dict[str, object]:
    if not isinstance(candidate, dict):
        raise UsageReportRunFatal(f"{field_name} must be an object")
    return {
        each_key: each_entry
        for each_key, each_entry in candidate.items()
        if isinstance(each_key, str)
    }


def _require_list(candidate: object, field_name: str) -> list[object]:
    if not isinstance(candidate, list):
        raise UsageReportRunFatal(f"{field_name} must be a list")
    return candidate


def _usage_object(candidate: object) -> dict[str, object]:
    if candidate is None:
        return {}
    return _require_object(candidate, "usage")


def _read_count(all_fields: dict[str, object], field_name: str) -> int | None:
    if field_name not in all_fields:
        return None
    candidate = all_fields[field_name]
    if isinstance(candidate, bool):
        raise UsageReportRunFatal(f"{field_name} must be a nonnegative integer")
    if isinstance(candidate, int) and candidate >= 0:
        return candidate
    if isinstance(candidate, str) and candidate.isascii() and candidate.isdecimal():
        return int(candidate)
    raise ValueError(f"{field_name} must be a nonnegative integer")


def _read_money(all_fields: Mapping[str, object], field_name: str) -> Decimal | None:
    if field_name not in all_fields or all_fields[field_name] is None:
        return None
    candidate = all_fields[field_name]
    if isinstance(candidate, bool) or not isinstance(candidate, (int, float, str)):
        raise UsageReportRunFatal(f"{field_name} must be a nonnegative amount")
    try:
        amount = Decimal(str(candidate))
    except InvalidOperation as error:
        raise ValueError(f"{field_name} must be a nonnegative amount") from error
    if not amount.is_finite() or amount < 0:
        raise ValueError(f"{field_name} must be a nonnegative amount")
    return amount


def _safe_label(candidate: object) -> str:
    if not isinstance(candidate, str):
        return "unknown"
    if not candidate:
        return "unknown"
    if not candidate.isascii() or not all(
        each_character.isalnum() or each_character in "._-/"
        for each_character in candidate
    ):
        return "unknown"
    return candidate


def _require_label(candidate: str, field_name: str) -> str:
    label = _safe_label(candidate)
    if label == "unknown":
        raise ValueError(f"{field_name} needs a nonempty identifier")
    return label


def _sum_known(all_counts: list[int | None]) -> int | None:
    if not all_counts or any(each_count is None for each_count in all_counts):
        return None
    return sum(each_count for each_count in all_counts if each_count is not None)


def _sum_costs(all_costs: list[Decimal | None]) -> Decimal | None:
    if not all_costs or any(each_cost is None for each_cost in all_costs):
        return None
    return sum(
        (each_cost for each_cost in all_costs if each_cost is not None), Decimal(0)
    )


def _display_money(amount: Decimal | None) -> str | None:
    if amount is None:
        return None
    return format(amount.normalize(), "f")


def _parse_rate(specification: str) -> tuple[str, ModelRates]:
    model_text, separator, rate_text = specification.partition("=")
    if not separator or _safe_label(model_text) == "unknown":
        raise ValueError("rate needs MODEL=INPUT,WRITE,READ,OUTPUT")
    all_rate_texts = rate_text.split(",")
    if len(all_rate_texts) != len(dataclass_fields(ModelRates)):
        raise ValueError("rate needs four prices per million tokens")
    rate_fields = {str(i): each_rate for i, each_rate in enumerate(all_rate_texts)}
    all_rates = [
        _read_money(rate_fields, str(i))
        for i in range(len(dataclass_fields(ModelRates)))
    ]
    if any(each_rate is None for each_rate in all_rates):
        raise ValueError("rate needs four prices per million tokens")
    return model_text, ModelRates(
        *[each_rate for each_rate in all_rates if each_rate is not None]
    )


def _calculate_codex_cost(
    usage_event: UsageEvent, rates: ModelRates | None
) -> Decimal | None:
    if rates is None:
        return None
    all_counts = (
        usage_event.uncached_input_tokens,
        usage_event.cache_write_tokens,
        usage_event.cache_read_tokens,
        usage_event.generated_tokens,
    )
    if any(each_count is None for each_count in all_counts):
        return None
    all_prices = (
        rates.input_per_million,
        rates.write_per_million,
        rates.read_per_million,
        rates.generated_per_million,
    )
    return sum(
        Decimal(each_count) * each_price
        for each_count, each_price in zip(all_counts, all_prices)
        if each_count is not None
    ) / Decimal(1_000_000)


def _parse_claude_usage(
    all_fields: dict[str, object], model: str, is_model_usage: bool
) -> UsageEvent:
    if is_model_usage:
        return UsageEvent(
            model=model,
            uncached_input_tokens=_read_count(all_fields, "inputTokens"),
            cache_write_tokens=_read_count(all_fields, "cacheCreationInputTokens"),
            cache_read_tokens=_read_count(all_fields, "cacheReadInputTokens"),
            generated_tokens=_read_count(all_fields, "outputTokens"),
            cost_usd=_read_money(all_fields, "costUSD"),
        )
    return UsageEvent(
        model=model,
        uncached_input_tokens=_read_count(all_fields, "input_tokens"),
        cache_write_tokens=_read_count(all_fields, "cache_creation_input_tokens"),
        cache_read_tokens=_read_count(all_fields, "cache_read_input_tokens"),
        generated_tokens=_read_count(all_fields, "output_tokens"),
    )


def _parse_claude_json(
    all_document_fields: dict[str, object],
) -> tuple[list[UsageEvent], Decimal | None]:
    if all_document_fields.get("type") != "result":
        raise ValueError("Claude JSON needs one result object")
    model_usage = all_document_fields.get("modelUsage")
    if isinstance(model_usage, dict) and model_usage:
        all_events = [
            _parse_claude_usage(
                _require_object(each_usage, "model usage"),
                _safe_label(each_model),
                True,
            )
            for each_model, each_usage in model_usage.items()
        ]
    else:
        usage_fields = _usage_object(all_document_fields.get("usage"))
        all_events = [
            _parse_claude_usage(
                usage_fields, _safe_label(all_document_fields.get("model")), False
            )
        ]
    total_cost = _read_money(all_document_fields, "total_cost_usd")
    return all_events, (
        total_cost
        if total_cost is not None
        else _sum_costs([each_event.cost_usd for each_event in all_events])
    )


def _validate_reasoning_tokens(
    generated_tokens: int | None, reasoning_tokens: int | None
) -> None:
    if (
        generated_tokens is not None
        and reasoning_tokens is not None
        and reasoning_tokens > generated_tokens
    ):
        raise ValueError("reasoning output exceeds output tokens")


def _uncached_codex_tokens(
    input_tokens: int | None,
    cache_read_tokens: int | None,
    cache_write_tokens: int | None,
) -> int | None:
    if input_tokens is None or cache_read_tokens is None or cache_write_tokens is None:
        return None
    uncached_tokens = input_tokens - cache_read_tokens - cache_write_tokens
    if uncached_tokens < 0:
        raise ValueError("cached input exceeds input tokens")
    return uncached_tokens


def _parse_codex_usage(
    all_fields: dict[str, object], model: str, event_id: str | None
) -> UsageEvent:
    input_tokens = _read_count(all_fields, "input_tokens")
    cache_read_tokens = _read_count(all_fields, "cached_input_tokens")
    cache_write_tokens = (
        _read_count(all_fields, "cache_write_input_tokens")
        if "cache_write_input_tokens" in all_fields
        else 0
        if all_fields
        else None
    )
    generated_tokens = _read_count(all_fields, "output_tokens")
    reasoning_tokens = _read_count(all_fields, "reasoning_output_tokens")
    _validate_reasoning_tokens(generated_tokens, reasoning_tokens)
    uncached_tokens = _uncached_codex_tokens(
        input_tokens, cache_read_tokens, cache_write_tokens
    )
    return UsageEvent(
        model,
        uncached_tokens,
        cache_write_tokens,
        cache_read_tokens,
        generated_tokens,
        reasoning_tokens,
        event_id=event_id,
    )


def _parse_codex_event(
    all_document_fields: dict[str, object],
    fallback_model: str,
    rates_by_model: dict[str, ModelRates],
) -> UsageEvent | None:
    if all_document_fields.get("type") != "turn.completed":
        return None
    model = _safe_label(all_document_fields.get("model"))
    if model == "unknown":
        model = fallback_model
    usage_fields = _usage_object(all_document_fields.get("usage"))
    event_id = _safe_label(all_document_fields.get("turn_id"))
    usage_event = _parse_codex_usage(
        usage_fields, model, None if event_id == "unknown" else event_id
    )
    return UsageEvent(
        model=usage_event.model,
        uncached_input_tokens=usage_event.uncached_input_tokens,
        cache_write_tokens=usage_event.cache_write_tokens,
        cache_read_tokens=usage_event.cache_read_tokens,
        generated_tokens=usage_event.generated_tokens,
        reasoning_generated_tokens=usage_event.reasoning_generated_tokens,
        cost_usd=_calculate_codex_cost(usage_event, rates_by_model.get(model)),
        event_id=usage_event.event_id,
    )


def _unwrap_otel_attribute(candidate: object) -> object:
    if not isinstance(candidate, dict):
        return candidate
    for each_key in ("stringValue", "intValue", "doubleValue"):
        if each_key in candidate:
            return candidate[each_key]
    return candidate


def _otel_attributes(all_document_fields: dict[str, object]) -> dict[str, object]:
    raw_attributes = all_document_fields.get("attributes", {})
    if isinstance(raw_attributes, dict):
        return {
            each_key: _unwrap_otel_attribute(each_entry)
            for each_key, each_entry in raw_attributes.items()
        }
    all_attributes = _require_list(raw_attributes, "attributes")
    attributes: dict[str, object] = {}
    for each_attribute in all_attributes:
        attribute = _require_object(each_attribute, "attribute")
        attribute_key = attribute.get("key")
        if isinstance(attribute_key, str):
            attributes[attribute_key] = _unwrap_otel_attribute(attribute.get("value"))
    return attributes


def _parse_otel_event(all_document_fields: dict[str, object]) -> UsageEvent | None:
    attributes = (
        _otel_attributes(all_document_fields)
        if "attributes" in all_document_fields
        else all_document_fields
    )
    event_name = _unwrap_otel_attribute(
        all_document_fields.get("body", all_document_fields.get("event.name"))
    )
    if (
        event_name not in ("claude_code.api_request", "api_request")
        and attributes.get("event.name") != "api_request"
    ):
        return None
    cost = _read_money(attributes, "cost_usd")
    if cost is None:
        cost_micros = _read_count(attributes, "cost_usd_micros")
        cost = (
            None if cost_micros is None else Decimal(cost_micros) / Decimal(1_000_000)
        )
    event_id = _safe_label(attributes.get("request_id"))
    return UsageEvent(
        model=_safe_label(attributes.get("model")),
        uncached_input_tokens=_read_count(attributes, "input_tokens"),
        cache_write_tokens=_read_count(attributes, "cache_creation_tokens"),
        cache_read_tokens=_read_count(attributes, "cache_read_tokens"),
        generated_tokens=_read_count(attributes, "output_tokens"),
        cost_usd=cost,
        event_id=None if event_id == "unknown" else event_id,
    )


def _require_one_otel_session(all_records: list[dict[str, object]]) -> None:
    all_session_ids: set[str] = set()
    for each_record in all_records:
        attributes = (
            _otel_attributes(each_record)
            if "attributes" in each_record
            else each_record
        )
        all_session_ids.add(_safe_label(attributes.get("session.id")))
    if len(all_session_ids) != 1 or "unknown" in all_session_ids:
        raise ValueError("OTel input needs one session ID across all log records")


def _cost_basis(source_format: str, total_cost: Decimal | None) -> str:
    if total_cost is None:
        return "unknown"
    if source_format == "codex-json":
        return "caller_rates"
    return "provider_estimate"


def _require_one_codex_thread(all_documents: list[dict[str, object]]) -> None:
    all_thread_starts = [
        _safe_label(each_document.get("thread_id"))
        for each_document in all_documents
        if each_document.get("type") == "thread.started"
    ]
    if len(all_thread_starts) != 1 or all_thread_starts[0] == "unknown":
        raise ValueError("Codex input needs one thread.started event")
