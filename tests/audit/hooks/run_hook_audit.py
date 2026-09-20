"""Give every registered hook a first verdict and write the evidence tables.

Usage: python tests/audit/hooks/run_hook_audit.py
       python tests/audit/hooks/run_hook_audit.py --plugin-root <checkout>/packages/claude-dev-env
           --cases tests/audit/hooks/hook_cases_removed.json --output-suffix=-baseline

Writes ``tests/audit/data/hook-case-runs.tsv`` (one row per case run) and
``tests/audit/data/hook-verdicts.tsv`` (one row per registered hook).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import tempfile
from pathlib import Path
from typing import TextIO

_hooks_audit_directory = Path(__file__).resolve().parent
if str(_hooks_audit_directory) not in sys.path:
    sys.path.insert(0, str(_hooks_audit_directory))

from hook_audit_parts.config.hook_cases_constants import (
    ALL_STOPPING_OUTCOMES,
    UTF8_ENCODING,
)
from hook_audit_parts.config.run_hook_audit_constants import (
    ALL_CASE_RUN_COLUMNS,
    ALL_DEFAULT_CASES,
    ALL_VERDICT_COLUMNS,
    COLUMN_TEXT_SEPARATOR,
    DEFAULT_CASES_FILE_NAME,
    DEFAULT_PLUGIN_ROOT,
    EVIDENCE_DIRECTORY,
    HOOKS_REGISTRATION_RELATIVE_PATH,
    REASON_SEPARATOR,
    SCRATCH_PREFIX,
    STDERR_HEAD_CHARACTERS,
    TABLE_DELIMITER,
    TABLE_LINE_TERMINATOR,
)
from hook_cases import CaseRun, first_verdict, run_case
from hook_harness import (
    HookRegistration,
    Sandbox,
    build_payload,
    load_registrations,
    run_event_chain,
)


def _redundancy(
    registration: HookRegistration,
    all_case_fields: dict[str, object],
    case_run: CaseRun,
    all_registrations: list[HookRegistration],
    sandbox_root: Path,
    plugin_root: Path,
) -> str:
    if case_run.run.outcome not in ALL_STOPPING_OUTCOMES:
        return "n/a: no stop or rewrite to duplicate"
    sandbox = Sandbox(sandbox_root)
    payload = build_payload(
        str(all_case_fields.get("event", registration.event)),
        sandbox,
        dict(all_case_fields["payload"]),
    )
    remaining_outcome = run_event_chain(
        all_registrations, payload, plugin_root, sandbox, registration.hook_id
    )
    if remaining_outcome in ALL_STOPPING_OUTCOMES:
        return f"redundant: remaining hooks still give {remaining_outcome}"
    return f"unique: remaining hooks give {remaining_outcome}"


def _summarize(all_case_runs: list[CaseRun], kind: str) -> str:
    all_kind_runs = [
        each_case_run for each_case_run in all_case_runs if each_case_run.kind == kind
    ]
    if not all_kind_runs:
        return "n/a: fires on every occurrence"
    return REASON_SEPARATOR.join(
        f"{'PASS' if each_case_run.is_pass else 'FAIL'} {each_case_run.run.outcome}"
        for each_case_run in all_kind_runs
    )


def _case_row(
    hook_id: str, all_case_fields: dict[str, object], case_run: CaseRun
) -> dict[str, object]:
    return {
        "hook_id": hook_id,
        "kind": case_run.kind,
        "hosted_hook": all_case_fields.get("hosted_hook", ""),
        "matcher_hit": case_run.is_matcher_hit,
        "expected": case_run.expected_outcome,
        "observed": case_run.run.outcome,
        "pass": case_run.is_pass,
        "exit_code": case_run.run.exit_code,
        "wall_ms": round(case_run.run.wall_ms),
        "injected_characters": case_run.run.injected_characters,
        "effect_failures": COLUMN_TEXT_SEPARATOR.join(case_run.all_effect_failures),
        "claim_chain": (
            f"expected {case_run.claim_chain_expected}, observed {case_run.claim_chain_observed}"
            if case_run.claim_chain_expected
            else ""
        ),
        "stderr_head": case_run.run.stderr.strip().replace("\n", " ")[
            :STDERR_HEAD_CHARACTERS
        ],
    }


def _verdict_row(
    all_hook_fields: dict[str, object],
    registration: HookRegistration,
    verdict: str,
    all_case_runs: list[CaseRun],
    all_redundancy: list[str],
    all_reasons: list[str],
) -> dict[str, object]:
    all_wall_ms = sorted(each_case_run.run.wall_ms for each_case_run in all_case_runs)
    return {
        "hook_id": registration.hook_id,
        "event": registration.event,
        "matcher": registration.matcher,
        "claim": all_hook_fields["claim"],
        "component_class": all_hook_fields["component_class"],
        "mechanism_verdict": verdict,
        "prohibited_result": _summarize(all_case_runs, "prohibited"),
        "near_neighbor_result": _summarize(all_case_runs, "near_neighbor"),
        "malformed_result": _summarize(all_case_runs, "malformed"),
        "non_matching_result": _summarize(all_case_runs, "non_matching"),
        "redundancy_result": REASON_SEPARATOR.join(all_redundancy),
        "median_wall_ms": round(all_wall_ms[len(all_wall_ms) // 2]),
        "injected_characters": max(
            each_case_run.run.injected_characters for each_case_run in all_case_runs
        ),
        "reasons": COLUMN_TEXT_SEPARATOR.join(all_reasons),
    }


def _run_hook_cases(
    all_hook_fields: dict[str, object],
    registration: HookRegistration,
    plugin_root: Path,
    all_registrations: list[HookRegistration],
    scratch_root: Path,
) -> tuple[list[dict[str, object]], list[CaseRun], list[str]]:
    hook_id = registration.hook_id
    all_case_rows: list[dict[str, object]] = []
    all_case_runs: list[CaseRun] = []
    all_redundancy: list[str] = []
    all_cases = [*all_hook_fields["cases"], *ALL_DEFAULT_CASES]
    for each_index, each_case in enumerate(all_cases):
        case_root = scratch_root / hook_id.replace(":", "_") / str(each_index)
        case_run = run_case(
            registration, each_case, plugin_root, case_root, all_registrations
        )
        all_case_runs.append(case_run)
        if each_case["kind"] == "prohibited":
            all_redundancy.append(
                _redundancy(
                    registration,
                    each_case,
                    case_run,
                    all_registrations,
                    case_root.with_name(f"{each_index}-redundancy"),
                    plugin_root,
                )
            )
        all_case_rows.append(_case_row(hook_id, each_case, case_run))
    return all_case_rows, all_case_runs, all_redundancy


def _audit_every_hook(
    all_registry_hooks: list[dict[str, object]],
    all_registrations_by_id: dict[str, HookRegistration],
    all_registrations: list[HookRegistration],
    plugin_root: Path,
    scratch_root: Path,
    stream: TextIO,
) -> tuple[list[dict[str, object]], list[dict[str, object]], set[str]]:
    all_case_rows: list[dict[str, object]] = []
    all_verdict_rows: list[dict[str, object]] = []
    covered_hook_ids: set[str] = set()
    for each_hook in all_registry_hooks:
        hook_id = str(each_hook["hook_id"])
        registration = all_registrations_by_id.get(hook_id)
        if registration is None:
            stream.write(f"SKIP {hook_id}: not registered in hooks.json\n")
            continue
        covered_hook_ids.add(hook_id)
        all_hook_case_rows, all_case_runs, all_redundancy = _run_hook_cases(
            each_hook, registration, plugin_root, all_registrations, scratch_root
        )
        all_case_rows.extend(all_hook_case_rows)
        verdict, all_reasons = first_verdict(all_case_runs)
        all_verdict_rows.append(
            _verdict_row(
                each_hook,
                registration,
                verdict,
                all_case_runs,
                all_redundancy,
                all_reasons,
            )
        )
        stream.write(f"{verdict:16} {hook_id} {all_reasons}\n")
    return all_case_rows, all_verdict_rows, covered_hook_ids


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin-root", type=Path, default=DEFAULT_PLUGIN_ROOT)
    parser.add_argument(
        "--cases",
        type=Path,
        default=_hooks_audit_directory / DEFAULT_CASES_FILE_NAME,
    )
    parser.add_argument("--output-suffix", default="")
    return parser.parse_args()


def main(stream: TextIO = sys.stdout) -> int:
    """Audit every registered hook and write both evidence tables.

    Args:
        stream: Where the per-hook progress lines are written.

    Returns:
        1 when a registered hook has no case row, and 0 otherwise.
    """
    arguments = _parse_arguments()
    plugin_root: Path = arguments.plugin_root.resolve()
    all_registrations = load_registrations(
        plugin_root / HOOKS_REGISTRATION_RELATIVE_PATH
    )
    all_registrations_by_id = {
        each_registration.hook_id: each_registration
        for each_registration in all_registrations
    }
    registry = json.loads(arguments.cases.read_text(encoding=UTF8_ENCODING))
    with tempfile.TemporaryDirectory(
        prefix=SCRATCH_PREFIX, ignore_cleanup_errors=True
    ) as scratch:
        all_case_rows, all_verdict_rows, covered_hook_ids = _audit_every_hook(
            registry["hooks"],
            all_registrations_by_id,
            all_registrations,
            plugin_root,
            Path(scratch),
            stream,
        )
    for each_hook_id in sorted(set(all_registrations_by_id) - covered_hook_ids):
        stream.write(f"UNCOVERED {each_hook_id}: registered with no case row\n")
    suffix = arguments.output_suffix
    _write_table(
        EVIDENCE_DIRECTORY / f"hook-case-runs{suffix}.tsv",
        ALL_CASE_RUN_COLUMNS,
        all_case_rows,
    )
    _write_table(
        EVIDENCE_DIRECTORY / f"hook-verdicts{suffix}.tsv",
        ALL_VERDICT_COLUMNS,
        all_verdict_rows,
    )
    return 1 if set(all_registrations_by_id) - covered_hook_ids else 0


def _write_table(
    table_path: Path, all_columns: list[str], all_rows: list[dict[str, object]]
) -> None:
    with table_path.open("w", encoding=UTF8_ENCODING, newline="") as table_file:
        writer = csv.DictWriter(
            table_file,
            fieldnames=all_columns,
            delimiter=TABLE_DELIMITER,
            lineterminator=TABLE_LINE_TERMINATOR,
        )
        writer.writeheader()
        writer.writerows(all_rows)


if __name__ == "__main__":
    raise SystemExit(main())
