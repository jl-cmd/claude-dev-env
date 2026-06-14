"""Named constants for render_report.py."""

STRUCTURED_OUTPUT_TOOL_NAME = "StructuredOutput"

LABEL_RESOLVE_HEAD = "resolve-head"
LABEL_PREFIX_LENS = "lens:"
LABEL_PREFIX_FIX = "fix:"
LABEL_COPILOT_GATE = "copilot-gate"
LABEL_CONVERGENCE_SUMMARY = "convergence-summary"

JOURNAL_SIBLING_SUBAGENTS = "subagents"
JOURNAL_SIBLING_WORKFLOWS = "workflows"

DEFAULT_FINDING_CATEGORY = "bug"
DEFAULT_FINDING_SEVERITY = "P2"

ISO_DATE_LENGTH = 10
SHORT_SHA_LENGTH = 8

SUMMARY_FIELD_VERDICT_LINE = "verdictLine"
SUMMARY_FIELD_ISSUE_CLASSES = "issueClasses"
ISSUE_CLASS_FIELD_PLAIN_NAME = "plainName"
ISSUE_CLASS_FIELD_COUNT = "count"
ISSUE_CLASS_FIELD_SEVERITY = "severity"
ISSUE_CLASS_FIELD_CATEGORY = "category"
ISSUE_CLASS_FIELD_STATUS = "status"
ISSUE_CLASS_FIELD_WHAT_IT_WAS = "whatItWas"

CATEGORY_BUG = "bug"
CATEGORY_CODE_STANDARD = "code-standard"
CATEGORY_LABEL_BY_VALUE = {
    "bug": "Bug",
    "code-standard": "Code standard",
}
CATEGORY_SORT_ORDER = {
    "bug": 0,
    "code-standard": 1,
}
CATEGORY_TAG_CLASS_BY_VALUE = {
    "bug": "cat-bug",
    "code-standard": "cat-code-standard",
}

STATUS_DEFERRED = "deferred"
STATUS_LABEL_BY_VALUE = {
    "fixed": "Fixed",
    "deferred": "Deferred",
}
STATUS_PILL_CLASS_BY_VALUE = {
    "fixed": "pill-fixed",
    "deferred": "pill-deferred",
}

VERDICT_PILL_LABEL_CONVERGED = "Converged"
VERDICT_PILL_LABEL_DEFERRED = "Deferred items"

SEVERITY_ORDER = ("P0", "P1", "P2")
SEVERITY_SORT_RANK = {
    "P0": 0,
    "P1": 1,
    "P2": 2,
}
SEVERITY_DOT_CLASS_BY_LEVEL = {
    "P0": "dot-p0",
    "P1": "dot-p1",
    "P2": "dot-p2",
}

GITHUB_PR_URL_TEMPLATE = "https://github.com/{owner}/{repo}/pull/{number}"

HTML_DOCTYPE = "<!DOCTYPE html>"

HTML_HEAD_TEMPLATE = """\
<head>
    <meta charset="utf-8">
    <title>PR #{pr_number} Convergence Summary</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    {style_block}
</head>"""

HTML_STYLE_BLOCK = """\
<style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; background: #f8fafc; color: #334155; line-height: 1.65; padding: 48px 24px; }
    .container { max-width: 800px; margin: 0 auto; }
    h1 { font-size: 28px; font-weight: 700; color: #0f172a; margin-bottom: 8px; }
    h2 { font-size: 18px; font-weight: 600; color: #0f172a; margin-top: 36px; margin-bottom: 14px; }
    .subtitle { color: #64748b; font-size: 14px; margin-bottom: 28px; }
    .verdict-banner { border-radius: 12px; padding: 20px 24px; margin-bottom: 24px; display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }
    .verdict-banner.converged { background: linear-gradient(135deg, #dcfce7 0%, #bbf7d0 100%); border: 1px solid #22c55e; }
    .verdict-banner.deferred { background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); border: 1px solid #f59e0b; }
    .verdict-line { flex: 1 1 320px; font-size: 16px; font-weight: 600; color: #0f172a; line-height: 1.5; }
    .verdict-pill { font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .5px; padding: 6px 14px; border-radius: 20px; white-space: nowrap; }
    .verdict-pill.converged { background: #166534; color: #f0fdf4; }
    .verdict-pill.deferred { background: #92400e; color: #fffbeb; }
    .rollup { font-size: 14px; color: #475569; background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px 18px; margin-bottom: 8px; }
    .rollup b { color: #0f172a; }
    .fix-line { font-size: 14px; color: #166534; background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 12px 18px; margin: 18px 0 8px 0; }
    .fix-line b { color: #15803d; }
    .issue-table { width: 100%; border-collapse: collapse; background: white; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; }
    .issue-table th { text-align: left; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .4px; color: #64748b; padding: 10px 14px; background: #f8fafc; border-bottom: 1px solid #e2e8f0; }
    .issue-table td { font-size: 13px; color: #334155; padding: 12px 14px; border-bottom: 1px solid #f1f5f9; vertical-align: top; }
    .issue-table tr:last-child td { border-bottom: none; }
    .issue-name { font-weight: 600; color: #0f172a; }
    .issue-what { font-size: 13px; color: #64748b; line-height: 1.5; }
    .count-badge { display: inline-block; font-size: 12px; font-weight: 700; color: #475569; background: #f1f5f9; border-radius: 12px; padding: 2px 9px; white-space: nowrap; }
    .sev-dot { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 600; white-space: nowrap; }
    .sev-dot::before { content: ''; width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
    .sev-dot.dot-p0::before { background: #dc2626; }
    .sev-dot.dot-p1::before { background: #ea580c; }
    .sev-dot.dot-p2::before { background: #eab308; }
    .cat-tag { display: inline-block; font-size: 11px; font-weight: 600; padding: 3px 9px; border-radius: 6px; white-space: nowrap; }
    .cat-tag.cat-bug { background: #fee2e2; color: #991b1b; }
    .cat-tag.cat-code-standard { background: #e0e7ff; color: #3730a3; }
    .status-pill { display: inline-block; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .4px; padding: 3px 9px; border-radius: 20px; white-space: nowrap; }
    .status-pill.pill-fixed { background: #dcfce7; color: #166534; }
    .status-pill.pill-deferred { background: #fef3c7; color: #92400e; }
    .group-list { display: flex; flex-direction: column; gap: 18px; }
    .group { background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px 18px; }
    .group-head { font-size: 13px; font-weight: 600; color: #0f172a; margin-bottom: 8px; }
    .group-item { font-size: 13px; color: #475569; padding: 3px 0; }
    .group-item code { background: #f1f5f9; padding: 1px 6px; border-radius: 4px; font-family: monospace; color: #475569; }
    details.appendix { margin-top: 28px; background: white; border: 1px solid #e2e8f0; border-radius: 8px; }
    details.appendix summary { cursor: pointer; font-size: 13px; font-weight: 600; color: #475569; padding: 14px 18px; list-style: none; }
    details.appendix summary::-webkit-details-marker { display: none; }
    details.appendix summary::before { content: '\\25B8'; display: inline-block; margin-right: 8px; transition: transform 0.15s; }
    details.appendix[open] summary::before { transform: rotate(90deg); }
    details.appendix .appendix-body { padding: 0 18px 16px 18px; }
    .appendix-group-head { font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: .4px; color: #94a3b8; margin: 12px 0 6px 0; }
    .appendix-item { font-size: 12px; color: #475569; padding: 2px 0; font-family: monospace; }
    footer { margin-top: 36px; padding-top: 18px; border-top: 1px solid #e2e8f0; color: #94a3b8; font-size: 12px; }
    footer code { background: #f1f5f9; padding: 1px 6px; border-radius: 4px; font-family: monospace; color: #475569; }
    @media (max-width: 640px) { .issue-table th:nth-child(6), .issue-table td:nth-child(6) { display: none; } }
</style>"""
