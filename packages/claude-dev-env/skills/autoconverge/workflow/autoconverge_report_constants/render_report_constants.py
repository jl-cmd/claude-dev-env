"""Named constants for render_report.py."""

STRUCTURED_OUTPUT_TOOL_NAME = "StructuredOutput"

LABEL_RESOLVE_HEAD = "resolve-head"
LABEL_PREFIX_LENS = "lens:"
LABEL_PREFIX_FIX = "fix:"
LABEL_COPILOT_GATE = "copilot-gate"

JOURNAL_SIBLING_SUBAGENTS = "subagents"
JOURNAL_SIBLING_WORKFLOWS = "workflows"

THEME_PATH_SEGMENT_COUNT = 2
THEME_FALLBACK = "other"

SEVERITY_CRITICAL_BUCKET = "Critical"
SEVERITY_MINOR_BUCKET = "Minor"
SEVERITY_CRITICAL_LEVELS = frozenset({"P0", "P1"})
SEVERITY_BADGE_CLASS_BY_LEVEL = {
    "P0": "b-p0",
    "P1": "b-p1",
    "P2": "b-p2",
}

BAR_COLOR_SEVERITY_CRITICAL = "#dc2626"
BAR_COLOR_SEVERITY_MINOR = "#eab308"
BAR_COLOR_ROUND = "#2563eb"
BAR_COLOR_TESTS = "#10b981"
BAR_COLOR_THEME = "#8b5cf6"

TEST_DEFINITION_PATTERN = r"^\+\s*(async\s+)?def\s+(test|should)"
TEST_PATH_GLOBS = ("*test*.py", "**/*test*.py")

BAR_FILL_MAX_PERCENT = 100

GITHUB_PR_URL_TEMPLATE = "https://github.com/{owner}/{repo}/pull/{number}"

HTML_DOCTYPE = "<!DOCTYPE html>"

HTML_HEAD_TEMPLATE = """\
<head>
    <meta charset="utf-8">
    <title>PR #{pr_number} Convergence Insights</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    {style_block}
</head>"""

HTML_STYLE_BLOCK = """\
<style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; background: #f8fafc; color: #334155; line-height: 1.65; padding: 48px 24px; }
    .container { max-width: 800px; margin: 0 auto; }
    h1 { font-size: 32px; font-weight: 700; color: #0f172a; margin-bottom: 8px; }
    h2 { font-size: 20px; font-weight: 600; color: #0f172a; margin-top: 48px; margin-bottom: 16px; }
    .subtitle { color: #64748b; font-size: 15px; margin-bottom: 32px; }
    .nav-toc { display: flex; flex-wrap: wrap; gap: 8px; margin: 24px 0 32px 0; padding: 16px; background: white; border-radius: 8px; border: 1px solid #e2e8f0; }
    .nav-toc a { font-size: 12px; color: #64748b; text-decoration: none; padding: 6px 12px; border-radius: 6px; background: #f1f5f9; transition: all 0.15s; }
    .nav-toc a:hover { background: #e2e8f0; color: #334155; }
    .stats-row { display: flex; gap: 24px; margin-bottom: 40px; padding: 20px 0; border-top: 1px solid #e2e8f0; border-bottom: 1px solid #e2e8f0; flex-wrap: wrap; }
    .stat { text-align: center; }
    .stat-value { font-size: 24px; font-weight: 700; color: #0f172a; }
    .stat-label { font-size: 11px; color: #64748b; text-transform: uppercase; }
    .at-a-glance { background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); border: 1px solid #f59e0b; border-radius: 12px; padding: 20px 24px; margin-bottom: 32px; }
    .glance-title { font-size: 16px; font-weight: 700; color: #92400e; margin-bottom: 16px; }
    .glance-sections { display: flex; flex-direction: column; gap: 12px; }
    .glance-section { font-size: 14px; color: #78350f; line-height: 1.6; }
    .glance-section strong { color: #92400e; }
    .section-intro { font-size: 14px; color: #64748b; margin-bottom: 16px; }
    .charts-row { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin: 24px 0; }
    .chart-card { background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; }
    .chart-title { font-size: 12px; font-weight: 600; color: #64748b; text-transform: uppercase; margin-bottom: 12px; }
    .bar-row { display: flex; align-items: center; margin-bottom: 6px; }
    .bar-label { width: 116px; font-size: 11px; color: #475569; flex-shrink: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .bar-track { flex: 1; height: 6px; background: #f1f5f9; border-radius: 3px; margin: 0 8px; }
    .bar-fill { height: 100%; border-radius: 3px; }
    .bar-value { width: 28px; font-size: 11px; font-weight: 500; color: #64748b; text-align: right; }
    .bugs { display: flex; flex-direction: column; gap: 16px; margin-bottom: 24px; }
    .bug-card { border-radius: 8px; padding: 16px; }
    .bug-card.crit { background: #fef2f2; border: 1px solid #fca5a5; }
    .bug-card.minor { background: #fffbeb; border: 1px solid #fcd34d; }
    .bug-head { display: flex; align-items: flex-start; gap: 10px; flex-wrap: wrap; }
    .bug-num { font-size: 13px; font-weight: 700; color: #94a3b8; min-width: 28px; }
    .bug-title { flex: 1 1 300px; font-weight: 600; font-size: 15px; }
    .bug-card.crit .bug-title { color: #991b1b; }
    .bug-card.minor .bug-title { color: #92400e; }
    .badges { display: flex; gap: 6px; flex-wrap: wrap; }
    .badge { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .5px; padding: 3px 8px; border-radius: 20px; white-space: nowrap; }
    .b-p0 { background: #fee2e2; color: #991b1b; }
    .b-p1 { background: #fee2e2; color: #991b1b; }
    .b-p2 { background: #fef3c7; color: #92400e; }
    .b-fixed { background: #dcfce7; color: #166534; }
    .bug-impact { font-size: 13px; color: #7f1d1d; margin-top: 10px; line-height: 1.55; }
    .bug-card.minor .bug-impact { color: #78350f; }
    .bug-fix { background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 6px; padding: 10px 12px; margin-top: 10px; font-size: 13px; color: #166534; line-height: 1.5; }
    .bug-fix b { color: #15803d; }
    .bug-meta { font-size: 11px; color: #94a3b8; margin-top: 10px; }
    .bug-meta code { background: #f1f5f9; padding: 1px 6px; border-radius: 4px; font-family: monospace; color: #475569; }
    .horizon-card { background: linear-gradient(135deg, #faf5ff 0%, #f5f3ff 100%); border: 1px solid #c4b5fd; border-radius: 8px; padding: 16px; }
    .horizon-title { font-weight: 600; font-size: 15px; color: #5b21b6; margin-bottom: 8px; }
    .horizon-possible { font-size: 14px; color: #334155; margin-bottom: 10px; line-height: 1.5; }
    .horizon-tip { font-size: 13px; color: #6b21a8; background: rgba(255,255,255,0.6); padding: 8px 12px; border-radius: 4px; }
    footer { margin-top: 40px; padding-top: 18px; border-top: 1px solid #e2e8f0; color: #94a3b8; font-size: 12px; }
    footer code { background: #f1f5f9; padding: 1px 6px; border-radius: 4px; font-family: monospace; color: #475569; }
    @media (max-width: 640px) { .charts-row { grid-template-columns: 1fr; } .stats-row { justify-content: center; } }
</style>"""
