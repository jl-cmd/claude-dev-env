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

HOOKS_AUDIT_DIRECTORY = Path(__file__).resolve().parent
if str(HOOKS_AUDIT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(HOOKS_AUDIT_DIRECTORY))

from hook_cases import CaseResult, first_verdict, run_case
from hook_harness import (
    HookRegistration,
    Sandbox,
    build_payload,
    load_registrations,
    run_event_chain,
)

REPOSITORY_ROOT = HOOKS_AUDIT_DIRECTORY.parents[2]
DEFAULT_PLUGIN_ROOT = REPOSITORY_ROOT / "packages" / "claude-dev-env"
DATA_DIRECTORY = REPOSITORY_ROOT / "tests" / "audit" / "data"
ALL_STOPPING_OUTCOMES = frozenset({"block", "ask", "rewrite"})
ALL_DEFAULT_CASES: list[dict[str, object]] = [
    {"kind": "malformed", "expect": {}},
    {
        "kind": "non_matching",
        "event": "PreToolUse",
        "payload": {
            "tool_name": "Read",
            "tool_input": {"file_path": "{sandbox}/notes.txt"},
        },
        "expect": {"outcome": "silent"},
    },
]
CASE_RUN_COLUMNS = [
    "hook_id",
    "kind",
    "hosted_hook",
    "matcher_hit",
    "expected",
    "observed",
    "pass",
    "exit_code",
    "wall_ms",
    "injected_characters",
    "effect_failures",
    "claim_chain",
    "stderr_head",
]
VERDICT_COLUMNS = [
    "hook_id",
    "event",
    "matcher",
    "claim",
    "component_class",
    "mechanism_verdict",
    "prohibited_result",
    "near_neighbor_result",
    "malformed_result",
    "non_matching_result",
    "redundancy_result",
    "median_wall_ms",
    "injected_characters",
    "reasons",
]


def _redundancy(
    registration: HookRegistration,
    case: dict[str, object],
    result: CaseResult,
    all_registrations: list[HookRegistration],
    sandbox_root: Path,
    plugin_root: Path,
) -> str:
    if result.run.outcome not in ALL_STOPPING_OUTCOMES:
        return "n/a: no stop or rewrite to duplicate"
    sandbox = Sandbox(sandbox_root)
    payload = build_payload(
        str(case.get("event", registration.event)), sandbox, dict(case["payload"])
    )
    remaining_outcome = run_event_chain(
        all_registrations, payload, plugin_root, sandbox, registration.hook_id
    )
    if remaining_outcome in ALL_STOPPING_OUTCOMES:
        return f"redundant: remaining hooks still give {remaining_outcome}"
    return f"unique: remaining hooks give {remaining_outcome}"


def _summarize(all_results: list[CaseResult], kind: str) -> str:
    all_kind_results = [
        each_result for each_result in all_results if each_result.kind == kind
    ]
    if not all_kind_results:
        return "n/a: fires on every occurrence"
    return "; ".join(
        f"{'PASS' if each_result.is_pass else 'FAIL'} {each_result.run.outcome}"
        for each_result in all_kind_results
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin-root", type=Path, default=DEFAULT_PLUGIN_ROOT)
    parser.add_argument("--cases", type=Path, default=HOOKS_AUDIT_DIRECTORY / "hook_cases.json")
    parser.add_argument("--output-suffix", default="")
    arguments = parser.parse_args()
    plugin_root: Path = arguments.plugin_root.resolve()
    all_registrations = load_registrations(plugin_root / "hooks" / "hooks.json")
    registration_by_id = {each.hook_id: each for each in all_registrations}
    registry = json.loads(
        arguments.cases.read_text(encoding="utf-8")
    )
    all_case_rows: list[dict[str, object]] = []
    all_verdict_rows: list[dict[str, object]] = []
    covered_hook_ids: set[str] = set()
    with tempfile.TemporaryDirectory(
        prefix="hook-audit-", ignore_cleanup_errors=True
    ) as scratch:
        for each_hook in registry["hooks"]:
            hook_id = each_hook["hook_id"]
            registration = registration_by_id.get(hook_id)
            if registration is None:
                print(f"SKIP {hook_id}: not registered in hooks.json")
                continue
            covered_hook_ids.add(hook_id)
            all_results: list[CaseResult] = []
            all_redundancy: list[str] = []
            all_cases = [*each_hook["cases"], *ALL_DEFAULT_CASES]
            for each_index, each_case in enumerate(all_cases):
                case_root = Path(scratch) / hook_id.replace(":", "_") / str(each_index)
                result = run_case(
                    registration, each_case, plugin_root, case_root, all_registrations
                )
                all_results.append(result)
                if each_case["kind"] == "prohibited":
                    all_redundancy.append(
                        _redundancy(
                            registration,
                            each_case,
                            result,
                            all_registrations,
                            case_root.with_name(f"{each_index}-redundancy"),
                            plugin_root,
                        )
                    )
                all_case_rows.append(
                    {
                        "hook_id": hook_id,
                        "kind": result.kind,
                        "hosted_hook": each_case.get("hosted_hook", ""),
                        "matcher_hit": result.is_matcher_hit,
                        "expected": result.expected_outcome,
                        "observed": result.run.outcome,
                        "pass": result.is_pass,
                        "exit_code": result.run.exit_code,
                        "wall_ms": round(result.run.wall_ms),
                        "injected_characters": result.run.injected_characters,
                        "effect_failures": " | ".join(result.all_effect_failures),
                        "claim_chain": (
                            f"expected {result.claim_chain_expected}, observed {result.claim_chain_observed}"
                            if result.claim_chain_expected
                            else ""
                        ),
                        "stderr_head": result.run.stderr.strip().replace("\n", " ")[
                            :200
                        ],
                    }
                )
            verdict, all_reasons = first_verdict(all_results)
            all_wall_ms = sorted(each_result.run.wall_ms for each_result in all_results)
            all_verdict_rows.append(
                {
                    "hook_id": hook_id,
                    "event": registration.event,
                    "matcher": registration.matcher,
                    "claim": each_hook["claim"],
                    "component_class": each_hook["component_class"],
                    "mechanism_verdict": verdict,
                    "prohibited_result": _summarize(all_results, "prohibited"),
                    "near_neighbor_result": _summarize(all_results, "near_neighbor"),
                    "malformed_result": _summarize(all_results, "malformed"),
                    "non_matching_result": _summarize(all_results, "non_matching"),
                    "redundancy_result": "; ".join(all_redundancy),
                    "median_wall_ms": round(all_wall_ms[len(all_wall_ms) // 2]),
                    "injected_characters": max(
                        each_result.run.injected_characters
                        for each_result in all_results
                    ),
                    "reasons": " | ".join(all_reasons),
                }
            )
            print(f"{verdict:16} {hook_id} {all_reasons}")
    for each_hook_id in sorted(set(registration_by_id) - covered_hook_ids):
        print(f"UNCOVERED {each_hook_id}: registered with no case row")
    _write_table(DATA_DIRECTORY / f"hook-case-runs{arguments.output_suffix}.tsv", CASE_RUN_COLUMNS, all_case_rows)
    _write_table(
        DATA_DIRECTORY / f"hook-verdicts{arguments.output_suffix}.tsv", VERDICT_COLUMNS, all_verdict_rows
    )
    return 1 if set(registration_by_id) - covered_hook_ids else 0


def _write_table(
    table_path: Path, all_columns: list[str], all_rows: list[dict[str, object]]
) -> None:
    with table_path.open("w", encoding="utf-8", newline="") as table_file:
        writer = csv.DictWriter(
            table_file, fieldnames=all_columns, delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(all_rows)


if __name__ == "__main__":
    raise SystemExit(main())
