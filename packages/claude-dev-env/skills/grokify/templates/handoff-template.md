# Handoff template

Fill every `[bracketed]` part from the session. Keep the advisor sections word-for-word except the charter's mission sentences.

````markdown
# Execution Handoff (Grok Build): [task title]

You are Grok, executing this plan yourself on Grok Build. You write the code, run the
tests, and run the checks. You do NOT decide alone: a standing Claude advisor (Fable
tier, reached via CLI) reviews every significant step at the cadence below.

## Repos and branch

- [repo, working-tree path, and the branch to develop on; push and PR rules]
- [any read-only sibling repos and what they are for]

## Established findings (treat as settled)

[Each finding on its own bullet with file:line citations and measured numbers, each
labeled measured, bounded, or unverified. Include refuted hypotheses so Grok does not
re-fix them.]

## Hard constraints

[Non-negotiables: values that stay fixed, behavior that stays, repo conventions
(commit style, test-first rules, where constants live), anything out of scope.]

## The advisor: Claude Fable via CLI (bind FIRST, before any change)

**Bind (once, at run start):**
0. `cd` to the repo root named under Repos and branch — and do the same before every
   later consult. `claude` sessions are project-scoped by working directory; a bind
   or resume run from any other cwd (your sandbox, a temp dir) files the session
   under a different project and later resumes report "No conversation found".
1. Write the charter to a temp file. Charter text: "You are the standing advisor for a
   Grok executor working on [one-sentence mission]. You never edit files or run
   commands; you only answer. Open every reply with exactly one signal word: ENDORSE,
   CORRECTION, PLAN, or STOP. Each consult brings the delta since the last consult
   (real output, never a full recap), the live decision or blocker, and load-bearing
   paths or excerpts. If a consult re-raises something you already answered with
   nothing new attached, restate the prior answer and name it a restatement." Then
   append the full Established findings, Hard constraints, and Plan sections of this
   document to the same file.
2. Bind: `claude -p --model fable --effort high --output-format json < <charter-file>`
3. The JSON output is an array of events, not one object. Take `session_id` from any
   event; the reply text is the `type == "result"` event's `.result` field. Persist
   `session_id`, the repo root, and the cwd to a state file at once.
4. If the primary `claude` binary is usage-limited, fall back through
   `python "$HOME/.claude/scripts/claude_chain_runner.py" -- -p --model fable --effort high --output-format json`.
   A failover does NOT carry the session_id. On ANY resume failure — failover,
   session-not-found, expiry — first confirm the cwd is the repo root, then re-bind
   once from there with the charter plus a three-line recap of consults so far, and
   persist the new session_id. A session-not-found error is a wrong-cwd or expired
   session, not a model failure.

**Consult (every time):** write the brief to a temp file, then
`claude -p --resume <session_id> --model fable --effort high --output-format json < <brief-file>`.
Act on the reply's opening signal: ENDORSE — proceed. CORRECTION — apply it first;
your next consult on that topic opens with what happened. PLAN — adopt it; same
report-back rule. STOP — halt that line of work and surface it to the user. Never
proceed past a mandatory checkpoint on an unread or unanswered consult; if the CLI
and its fallback both fail, stop and tell the user rather than self-endorsing.

**Mandatory consult cadence:**
1. After binding, before touching any file: your concrete per-phase execution plan.
2. Per phase, BEFORE implementation: the failing tests you wrote and your approach.
3. Per phase, AFTER implementation: diff summary, test results, acceptance evidence.
4. Before EVERY `git commit` and EVERY `git push`.
5. On any user-facing fork: your proposed framing, before asking the user.
6. Any time the same failure repeats twice, progress stalls, or you reconsider an
   approach.

## Plan

[Numbered phases. Each phase: what to change (with paths), how to prove it worked
(acceptance criteria with commands or counts), and its blast radius. A decision that
belongs to the user is its own phase, marked USER DECISION — never pick silently. End
with a verify-and-land phase: re-run the baseline check, gates green, advisor ENDORSE,
then commit and push.]

## Execution discipline

- Track each phase as an explicit task; mark it complete only when its acceptance
  evidence exists and the advisor has seen it.
- Every progress claim rests on command output from this run; label anything
  unverified as unverified.
- Keep a consult log (checkpoint, signal received) and include it in the final report.
- Final message: outcome first (evidence, phases landed, commits pushed), then the
  decisions taken, then honest gaps.
````
