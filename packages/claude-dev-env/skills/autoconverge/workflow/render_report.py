"""Render a convergence insights HTML report from an autoconverge workflow journal."""

import argparse
import html
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from autoconverge_report_constants.render_report_constants import (
    BAR_COLOR_ROUND,
    BAR_COLOR_SEVERITY_CRITICAL,
    BAR_COLOR_SEVERITY_MINOR,
    BAR_COLOR_TESTS,
    BAR_COLOR_THEME,
    BAR_FILL_MAX_PERCENT,
    GITHUB_PR_URL_TEMPLATE,
    HTML_DOCTYPE,
    HTML_HEAD_TEMPLATE,
    HTML_STYLE_BLOCK,
    JOURNAL_SIBLING_SUBAGENTS,
    JOURNAL_SIBLING_WORKFLOWS,
    LABEL_COPILOT_GATE,
    LABEL_PREFIX_FIX,
    LABEL_PREFIX_LENS,
    LABEL_RESOLVE_HEAD,
    SEVERITY_BADGE_CLASS_BY_LEVEL,
    SEVERITY_CRITICAL_BUCKET,
    SEVERITY_CRITICAL_LEVELS,
    SEVERITY_MINOR_BUCKET,
    STRUCTURED_OUTPUT_TOOL_NAME,
    TEST_DEFINITION_PATTERN,
    TEST_PATH_GLOBS,
    THEME_FALLBACK,
    THEME_PATH_SEGMENT_COUNT,
)


@dataclass(frozen=True)
class RawFinding:
    """A single finding from a lens or copilot-gate agent result, tagged with round context."""

    file: str
    line: int
    severity: str
    title: str
    detail: str
    round_number: int
    sha: str


@dataclass(frozen=True)
class FixRecord:
    """The structured result of a fix agent, with round and base-sha context attached."""

    new_sha: str
    pushed: bool
    resolved_without_commit: bool
    round_number: int
    base_sha: str


@dataclass(frozen=True)
class PrMetadata:
    """Owner, repo, number, and pre-built URL for the PR being reported on."""

    owner: str
    repo: str
    number: int
    url: str
    final_sha: str
    round_count: int


@dataclass
class RunData:
    """Aggregated metrics parsed from a workflow journal and agent transcripts."""

    generated_date: str
    total_finding_count: int
    critical_finding_count: int
    minor_finding_count: int
    fix_commit_count: int
    tests_added_by_round: dict[int, int]
    finding_count_by_round: dict[int, int]
    finding_count_by_theme: dict[str, int]
    all_critical_findings: list[RawFinding]
    all_minor_findings: list[RawFinding]
    fix_by_round: dict[int, FixRecord]


def _resolve_agents_dir(journal_path: Path) -> Path:
    """Return the directory containing per-agent transcript files for this run.

    Args:
        journal_path: Absolute path to the wf_<runId>.json journal file.

    Returns:
        Path to the subagents/workflows/<runId>/ directory.
    """
    run_id = journal_path.stem
    return (
        journal_path.parent.parent
        / JOURNAL_SIBLING_SUBAGENTS
        / JOURNAL_SIBLING_WORKFLOWS
        / run_id
    )


def _extract_structured_output(transcript_path: Path) -> dict | None:
    """Return the last StructuredOutput tool input from an agent transcript.

    Args:
        transcript_path: Path to an agent-<id>.jsonl file.

    Returns:
        The input dict of the last StructuredOutput tool_use, or None when absent.
    """
    last_input: dict | None = None
    try:
        with transcript_path.open(encoding="utf-8") as transcript_file:
            for each_line in transcript_file:
                last_input = _last_structured_input_in_line(each_line, last_input)
    except OSError:
        return None

    return last_input


def _last_structured_input_in_line(
    transcript_line: str, prior_input: dict | None
) -> dict | None:
    """Return the StructuredOutput input on a transcript line, else the prior input.

    Args:
        transcript_line: One raw JSON line from an agent transcript.
        prior_input: The last StructuredOutput input seen before this line.

    Returns:
        The input dict of the last StructuredOutput tool_use on this line, or
        prior_input when the line carries none.
    """
    try:
        parsed = json.loads(transcript_line)
    except (ValueError, json.JSONDecodeError):
        return prior_input

    message = parsed.get("message") if isinstance(parsed, dict) else None
    content_list = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content_list, list):
        return prior_input

    latest_input = prior_input
    for each_block in content_list:
        if not isinstance(each_block, dict):
            continue
        if (
            each_block.get("type") == "tool_use"
            and each_block.get("name") == STRUCTURED_OUTPUT_TOOL_NAME
            and isinstance(each_block.get("input"), dict)
        ):
            latest_input = each_block["input"]

    return latest_input


def _derive_theme(file_path: str) -> str:
    """Return the first two slash-separated segments of a file path.

    Args:
        file_path: A relative file path string from a finding.

    Returns:
        A theme string like 'src/exports', the whole path when fewer than two
        segments exist, or THEME_FALLBACK when the path is empty.
    """
    if not file_path:
        return THEME_FALLBACK
    segments = file_path.split("/")
    return "/".join(segments[:THEME_PATH_SEGMENT_COUNT])


def _count_tests_added(base_sha: str, new_sha: str, repo_path: Path) -> int:
    """Count new test definitions introduced between two commits.

    Args:
        base_sha: The commit sha the round reviewed.
        new_sha: The sha produced by the fix commit.
        repo_path: Path to the git repository root.

    Returns:
        Number of newly added test-function definitions; 0 on any git error.
    """
    diff_command = [
        "git",
        "-C",
        str(repo_path),
        "diff",
        f"{base_sha}..{new_sha}",
        "--",
        *TEST_PATH_GLOBS,
    ]
    try:
        completed = subprocess.run(
            diff_command,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.SubprocessError, OSError):
        return 0

    diff_text = completed.stdout
    test_def_pattern = re.compile(TEST_DEFINITION_PATTERN, re.MULTILINE)

    return len(test_def_pattern.findall(diff_text))


def _build_dedup_key(file_path: str, line: int, title: str) -> tuple[str, int, str]:
    """Return a deduplication key for a finding.

    Args:
        file_path: The file field from the finding.
        line: The line number from the finding.
        title: The title field from the finding.

    Returns:
        A tuple of (file, line, lowercased_title).
    """
    return (file_path, line, title.lower())


def _parse_finding_from_dict(raw: dict, round_number: int, sha: str) -> RawFinding:
    """Construct a RawFinding from a raw agent result dict.

    Args:
        raw: The raw finding dict from the agent result.
        round_number: The round this finding belongs to.
        sha: The commit sha this finding was discovered on.

    Returns:
        A RawFinding dataclass instance.
    """
    return RawFinding(
        file=raw.get("file", ""),
        line=raw.get("line", 0),
        severity=raw.get("severity", "P2"),
        title=raw.get("title", ""),
        detail=raw.get("detail", ""),
        round_number=round_number,
        sha=sha,
    )


def _parse_fix_record(
    agent_result: dict, round_number: int, base_sha: str
) -> FixRecord:
    """Construct a FixRecord from a fix agent's structured output.

    Args:
        agent_result: The structured output dict from the fix agent.
        round_number: The round this fix belongs to.
        base_sha: The HEAD sha the round reviewed before fixing.

    Returns:
        A FixRecord dataclass instance.
    """
    return FixRecord(
        new_sha=agent_result.get("newSha", ""),
        pushed=bool(agent_result.get("pushed", False)),
        resolved_without_commit=bool(agent_result.get("resolvedWithoutCommit", False)),
        round_number=round_number,
        base_sha=base_sha,
    )


def _parse_progress_entries(
    progress_entries: list[dict],
    agents_dir: Path,
) -> tuple[list[RawFinding], dict[int, FixRecord]]:
    """Walk workflowProgress in order and collect findings and fix results by round.

    Args:
        progress_entries: The workflowProgress list from the journal.
        agents_dir: Directory containing per-agent .jsonl transcript files.

    Returns:
        A tuple of (all_raw_findings, fix_by_round).
    """
    all_findings: list[RawFinding] = []
    fix_by_round: dict[int, FixRecord] = {}
    current_round = 0
    current_round_base_sha = ""

    for each_entry in progress_entries:
        label: str = each_entry.get("label", "")
        agent_id: str | None = each_entry.get("agentId")

        if label == LABEL_RESOLVE_HEAD:
            current_round += 1
            current_round_base_sha = ""
            continue

        if agent_id is None:
            continue

        transcript_path = agents_dir / f"agent-{agent_id}.jsonl"
        agent_result = _extract_structured_output(transcript_path)
        if agent_result is None:
            continue

        is_lens = label.startswith(LABEL_PREFIX_LENS)
        is_copilot = label == LABEL_COPILOT_GATE
        is_fix = label.startswith(LABEL_PREFIX_FIX)

        if is_lens or is_copilot:
            sha = agent_result.get("sha", "")
            if not current_round_base_sha and sha:
                current_round_base_sha = sha
            raw_findings: list[dict] = agent_result.get("findings", [])
            for each_raw in raw_findings:
                all_findings.append(
                    _parse_finding_from_dict(each_raw, current_round, sha)
                )

        if is_fix:
            fix_by_round[current_round] = _parse_fix_record(
                agent_result, current_round, current_round_base_sha
            )

    return all_findings, fix_by_round


def _dedup_findings(all_findings: list[RawFinding]) -> list[RawFinding]:
    """Deduplicate findings globally by (file, line, lower title), keeping earliest round.

    Args:
        all_findings: All raw findings in discovery order.

    Returns:
        A list of distinct findings with the earliest occurrence retained.
    """
    seen_keys: set[tuple[str, int, str]] = set()
    distinct: list[RawFinding] = []
    for each_finding in all_findings:
        dedup_key = _build_dedup_key(
            each_finding.file, each_finding.line, each_finding.title
        )
        if dedup_key not in seen_keys:
            seen_keys.add(dedup_key)
            distinct.append(each_finding)
    return distinct


def load_run_data(journal_path: Path, repo_path: Path) -> RunData:
    """Parse a workflow journal and its agent transcripts into aggregated metrics.

    Args:
        journal_path: Path to the wf_<runId>.json journal file.
        repo_path: Path to the git repository for counting tests added.

    Returns:
        A RunData instance with all counts and finding lists populated.
    """
    journal = json.loads(journal_path.read_text(encoding="utf-8"))
    timestamp: str = journal.get("timestamp", "")
    generated_date = timestamp[:10] if len(timestamp) >= 10 else ""

    progress_entries: list[dict] = journal.get("workflowProgress", [])
    agents_dir = _resolve_agents_dir(journal_path)

    all_raw_findings, fix_by_round = _parse_progress_entries(
        progress_entries, agents_dir
    )
    distinct_findings = _dedup_findings(all_raw_findings)

    all_critical_findings: list[RawFinding] = []
    all_minor_findings: list[RawFinding] = []
    finding_count_by_round: dict[int, int] = {}
    finding_count_by_theme: dict[str, int] = {}

    for each_finding in distinct_findings:
        severity = each_finding.severity
        round_number = each_finding.round_number
        theme = _derive_theme(each_finding.file)

        if severity in SEVERITY_CRITICAL_LEVELS:
            all_critical_findings.append(each_finding)
        else:
            all_minor_findings.append(each_finding)

        finding_count_by_round[round_number] = (
            finding_count_by_round.get(round_number, 0) + 1
        )
        finding_count_by_theme[theme] = finding_count_by_theme.get(theme, 0) + 1

    fix_commit_count = sum(1 for each_fix in fix_by_round.values() if each_fix.pushed)

    tests_added_by_round: dict[int, int] = {}
    for each_round_number, each_fix in fix_by_round.items():
        if not each_fix.pushed:
            tests_added_by_round[each_round_number] = 0
            continue
        tests_added_by_round[each_round_number] = _count_tests_added(
            each_fix.base_sha,
            each_fix.new_sha,
            repo_path,
        )

    return RunData(
        generated_date=generated_date,
        total_finding_count=len(distinct_findings),
        critical_finding_count=len(all_critical_findings),
        minor_finding_count=len(all_minor_findings),
        fix_commit_count=fix_commit_count,
        tests_added_by_round=tests_added_by_round,
        finding_count_by_round=finding_count_by_round,
        finding_count_by_theme=finding_count_by_theme,
        all_critical_findings=all_critical_findings,
        all_minor_findings=all_minor_findings,
        fix_by_round=fix_by_round,
    )


def _render_bar_row(label: str, bar_value: int, max_value: int, color: str) -> str:
    """Return an HTML .bar-row element for a single chart bar.

    Args:
        label: The text label displayed on the left.
        bar_value: The numeric value for this bar.
        max_value: The maximum value across all bars in this chart.
        color: The CSS hex color for the bar fill.

    Returns:
        An HTML string for one .bar-row.
    """
    fill_width = round(bar_value / max(max_value, 1) * BAR_FILL_MAX_PERCENT, 1)
    escaped_label = html.escape(label)
    return (
        f'<div class="bar-row">'
        f'<span class="bar-label">{escaped_label}</span>'
        f'<div class="bar-track">'
        f'<div class="bar-fill" style="width:{fill_width}%;background:{color};"></div>'
        f"</div>"
        f'<span class="bar-value">{bar_value}</span>'
        f"</div>"
    )


def _render_chart_card(title: str, bar_rows_html: str) -> str:
    """Return an HTML .chart-card wrapping the given bar rows.

    Args:
        title: The chart title displayed in uppercase.
        bar_rows_html: Pre-rendered HTML for all bar rows.

    Returns:
        An HTML string for one .chart-card.
    """
    escaped_title = html.escape(title)
    return (
        f'<div class="chart-card">'
        f'<div class="chart-title">{escaped_title}</div>'
        f"{bar_rows_html}"
        f"</div>"
    )


def _render_severity_chart(critical_count: int, minor_count: int) -> str:
    """Return a severity breakdown chart card.

    Args:
        critical_count: Total critical (P0/P1) findings.
        minor_count: Total minor (P2) findings.

    Returns:
        An HTML .chart-card string.
    """
    max_count = max(critical_count, minor_count, 1)
    rows = _render_bar_row(
        SEVERITY_CRITICAL_BUCKET, critical_count, max_count, BAR_COLOR_SEVERITY_CRITICAL
    ) + _render_bar_row(
        SEVERITY_MINOR_BUCKET, minor_count, max_count, BAR_COLOR_SEVERITY_MINOR
    )
    return _render_chart_card("Findings by severity", rows)


def _render_round_findings_chart(
    round_count: int, finding_count_by_round: dict[int, int]
) -> str:
    """Return a per-round finding count chart card.

    Args:
        round_count: Total number of rounds in the run.
        finding_count_by_round: Mapping of round number to distinct finding count.

    Returns:
        An HTML .chart-card string.
    """
    all_counts = [finding_count_by_round.get(r, 0) for r in range(1, round_count + 1)]
    max_count = max(all_counts + [1])
    rows = "".join(
        _render_bar_row(
            f"Round {r}", finding_count_by_round.get(r, 0), max_count, BAR_COLOR_ROUND
        )
        for r in range(1, round_count + 1)
    )
    return _render_chart_card("Findings by round", rows)


def _render_tests_chart(round_count: int, tests_added_by_round: dict[int, int]) -> str:
    """Return a per-round tests-added chart card.

    Args:
        round_count: Total number of rounds in the run.
        tests_added_by_round: Mapping of round number to tests added count.

    Returns:
        An HTML .chart-card string.
    """
    all_counts = [tests_added_by_round.get(r, 0) for r in range(1, round_count + 1)]
    max_count = max(all_counts + [1])
    rows = "".join(
        _render_bar_row(
            f"Round {r}", tests_added_by_round.get(r, 0), max_count, BAR_COLOR_TESTS
        )
        for r in range(1, round_count + 1)
    )
    return _render_chart_card("Tests added per round", rows)


def _render_theme_chart(finding_count_by_theme: dict[str, int]) -> str:
    """Return a findings-by-theme chart card.

    Args:
        finding_count_by_theme: Mapping of theme string to distinct finding count.

    Returns:
        An HTML .chart-card string.
    """
    sorted_themes = sorted(
        finding_count_by_theme.items(), key=lambda pair: pair[1], reverse=True
    )
    max_count = max((each_count for _, each_count in sorted_themes), default=1)
    rows = "".join(
        _render_bar_row(each_theme, each_count, max_count, BAR_COLOR_THEME)
        for each_theme, each_count in sorted_themes
    )
    return _render_chart_card("Findings by theme", rows)


def _render_fix_block(finding: RawFinding, fix_by_round: dict[int, FixRecord]) -> str:
    """Return the green fix resolution sub-block for a finding card.

    Args:
        finding: The raw finding being described.
        fix_by_round: Mapping of round number to fix record.

    Returns:
        An HTML .bug-fix string describing how the finding was resolved.
    """
    round_number = finding.round_number
    fix_record = fix_by_round.get(round_number)

    if fix_record is None:
        return '<div class="bug-fix"><b>Fix:</b> resolved during convergence.</div>'

    if fix_record.resolved_without_commit:
        return (
            f'<div class="bug-fix"><b>Fix:</b> already resolved at HEAD in round {round_number}; '
            f"threads closed.</div>"
        )

    if not fix_record.new_sha:
        return '<div class="bug-fix"><b>Fix:</b> resolved during convergence.</div>'

    new_sha_short = fix_record.new_sha[:8]
    return (
        f'<div class="bug-fix"><b>Fix:</b> resolved in the round {round_number} fix commit '
        f"<code>{html.escape(new_sha_short)}</code>.</div>"
    )


def _render_bug_card(
    index: int,
    finding: RawFinding,
    fix_by_round: dict[int, FixRecord],
    card_class: str,
) -> str:
    """Return an HTML .bug-card element for one finding.

    Args:
        index: 1-based display index for the card.
        finding: The raw finding to render.
        fix_by_round: Mapping of round number to fix record for the fix sub-block.
        card_class: Either 'crit' or 'minor'.

    Returns:
        An HTML string for one .bug-card.
    """
    severity = finding.severity
    badge_class = SEVERITY_BADGE_CLASS_BY_LEVEL.get(severity, "b-p2")
    escaped_title = html.escape(finding.title)
    escaped_detail = html.escape(finding.detail)
    escaped_file = html.escape(finding.file)
    line_number = finding.line
    round_number = finding.round_number

    fix_block = _render_fix_block(finding, fix_by_round)

    return (
        f'<div class="bug-card {card_class}">'
        f'<div class="bug-head">'
        f'<span class="bug-num">#{index}</span>'
        f'<span class="bug-title">{escaped_title}</span>'
        f'<div class="badges">'
        f'<span class="badge {badge_class}">{html.escape(severity)}</span>'
        f'<span class="badge b-fixed">Fixed</span>'
        f"</div>"
        f"</div>"
        f'<div class="bug-impact">{escaped_detail}</div>'
        f"{fix_block}"
        f'<div class="bug-meta"><code>{escaped_file}</code>:{line_number} · round {round_number}</div>'
        f"</div>"
    )


def _render_stat(label: str, stat_value: int) -> str:
    """Return an HTML .stat block for the summary stats row.

    Args:
        label: The label displayed below the number.
        stat_value: The numeric value to display.

    Returns:
        An HTML string for one .stat element.
    """
    escaped_label = html.escape(label)
    return (
        f'<div class="stat">'
        f'<div class="stat-value">{stat_value}</div>'
        f'<div class="stat-label">{escaped_label}</div>'
        f"</div>"
    )


def _render_finding_cards(
    findings: list[RawFinding],
    fix_by_round: dict[int, FixRecord],
    card_class: str,
) -> str:
    """Return an HTML .bugs container with one .bug-card per finding.

    Args:
        findings: The list of raw findings to render.
        fix_by_round: Mapping of round number to fix record.
        card_class: Either 'crit' or 'minor'.

    Returns:
        An HTML string for the .bugs container, or empty string when findings is empty.
    """
    if not findings:
        return ""
    cards = "".join(
        _render_bug_card(each_index + 1, each_finding, fix_by_round, card_class)
        for each_index, each_finding in enumerate(findings)
    )
    return f'<div class="bugs">{cards}</div>'


def render_report_html(
    run_data: RunData, pr_metadata: PrMetadata, generated_date: str
) -> str:
    """Render the convergence insights report as an HTML string.

    Args:
        run_data: Aggregated metrics from the workflow journal and transcripts.
        pr_metadata: Owner, repo, number, URL, final sha, and round count for the PR.
        generated_date: ISO date string derived from the journal timestamp.

    Returns:
        A complete HTML document string.
    """
    pr_number = pr_metadata.number
    owner = html.escape(pr_metadata.owner)
    repo = html.escape(pr_metadata.repo)
    final_sha_short = pr_metadata.final_sha[:8]
    round_count = pr_metadata.round_count

    total_findings = run_data.total_finding_count
    critical_count = run_data.critical_finding_count
    minor_count = run_data.minor_finding_count
    fix_commit_count = run_data.fix_commit_count
    tests_added_total = sum(run_data.tests_added_by_round.values())

    head_html = HTML_HEAD_TEMPLATE.format(
        pr_number=pr_number,
        style_block=HTML_STYLE_BLOCK,
    )

    subtitle = (
        f'<p class="subtitle">{owner}/{repo} · {total_findings} findings '
        f"across {round_count} rounds · {html.escape(generated_date)}</p>"
    )

    glance_caught = (
        f'<div class="glance-section"><strong>What was caught:</strong> autoconverge ran '
        f"{round_count} rounds and surfaced {total_findings} distinct findings — "
        f"{critical_count} critical, {minor_count} minor.</div>"
    )
    glance_resolution = (
        f'<div class="glance-section"><strong>Resolution:</strong> every finding was fixed '
        f"before the PR was marked ready; {fix_commit_count} fix commits landed.</div>"
    )
    glance_status = (
        f'<div class="glance-section"><strong>Status:</strong> the run converged on commit '
        f"{html.escape(final_sha_short)}.</div>"
    )
    at_a_glance = (
        f'<div class="at-a-glance">'
        f'<div class="glance-title">At a Glance</div>'
        f'<div class="glance-sections">'
        f"{glance_caught}{glance_resolution}{glance_status}"
        f"</div></div>"
    )

    nav_toc = (
        '<nav class="nav-toc">'
        '<a href="#numbers">The numbers</a>'
        '<a href="#critical">Critical findings</a>'
        '<a href="#minor">Minor findings</a>'
        '<a href="#status">Status</a>'
        "</nav>"
    )

    stats_row = (
        '<div class="stats-row">'
        + _render_stat("Findings", total_findings)
        + _render_stat("Critical", critical_count)
        + _render_stat("Minor", minor_count)
        + _render_stat("Rounds", round_count)
        + _render_stat("Fix commits", fix_commit_count)
        + _render_stat("Tests added", tests_added_total)
        + "</div>"
    )

    severity_chart = _render_severity_chart(critical_count, minor_count)
    round_chart = _render_round_findings_chart(
        round_count, run_data.finding_count_by_round
    )
    tests_chart = _render_tests_chart(round_count, run_data.tests_added_by_round)
    theme_chart = _render_theme_chart(run_data.finding_count_by_theme)

    charts_row_one = f'<div class="charts-row">{severity_chart}{round_chart}</div>'
    charts_row_two = f'<div class="charts-row">{tests_chart}{theme_chart}</div>'

    numbers_section = (
        f'<h2 id="numbers">The numbers</h2>{charts_row_one}{charts_row_two}'
    )

    critical_cards = _render_finding_cards(
        run_data.all_critical_findings, run_data.fix_by_round, "crit"
    )
    critical_intro = '<p class="section-intro">P0 and P1 findings caught and fixed during the run.</p>'
    critical_section = f'<h2 id="critical">Critical findings</h2>' + (
        f"{critical_intro}{critical_cards}"
        if run_data.all_critical_findings
        else '<p class="section-intro">No critical findings.</p>'
    )

    minor_intro = (
        '<p class="section-intro">P2 findings caught and fixed during the run.</p>'
    )
    minor_cards = _render_finding_cards(
        run_data.all_minor_findings, run_data.fix_by_round, "minor"
    )
    minor_section = f'<h2 id="minor">Minor findings</h2>{minor_intro}{minor_cards}'

    horizon_tip = (
        f'<div class="horizon-tip">Final commit <code>{html.escape(final_sha_short)}</code> '
        f"· {round_count} rounds · {fix_commit_count} fix commits.</div>"
    )
    status_section = (
        f'<h2 id="status">Status</h2>'
        f'<div class="horizon-card">'
        f'<div class="horizon-title">Converged</div>'
        f'<div class="horizon-possible">The run converged and the PR was marked ready.</div>'
        f"{horizon_tip}"
        f"</div>"
    )

    footer = (
        f"<footer>{owner}/{repo} · PR #{pr_number} · "
        f"generated {html.escape(generated_date)} from the autoconverge run journal.</footer>"
    )

    body_content = (
        f"<h1>PR #{pr_number} Convergence Insights</h1>"
        f"{subtitle}"
        f"{at_a_glance}"
        f"{nav_toc}"
        f"{stats_row}"
        f"{numbers_section}"
        f"{critical_section}"
        f"{minor_section}"
        f"{status_section}"
        f"{footer}"
    )

    return (
        f"{HTML_DOCTYPE}\n"
        f"<html lang='en'>\n"
        f"{head_html}\n"
        f"<body>\n"
        f'<div class="container">\n'
        f"{body_content}\n"
        f"</div>\n"
        f"</body>\n"
        f"</html>"
    )


def _parse_pr_arg(pr_arg: str, err_stream: TextIO) -> tuple[str, str, int] | None:
    """Parse an 'owner/repo#number' string into its three components.

    Args:
        pr_arg: A string in the form 'owner/repo#number'.
        err_stream: Stream to write error messages to.

    Returns:
        A tuple of (owner, repo, pr_number_int), or None on parse failure.
    """
    match = re.fullmatch(r"([^/]+)/([^#]+)#(\d+)", pr_arg)
    if not match:
        err_stream.write(
            f"Invalid --pr format: {pr_arg!r}. Expected owner/repo#number.\n"
        )
        return None
    return match.group(1), match.group(2), int(match.group(3))


def main(out_stream: TextIO = sys.stdout, err_stream: TextIO = sys.stderr) -> int:
    """Parse CLI arguments, load run data, render HTML, write the output file, and emit the path.

    Args:
        out_stream: Stream to write the output file path to on success.
        err_stream: Stream to write error messages to.

    Returns:
        Exit code (0 on success, 1 on argument error).
    """
    argument_parser = argparse.ArgumentParser(
        description="Render autoconverge convergence insights HTML."
    )
    argument_parser.add_argument(
        "--journal", required=True, help="Path to wf_<runId>.json"
    )
    argument_parser.add_argument("--out", required=True, help="Output HTML file path")
    argument_parser.add_argument("--pr", required=True, help="owner/repo#number")
    argument_parser.add_argument("--final-sha", required=True, help="Final commit SHA")
    argument_parser.add_argument(
        "--rounds", required=True, type=int, help="Total round count"
    )
    argument_parser.add_argument(
        "--repo", default=".", help="Path to the git repository root"
    )

    parsed_args = argument_parser.parse_args()

    journal_path = Path(parsed_args.journal).resolve()
    out_path = Path(parsed_args.out)
    repo_path = Path(parsed_args.repo).resolve()

    parsed_pr = _parse_pr_arg(parsed_args.pr, err_stream)
    if parsed_pr is None:
        return 1

    owner, repo, pr_number = parsed_pr
    pr_url = GITHUB_PR_URL_TEMPLATE.format(owner=owner, repo=repo, number=pr_number)

    pr_metadata = PrMetadata(
        owner=owner,
        repo=repo,
        number=pr_number,
        url=pr_url,
        final_sha=parsed_args.final_sha,
        round_count=parsed_args.rounds,
    )

    run_data = load_run_data(journal_path, repo_path)
    html_content = render_report_html(run_data, pr_metadata, run_data.generated_date)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_content, encoding="utf-8")
    out_stream.write(str(out_path) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
