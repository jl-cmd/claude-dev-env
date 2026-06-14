"""Render a plain-language convergence summary HTML report from an autoconverge journal."""

import argparse
import html
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from autoconverge_report_constants.render_report_constants import (
    CATEGORY_BUG,
    CATEGORY_LABEL_BY_VALUE,
    CATEGORY_SORT_ORDER,
    CATEGORY_TAG_CLASS_BY_VALUE,
    DEFAULT_FINDING_CATEGORY,
    DEFAULT_FINDING_SEVERITY,
    GITHUB_PR_URL_TEMPLATE,
    HTML_DOCTYPE,
    HTML_HEAD_TEMPLATE,
    HTML_STYLE_BLOCK,
    ISO_DATE_LENGTH,
    ISSUE_CLASS_FIELD_CATEGORY,
    ISSUE_CLASS_FIELD_COUNT,
    ISSUE_CLASS_FIELD_PLAIN_NAME,
    ISSUE_CLASS_FIELD_SEVERITY,
    ISSUE_CLASS_FIELD_STATUS,
    ISSUE_CLASS_FIELD_WHAT_IT_WAS,
    JOURNAL_SIBLING_SUBAGENTS,
    JOURNAL_SIBLING_WORKFLOWS,
    LABEL_CONVERGENCE_SUMMARY,
    LABEL_COPILOT_GATE,
    LABEL_PREFIX_FIX,
    LABEL_PREFIX_LENS,
    LABEL_RESOLVE_HEAD,
    SEVERITY_DOT_CLASS_BY_LEVEL,
    SEVERITY_ORDER,
    SEVERITY_SORT_RANK,
    SHORT_SHA_LENGTH,
    STATUS_DEFERRED,
    STATUS_LABEL_BY_VALUE,
    STATUS_PILL_CLASS_BY_VALUE,
    STRUCTURED_OUTPUT_TOOL_NAME,
    SUMMARY_FIELD_ISSUE_CLASSES,
    SUMMARY_FIELD_VERDICT_LINE,
    VERDICT_PILL_LABEL_CONVERGED,
    VERDICT_PILL_LABEL_DEFERRED,
)


@dataclass(frozen=True)
class RawFinding:
    """A single finding from a lens or copilot-gate agent result, tagged with round context."""

    file: str
    line: int
    severity: str
    title: str
    detail: str
    category: str
    round_number: int
    sha: str


@dataclass(frozen=True)
class FixRecord:
    """The structured result of a fix agent, with round and base-sha context attached."""

    new_sha: str
    pushed: bool
    resolved_without_commit: bool
    summary: str
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
    fix_commit_count: int
    all_distinct_findings: list[RawFinding]
    fix_by_round: dict[int, FixRecord]
    convergence_summary: dict | None


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
        severity=raw.get("severity", DEFAULT_FINDING_SEVERITY),
        title=raw.get("title", ""),
        detail=raw.get("detail", ""),
        category=raw.get("category", DEFAULT_FINDING_CATEGORY),
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
        summary=agent_result.get("summary", ""),
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


def _extract_convergence_summary(
    progress_entries: list[dict], agents_dir: Path
) -> dict | None:
    """Return the convergence-summary StructuredOutput, or None when absent.

    Args:
        progress_entries: The workflowProgress list from the journal.
        agents_dir: Directory containing per-agent .jsonl transcript files.

    Returns:
        The summarizer agent's last StructuredOutput input dict, or None when
        no convergence-summary entry exists or its transcript is unreadable.
    """
    for each_entry in progress_entries:
        if each_entry.get("label") != LABEL_CONVERGENCE_SUMMARY:
            continue
        agent_id = each_entry.get("agentId")
        if not agent_id:
            return None
        transcript_path = agents_dir / f"agent-{agent_id}.jsonl"
        return _extract_structured_output(transcript_path)
    return None


def load_run_data(journal_path: Path) -> RunData:
    """Parse a workflow journal and its agent transcripts into aggregated metrics.

    Args:
        journal_path: Path to the wf_<runId>.json journal file.

    Returns:
        A RunData instance with finding lists, fix records, and the summary populated.
    """
    iso_date_length = ISO_DATE_LENGTH
    journal = json.loads(journal_path.read_text(encoding="utf-8"))
    timestamp: str = journal.get("timestamp", "")
    generated_date = (
        timestamp[:iso_date_length] if len(timestamp) >= iso_date_length else ""
    )

    progress_entries: list[dict] = journal.get("workflowProgress", [])
    agents_dir = _resolve_agents_dir(journal_path)

    all_raw_findings, fix_by_round = _parse_progress_entries(
        progress_entries, agents_dir
    )
    distinct_findings = _dedup_findings(all_raw_findings)
    convergence_summary = _extract_convergence_summary(progress_entries, agents_dir)

    fix_commit_count = sum(1 for each_fix in fix_by_round.values() if each_fix.pushed)

    return RunData(
        generated_date=generated_date,
        total_finding_count=len(distinct_findings),
        fix_commit_count=fix_commit_count,
        all_distinct_findings=distinct_findings,
        fix_by_round=fix_by_round,
        convergence_summary=convergence_summary,
    )


def _count_findings_by_severity(findings: list[RawFinding]) -> dict[str, int]:
    """Return a count of findings per severity level.

    Args:
        findings: The distinct findings to tally.

    Returns:
        A mapping of severity level to count, including only present levels.
    """
    count_by_severity: dict[str, int] = {}
    for each_finding in findings:
        count_by_severity[each_finding.severity] = (
            count_by_severity.get(each_finding.severity, 0) + 1
        )
    return count_by_severity


def _is_summary_structurally_valid(convergence_summary: dict | None) -> bool:
    """Return whether the summary carries a verdict string and an issue-class list.

    Args:
        convergence_summary: The parsed convergence summary, or None.

    Returns:
        True when verdictLine is a str and issueClasses is a list, else False.
    """
    if convergence_summary is None:
        return False
    verdict_line = convergence_summary.get(SUMMARY_FIELD_VERDICT_LINE)
    issue_classes = convergence_summary.get(SUMMARY_FIELD_ISSUE_CLASSES)
    return isinstance(verdict_line, str) and isinstance(issue_classes, list)


def _render_severity_breakdown(count_by_severity: dict[str, int]) -> str:
    """Return a comma-joined per-severity breakdown like 'P0 1, P2 14'.

    Args:
        count_by_severity: Mapping of severity level to count.

    Returns:
        A human-readable breakdown string, or 'none' when no findings exist.
    """
    parts = [
        f"{each_level} {count_by_severity[each_level]}"
        for each_level in SEVERITY_ORDER
        if count_by_severity.get(each_level, 0)
    ]
    return ", ".join(parts) if parts else "none"


def _render_rollup_line(
    run_data: RunData, round_count: int, final_sha_short: str
) -> str:
    """Return the deterministic Python-owned rollup line of run numbers.

    Args:
        run_data: Aggregated metrics from the journal.
        round_count: Total number of convergence rounds.
        final_sha_short: First eight characters of the final commit sha.

    Returns:
        An HTML .rollup string with totals computed entirely in Python.
    """
    count_by_severity = _count_findings_by_severity(run_data.all_distinct_findings)
    breakdown = _render_severity_breakdown(count_by_severity)
    return (
        f'<div class="rollup">'
        f"<b>{run_data.total_finding_count}</b> distinct findings "
        f"({html.escape(breakdown)}) across <b>{round_count}</b> rounds, "
        f"resolved in <b>{run_data.fix_commit_count}</b> fix commits. "
        f"Final commit <code>{html.escape(final_sha_short)}</code>."
        f"</div>"
    )


def _verdict_has_deferral(convergence_summary: dict) -> bool:
    """Return whether any issue class is marked deferred.

    Args:
        convergence_summary: A structurally valid convergence summary.

    Returns:
        True when at least one issue class has status 'deferred'.
    """
    issue_classes = convergence_summary.get(SUMMARY_FIELD_ISSUE_CLASSES, [])
    for each_class in issue_classes:
        if isinstance(each_class, dict) and (
            each_class.get(ISSUE_CLASS_FIELD_STATUS) == STATUS_DEFERRED
        ):
            return True
    return False


def _render_verdict_banner(convergence_summary: dict) -> str:
    """Return the BLUF verdict banner with a green or amber status pill.

    Args:
        convergence_summary: A structurally valid convergence summary.

    Returns:
        An HTML .verdict-banner string.
    """
    verdict_line = convergence_summary.get(SUMMARY_FIELD_VERDICT_LINE, "")
    has_deferral = _verdict_has_deferral(convergence_summary)
    banner_state = "deferred" if has_deferral else "converged"
    pill_label = (
        VERDICT_PILL_LABEL_DEFERRED if has_deferral else VERDICT_PILL_LABEL_CONVERGED
    )
    return (
        f'<div class="verdict-banner {banner_state}">'
        f'<div class="verdict-line">{html.escape(verdict_line)}</div>'
        f'<span class="verdict-pill {banner_state}">{html.escape(pill_label)}</span>'
        f"</div>"
    )


def _issue_class_sort_key(issue_class: dict) -> tuple[int, int]:
    """Return a sort key ordering bug classes first, then by severity.

    Args:
        issue_class: One issue-class dict from the summary.

    Returns:
        A tuple of (category rank, severity rank); lower sorts first.
    """
    category = issue_class.get(ISSUE_CLASS_FIELD_CATEGORY, CATEGORY_BUG)
    severity = issue_class.get(ISSUE_CLASS_FIELD_SEVERITY, DEFAULT_FINDING_SEVERITY)
    category_rank = CATEGORY_SORT_ORDER.get(category, len(CATEGORY_SORT_ORDER))
    severity_rank = SEVERITY_SORT_RANK.get(severity, len(SEVERITY_SORT_RANK))
    return (category_rank, severity_rank)


def _render_issue_class_row(issue_class: dict) -> str:
    """Return one HTML table row for a single issue class.

    Args:
        issue_class: One issue-class dict from the summary.

    Returns:
        An HTML <tr> string with name, count, severity, category, status, detail.
    """
    plain_name = str(issue_class.get(ISSUE_CLASS_FIELD_PLAIN_NAME, ""))
    count = int(issue_class.get(ISSUE_CLASS_FIELD_COUNT, 0))
    severity = str(issue_class.get(ISSUE_CLASS_FIELD_SEVERITY, DEFAULT_FINDING_SEVERITY))
    category = str(issue_class.get(ISSUE_CLASS_FIELD_CATEGORY, CATEGORY_BUG))
    status = str(issue_class.get(ISSUE_CLASS_FIELD_STATUS, ""))
    what_it_was = str(issue_class.get(ISSUE_CLASS_FIELD_WHAT_IT_WAS, ""))

    dot_class = SEVERITY_DOT_CLASS_BY_LEVEL.get(severity, "dot-p2")
    category_class = CATEGORY_TAG_CLASS_BY_VALUE.get(category, "cat-bug")
    category_label = CATEGORY_LABEL_BY_VALUE.get(category, category)
    status_class = STATUS_PILL_CLASS_BY_VALUE.get(status, "pill-fixed")
    status_label = STATUS_LABEL_BY_VALUE.get(status, status)

    return (
        f"<tr>"
        f'<td class="issue-name">{html.escape(plain_name)}</td>'
        f'<td><span class="count-badge">&times;{count}</span></td>'
        f'<td><span class="sev-dot {dot_class}">{html.escape(severity)}</span></td>'
        f'<td><span class="cat-tag {category_class}">{html.escape(category_label)}</span></td>'
        f'<td><span class="status-pill {status_class}">{html.escape(status_label)}</span></td>'
        f'<td class="issue-what">{html.escape(what_it_was)}</td>'
        f"</tr>"
    )


def _render_issue_class_table(convergence_summary: dict) -> str:
    """Return the grouped issue-class table, bug rows first then code-standard.

    Args:
        convergence_summary: A structurally valid convergence summary.

    Returns:
        An HTML .issue-table string, or an empty-state paragraph when no classes.
    """
    issue_classes = [
        each_class
        for each_class in convergence_summary.get(SUMMARY_FIELD_ISSUE_CLASSES, [])
        if isinstance(each_class, dict)
    ]
    if not issue_classes:
        return '<p class="subtitle">No issue classes were caught during the run.</p>'

    sorted_classes = sorted(issue_classes, key=_issue_class_sort_key)
    rows = "".join(_render_issue_class_row(each_class) for each_class in sorted_classes)
    return (
        '<table class="issue-table">'
        "<thead><tr>"
        "<th>Issue class</th><th>Count</th><th>Severity</th>"
        "<th>Category</th><th>Status</th><th>What it was</th>"
        "</tr></thead>"
        f"<tbody>{rows}</tbody>"
        "</table>"
    )


def _pluralize(count: int, singular: str, plural: str) -> str:
    """Return a 'count word' phrase choosing the singular or plural noun.

    Args:
        count: The quantity that decides the noun form.
        singular: The noun to use when count is exactly one.
        plural: The noun to use for every other count.

    Returns:
        A phrase like '1 fix commit' or '2 fix commits'.
    """
    noun = singular if count == 1 else plural
    return f"{count} {noun}"


def _render_fix_resolution_line(run_data: RunData) -> str:
    """Return the single fix-resolution line stated once for the whole run.

    Args:
        run_data: Aggregated metrics from the journal.

    Returns:
        An HTML .fix-line string describing how findings were resolved.
    """
    pushed_phrase = _pluralize(run_data.fix_commit_count, "fix commit", "fix commits")
    resolved_at_head_count = sum(
        1
        for each_fix in run_data.fix_by_round.values()
        if each_fix.resolved_without_commit
    )
    rounds_phrase = _pluralize(resolved_at_head_count, "round was", "rounds were")
    return (
        f'<div class="fix-line"><b>Resolution:</b> every finding was addressed before '
        f"the PR was marked ready &mdash; {pushed_phrase} landed and "
        f"{rounds_phrase} already clean at HEAD.</div>"
    )


def _appendix_finding_sort_key(finding: RawFinding) -> tuple[int, int, str, int]:
    """Return a sort key grouping appendix findings by category then severity.

    Args:
        finding: One distinct finding.

    Returns:
        A tuple of (category rank, severity rank, file, line).
    """
    category_rank = CATEGORY_SORT_ORDER.get(finding.category, len(CATEGORY_SORT_ORDER))
    severity_rank = SEVERITY_SORT_RANK.get(finding.severity, len(SEVERITY_SORT_RANK))
    return (category_rank, severity_rank, finding.file, finding.line)


def _render_appendix(findings: list[RawFinding]) -> str:
    """Return a collapsed <details> appendix of raw distinct findings.

    Args:
        findings: The distinct findings to list, grouped by category then severity.

    Returns:
        An HTML <details> string listing each finding as 'file:line — P# — title'.
    """
    if not findings:
        return ""
    sorted_findings = sorted(findings, key=_appendix_finding_sort_key)
    items = "".join(
        f'<div class="appendix-item">'
        f"{html.escape(each_finding.file)}:{each_finding.line} &mdash; "
        f"{html.escape(each_finding.severity)} &mdash; "
        f"{html.escape(each_finding.title)}"
        f"</div>"
        for each_finding in sorted_findings
    )
    return (
        '<details class="appendix">'
        f"<summary>Raw findings ({len(findings)})</summary>"
        f'<div class="appendix-body">{items}</div>'
        "</details>"
    )


def _group_distinct_findings(
    findings: list[RawFinding],
) -> dict[tuple[str, str], list[RawFinding]]:
    """Group distinct findings by (category, severity).

    Args:
        findings: The distinct findings to group.

    Returns:
        A mapping of (category, severity) to the findings in that group.
    """
    findings_by_group: dict[tuple[str, str], list[RawFinding]] = {}
    for each_finding in findings:
        group_key = (each_finding.category, each_finding.severity)
        findings_by_group.setdefault(group_key, []).append(each_finding)
    return findings_by_group


def _degraded_group_sort_key(group_key: tuple[str, str]) -> tuple[int, int]:
    """Return a sort key ordering degraded groups by category then severity.

    Args:
        group_key: A (category, severity) tuple identifying a group.

    Returns:
        A tuple of (category rank, severity rank); lower sorts first.
    """
    category, severity = group_key
    category_rank = CATEGORY_SORT_ORDER.get(category, len(CATEGORY_SORT_ORDER))
    severity_rank = SEVERITY_SORT_RANK.get(severity, len(SEVERITY_SORT_RANK))
    return (category_rank, severity_rank)


def _render_degraded_groups(findings: list[RawFinding]) -> str:
    """Return a grouped distinct-finding list with near-duplicate titles counted.

    Args:
        findings: The distinct findings to render without an LLM summary.

    Returns:
        An HTML .group-list string grouped by category then severity.
    """
    if not findings:
        return '<p class="subtitle">No findings were caught during the run.</p>'

    findings_by_group = _group_distinct_findings(findings)
    sorted_groups = sorted(
        findings_by_group.items(), key=lambda pair: _degraded_group_sort_key(pair[0])
    )

    blocks = "".join(
        _render_degraded_group(each_category, each_severity, each_findings)
        for (each_category, each_severity), each_findings in sorted_groups
    )
    return f'<div class="group-list">{blocks}</div>'


def _render_degraded_group(
    category: str, severity: str, findings: list[RawFinding]
) -> str:
    """Return one .group block for a (category, severity) bucket of findings.

    Args:
        category: The category shared by every finding in this group.
        severity: The severity shared by every finding in this group.
        findings: The findings in this group.

    Returns:
        An HTML .group string with one row per near-duplicate title and a count.
    """
    category_label = CATEGORY_LABEL_BY_VALUE.get(category, category)
    head = f"{html.escape(category_label)} &middot; {html.escape(severity)}"
    count_by_title = _count_findings_by_title(findings)
    items = "".join(
        f'<div class="group-item">{html.escape(each_title)} '
        f'<span class="count-badge">&times;{each_count}</span></div>'
        for each_title, each_count in count_by_title.items()
    )
    return f'<div class="group"><div class="group-head">{head}</div>{items}</div>'


def _count_findings_by_title(findings: list[RawFinding]) -> dict[str, int]:
    """Return a count of findings per title, preserving first-seen order.

    Args:
        findings: The findings whose titles to tally.

    Returns:
        A mapping of title to occurrence count.
    """
    count_by_title: dict[str, int] = {}
    for each_finding in findings:
        count_by_title[each_finding.title] = (
            count_by_title.get(each_finding.title, 0) + 1
        )
    return count_by_title


def _render_summary_body(
    run_data: RunData, round_count: int, final_sha_short: str
) -> str:
    """Return the body for a run that carries a valid convergence summary.

    Args:
        run_data: Aggregated metrics from the journal.
        round_count: Total number of convergence rounds.
        final_sha_short: First eight characters of the final commit sha.

    Returns:
        An HTML body fragment: verdict banner, rollup, table, fix line, appendix.
    """
    convergence_summary = run_data.convergence_summary
    if convergence_summary is None:
        return _render_degraded_body(run_data, round_count, final_sha_short)

    verdict_banner = _render_verdict_banner(convergence_summary)
    rollup_line = _render_rollup_line(run_data, round_count, final_sha_short)
    issue_table = _render_issue_class_table(convergence_summary)
    fix_line = _render_fix_resolution_line(run_data)
    appendix = _render_appendix(run_data.all_distinct_findings)
    return (
        f"{verdict_banner}"
        f"{rollup_line}"
        f"<h2>What was caught</h2>{issue_table}"
        f"{fix_line}"
        f"{appendix}"
    )


def _render_degraded_body(
    run_data: RunData, round_count: int, final_sha_short: str
) -> str:
    """Return the chart-free degraded body for a run with no valid summary.

    Args:
        run_data: Aggregated metrics from the journal.
        round_count: Total number of convergence rounds.
        final_sha_short: First eight characters of the final commit sha.

    Returns:
        An HTML body fragment: rollup, grouped distinct findings, fix line, appendix.
    """
    rollup_line = _render_rollup_line(run_data, round_count, final_sha_short)
    grouped = _render_degraded_groups(run_data.all_distinct_findings)
    fix_line = _render_fix_resolution_line(run_data)
    appendix = _render_appendix(run_data.all_distinct_findings)
    return (
        f"{rollup_line}"
        f"<h2>What was caught</h2>{grouped}"
        f"{fix_line}"
        f"{appendix}"
    )


def render_report_html(
    run_data: RunData, pr_metadata: PrMetadata, generated_date: str
) -> str:
    """Render the convergence summary report as an HTML string.

    Args:
        run_data: Aggregated metrics from the workflow journal and transcripts.
        pr_metadata: Owner, repo, number, URL, final sha, and round count for the PR.
        generated_date: ISO date string derived from the journal timestamp.

    Returns:
        A complete HTML document string.
    """
    short_sha_length = SHORT_SHA_LENGTH
    pr_number = pr_metadata.number
    owner = html.escape(pr_metadata.owner)
    repo = html.escape(pr_metadata.repo)
    final_sha_short = pr_metadata.final_sha[:short_sha_length]
    round_count = pr_metadata.round_count

    head_html = HTML_HEAD_TEMPLATE.format(
        pr_number=pr_number,
        style_block=HTML_STYLE_BLOCK,
    )

    subtitle = (
        f'<p class="subtitle">{owner}/{repo} &middot; '
        f"{run_data.total_finding_count} findings across {round_count} rounds "
        f"&middot; {html.escape(generated_date)}</p>"
    )

    if _is_summary_structurally_valid(run_data.convergence_summary):
        body_main = _render_summary_body(run_data, round_count, final_sha_short)
    else:
        body_main = _render_degraded_body(run_data, round_count, final_sha_short)

    footer = (
        f"<footer>{owner}/{repo} &middot; PR #{pr_number} &middot; "
        f"{run_data.total_finding_count} findings &middot; {round_count} rounds "
        f"&middot; {run_data.fix_commit_count} fix commits &middot; "
        f"generated {html.escape(generated_date)} from the autoconverge run journal.</footer>"
    )

    body_content = (
        f"<h1>PR #{pr_number} Convergence Summary</h1>"
        f"{subtitle}"
        f"{body_main}"
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
    """Parse CLI arguments, load run data, render HTML, write the file, emit the path.

    Args:
        out_stream: Stream to write the output file path to on success.
        err_stream: Stream to write error messages to.

    Returns:
        Exit code (0 on success, 1 on argument error).
    """
    argument_parser = argparse.ArgumentParser(
        description="Render autoconverge convergence summary HTML."
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

    run_data = load_run_data(journal_path)
    html_content = render_report_html(run_data, pr_metadata, run_data.generated_date)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_content, encoding="utf-8")
    out_stream.write(str(out_path) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
