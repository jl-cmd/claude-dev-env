"""Render a visual convergence summary HTML report from an autoconverge journal."""

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
    CAUSE_MUTED_STYLE,
    DEFAULT_FINDING_CATEGORY,
    DEFAULT_FINDING_SEVERITY,
    DEFAULT_ISSUE_ICON,
    HTML_DOCTYPE,
    HTML_HEAD_TEMPLATE,
    HTML_STYLE_BLOCK,
    ISO_DATE_LENGTH,
    ISSUE_CLASS_FIELD_AFTER_LINES,
    ISSUE_CLASS_FIELD_BEFORE_LINES,
    ISSUE_CLASS_FIELD_CATEGORY,
    ISSUE_CLASS_FIELD_CAUSE,
    ISSUE_CLASS_FIELD_COUNT,
    ISSUE_CLASS_FIELD_MEDIUM,
    ISSUE_CLASS_FIELD_PLAINNAME,
    ISSUE_CLASS_FIELD_SEVERITY,
    ISSUE_CLASS_FIELD_STATUS,
    ISSUE_ICON_BY_CATEGORY,
    JOURNAL_SIBLING_SUBAGENTS,
    JOURNAL_SIBLING_WORKFLOWS,
    LABEL_CONVERGENCE_SUMMARY,
    LABEL_COPILOT_GATE,
    LABEL_PREFIX_FIX,
    LABEL_PREFIX_LENS,
    LABEL_RESOLVE_HEAD,
    MEDIUM_CODE,
    MEDIUM_TERMINAL,
    SCENE_FIELD_CAPTION,
    SCENE_FIELD_CONDITION,
    SCENE_FIELD_RESULT,
    SCENE_FIELD_TRIGGER,
    SCORECARD_LABEL_CAUGHT,
    SCORECARD_LABEL_REMAINING,
    SCORECARD_LABEL_ROUNDS,
    SEVERITY_SORT_RANK,
    SHORT_SHA_LENGTH,
    STATUS_LABEL_BY_VALUE,
    STRUCTURED_OUTPUT_TOOL_NAME,
    SUMMARY_FIELD_FIX_SCENES,
    SUMMARY_FIELD_ISSUE_CLASSES,
    SUMMARY_FIELD_PR_FIX,
    SUMMARY_FIELD_PR_PROBLEM,
    SUMMARY_FIELD_PROBLEM_SCENES,
    SUMMARY_FIELD_VERDICT_LINE,
    TIMELINE_AFTER_LABEL,
    TIMELINE_AFTER_PILL,
    TIMELINE_BEFORE_LABEL,
    TIMELINE_BEFORE_PILL,
    TIMELINE_TERMINAL_BAR_LABEL,
)


@dataclass(frozen=True)
class RawFinding:
    """A single finding from a lens or copilot-gate agent result."""

    file: str
    line: int
    severity: str
    title: str
    detail: str
    category: str


@dataclass(frozen=True)
class FixRecord:
    """The structured result of a fix agent, with base-sha context attached."""

    new_sha: str
    pushed: bool
    resolved_without_commit: bool
    summary: str
    base_sha: str


@dataclass(frozen=True)
class PrMetadata:
    """Owner, repo, number, final sha, and round count for the PR being reported on."""

    owner: str
    repo: str
    number: int
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


def _parse_finding_from_dict(raw: dict) -> RawFinding:
    """Construct a RawFinding from a raw agent result dict.

    Args:
        raw: The raw finding dict from the agent result.

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
    )


def _parse_fix_record(agent_result: dict, base_sha: str) -> FixRecord:
    """Construct a FixRecord from a fix agent's structured output.

    Args:
        agent_result: The structured output dict from the fix agent.
        base_sha: The HEAD sha the round reviewed before fixing.

    Returns:
        A FixRecord dataclass instance.
    """
    return FixRecord(
        new_sha=agent_result.get("newSha", ""),
        pushed=bool(agent_result.get("pushed", False)),
        resolved_without_commit=bool(agent_result.get("resolvedWithoutCommit", False)),
        summary=agent_result.get("summary", ""),
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
                all_findings.append(_parse_finding_from_dict(each_raw))

        if is_fix:
            fix_by_round[current_round] = _parse_fix_record(
                agent_result, current_round_base_sha
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


def _is_summary_structurally_valid(convergence_summary: object) -> bool:
    """Return whether the summary carries a verdict string and an issue-class list.

    Args:
        convergence_summary: The parsed convergence summary, which may be None or
            any non-dict JSON value an agent emits in place of the expected object.

    Returns:
        True when the summary is a dict whose verdictLine is a str and whose
        issueClasses is a list, else False.
    """
    if not isinstance(convergence_summary, dict):
        return False
    verdict_line = convergence_summary.get(SUMMARY_FIELD_VERDICT_LINE)
    issue_classes = convergence_summary.get(SUMMARY_FIELD_ISSUE_CLASSES)
    return isinstance(verdict_line, str) and isinstance(issue_classes, list)


def _coerce_count(raw_count: object) -> int:
    """Return a non-negative integer count from an LLM-authored field, else zero.

    Args:
        raw_count: The count value as read from the convergence summary, which an
            agent may emit as null, a non-numeric string, or a valid number.

    Returns:
        The value parsed to an int, or 0 when it is null, non-numeric, or absent.
    """
    if isinstance(raw_count, bool):
        return int(raw_count)
    if isinstance(raw_count, int):
        return raw_count
    if isinstance(raw_count, (float, str)):
        try:
            return int(float(raw_count))
        except (TypeError, ValueError):
            return 0
    return 0


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


def _render_verdict_banner(
    convergence_summary: dict, run_data: RunData, final_sha_short: str
) -> str:
    """Return the verdict banner with the verdict line and a Python-computed sub-line.

    Args:
        convergence_summary: A structurally valid convergence summary.
        run_data: Aggregated metrics from the journal.
        final_sha_short: First eight characters of the final commit sha.

    Returns:
        An HTML .verdict banner string with a check circle, vtext, and vsub.
    """
    verdict_line = str(convergence_summary.get(SUMMARY_FIELD_VERDICT_LINE, ""))
    fix_commit_phrase = _pluralize(
        run_data.fix_commit_count, "fix commit", "fix commits"
    )
    vsub = f"{fix_commit_phrase} &middot; final commit {html.escape(final_sha_short)}"
    return (
        '<div class="verdict">'
        '<div class="check">&#10003;</div>'
        "<div>"
        f'<div class="vtext">{html.escape(verdict_line)}</div>'
        f'<div class="vsub">{vsub}</div>'
        "</div>"
        "</div>"
    )


def _render_scorecard(run_data: RunData, round_count: int) -> str:
    """Return the at-a-glance scorecard: findings caught, rounds, and zero remaining.

    Args:
        run_data: Aggregated metrics from the journal.
        round_count: Total number of convergence rounds.

    Returns:
        An HTML .scorecard grid of three .stat tiles; the remaining tile is marked
        .good and reads zero, since the report renders only on a converged run.
    """
    remaining_count = 0
    return (
        '<div class="scorecard">'
        f'<div class="stat"><div class="stat-num">{run_data.total_finding_count}</div>'
        f'<div class="stat-label">{SCORECARD_LABEL_CAUGHT}</div></div>'
        f'<div class="stat"><div class="stat-num">{round_count}</div>'
        f'<div class="stat-label">{SCORECARD_LABEL_ROUNDS}</div></div>'
        f'<div class="stat good"><div class="stat-num">{remaining_count}</div>'
        f'<div class="stat-label">{SCORECARD_LABEL_REMAINING}</div></div>'
        "</div>"
    )


def _render_scene_row(scene: dict, is_problem: bool) -> str:
    """Return one .scene row plus its caption for a problem-or-fix scene.

    Args:
        scene: A scene dict with trigger, condition, result, and caption.
        is_problem: True for a problem scene (bad result), False for a fix scene.

    Returns:
        An HTML .scene row followed by a .scene-cap caption line.
    """
    trigger = html.escape(str(scene.get(SCENE_FIELD_TRIGGER, "")))
    condition = str(scene.get(SCENE_FIELD_CONDITION, "")).strip()
    result_text = html.escape(str(scene.get(SCENE_FIELD_RESULT, "")))
    caption = html.escape(str(scene.get(SCENE_FIELD_CAPTION, "")))

    result_class = "res-bad" if is_problem else "res-good"
    result_mark = "&#10007;" if is_problem else "&#10003;"

    parts = [f'<span class="chip">{trigger}</span>']
    if condition:
        parts.append('<span class="arrow">&rarr;</span>')
        parts.append(f'<span class="note">{html.escape(condition)}</span>')
    parts.append('<span class="arrow">&rarr;</span>')
    parts.append(f'<span class="{result_class}">{result_mark} {result_text}</span>')

    scene_row = f'<div class="scene">{"".join(parts)}</div>'
    caption_row = f'<div class="scene-cap">{caption}</div>'
    return scene_row + caption_row


def _render_pf_card(convergence_summary: dict, is_problem: bool) -> str:
    """Return a single problem-or-fix card drawing its scenes or a fallback caption.

    Args:
        convergence_summary: A structurally valid convergence summary.
        is_problem: True for the problem card, False for the fix card.

    Returns:
        An HTML .pf card string with scene rows or a single fallback caption.
    """
    if is_problem:
        card_class = "problem"
        tag_label = "Problem"
        scenes_field = SUMMARY_FIELD_PROBLEM_SCENES
        fallback_field = SUMMARY_FIELD_PR_PROBLEM
    else:
        card_class = "fix"
        tag_label = "Fix"
        scenes_field = SUMMARY_FIELD_FIX_SCENES
        fallback_field = SUMMARY_FIELD_PR_FIX

    scenes = [
        each_scene
        for each_scene in convergence_summary.get(scenes_field, [])
        if isinstance(each_scene, dict)
    ]
    if scenes:
        body = "".join(
            _render_scene_row(each_scene, is_problem) for each_scene in scenes
        )
    else:
        fallback_text = html.escape(str(convergence_summary.get(fallback_field, "")))
        body = f'<div class="scene-cap">{fallback_text}</div>'

    return (
        f'<div class="pf {card_class}">'
        f'<span class="pf-tag">{tag_label}</span>'
        f"{body}"
        "</div>"
    )


def _render_pf_grid(convergence_summary: dict) -> str:
    """Return the 'What this PR does' grid with a problem card and a fix card.

    Args:
        convergence_summary: A structurally valid convergence summary.

    Returns:
        An HTML .pf-grid string with both cards.
    """
    problem_card = _render_pf_card(convergence_summary, is_problem=True)
    fix_card = _render_pf_card(convergence_summary, is_problem=False)
    return f'<div class="pf-grid">{problem_card}{fix_card}</div>'


def _render_panel_body(lines: list[str], medium: str) -> str:
    """Return the inner HTML for a before-or-after panel body.

    Args:
        lines: The literal short lines to show, joined with line breaks.
        medium: One of 'terminal', 'code', or 'text'.

    Returns:
        An HTML panel-body string escaped and joined with <br>.
    """
    escaped_lines = [html.escape(str(each_line)) for each_line in lines]
    joined = "<br>".join(escaped_lines)
    if medium == MEDIUM_TERMINAL:
        return (
            '<div class="terminal">'
            '<div class="term-bar"><i class="r"></i><i class="y"></i><i class="g"></i>'
            f"<span>{TIMELINE_TERMINAL_BAR_LABEL}</span></div>"
            f'<div class="term-body">{joined}</div>'
            "</div>"
        )
    panel_class = "code-panel" if medium == MEDIUM_CODE else "text-panel"
    return f'<div class="{panel_class}">{joined}</div>'


def _render_term_grid(issue_class: dict, medium: str) -> str:
    """Return the before/after panel grid for one issue class.

    Args:
        issue_class: One issue-class dict from the summary.
        medium: The medium that styles both panels.

    Returns:
        An HTML .term-grid string with a before panel and an after panel.
    """
    before_lines = list(issue_class.get(ISSUE_CLASS_FIELD_BEFORE_LINES, []))
    after_lines = list(issue_class.get(ISSUE_CLASS_FIELD_AFTER_LINES, []))
    before_body = _render_panel_body(before_lines, medium)
    after_body = _render_panel_body(after_lines, medium)
    return (
        '<div class="term-grid">'
        '<div class="term-wrap before">'
        f'<div class="tlabel">{TIMELINE_BEFORE_LABEL} '
        f'<span class="pill-x">{TIMELINE_BEFORE_PILL}</span></div>'
        f"{before_body}"
        "</div>"
        '<div class="term-wrap after">'
        f'<div class="tlabel">{TIMELINE_AFTER_LABEL} '
        f'<span class="pill-c">{TIMELINE_AFTER_PILL}</span></div>'
        f"{after_body}"
        "</div>"
        "</div>"
    )


def _render_cause_line(issue_class: dict) -> str:
    """Return the cause line plus a muted severity/category/count/status parenthetical.

    Args:
        issue_class: One issue-class dict from the summary.

    Returns:
        An HTML .cause string.
    """
    cause = html.escape(str(issue_class.get(ISSUE_CLASS_FIELD_CAUSE, "")))
    severity = str(issue_class.get(ISSUE_CLASS_FIELD_SEVERITY, DEFAULT_FINDING_SEVERITY))
    category = str(issue_class.get(ISSUE_CLASS_FIELD_CATEGORY, CATEGORY_BUG))
    count = _coerce_count(issue_class.get(ISSUE_CLASS_FIELD_COUNT, 0))
    status = str(issue_class.get(ISSUE_CLASS_FIELD_STATUS, ""))

    category_label = CATEGORY_LABEL_BY_VALUE.get(category, category)
    status_label = STATUS_LABEL_BY_VALUE.get(status, status)
    parenthetical = (
        f"({html.escape(severity)} {html.escape(category_label)} "
        f"&middot; &times;{count} &middot; {html.escape(status_label)})"
    )
    return (
        '<div class="cause">'
        f"<b>Why it happened:</b> {cause} "
        f'<span style="{CAUSE_MUTED_STYLE}">{parenthetical}</span>'
        "</div>"
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


def _render_issue_class_heading(issue_class: dict) -> str:
    """Return the per-class heading with a category icon, plain name, and count.

    Args:
        issue_class: One issue-class dict from the summary.

    Returns:
        An HTML .bug-head block: a category icon and the plain bug name grouped in
        a .bug-title span, plus a finding-count chip.
    """
    plain_name = html.escape(str(issue_class.get(ISSUE_CLASS_FIELD_PLAINNAME, "")))
    count = _coerce_count(issue_class.get(ISSUE_CLASS_FIELD_COUNT, 0))
    count_phrase = html.escape(_pluralize(count, "finding", "findings"))
    category = str(issue_class.get(ISSUE_CLASS_FIELD_CATEGORY, CATEGORY_BUG))
    icon = ISSUE_ICON_BY_CATEGORY.get(category, DEFAULT_ISSUE_ICON)
    return (
        '<div class="bug-head">'
        '<span class="bug-title">'
        f'<span class="bug-icon">{icon}</span>'
        f'<span class="bug-name">{plain_name}</span>'
        "</span>"
        f'<span class="bug-count">{count_phrase}</span>'
        "</div>"
    )


def _render_issue_class_block(issue_class: dict) -> str:
    """Return one issue-class block: a name heading, before/after panels, a cause line.

    Args:
        issue_class: One issue-class dict from the summary.

    Returns:
        An HTML fragment that opens with the .bug-head name heading, then a
        .term-grid when panel lines exist, then the .cause line; the heading and
        cause line alone when both before and after lines are empty.
    """
    heading = _render_issue_class_heading(issue_class)
    medium = str(issue_class.get(ISSUE_CLASS_FIELD_MEDIUM, MEDIUM_TERMINAL))
    before_lines = list(issue_class.get(ISSUE_CLASS_FIELD_BEFORE_LINES, []))
    after_lines = list(issue_class.get(ISSUE_CLASS_FIELD_AFTER_LINES, []))

    cause_line = _render_cause_line(issue_class)
    if not before_lines and not after_lines:
        return heading + cause_line

    term_grid = _render_term_grid(issue_class, medium)
    return heading + term_grid + cause_line


def _render_issue_class_panels(convergence_summary: dict) -> str:
    """Return the per-issue-class before/after panels and cause lines.

    Args:
        convergence_summary: A structurally valid convergence summary.

    Returns:
        An HTML fragment with one block per issue class, ordered bug classes
        first then by severity.
    """
    issue_classes = [
        each_class
        for each_class in convergence_summary.get(SUMMARY_FIELD_ISSUE_CLASSES, [])
        if isinstance(each_class, dict)
    ]
    if not issue_classes:
        return (
            '<p class="subtitle">No issues were caught &mdash; '
            "every review lens was clean.</p>"
        )
    sorted_classes = sorted(issue_classes, key=_issue_class_sort_key)
    return "".join(
        _render_issue_class_block(each_class) for each_class in sorted_classes
    )


def _render_caught_lead(
    convergence_summary: dict, run_data: RunData, round_count: int
) -> str:
    """Return the run-stats lead line that opens the caught section.

    Args:
        convergence_summary: A structurally valid convergence summary.
        run_data: Aggregated metrics from the journal.
        round_count: Total number of convergence rounds.

    Returns:
        An HTML .subtitle line stating bug-class, finding, round, and fix counts.
    """
    issue_classes = [
        each_class
        for each_class in convergence_summary.get(SUMMARY_FIELD_ISSUE_CLASSES, [])
        if isinstance(each_class, dict)
    ]
    class_phrase = _pluralize(len(issue_classes), "bug class", "bug classes")
    finding_phrase = _pluralize(run_data.total_finding_count, "finding", "findings")
    round_phrase = _pluralize(round_count, "round", "rounds")
    fix_phrase = _pluralize(run_data.fix_commit_count, "fix commit", "fix commits")
    return (
        f'<p class="subtitle">{class_phrase} ({finding_phrase} in all), '
        f"caught and fixed across {round_phrase} in {fix_phrase}.</p>"
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


def _render_summary_body(
    run_data: RunData, round_count: int, final_sha_short: str
) -> str:
    """Return the body for a run that carries a valid convergence summary.

    Args:
        run_data: Aggregated metrics from the journal.
        round_count: Total number of convergence rounds.
        final_sha_short: First eight characters of the final commit sha.

    Returns:
        An HTML body fragment: verdict banner, an at-a-glance scorecard,
        problem/fix cards, then a single caught section that opens with a
        run-stats lead line and holds the issue-class before/after panels,
        followed by the collapsed appendix.
    """
    convergence_summary = run_data.convergence_summary
    if convergence_summary is None:
        return _render_degraded_body(run_data, round_count, final_sha_short)

    verdict_banner = _render_verdict_banner(
        convergence_summary, run_data, final_sha_short
    )
    scorecard = _render_scorecard(run_data, round_count)
    pf_grid = _render_pf_grid(convergence_summary)
    caught_lead = _render_caught_lead(convergence_summary, run_data, round_count)
    issue_panels = _render_issue_class_panels(convergence_summary)
    appendix = _render_appendix(run_data.all_distinct_findings)
    return (
        f"{verdict_banner}"
        f"{scorecard}"
        f"<h2>What this PR does</h2>{pf_grid}"
        f"<h2>What was caught &mdash; and how it looked</h2>{caught_lead}{issue_panels}"
        f"{appendix}"
    )


def _render_degraded_body(
    run_data: RunData, round_count: int, final_sha_short: str
) -> str:
    """Return the minimal degraded body for a run with no valid summary.

    Args:
        run_data: Aggregated metrics from the journal.
        round_count: Total number of convergence rounds.
        final_sha_short: First eight characters of the final commit sha.

    Returns:
        An HTML body fragment: a plain run-stats note and the collapsed
        raw-findings appendix, with no scene, table, rollup, or timeline markup.
    """
    fix_commit_phrase = _pluralize(
        run_data.fix_commit_count, "fix commit", "fix commits"
    )
    note = (
        '<p class="subtitle">'
        f"{run_data.total_finding_count} distinct findings across {round_count} "
        f"rounds, resolved in {fix_commit_phrase}. "
        f"Final commit <code>{html.escape(final_sha_short)}</code>."
        "</p>"
    )
    appendix = _render_appendix(run_data.all_distinct_findings)
    return f"{note}{appendix}"


def render_report_html(
    run_data: RunData, pr_metadata: PrMetadata, generated_date: str
) -> str:
    """Render the convergence summary report as an HTML string.

    Args:
        run_data: Aggregated metrics from the workflow journal and transcripts.
        pr_metadata: Owner, repo, number, final sha, and round count for the PR.
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
        f"{run_data.total_finding_count} findings over {round_count} rounds "
        f"&middot; {html.escape(generated_date)}</p>"
    )

    if _is_summary_structurally_valid(run_data.convergence_summary):
        body_main = _render_summary_body(run_data, round_count, final_sha_short)
    else:
        body_main = _render_degraded_body(run_data, round_count, final_sha_short)

    fix_commit_phrase = _pluralize(
        run_data.fix_commit_count, "fix commit", "fix commits"
    )
    footer = (
        f"<footer>{owner}/{repo} &middot; PR #{pr_number} &middot; "
        f"{run_data.total_finding_count} findings &middot; {round_count} rounds "
        f"&middot; {fix_commit_phrase} &middot; "
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
        "--summary-file",
        default=None,
        help="Path to a JSON file with the convergence summary to inject",
    )

    parsed_args = argument_parser.parse_args()

    journal_path = Path(parsed_args.journal).resolve()
    out_path = Path(parsed_args.out)

    parsed_pr = _parse_pr_arg(parsed_args.pr, err_stream)
    if parsed_pr is None:
        return 1

    owner, repo, pr_number = parsed_pr

    pr_metadata = PrMetadata(
        owner=owner,
        repo=repo,
        number=pr_number,
        final_sha=parsed_args.final_sha,
        round_count=parsed_args.rounds,
    )

    run_data = load_run_data(journal_path)
    if parsed_args.summary_file:
        run_data.convergence_summary = json.loads(
            Path(parsed_args.summary_file).read_text(encoding="utf-8")
        )
    html_content = render_report_html(run_data, pr_metadata, run_data.generated_date)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_content, encoding="utf-8")
    out_stream.write(str(out_path) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
