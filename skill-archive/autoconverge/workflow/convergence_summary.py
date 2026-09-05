"""Build the convergence-summary agent prompt over a PR's aggregated findings."""

from autoconverge_report_constants.render_report_constants import (
    GITHUB_PR_URL_TEMPLATE,
    SUMMARY_COPILOT_NOTE_TEMPLATE,
    SUMMARY_DETAIL_MAX_CHARS,
    SUMMARY_FINDING_LINE_TEMPLATE,
    SUMMARY_FINDINGS_EMPTY_TEXT,
    SUMMARY_FIX_EMPTY_TEXT,
    SUMMARY_FIX_LINE_TEMPLATE,
    SUMMARY_PR_COORDINATES_TEMPLATE,
    SUMMARY_PROMPT_TEMPLATE,
    SUMMARY_STANDARDS_NOTE_TEMPLATE,
)


def _format_findings_block(findings: list[dict]) -> str:
    """Return the numbered findings block, or a clean-run sentence when empty.

    Args:
        findings: Aggregated distinct findings, each carrying severity, category,
            file, line, title, and detail keys.

    Returns:
        A newline-joined numbered list, or a sentence stating every lens was clean.
    """
    if not findings:
        return SUMMARY_FINDINGS_EMPTY_TEXT
    numbered_lines: list[str] = []
    for position, each_finding in enumerate(findings):
        detail = str(each_finding.get("detail", ""))[:SUMMARY_DETAIL_MAX_CHARS]
        numbered_lines.append(
            SUMMARY_FINDING_LINE_TEMPLATE.format(
                number=position + 1,
                severity=each_finding.get("severity", ""),
                category=each_finding.get("category", ""),
                file=each_finding.get("file", ""),
                line=each_finding.get("line", 0),
                title=each_finding.get("title", ""),
                detail=detail,
            )
        )
    return "\n".join(numbered_lines)


def _format_fix_block(fix_summaries: list[str]) -> str:
    """Return the numbered per-round fix-summary block, or 'none' when empty.

    Args:
        fix_summaries: One-line fix summaries collected across every round.

    Returns:
        A newline-joined numbered list, or the empty-state literal.
    """
    if not fix_summaries:
        return SUMMARY_FIX_EMPTY_TEXT
    return "\n".join(
        SUMMARY_FIX_LINE_TEMPLATE.format(number=position + 1, summary=each_summary)
        for position, each_summary in enumerate(fix_summaries)
    )


def build_summary_prompt(
    owner: str,
    repo: str,
    pr_number: int,
    round_count: int,
    findings: list[dict],
    fix_summaries: list[str],
    standards_note: str | None,
    copilot_note: str | None,
) -> str:
    """Return the convergence-summary agent prompt for a PR's aggregated findings.

    Args:
        owner: The PR's repository owner.
        repo: The PR's repository name.
        pr_number: The PR number.
        round_count: Total converge rounds across every run aggregated.
        findings: Aggregated distinct findings across every run.
        fix_summaries: One-line fix summaries collected across every run.
        standards_note: Deferral note when a round was code-standard-only, else None.
        copilot_note: Outage note when the Copilot gate was bypassed, else None.

    Returns:
        The full agent prompt instructing a plain-JSON convergence summary.
    """
    pr_url = GITHUB_PR_URL_TEMPLATE.format(owner=owner, repo=repo, number=pr_number)
    pr_coordinates = SUMMARY_PR_COORDINATES_TEMPLATE.format(
        owner=owner, repo=repo, pr_number=pr_number, url=pr_url
    )
    standards_block = (
        SUMMARY_STANDARDS_NOTE_TEMPLATE.format(note=standards_note)
        if standards_note
        else ""
    )
    copilot_block = (
        SUMMARY_COPILOT_NOTE_TEMPLATE.format(note=copilot_note) if copilot_note else ""
    )
    return SUMMARY_PROMPT_TEMPLATE.format(
        pr_coordinates=pr_coordinates,
        owner=owner,
        repo=repo,
        pr_number=pr_number,
        round_count=round_count,
        findings_block=_format_findings_block(findings),
        fix_block=_format_fix_block(fix_summaries),
        standards_block=standards_block,
        copilot_block=copilot_block,
    )
