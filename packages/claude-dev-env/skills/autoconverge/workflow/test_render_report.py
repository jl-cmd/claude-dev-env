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
EXPECTED_ROUND_COUNT = 4


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
        ],
        capture_output=True,
        text=True,
    )


def test_rendered_report_defines_every_referenced_css_class(tmp_path: Path) -> None:
    """Every class the rendered report markup references resolves to a CSS selector.

    Renders the report from the findings fixture so the raw-findings appendix is
    present, then asserts no class attribute names a style the stylesheet omits,
    keeping the report markup and HTML_STYLE_BLOCK from drifting apart.
    """
    out_path = tmp_path / "report.html"
    completed = _render_cli(FIXTURE_JOURNAL, out_path)
    assert completed.returncode == 0, f"CLI failed:\n{completed.stderr}"
    html_content = out_path.read_text(encoding="utf-8")

    style_match = re.search(r"<style>(.*?)</style>", html_content, re.DOTALL)
    assert style_match is not None
    defined_classes = set(re.findall(r"\.([A-Za-z][\w-]*)", style_match.group(1)))
    referenced_classes = {
        each_name
        for attribute_value in re.findall(r'class="([^"]*)"', html_content)
        for each_name in attribute_value.split()
    }

    orphan_classes = referenced_classes - defined_classes
    assert not orphan_classes, f"classes referenced but undefined: {sorted(orphan_classes)}"


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


def test_cli_renders_verdict_banner_with_python_computed_vsub(tmp_path: Path) -> None:
    """Should render the verdict banner with verdictLine and a Python-computed vsub."""
    out_path = tmp_path / "report.html"

    completed = _render_cli(FIXTURE_JOURNAL, out_path)

    assert completed.returncode == 0, f"CLI failed:\n{completed.stderr}"
    assert completed.stdout.strip() == str(out_path)
    assert out_path.exists(), "Output HTML file was not written"

    html_content = out_path.read_text(encoding="utf-8")
    assert "PR #211 Convergence Summary" in html_content
    assert 'class="verdict"' in html_content
    assert 'class="vtext"' in html_content
    assert "Converged in 4 rounds; 3 distinct issue classes were caught and fixed." in (
        html_content
    )
    assert 'class="vsub"' in html_content
    assert "2 fix commits" in html_content
    assert "final commit 7c2f420c" in html_content


def test_cli_renders_scorecard_with_caught_rounds_and_zero_remaining(
    tmp_path: Path,
) -> None:
    """Should render an at-a-glance scorecard: findings caught, rounds, and zero left."""
    out_path = tmp_path / "report-scorecard.html"

    completed = _render_cli(FIXTURE_JOURNAL, out_path)
    assert completed.returncode == 0, f"CLI failed:\n{completed.stderr}"

    html_content = out_path.read_text(encoding="utf-8")
    assert 'class="scorecard"' in html_content
    assert 'class="stat good"' in html_content
    assert f'<div class="stat-num">{EXPECTED_TOTAL_FINDINGS}</div>' in html_content
    assert f'<div class="stat-num">{EXPECTED_ROUND_COUNT}</div>' in html_content
    assert '<div class="stat-num">0</div>' in html_content
    assert ">caught</div>" in html_content
    assert ">rounds</div>" in html_content
    assert ">left</div>" in html_content


def test_render_issue_class_heading_carries_a_category_icon() -> None:
    """Should prefix the plain name with the icon matching the issue category."""
    bug_heading = render_report._render_issue_class_heading(
        {"plainName": "A plain symptom", "count": 2, "category": "bug"}
    )
    assert 'class="bug-title"' in bug_heading
    assert 'class="bug-icon"' in bug_heading
    assert render_report.ISSUE_ICON_BY_CATEGORY["bug"] in bug_heading

    standard_heading = render_report._render_issue_class_heading(
        {"plainName": "A standard symptom", "count": 1, "category": "code-standard"}
    )
    assert render_report.ISSUE_ICON_BY_CATEGORY["code-standard"] in standard_heading


def test_render_issue_class_heading_uses_default_icon_for_unknown_category() -> None:
    """Should fall back to the default icon when the category has no mapped icon."""
    heading = render_report._render_issue_class_heading(
        {"plainName": "An unmapped symptom", "count": 1, "category": "mystery"}
    )
    assert render_report.DEFAULT_ISSUE_ICON in heading


def test_cli_renders_problem_and_fix_scene_cards(tmp_path: Path) -> None:
    """Should draw problem and fix scene cards with trigger, result, and caption."""
    out_path = tmp_path / "report-scenes.html"

    completed = _render_cli(FIXTURE_JOURNAL, out_path)
    assert completed.returncode == 0, f"CLI failed:\n{completed.stderr}"

    html_content = out_path.read_text(encoding="utf-8")
    assert 'class="pf-grid"' in html_content
    assert 'class="pf problem"' in html_content
    assert 'class="pf fix"' in html_content
    assert "export stops at batch 90 of 100" in html_content
    assert "starts again at batch 1" in html_content
    assert "continues at batch 91" in html_content
    assert 'class="res-bad"' in html_content
    assert 'class="res-good"' in html_content
    assert "began again" in html_content


def test_render_issue_class_panels_for_each_medium() -> None:
    """Should draw before/after panels: a code panel and a terminal panel per medium."""
    convergence_summary = {
        "verdictLine": "Converged.",
        "problemScenes": [],
        "fixScenes": [],
        "issueClasses": [
            {
                "plainName": "A missing return type",
                "count": 3,
                "severity": "P2",
                "category": "code-standard",
                "status": "fixed",
                "cause": "Tests did not declare their return type.",
                "medium": "code",
                "beforeLines": ["def test_x():"],
                "afterLines": ["def test_x() -> None:"],
            },
            {
                "plainName": "An install that did nothing",
                "count": 1,
                "severity": "P1",
                "category": "bug",
                "status": "fixed",
                "cause": "The command skipped the install.",
                "medium": "terminal",
                "beforeLines": ["~ $ install", "(no output)"],
                "afterLines": ["~ $ install", "Installed."],
            },
        ],
    }

    panels_html = render_report._render_issue_class_panels(convergence_summary)

    assert 'class="code-panel"' in panels_html
    assert "def test_x() -&gt; None:" in panels_html
    assert 'class="terminal"' in panels_html
    assert 'class="term-bar"' in panels_html
    assert "Installed." in panels_html
    assert 'class="term-grid"' in panels_html
    assert 'class="bug-head"' in panels_html
    assert "A missing return type" in panels_html
    assert "An install that did nothing" in panels_html
    assert "3 findings" in panels_html
    assert "1 finding" in panels_html


def test_render_issue_class_panels_draws_text_panel_for_text_medium() -> None:
    """Should draw a text panel holding the supplied lines when the medium is text."""
    convergence_summary = {
        "verdictLine": "Converged.",
        "problemScenes": [],
        "fixScenes": [],
        "issueClasses": [
            {
                "plainName": "A plain-text symptom",
                "count": 1,
                "severity": "P2",
                "category": "bug",
                "status": "fixed",
                "cause": "A grounded cause sentence.",
                "medium": "text",
                "beforeLines": ["pages reloaded every visit"],
                "afterLines": ["pages reuse the saved copy"],
            }
        ],
    }

    panels_html = render_report._render_issue_class_panels(convergence_summary)

    assert 'class="text-panel"' in panels_html
    assert "pages reloaded every visit" in panels_html
    assert "pages reuse the saved copy" in panels_html
    assert 'class="terminal"' not in panels_html
    assert 'class="code-panel"' not in panels_html


def test_cli_renders_cause_line_with_severity_parenthetical(tmp_path: Path) -> None:
    """Should render a cause line carrying the plain cause and a muted parenthetical."""
    out_path = tmp_path / "report-cause.html"

    completed = _render_cli(FIXTURE_JOURNAL, out_path)
    assert completed.returncode == 0, f"CLI failed:\n{completed.stderr}"

    html_content = out_path.read_text(encoding="utf-8")
    assert 'class="cause"' in html_content
    assert "which the project&#x27;s type checker wants" in html_content
    assert "P2" in html_content
    assert "code standard" in html_content
    assert "&times;7" in html_content
    assert "fixed" in html_content


def test_render_issue_class_panels_omitted_when_lines_empty() -> None:
    """Should draw only the cause line when both before and after lines are empty."""
    convergence_summary = {
        "verdictLine": "Converged.",
        "problemScenes": [],
        "fixScenes": [],
        "issueClasses": [
            {
                "plainName": "A cause-only class",
                "count": 1,
                "severity": "P2",
                "category": "code-standard",
                "status": "fixed",
                "cause": "Nothing visual to show.",
                "medium": "text",
                "beforeLines": [],
                "afterLines": [],
            }
        ],
    }

    panels_html = render_report._render_issue_class_panels(convergence_summary)

    assert 'class="term-grid"' not in panels_html
    assert 'class="bug-head"' in panels_html
    assert "A cause-only class" in panels_html
    assert 'class="cause"' in panels_html
    assert "Nothing visual to show." in panels_html


def test_render_issue_class_panels_clean_state_when_no_classes() -> None:
    """Should render a clean-state line, not an empty section, when no classes exist."""
    convergence_summary = {
        "verdictLine": "Converged with no issues caught.",
        "problemScenes": [],
        "fixScenes": [],
        "issueClasses": [],
    }

    panels_html = render_report._render_issue_class_panels(convergence_summary)

    assert 'class="term-grid"' not in panels_html
    assert "No issues were caught" in panels_html


def test_cli_merges_run_stats_lead_into_caught_section(tmp_path: Path) -> None:
    """Should lead the caught section with run stats and omit any timeline section."""
    out_path = tmp_path / "report-caught-lead.html"

    completed = _render_cli(FIXTURE_JOURNAL, out_path)
    assert completed.returncode == 0, f"CLI failed:\n{completed.stderr}"

    html_content = out_path.read_text(encoding="utf-8")
    assert "What was caught" in html_content
    assert "3 bug classes" in html_content
    assert "15 findings in all" in html_content
    assert "caught and fixed across 4 rounds" in html_content
    assert "2 fix commits" in html_content
    assert "How it converged" not in html_content
    assert 'class="timeline"' not in html_content
    assert 'class="tstep' not in html_content


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
    """Should render the timeline and appendix but no scene, table, or rollup markup."""
    run_root = tmp_path / "wf_run_no_summary"
    journal_destination = _copy_run_tree_without_summary_entry(run_root)

    out_path = tmp_path / "report-degraded.html"
    completed = _render_cli(journal_destination, out_path)

    assert completed.returncode == 0, f"CLI failed:\n{completed.stderr}"
    html_content = out_path.read_text(encoding="utf-8")

    assert "PR #211 Convergence Summary" in html_content
    assert 'class="timeline"' not in html_content
    assert "distinct findings across 4 rounds" in html_content
    assert '<details class="appendix"' in html_content
    assert 'class="pf-grid"' not in html_content
    assert 'class="issue-table"' not in html_content
    assert 'class="rollup"' not in html_content
    assert 'class="pr-summary"' not in html_content


def test_cli_injects_summary_from_file_bypassing_transcripts(tmp_path: Path) -> None:
    """Should render the full summary body from --summary-file when no summary transcript exists."""
    run_root = tmp_path / "wf_run_inject"
    journal_destination = _copy_run_tree_without_summary_entry(run_root)

    summary = {
        "prProblem": "PhotoSync stopped backing up photos after an account switch.",
        "prFix": "It re-checks the account on each backup, so a switch never halts backups.",
        "problemScenes": [],
        "fixScenes": [],
        "verdictLine": "Converged in 4 rounds; every class is fixed.",
        "issueClasses": [
            {
                "plainName": "An injected class the transcript never carried",
                "count": 2,
                "severity": "P1",
                "category": "bug",
                "status": "fixed",
                "cause": "A concrete grounded cause sentence.",
                "medium": "text",
                "beforeLines": [],
                "afterLines": [],
            }
        ],
    }
    summary_path = tmp_path / "summary.json"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    out_path = tmp_path / "report-injected.html"
    render_script = Path(__file__).resolve().parent / "render_report.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(render_script),
            "--journal",
            str(journal_destination),
            "--out",
            str(out_path),
            "--pr",
            "example-owner/example-repo#211",
            "--final-sha",
            "7c2f420c4d5b7c83aa47f93d99a0f1420e3373c4",
            "--rounds",
            "4",
            "--summary-file",
            str(summary_path),
        ],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, f"CLI failed:\n{completed.stderr}"
    html_content = out_path.read_text(encoding="utf-8")
    assert 'class="verdict"' in html_content
    assert "Converged in 4 rounds; every class is fixed." in html_content
    assert "An injected class the transcript never carried" in html_content
    assert 'class="pf-grid"' in html_content
    assert f"Raw findings ({EXPECTED_TOTAL_FINDINGS})" in html_content
    assert "https://github.com/example-owner/example-repo/pull/211" not in html_content


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
        base_sha="base",
    )

    assert fix_record.summary == "renamed and annotated"


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


def _render_cli_with_summary_file(
    journal_path: Path, out_path: Path, summary_path: Path
) -> subprocess.CompletedProcess[str]:
    """Run the render CLI with an injected --summary-file and return the process."""
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
            "--summary-file",
            str(summary_path),
        ],
        capture_output=True,
        text=True,
    )


def test_cli_renders_when_issue_class_count_is_null(tmp_path: Path) -> None:
    """Should exit 0 and show a zero count when an issue class carries count: null."""
    run_root = tmp_path / "wf_run_null_count"
    journal_destination = _copy_run_tree_without_summary_entry(run_root)

    summary = {
        "prProblem": "A problem.",
        "prFix": "A fix.",
        "problemScenes": [],
        "fixScenes": [],
        "verdictLine": "Converged.",
        "issueClasses": [
            {
                "plainName": "A class with a null count",
                "count": None,
                "severity": "P2",
                "category": "bug",
                "status": "fixed",
                "cause": "A grounded cause.",
                "medium": "text",
                "beforeLines": [],
                "afterLines": [],
            }
        ],
    }
    summary_path = tmp_path / "summary-null-count.json"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    out_path = tmp_path / "report-null-count.html"
    completed = _render_cli_with_summary_file(
        journal_destination, out_path, summary_path
    )

    assert completed.returncode == 0, f"CLI crashed on null count:\n{completed.stderr}"
    html_content = out_path.read_text(encoding="utf-8")
    assert "A class with a null count" in html_content
    assert "0 findings" in html_content
    assert "&times;0" in html_content


def test_cli_renders_when_issue_class_count_is_non_numeric(tmp_path: Path) -> None:
    """Should exit 0 and show a zero count when an issue class count is a bad string."""
    run_root = tmp_path / "wf_run_bad_count"
    journal_destination = _copy_run_tree_without_summary_entry(run_root)

    summary = {
        "prProblem": "A problem.",
        "prFix": "A fix.",
        "problemScenes": [],
        "fixScenes": [],
        "verdictLine": "Converged.",
        "issueClasses": [
            {
                "plainName": "A class with a non-numeric count",
                "count": "x",
                "severity": "P2",
                "category": "bug",
                "status": "fixed",
                "cause": "A grounded cause.",
                "medium": "text",
                "beforeLines": [],
                "afterLines": [],
            }
        ],
    }
    summary_path = tmp_path / "summary-bad-count.json"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    out_path = tmp_path / "report-bad-count.html"
    completed = _render_cli_with_summary_file(
        journal_destination, out_path, summary_path
    )

    assert completed.returncode == 0, (
        f"CLI crashed on non-numeric count:\n{completed.stderr}"
    )
    html_content = out_path.read_text(encoding="utf-8")
    assert "A class with a non-numeric count" in html_content
    assert "0 findings" in html_content


def test_cli_renders_degraded_body_when_summary_is_a_list(tmp_path: Path) -> None:
    """Should render the degraded layout and exit 0 when --summary-file holds a list."""
    run_root = tmp_path / "wf_run_list_summary"
    journal_destination = _copy_run_tree_without_summary_entry(run_root)

    summary_path = tmp_path / "summary-list.json"
    summary_path.write_text(json.dumps([]), encoding="utf-8")

    out_path = tmp_path / "report-list-summary.html"
    completed = _render_cli_with_summary_file(
        journal_destination, out_path, summary_path
    )

    assert completed.returncode == 0, (
        f"CLI crashed on a list summary:\n{completed.stderr}"
    )
    html_content = out_path.read_text(encoding="utf-8")
    assert "distinct findings across 4 rounds" in html_content
    assert 'class="pf-grid"' not in html_content


def test_cli_renders_degraded_body_when_summary_is_a_scalar(tmp_path: Path) -> None:
    """Should render the degraded layout and exit 0 when --summary-file holds a scalar."""
    run_root = tmp_path / "wf_run_scalar_summary"
    journal_destination = _copy_run_tree_without_summary_entry(run_root)

    summary_path = tmp_path / "summary-scalar.json"
    summary_path.write_text(json.dumps(5), encoding="utf-8")

    out_path = tmp_path / "report-scalar-summary.html"
    completed = _render_cli_with_summary_file(
        journal_destination, out_path, summary_path
    )

    assert completed.returncode == 0, (
        f"CLI crashed on a scalar summary:\n{completed.stderr}"
    )
    html_content = out_path.read_text(encoding="utf-8")
    assert "distinct findings across 4 rounds" in html_content
    assert 'class="pf-grid"' not in html_content


def test_is_summary_structurally_valid_false_for_non_dict_summary() -> None:
    """Should return False for a list, string, or scalar summary, never raising."""
    assert render_report._is_summary_structurally_valid([]) is False
    assert render_report._is_summary_structurally_valid("str") is False
    assert render_report._is_summary_structurally_valid(5) is False


def test_cli_rejects_orphaned_repo_argument(tmp_path: Path) -> None:
    """Should reject --repo with a usage error, proving the flag is no longer declared."""
    render_script = Path(__file__).resolve().parent / "render_report.py"
    out_path = tmp_path / "report-repo-rejected.html"
    completed = subprocess.run(
        [
            sys.executable,
            str(render_script),
            "--journal",
            str(FIXTURE_JOURNAL),
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

    assert completed.returncode != 0
    assert "unrecognized arguments: --repo" in completed.stderr


def test_robustness_with_missing_transcripts(tmp_path: Path) -> None:
    """Should exit 0 and render the timeline and appendix when no transcripts exist."""
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
    assert 'class="timeline"' not in html_content
    assert 'class="pf-grid"' not in html_content
