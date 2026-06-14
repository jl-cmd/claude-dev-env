"""Tests for render_report.py against the real wf_881252e6-700 fixture."""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import render_report

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "wf_run"
FIXTURE_JOURNAL = FIXTURE_DIR / "workflows" / "wf_881252e6-700.json"

EXPECTED_TOTAL_FINDINGS = 15
EXPECTED_FIX_COMMIT_COUNT = 2
EXPECTED_GENERATED_DATE = "2026-06-13"
RETURN_TYPE_ISSUE_COUNT = 7


def _render_cli(journal_path: Path, out_path: Path) -> subprocess.CompletedProcess[str]:
    """Run the render_report CLI against a journal and return the completed process."""
    render_script = Path(__file__).resolve().parent / "render_report.py"
    return subprocess.run(
        [
            sys.executable,
            str(render_script),
            "--journal",
            str(journal_path),
            "--out",
            str(out_path),
            "--pr",
            "example-owner/example-repo#211",
            "--final-sha",
            "7c2f420c4d5b7c83aa47f93d99a0f1420e3373c4",
            "--rounds",
            "4",
            "--repo",
            ".",
        ],
        capture_output=True,
        text=True,
    )


def _copy_run_tree_without_summary_entry(destination_root: Path) -> Path:
    """Copy the fixture run tree, dropping the convergence-summary workflowProgress entry.

    Returns the path to the copied journal whose summarizer entry has been removed.
    """
    shutil.copytree(FIXTURE_DIR, destination_root)
    journal_destination = destination_root / "workflows" / FIXTURE_JOURNAL.name
    journal = json.loads(journal_destination.read_text(encoding="utf-8"))
    journal["workflowProgress"] = [
        each_entry
        for each_entry in journal["workflowProgress"]
        if each_entry.get("label") != render_report.LABEL_CONVERGENCE_SUMMARY
    ]
    journal_destination.write_text(json.dumps(journal, indent=2), encoding="utf-8")
    return journal_destination


def test_load_run_data_aggregate_counts() -> None:
    """Should parse the fixture journal and transcripts into correct aggregate counts."""
    run_data = render_report.load_run_data(FIXTURE_JOURNAL)

    assert run_data.total_finding_count == EXPECTED_TOTAL_FINDINGS
    assert run_data.fix_commit_count == EXPECTED_FIX_COMMIT_COUNT
    assert run_data.generated_date == EXPECTED_GENERATED_DATE
    assert len(run_data.all_distinct_findings) == EXPECTED_TOTAL_FINDINGS


def test_load_run_data_parses_convergence_summary() -> None:
    """Should locate the convergence-summary entry and parse its StructuredOutput."""
    run_data = render_report.load_run_data(FIXTURE_JOURNAL)

    assert run_data.convergence_summary is not None
    verdict_line = run_data.convergence_summary["verdictLine"]
    issue_classes = run_data.convergence_summary["issueClasses"]
    assert isinstance(verdict_line, str) and verdict_line
    assert isinstance(issue_classes, list) and len(issue_classes) == 3


def test_load_run_data_carries_category_on_findings() -> None:
    """Should default each finding's category to 'bug' when the raw dict omits it."""
    run_data = render_report.load_run_data(FIXTURE_JOURNAL)

    assert all(
        each_finding.category == render_report.CATEGORY_BUG
        for each_finding in run_data.all_distinct_findings
    )


def test_cli_renders_verdict_banner_and_grouped_table(tmp_path: Path) -> None:
    """Should render a verdict banner and a grouped issue-class table from the summary."""
    out_path = tmp_path / "report.html"

    completed = _render_cli(FIXTURE_JOURNAL, out_path)

    assert completed.returncode == 0, f"CLI failed:\n{completed.stderr}"
    assert completed.stdout.strip() == str(out_path)
    assert out_path.exists(), "Output HTML file was not written"

    html_content = out_path.read_text(encoding="utf-8")
    assert "PR #211 Convergence Summary" in html_content
    assert 'class="verdict-banner' in html_content
    assert 'class="verdict-pill' in html_content
    assert 'class="issue-table"' in html_content
    assert "Tests did not declare their return type" in html_content
    assert "7c2f420c" in html_content


def test_cli_collapses_seven_return_type_findings_into_one_row(tmp_path: Path) -> None:
    """Should render the seven return-type findings as one table row carrying a count of 7."""
    out_path = tmp_path / "report-row.html"

    completed = _render_cli(FIXTURE_JOURNAL, out_path)
    assert completed.returncode == 0, f"CLI failed:\n{completed.stderr}"

    html_content = out_path.read_text(encoding="utf-8")
    return_type_row_count = html_content.count(
        "Tests did not declare their return type"
    )
    assert return_type_row_count == 1, (
        f"Expected the return-type class to appear in exactly one row, "
        f"found it {return_type_row_count} times"
    )
    assert f"&times;{RETURN_TYPE_ISSUE_COUNT}" in html_content


def test_cli_default_view_has_no_charts_or_raw_jargon(tmp_path: Path) -> None:
    """Should render no chart markup and keep raw guideline jargon out of the default view."""
    out_path = tmp_path / "report-clean.html"

    completed = _render_cli(FIXTURE_JOURNAL, out_path)
    assert completed.returncode == 0, f"CLI failed:\n{completed.stderr}"

    html_content = out_path.read_text(encoding="utf-8")
    for chart_marker in ("bar-row", "bar-fill", "chart-card", "chart-title"):
        assert chart_marker not in html_content, (
            f"Chart markup {chart_marker!r} leaked into the rendered report"
        )

    appendix_start = html_content.index('<details class="appendix"')
    default_view = html_content[:appendix_start]
    assert "CodingGuidelineID" not in default_view, (
        "Raw guideline jargon leaked into the default (non-appendix) view"
    )


def test_cli_includes_collapsed_appendix(tmp_path: Path) -> None:
    """Should include a collapsed details appendix listing every distinct finding."""
    out_path = tmp_path / "report-appendix.html"

    completed = _render_cli(FIXTURE_JOURNAL, out_path)
    assert completed.returncode == 0, f"CLI failed:\n{completed.stderr}"

    html_content = out_path.read_text(encoding="utf-8")
    assert '<details class="appendix"' in html_content
    assert f"Raw findings ({EXPECTED_TOTAL_FINDINGS})" in html_content
    assert "src/exports/tests/test_resume_skip_export.py:35" in html_content


def test_cli_degraded_layout_when_summary_entry_absent(tmp_path: Path) -> None:
    """Should render a valid, chart-free degraded layout when no summarizer entry exists."""
    run_root = tmp_path / "wf_run_no_summary"
    journal_destination = _copy_run_tree_without_summary_entry(run_root)

    out_path = tmp_path / "report-degraded.html"
    completed = _render_cli(journal_destination, out_path)

    assert completed.returncode == 0, f"CLI failed:\n{completed.stderr}"
    html_content = out_path.read_text(encoding="utf-8")

    assert "PR #211 Convergence Summary" in html_content
    assert 'class="verdict-banner' not in html_content
    assert 'class="issue-table"' not in html_content
    assert 'class="group-list"' in html_content
    assert 'class="rollup"' in html_content
    assert '<details class="appendix"' in html_content
    for chart_marker in ("bar-row", "bar-fill", "chart-card"):
        assert chart_marker not in html_content


def test_html_contains_no_hedging_words(tmp_path: Path) -> None:
    """Should produce HTML with no hedging language anywhere in the rendered narrative."""
    out_path = tmp_path / "report-hedge.html"

    completed = _render_cli(FIXTURE_JOURNAL, out_path)
    assert completed.returncode == 0, f"CLI failed:\n{completed.stderr}"

    html_content = out_path.read_text(encoding="utf-8")
    all_hedging_words = [
        "could",
        "might",
        "would",
        "should",
        "likely",
        "probably",
        "appears",
        "seems",
    ]
    for each_word in all_hedging_words:
        pattern = re.compile(r"\b" + re.escape(each_word) + r"\b", re.IGNORECASE)
        assert not pattern.search(html_content), (
            f"Hedging word {each_word!r} found in rendered HTML"
        )


def test_extract_structured_output_returns_last_tool_input(tmp_path: Path) -> None:
    """Should return the input of the last StructuredOutput tool_use in the transcript."""
    transcript_path = tmp_path / "agent-stream.jsonl"
    earlier_line = json.dumps(
        {
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": render_report.STRUCTURED_OUTPUT_TOOL_NAME,
                        "input": {"newSha": "aaaa1111", "pushed": False},
                    }
                ]
            }
        }
    )
    later_line = json.dumps(
        {
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": render_report.STRUCTURED_OUTPUT_TOOL_NAME,
                        "input": {"newSha": "bbbb2222", "pushed": True},
                    }
                ]
            }
        }
    )
    transcript_path.write_text(
        earlier_line + "\n" + later_line + "\n", encoding="utf-8"
    )

    extracted = render_report._extract_structured_output(transcript_path)

    assert extracted == {"newSha": "bbbb2222", "pushed": True}


def test_extract_structured_output_returns_none_on_missing_file(tmp_path: Path) -> None:
    """Should return None when the transcript file does not exist."""
    missing_path = tmp_path / "does-not-exist.jsonl"

    extracted = render_report._extract_structured_output(missing_path)

    assert extracted is None


def test_fix_record_carries_summary_text() -> None:
    """Should read the fix agent's summary field into the FixRecord."""
    fix_record = render_report._parse_fix_record(
        {"newSha": "abcd1234", "pushed": True, "summary": "renamed and annotated"},
        round_number=1,
        base_sha="base",
    )

    assert fix_record.summary == "renamed and annotated"


def test_render_verdict_banner_uses_deferred_pill_when_class_deferred() -> None:
    """Should mark the banner deferred when any issue class carries a deferred status."""
    convergence_summary = {
        "verdictLine": "Converged with one deferred class.",
        "issueClasses": [
            {
                "plainName": "A deferred standard",
                "count": 1,
                "severity": "P2",
                "category": "code-standard",
                "status": "deferred",
                "whatItWas": "A standard left for a follow-up.",
            }
        ],
    }

    banner_html = render_report._render_verdict_banner(convergence_summary)

    assert "verdict-banner deferred" in banner_html
    assert render_report.VERDICT_PILL_LABEL_DEFERRED in banner_html


def test_render_issue_class_table_orders_bug_rows_before_code_standard() -> None:
    """Should place bug rows ahead of code-standard rows in the rendered table."""
    convergence_summary = {
        "verdictLine": "Converged.",
        "issueClasses": [
            {
                "plainName": "A standard slip",
                "count": 3,
                "severity": "P2",
                "category": "code-standard",
                "status": "fixed",
                "whatItWas": "A style rule.",
            },
            {
                "plainName": "A real defect",
                "count": 1,
                "severity": "P0",
                "category": "bug",
                "status": "fixed",
                "whatItWas": "A crash.",
            },
        ],
    }

    table_html = render_report._render_issue_class_table(convergence_summary)

    assert table_html.index("A real defect") < table_html.index("A standard slip")


def _write_structured_output_transcript(
    transcript_path: Path, tool_input: dict[str, object]
) -> None:
    """Write a one-line agent transcript carrying a single StructuredOutput tool_use."""
    line = json.dumps(
        {
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": render_report.STRUCTURED_OUTPUT_TOOL_NAME,
                        "input": tool_input,
                    }
                ]
            }
        }
    )
    transcript_path.write_text(line + "\n", encoding="utf-8")


def test_base_sha_resets_each_round_when_prior_fix_transcript_missing(
    tmp_path: Path,
) -> None:
    """Should bind each round's fix base sha to that round's own head, never a prior round's."""
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()

    round_one_head = "1111111111111111111111111111111111111111"
    round_two_head = "2222222222222222222222222222222222222222"

    round_one_gate_id = "round-one-gate"
    round_two_gate_id = "round-two-gate"
    round_two_fix_id = "round-two-fix"

    _write_structured_output_transcript(
        agents_dir / f"agent-{round_one_gate_id}.jsonl",
        {"sha": round_one_head, "clean": False, "findings": []},
    )
    _write_structured_output_transcript(
        agents_dir / f"agent-{round_two_gate_id}.jsonl",
        {"sha": round_two_head, "clean": False, "findings": []},
    )
    _write_structured_output_transcript(
        agents_dir / f"agent-{round_two_fix_id}.jsonl",
        {"newSha": round_two_head, "pushed": True, "resolvedWithoutCommit": False},
    )

    progress_entries: list[dict] = [
        {"label": render_report.LABEL_RESOLVE_HEAD, "agentId": "round-one-resolve"},
        {"label": render_report.LABEL_COPILOT_GATE, "agentId": round_one_gate_id},
        {"label": render_report.LABEL_PREFIX_FIX + "copilot", "agentId": "missing-fix"},
        {"label": render_report.LABEL_RESOLVE_HEAD, "agentId": "round-two-resolve"},
        {"label": render_report.LABEL_COPILOT_GATE, "agentId": round_two_gate_id},
        {
            "label": render_report.LABEL_PREFIX_FIX + "copilot",
            "agentId": round_two_fix_id,
        },
    ]

    _all_findings, fix_by_round = render_report._parse_progress_entries(
        progress_entries, agents_dir
    )

    assert fix_by_round[2].base_sha == round_two_head, (
        "Round 2 fix recorded a stale base sha leaked from round 1; "
        f"expected {round_two_head}, got {fix_by_round[2].base_sha}"
    )


def test_robustness_with_missing_transcripts(tmp_path: Path) -> None:
    """Should exit 0 and render a chart-free report when no agent transcripts exist."""
    run_root = tmp_path / "wf_run"
    journal_destination = run_root / "workflows" / FIXTURE_JOURNAL.name
    journal_destination.parent.mkdir(parents=True)
    shutil.copy(FIXTURE_JOURNAL, journal_destination)

    run_id = FIXTURE_JOURNAL.stem
    empty_agents_dir = run_root / "subagents" / "workflows" / run_id
    empty_agents_dir.mkdir(parents=True)

    out_path = tmp_path / "report-robust.html"
    completed = _render_cli(journal_destination, out_path)

    assert completed.returncode == 0, (
        f"Render failed despite missing transcripts:\n{completed.stderr}"
    )

    html_content = out_path.read_text(encoding="utf-8")
    assert "PR #211 Convergence Summary" in html_content
    assert "No findings were caught during the run." in html_content
    for chart_marker in ("bar-row", "bar-fill", "chart-card"):
        assert chart_marker not in html_content
