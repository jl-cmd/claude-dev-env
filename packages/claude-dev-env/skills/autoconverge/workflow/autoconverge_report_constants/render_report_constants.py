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

WORKFLOW_NAME_AUTOCONVERGE = "autoconverge"
PROJECTS_DIR_NAME = "projects"
COMBINED_RUN_ID_PREFIX = "wf_combined-"
SUMMARY_DETAIL_MAX_CHARS = 400

ARGS_FIELD_OWNER = "owner"
ARGS_FIELD_REPO = "repo"
ARGS_FIELD_PR_NUMBER = "prNumber"
JOURNAL_FIELD_ARGS = "args"
JOURNAL_FIELD_WORKFLOW_NAME = "workflowName"
JOURNAL_FIELD_TIMESTAMP = "timestamp"
JOURNAL_FIELD_RESULT = "result"
JOURNAL_FIELD_RUN_ID = "runId"
JOURNAL_FIELD_WORKFLOW_PROGRESS = "workflowProgress"
RESULT_FIELD_FINAL_SHA = "finalSha"
PROGRESS_FIELD_AGENT_ID = "agentId"
PROGRESS_FIELD_LABEL = "label"

SUMMARY_FIELD_PR_PROBLEM = "prProblem"
SUMMARY_FIELD_PR_FIX = "prFix"
SUMMARY_FIELD_PROBLEM_SCENES = "problemScenes"
SUMMARY_FIELD_FIX_SCENES = "fixScenes"
SUMMARY_FIELD_VERDICT_LINE = "verdictLine"
SUMMARY_FIELD_ISSUE_CLASSES = "issueClasses"

ISSUE_CLASS_FIELD_PLAINNAME = "plainName"
ISSUE_CLASS_FIELD_COUNT = "count"
ISSUE_CLASS_FIELD_SEVERITY = "severity"
ISSUE_CLASS_FIELD_CATEGORY = "category"
ISSUE_CLASS_FIELD_STATUS = "status"
ISSUE_CLASS_FIELD_CAUSE = "cause"
ISSUE_CLASS_FIELD_MEDIUM = "medium"
ISSUE_CLASS_FIELD_BEFORE_LINES = "beforeLines"
ISSUE_CLASS_FIELD_AFTER_LINES = "afterLines"

SCENE_FIELD_TRIGGER = "trigger"
SCENE_FIELD_CONDITION = "condition"
SCENE_FIELD_RESULT = "result"
SCENE_FIELD_CAPTION = "caption"

MEDIUM_TERMINAL = "terminal"
MEDIUM_CODE = "code"
MEDIUM_TEXT = "text"

CATEGORY_BUG = "bug"
CATEGORY_LABEL_BY_VALUE = {
    "bug": "bug",
    "code-standard": "code standard",
}
CATEGORY_SORT_ORDER = {
    "bug": 0,
    "code-standard": 1,
}

STATUS_LABEL_BY_VALUE = {
    "fixed": "fixed",
    "deferred": "deferred",
}

SEVERITY_SORT_RANK = {
    "P0": 0,
    "P1": 1,
    "P2": 2,
}

TIMELINE_BEFORE_LABEL = "Before the fix"
TIMELINE_AFTER_LABEL = "After the fix"
TIMELINE_BEFORE_PILL = "BROKEN"
TIMELINE_AFTER_PILL = "WORKS"
TIMELINE_TERMINAL_BAR_LABEL = "terminal"

CAUSE_MUTED_STYLE = "color:#94a3b8;"

GITHUB_PR_URL_TEMPLATE = "https://github.com/{owner}/{repo}/pull/{number}"

SUMMARY_PR_COORDINATES_TEMPLATE = "owner={owner} repo={repo} PR #{pr_number} ({url})"
SUMMARY_FINDING_LINE_TEMPLATE = (
    "{number}. [{severity}/{category}] {file}:{line} - {title} :: {detail}"
)
SUMMARY_FIX_LINE_TEMPLATE = "{number}. {summary}"
SUMMARY_FINDINGS_EMPTY_TEXT = "none - every lens was clean on a stable HEAD"
SUMMARY_FIX_EMPTY_TEXT = "none"
SUMMARY_STANDARDS_NOTE_TEMPLATE = "\nDeferred code-standard note: {note}\n"
SUMMARY_COPILOT_NOTE_TEMPLATE = "\nCopilot gate note: {note}\n"

SUMMARY_PROMPT_TEMPLATE = """\
You write the plain-language convergence summary for {pr_coordinates}. The autoconverge run reached convergence in {round_count} round(s).

First read what THIS PR is for. Run exactly:
  gh api repos/{owner}/{repo}/pulls/{pr_number} --jq '{{title: .title, body: .body}}'
Ground every sentence in that PR title and description plus the findings and fix summaries below; invent nothing not present in those sources.

Distinct findings caught across the run (already deduped):
{findings_block}

Per-round fix summaries:
{fix_block}
{standards_block}{copilot_block}
Write so a non-programmer understands every line. The reader has never seen the code and does not know its internals.
- prProblem and prFix are each ONE plain sentence describing THIS PR for a reader with zero prior context. prProblem: what was wrong or at risk before this PR. prFix: what this PR changes to solve it. They are the fallback shown when problemScenes/fixScenes are empty, so keep them self-contained.
- In prProblem, NAME the concrete project or component (from the repo name and PR description) and gloss in plain words what it is the first time you mention it. NEVER write a bare "the tool", "the app", or "the system" before naming it.
- Read the PR description for the motivation it states (often a "Hardens against X" / "Fixes Y" line) and write prProblem from that. Cover the whole PR, not only what the review caught.
- EVERY sentence must be concrete and checkable against the PR description. A reader must be able to picture exactly what happened. If you cannot state something concretely and truthfully from the PR title and description, leave it out - never fill space with a vague claim.
- Banned vague phrasings (a reader cannot picture them): "installs itself", "more reliable", "sets things up properly", "works better", "improves handling", "eliminates side effects", "hardens". Replace each with the concrete thing that happened.
- prProblem/prFix example (a DIFFERENT project, to show the style not the answer). WEAK: prProblem "This makes the tool's setup more reliable." STRONG: prProblem "PhotoSync, the app that backs up your phone photos, stopped backing them up after you switched accounts and never said so." prFix "It now re-checks your account on each backup, so a switch does not halt backups."
- problemScenes and fixScenes turn the problem and the fix into 1 to 3 short cause->effect scenes each. Each scene has very short fragments (chips): trigger = the starting action or state, condition = the middle event (may be the empty string), result = the outcome (bad in a problem scene, good in a fix scene), plus caption = one plain grounded sentence explaining the scene. A fix scene mirrors a problem scene: same trigger, good result. If the PR is one-dimensional, one scene each is fine.
- problemScenes/fixScenes example (a DIFFERENT project, to teach the style not the answer). Problem scene: trigger "export stops at batch 90", condition "you restart it", result "starts again at batch 1", caption "A halted export threw away the 90 batches it had already finished and began again." Mirroring fix scene: trigger "export stops at batch 90", condition "you restart it", result "continues at batch 91", caption "A restarted export now picks up at the next unfinished batch."
- GROUP near-duplicate findings into issue CLASSES: the same KIND of problem across different files or lines becomes ONE class with a count. Example: seven "Missing return type annotation on test function" findings become one class with count 7.
- TRANSLATE reviewer jargon into plain everyday English. Examples: "CodingGuidelineID 1000000 / Repository guideline (Types)" -> "a typing rule the project enforces"; "missing return type annotation / Add -> None" -> "a test did not declare what it returns"; "Banned identifier result" -> "a vague variable name the project bans"; a magic-value finding -> "a raw number or string that should be a named value".
- plainName: a short plain symptom a non-programmer recognizes - name what BROKE or what a person would notice, not the internal component. Carry NO tool token, rule id, file path, line number, severity code (P0/P1/P2), or bot name. Good: "The install command quietly did nothing". Weak: "Entry-point guard misfires under symlinked bin invocation".
- cause is the field that matters most. Sentence 1: the observable impact - what a person saw go wrong, or would have. Sentence 2: the cause in everyday terms. At most 2 sentences, no paragraphs.
- In cause describe the CONSEQUENCE, never the internal mechanism. Do not narrate control flow, comparisons, or internal state. Banned phrasings: "a check returned false", "two forms of the path", "treated the run as a non-run", "the values did not match", "a guard misfired". Say what that meant for the person instead.
- Prefer concrete everyday words: "the install command" and "on Mac and Linux" over "the launcher", "the entry-point guard", or "the symlink". Read each sentence as if aloud to a non-programmer; if they would not follow it, rewrite it.
- cause worked example (a DIFFERENT problem, to show the style, not the answer). WEAK, do not write like this: "A cached value's timestamp was compared across mismatched time zones, so the freshness check evaluated false and the entry was treated as stale and re-fetched on every request." STRONG, write like this: "Every page re-downloaded the same data from scratch instead of reusing the copy it already had, so pages loaded slower than needed. The app misjudged its saved copy as out of date."
- medium picks how the before/after panels are drawn: 'terminal' when the user-visible effect is command-line behavior; 'code' when the finding is best shown as a small before/after code snippet (e.g. a missing return type: before "def test_x():" / after "def test_x() -> None:"); 'text' otherwise.
- beforeLines and afterLines are the literal short lines to show in each panel - what a person sees. For a terminal: include the prompt + command + the (missing or present) output. For code: 1 to 4 lines before, 1 to 4 lines after. Keep every line short. Never fabricate exact output text that is not implied by the finding - if the exact text is unknown, show the shape (e.g. "(no output - nothing installed)"). Leave both arrays empty to fall back to the cause line alone.
- Lead with category 'bug' classes, then 'code-standard'. Create one class per distinct KIND of problem, however many that is; never merge different kinds or drop classes to hit a number.
- status is 'fixed' unless the fix summaries or the deferred code-standard note mark the class deferred, in which case status is 'deferred'.
- Use NO hedging words anywhere (likely, probably, should, appears, seems, may, might, could, possibly). State facts ("caught and fixed").
- When there are zero findings, return issueClasses: [] and a verdictLine stating the run converged with no issues caught.
- verdictLine is one plain factual sentence naming the round count and that all classes are fixed or deferred.

Return strictly a JSON object with keys prProblem, prFix, problemScenes, fixScenes, verdictLine, and issueClasses."""

HTML_DOCTYPE = "<!DOCTYPE html>"

HTML_HEAD_TEMPLATE = """\
<head>
<meta charset="utf-8">
<title>PR #{pr_number} Convergence Summary</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
{style_block}
</head>"""

HTML_STYLE_BLOCK = """\
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; background: #f1f5f9; color: #334155; line-height: 1.6; padding: 48px 20px; }
  .container { max-width: 860px; margin: 0 auto; }
  h1 { font-size: 30px; font-weight: 800; color: #0f172a; letter-spacing: -0.5px; }
  .subtitle { color: #64748b; font-size: 14px; margin: 6px 0 26px; }
  h2 { font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.6px; color: #94a3b8; margin: 40px 0 16px; }

  /* verdict */
  .verdict { display: flex; align-items: center; gap: 14px; background: linear-gradient(135deg,#dcfce7,#bbf7d0); border:1px solid #22c55e; border-radius: 14px; padding: 18px 22px; }
  .verdict .check { width: 34px; height: 34px; border-radius: 50%; background:#16a34a; color:#fff; display:flex; align-items:center; justify-content:center; font-size:19px; flex:0 0 auto; }
  .verdict .vtext { font-size: 16px; font-weight: 700; color:#0f172a; }
  .verdict .vsub { font-size: 13px; font-weight: 500; color:#15803d; }

  /* problem / fix scenes */
  .pf-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  .pf { border-radius: 12px; padding: 18px 20px; border:1px solid #e2e8f0; background:#fff; }
  .pf-tag { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing:.5px; padding: 3px 10px; border-radius: 20px; display:inline-block; margin-bottom: 14px; }
  .pf.problem { border-left: 4px solid #ef4444; }
  .pf.fix { border-left: 4px solid #22c55e; }
  .pf.problem .pf-tag { background:#fee2e2; color:#b91c1c; }
  .pf.fix .pf-tag { background:#dcfce7; color:#15803d; }
  .scene { display:flex; align-items:center; gap:10px; font-family:'JetBrains Mono',monospace; font-size:12.5px; padding: 9px 0; flex-wrap: wrap; }
  .chip { background:#f1f5f9; border:1px solid #e2e8f0; border-radius:6px; padding:4px 9px; color:#334155; white-space:nowrap; }
  .arrow { color:#94a3b8; font-weight:700; }
  .note { color:#94a3b8; font-size:11px; font-style:italic; }
  .res-bad { color:#dc2626; font-weight:600; white-space:nowrap; }
  .res-good { color:#16a34a; font-weight:600; white-space:nowrap; }
  .scene-cap { font-size:12px; color:#64748b; margin: 2px 0 12px; }
  .scene-cap:last-child { margin-bottom:0; }

  /* bug class */
  .bug-head { display:flex; align-items:baseline; justify-content:space-between; gap:12px; margin:32px 0 12px; }
  .bug-head:first-of-type { margin-top:8px; }
  .bug-name { font-size:16px; font-weight:700; color:#0f172a; }
  .bug-count { font-size:12px; font-weight:600; color:#64748b; background:#f1f5f9; border:1px solid #e2e8f0; border-radius:20px; padding:3px 11px; white-space:nowrap; flex:0 0 auto; }

  /* terminals */
  .term-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; align-items:start; }
  .term-wrap .tlabel { font-size:12px; font-weight:700; margin-bottom:7px; display:flex; align-items:center; gap:7px; }
  .term-wrap.before .tlabel { color:#b91c1c; }
  .term-wrap.after .tlabel { color:#15803d; }
  .pill-x { background:#fee2e2; color:#b91c1c; border-radius:20px; font-size:10px; padding:2px 8px; font-weight:700; }
  .pill-c { background:#dcfce7; color:#15803d; border-radius:20px; font-size:10px; padding:2px 8px; font-weight:700; }
  .terminal { background:#0f172a; border-radius:10px; overflow:hidden; box-shadow:0 6px 18px rgba(15,23,42,.18); }
  .term-bar { background:#1e293b; padding:9px 12px; display:flex; gap:7px; align-items:center; }
  .term-bar i { width:11px; height:11px; border-radius:50%; display:inline-block; }
  .term-bar .r{background:#ef4444;} .term-bar .y{background:#f59e0b;} .term-bar .g{background:#22c55e;}
  .term-bar span { color:#64748b; font-size:11px; font-family:'JetBrains Mono',monospace; margin-left:6px; }
  .term-body { padding:14px 16px; font-family:'JetBrains Mono',monospace; font-size:12.5px; line-height:1.7; color:#e2e8f0; min-height:104px; }
  .term-body .pr { color:#38bdf8; }
  .term-body .cmd { color:#e2e8f0; }
  .term-body .dim { color:#64748b; }
  .term-body .ok { color:#4ade80; }
  .term-body .cursor { display:inline-block; width:8px; height:15px; background:#475569; vertical-align:-2px; }
  .code-panel { background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:14px 16px; font-family:'JetBrains Mono',monospace; font-size:12.5px; line-height:1.7; color:#334155; min-height:104px; overflow:auto; }
  .text-panel { background:#fff; border:1px solid #e2e8f0; border-radius:10px; padding:14px 16px; font-size:13px; line-height:1.7; color:#475569; min-height:104px; }

  .cause { background:#fff; border:1px solid #e2e8f0; border-radius:10px; padding:14px 18px; margin-top:16px; font-size:14px; color:#475569; }
  .cause b { color:#0f172a; }

  footer { margin-top:40px; padding-top:16px; border-top:1px solid #e2e8f0; color:#94a3b8; font-size:12px; }
  footer code { background:#e2e8f0; padding:1px 6px; border-radius:4px; font-family:'JetBrains Mono',monospace; }
  @media (max-width:680px){ .pf-grid,.term-grid{grid-template-columns:1fr;} }
</style>"""
