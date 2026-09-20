"""Behavior tests for the follow-up command."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

from dev_env_scripts_constants.followup_constants import (
    BACKLOG_EXCEEDED_EXIT_CODE,
    FOLLOWUP_BACKLOG_THRESHOLD,
)
from followup_cli import main

_hooks_directory = str(Path(__file__).resolve().parents[1] / "hooks")
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from followup_ledger import (
    FollowupFinding,
    all_recorded_findings,
    record_followup_finding,
)


def run_command(all_arguments: list[str]) -> tuple[int, str]:
    output_stream = io.StringIO()
    exit_code = main(all_arguments, stdout=output_stream)
    return exit_code, output_stream.getvalue()


def write_lint_report(
    report_path: Path, all_diagnostics: list[dict[str, object]]
) -> None:
    report_path.write_text(
        json.dumps(
            {"schema_version": 1, "diagnostics": all_diagnostics, "failed_rules": []}
        ),
        encoding="utf-8",
    )


def test_list_reports_nothing_outstanding_for_an_empty_ledger(tmp_path: Path) -> None:
    exit_code, output_text = run_command(["list", "--repository-root", str(tmp_path)])

    assert exit_code == 0
    assert "no follow-ups recorded" in output_text


def test_list_names_each_recorded_finding(tmp_path: Path) -> None:
    record_followup_finding(
        tmp_path, FollowupFinding("instruction-git-mode", "CLAUDE.md", "wrong mode")
    )

    exit_code, output_text = run_command(["list", "--repository-root", str(tmp_path)])

    assert exit_code == 0
    assert "instruction-git-mode" in output_text
    assert "CLAUDE.md" in output_text


def test_ingest_records_every_located_diagnostic(tmp_path: Path) -> None:
    report_path = tmp_path / "lint.json"
    write_lint_report(
        report_path,
        [
            {
                "rule_id": "line-length",
                "severity": "error",
                "message": "line runs past the limit",
                "location": {"path": "src/app.py", "start_line": 4, "start_column": 1},
            }
        ],
    )

    exit_code, _ = run_command(
        ["ingest", str(report_path), "--repository-root", str(tmp_path)]
    )

    assert exit_code == 0
    assert all_recorded_findings(tmp_path) == (
        FollowupFinding(
            "line-length", "src/app.py", "line runs past the limit", "line-length"
        ),
    )


def test_ingest_records_a_diagnostic_without_a_location(tmp_path: Path) -> None:
    report_path = tmp_path / "lint.json"
    write_lint_report(
        report_path,
        [
            {
                "rule_id": "inventory-drift",
                "severity": "error",
                "message": "inventory row missing",
                "location": None,
            }
        ],
    )

    run_command(["ingest", str(report_path), "--repository-root", str(tmp_path)])

    assert all_recorded_findings(tmp_path) == (
        FollowupFinding(
            "inventory-drift", "", "inventory row missing", "inventory-drift"
        ),
    )


def test_ingest_reports_an_unreadable_report(tmp_path: Path) -> None:
    exit_code, output_text = run_command(
        ["ingest", str(tmp_path / "absent.json"), "--repository-root", str(tmp_path)]
    )

    assert exit_code == 2
    assert "absent.json" in output_text


def test_brief_names_every_recorded_finding_and_the_repository(tmp_path: Path) -> None:
    record_followup_finding(
        tmp_path, FollowupFinding("instruction-git-mode", "CLAUDE.md", "wrong mode")
    )

    exit_code, output_text = run_command(["brief", "--repository-root", str(tmp_path)])

    assert exit_code == 0
    assert "instruction-git-mode" in output_text
    assert "wrong mode" in output_text
    assert "draft pull request" in output_text


def test_brief_asks_for_no_work_on_an_empty_ledger(tmp_path: Path) -> None:
    exit_code, output_text = run_command(["brief", "--repository-root", str(tmp_path)])

    assert exit_code == 0
    assert "no follow-ups recorded" in output_text


def test_clear_empties_the_ledger(tmp_path: Path) -> None:
    record_followup_finding(
        tmp_path, FollowupFinding("instruction-git-mode", "CLAUDE.md", "wrong mode")
    )

    exit_code, _ = run_command(["clear", "--repository-root", str(tmp_path)])

    assert exit_code == 0
    assert all_recorded_findings(tmp_path) == ()


def test_clear_on_an_empty_ledger_succeeds(tmp_path: Path) -> None:
    exit_code, _ = run_command(["clear", "--repository-root", str(tmp_path)])

    assert exit_code == 0


def test_an_unknown_command_reports_usage(tmp_path: Path) -> None:
    exit_code, output_text = run_command(
        ["stampede", "--repository-root", str(tmp_path)]
    )

    assert exit_code == 2
    assert "Usage" in output_text


def test_ingest_carries_the_check_identifier_a_diagnostic_names(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "lint.json"
    write_lint_report(
        report_path,
        [
            {
                "rule_id": "code-rules",
                "check_id": "code-rules/constant-outside-config",
                "severity": "error",
                "message": "Line 3: Constant TIMEOUT - move to config/",
                "location": {"path": "scripts/run.py", "start_line": 3},
            }
        ],
    )

    run_command(["ingest", str(report_path), "--repository-root", str(tmp_path)])

    recorded_finding = all_recorded_findings(tmp_path)[0]
    assert recorded_finding.check_id == "code-rules/constant-outside-config"
    assert recorded_finding.severity == "smell"


def test_ingest_records_the_revision_the_repository_has_checked_out(
    tmp_path: Path,
) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("f00dcafe\n", encoding="utf-8")
    report_path = tmp_path / "lint.json"
    write_lint_report(
        report_path,
        [
            {
                "rule_id": "code-rules",
                "check_id": "code-rules/function-length",
                "message": "Line 9: Function 'run' is 74 lines",
                "location": {"path": "scripts/run.py", "start_line": 9},
            }
        ],
    )

    run_command(["ingest", str(report_path), "--repository-root", str(tmp_path)])

    assert all_recorded_findings(tmp_path)[0].origin_commit == "f00dcafe"


def test_count_reports_an_empty_backlog(tmp_path: Path) -> None:
    exit_code, output_text = run_command(["count", "--repository-root", str(tmp_path)])

    assert exit_code == 0
    assert "0" in output_text


def test_count_passes_while_the_backlog_sits_under_the_threshold(
    tmp_path: Path,
) -> None:
    record_followup_finding(
        tmp_path, FollowupFinding("code-rules", "run.py", "one smell", "code-rules/x")
    )

    exit_code, output_text = run_command(["count", "--repository-root", str(tmp_path)])

    assert exit_code == 0
    assert "1" in output_text


def test_count_escalates_once_the_backlog_passes_the_threshold(
    tmp_path: Path,
) -> None:
    for each_index in range(FOLLOWUP_BACKLOG_THRESHOLD + 1):
        record_followup_finding(
            tmp_path,
            FollowupFinding(
                "code-rules",
                f"run{each_index}.py",
                "one smell",
                f"code-rules/x{each_index}",
            ),
        )

    exit_code, output_text = run_command(["count", "--repository-root", str(tmp_path)])

    assert exit_code == BACKLOG_EXCEEDED_EXIT_CODE
    assert str(FOLLOWUP_BACKLOG_THRESHOLD) in output_text


def test_list_names_the_check_behind_each_finding(tmp_path: Path) -> None:
    record_followup_finding(
        tmp_path,
        FollowupFinding(
            "code-rules",
            "run.py",
            "one smell",
            "code-rules/constant-outside-config",
            "smell",
            "f00dcafe",
        ),
    )

    _, output_text = run_command(["list", "--repository-root", str(tmp_path)])

    assert "code-rules/constant-outside-config" in output_text
    assert "f00dcafe" in output_text
