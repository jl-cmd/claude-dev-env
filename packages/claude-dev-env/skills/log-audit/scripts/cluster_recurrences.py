"""Group hook-block records by a normalized signature and rank the clusters.

Two failures can read differently only because one names line 12 and the other
line 348. They are the same failure. This script strips the varying parts down
to one signature, so it counts how often each real failure recurs. It ranks the
loudest first and weights recent blocks over stale ones. It also reads timing
samples for one operation and flags that operation when its recent runs have
grown slower than its earlier runs.

Reads the JSON record list collect_log_window prints, on stdin.

Usage:
    collect_log_window.py --hours 24 | cluster_recurrences.py
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

_script_directory = str(Path(__file__).resolve().parent)
if _script_directory not in sys.path:
    sys.path.insert(0, _script_directory)

from log_audit_constants.cluster_recurrences_constants import (  # noqa: E402
    DIGIT_PATTERN,
    HASH_PATTERN,
    MIN_TIMING_SAMPLES_PER_HALF,
    PATH_PATTERN,
    RECENCY_DECAY_BASE,
    RECENCY_HALF_LIFE_HOURS,
    SAMPLE_HALVES,
    SECONDS_PER_HOUR,
    SIGNATURE_PLACEHOLDER,
    TIMING_REGRESSION_RATIO,
)
from log_audit_constants.collect_log_window_constants import (  # noqa: E402
    RECORD_LEVEL_KEY,
    RECORD_MESSAGE_KEY,
    RECORD_SOURCE_KEY,
    RECORD_TIMESTAMP_KEY,
)

from collect_log_window import LogRecord  # noqa: E402


@dataclass(frozen=True)
class SignatureCluster:
    """A group of records that share one normalized message signature.

    Attributes:
        signature: The normalized message the grouped records share.
        count: How many records fell into the cluster.
        latest_timestamp: The most recent record's timestamp in the cluster.
        score: The recency-weighted sum of the cluster's records.
    """

    signature: str
    count: int
    latest_timestamp: datetime
    score: float


@dataclass(frozen=True)
class TimingSample:
    """One measured run of a repeated operation.

    Attributes:
        operation: The operation's name.
        timestamp: When the run happened.
        duration_ms: How long the run took, in milliseconds.
    """

    operation: str
    timestamp: datetime
    duration_ms: float


@dataclass(frozen=True)
class TimingRegression:
    """A repeated operation whose recent runs have grown slower.

    Attributes:
        operation: The operation's name.
        baseline_ms: The mean duration of the earliest runs.
        recent_ms: The mean duration of the latest runs.
        ratio: The recent mean divided by the baseline mean.
    """

    operation: str
    baseline_ms: float
    recent_ms: float
    ratio: float


def normalize_signature(message: str) -> str:
    """Reduce a message to a signature shared by its recurring variants.

    Args:
        message: A raw block-reason message.

    Returns:
        The message with paths, hashes, and numbers replaced by a placeholder
        and runs of whitespace collapsed to single spaces.
    """
    without_paths = re.sub(PATH_PATTERN, SIGNATURE_PLACEHOLDER, message)
    without_hashes = re.sub(HASH_PATTERN, SIGNATURE_PLACEHOLDER, without_paths)
    without_numbers = re.sub(DIGIT_PATTERN, SIGNATURE_PLACEHOLDER, without_hashes)
    return re.sub(r"\s+", " ", without_numbers).strip()


def recency_weight(record_timestamp: datetime, now: datetime) -> float:
    """Weight a record by how recent it is, halving each half-life of age.

    Args:
        record_timestamp: When the record was written.
        now: The current time age is measured against.

    Returns:
        A weight near one for a fresh record, falling toward zero as it ages.
    """
    age_hours = (now - record_timestamp).total_seconds() / SECONDS_PER_HOUR
    return RECENCY_DECAY_BASE ** (age_hours / RECENCY_HALF_LIFE_HOURS)


def rank_signature_clusters(
    all_records: list[LogRecord], now: datetime
) -> list[SignatureCluster]:
    """Group records by signature and rank them by recency-weighted count.

    Args:
        all_records: The block records to group.
        now: The current time used to weight each record.

    Returns:
        One cluster per distinct signature, highest score first.
    """
    records_by_signature: dict[str, list[LogRecord]] = defaultdict(list)
    for each_record in all_records:
        records_by_signature[normalize_signature(each_record.message)].append(
            each_record
        )
    clusters: list[SignatureCluster] = []
    for each_signature, each_signature_records in records_by_signature.items():
        score = sum(
            recency_weight(each_grouped.timestamp, now)
            for each_grouped in each_signature_records
        )
        latest_timestamp = max(
            each_grouped.timestamp for each_grouped in each_signature_records
        )
        clusters.append(
            SignatureCluster(
                signature=each_signature,
                count=len(each_signature_records),
                latest_timestamp=latest_timestamp,
                score=score,
            )
        )
    return sorted(
        clusters,
        key=lambda cluster: (cluster.score, cluster.count),
        reverse=True,
    )


def _mean_duration(all_samples: list[TimingSample]) -> float:
    """Return the mean duration in milliseconds of the given samples."""
    return sum(each_sample.duration_ms for each_sample in all_samples) / len(
        all_samples
    )


def detect_timing_regressions(
    all_samples: list[TimingSample],
) -> list[TimingRegression]:
    """Flag operations whose recent runs are slower than their earliest runs.

    Args:
        all_samples: Timing samples across one or more operations.

    Returns:
        One regression per operation whose recent-to-baseline duration ratio
        reaches the regression threshold, highest ratio first.
    """
    samples_by_operation: dict[str, list[TimingSample]] = defaultdict(list)
    for each_sample in all_samples:
        samples_by_operation[each_sample.operation].append(each_sample)
    regressions: list[TimingRegression] = []
    for each_operation, each_operation_samples in samples_by_operation.items():
        if len(each_operation_samples) < MIN_TIMING_SAMPLES_PER_HALF * SAMPLE_HALVES:
            continue
        ordered_samples = sorted(
            each_operation_samples, key=lambda sample: sample.timestamp
        )
        baseline_ms = _mean_duration(ordered_samples[:MIN_TIMING_SAMPLES_PER_HALF])
        recent_ms = _mean_duration(ordered_samples[-MIN_TIMING_SAMPLES_PER_HALF:])
        if baseline_ms <= 0:
            continue
        ratio = recent_ms / baseline_ms
        if ratio >= TIMING_REGRESSION_RATIO:
            regressions.append(
                TimingRegression(
                    operation=each_operation,
                    baseline_ms=baseline_ms,
                    recent_ms=recent_ms,
                    ratio=ratio,
                )
            )
    return sorted(regressions, key=lambda regression: regression.ratio, reverse=True)


def _record_from_json_dict(all_record_fields: dict[str, str]) -> LogRecord:
    """Rebuild a LogRecord from one collect_log_window JSON dict."""
    return LogRecord(
        timestamp=datetime.fromisoformat(all_record_fields[RECORD_TIMESTAMP_KEY]),
        source=all_record_fields[RECORD_SOURCE_KEY],
        level=all_record_fields[RECORD_LEVEL_KEY],
        message=all_record_fields[RECORD_MESSAGE_KEY],
    )


def main() -> int:
    """Read records on stdin and print ranked signature clusters.

    Returns:
        The process exit code; zero on success.
    """
    records_payload = json.load(sys.stdin)
    records = [
        _record_from_json_dict(each_record_fields)
        for each_record_fields in records_payload
    ]
    clusters = rank_signature_clusters(records, datetime.now())
    for each_cluster in clusters:
        print(
            f"{each_cluster.count}\t{each_cluster.score:.2f}\t{each_cluster.signature}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
