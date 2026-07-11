---
name: findbugs
description: >-
  Audits the current branch's pull request as a whole for bugs by spawning the
  code-quality-agent against the full PR diff with zero conversation context.
  Returns P0/P1/P2 findings with file:line evidence and a verified-clean
  coverage list. Read-only — never modifies code. Triggers: '/findbugs',
  'find bugs in this PR', 'audit the PR', 'bug audit on the branch'.
---

# Findbugs

**Core principle:** A clean-room bug audit on the entire pull request. The audit agent receives the PR diff and nothing else — no chat history, no prior framing, no implicit "we already looked at this." Independence is the point.

## Transport check (before any GitHub step)

Run `command -v gh`; when it succeeds, run `gh auth status`; once the PR scope is resolved, run `gh api repos/<owner>/<repo> --jq .permissions.push` and take `true` as the pass. When any check fails, run the `pr-loop-cloud-transport` skill first and route every `gh` operation in this skill through its substitution matrix.

## When this skill applies

User types `/findbugs` or asks for a bug audit on the current branch's PR. Typical moment: PR is up (draft or ready), and the user wants an independent second pair of eyes before merge or before requesting human review.

If the current branch has no associated PR and no diff against the default branch, say so and stop. Do not invent scope.

## Refusals

First match wins; respond with the quoted line exactly and stop:

- **Disabled via environment.** When `CLAUDE_REVIEWS_DISABLED` carries the
  token `bugteam`:
  `/findbugs is disabled via CLAUDE_REVIEWS_DISABLED.` Run the check via
  `python "$HOME/.claude/_shared/pr-loop/scripts/reviews_disabled.py" --reviewer bugteam`
  (exit 0 = disabled). `/findbugs` is a PR bug-audit skill in the same family
  as `/bugteam` and `/qbug`, so the shared `bugteam` token disables all three.
  The gate semantics live in the `reviewer-gates` skill (`../reviewer-gates/SKILL.md`).

## The Process

### Step 1: Resolve PR scope

Apply the `pr-scope-resolve` skill (`../pr-scope-resolve/SKILL.md`) with caller `findbugs`. Findbugs consumes the resolved `owner`, `repo`, `number`, `head_ref`, `base_ref`, and `url`; when no PR exists, the ladder's merge-base rung sets the audit scope. When no target exists, respond exactly with the sub-skill's canonical refusal line and stop:

`No PR or upstream diff. /findbugs needs a target.`

### Step 2: Capture the full PR diff

Resolve the temp diff path **once, Claude-side**, before invoking any shell command. Use Python's `tempfile.gettempdir()` which honors `TMPDIR`, `TEMP`, and `TMP` in the platform-correct order and falls back to `C:\Users\<user>\AppData\Local\Temp` on Windows or `/tmp` on Unix. Avoid hand-rolled env var chains. The lookup works on macOS, Linux, Windows cmd.exe, and PowerShell:

```
import tempfile
diff_temp_path = Path(tempfile.gettempdir()) / f"findbugs-pr-{os.getpid()}.patch"
```

`os.getpid()` supplies the per-invocation suffix that prevents collisions with parallel `/findbugs` runs (a UUID or timestamp is equally acceptable). Capture the resolved absolute path as `<diff_temp_path>` and pass that **literal** path to every shell command that follows. Shell-side parameter expansion (`${TMPDIR:-/tmp}`, `$$`, `%TEMP%`) is forbidden because cmd.exe and PowerShell do not honor it.

When a PR exists: call `pull_request_read(method="get_diff", pullNumber=N, owner=O, repo=R)` and save the returned diff content to `"<diff_temp_path>"`.

When falling back to merge-base diff: `git diff <merge-base>...HEAD > "<diff_temp_path>"`.

The audit's authoritative scope is this single diff file. Do not inject extra files, related history, or "files Claude edited this session" — those introduce anchoring bias.

### Step 3: Spawn the code-quality-agent — clean room

Call the Agent tool twice in a single message (primary + Haiku secondary per the audit contract's Haiku secondary section):

- Primary: `subagent_type: code-quality-agent`, `model: sonnet`, `description: "PR bug audit"`, `run_in_background: false`
- Secondary: `subagent_type: code-quality-agent`, `model: haiku`, `description: "PR bug audit (secondary)"`, `run_in_background: false`

After both return, merge per the contract's Haiku secondary section (de-dup key, max-wins severity, malformed-output fallback) before reporting to the user.

**The agent prompt must be self-contained and context-free.** Specifically:

- **No references to the orchestrator's conversation.** Forbidden phrases: "as we discussed," "the earlier issue," "given our prior work," "the bug from last turn," "you previously identified."
- **No hints about expected outcomes.** Do not pre-stage findings, do not suggest where bugs probably are, do not name files as "the suspicious one." The agent forms its own hypotheses.
- **No instructions to favor or skip particular categories** beyond the standard category list. No "skip the typing stuff" or "focus on the clipboard logic" — those bias the audit.
- **Minimal background.** Identify the repo, branch, base branch, and PR URL only. Do not summarize what the PR does.

The XML prompt skeleton:

```xml
<context>
  <repo>owner/repo</repo>
  <branch>head ref</branch>
  <base_branch>base ref</base_branch>
  <pr_url>url or "none"</pr_url>
</context>

<scope>
  <diff_path><diff_temp_path> (absolute scoped temp path from Step 2)</diff_path>
  <scope_rule>Audit only lines added or modified in the diff. Pre-existing code on untouched lines is out of scope.</scope_rule>
</scope>

<bug_categories>
  Investigate each explicitly:
  A. API contract verification
  B. Selector / query / engine compatibility
  C. Resource cleanup and lifecycle
  D. Variable scoping, ordering, and unbound references
  E. Dead code and unused imports
  F. Silent failures
  G. Off-by-one, bounds, integer overflow
  H. Security boundaries
  I. Concurrency hazards
  J. CODE_RULES.md compliance
  K. Codebase conflicts (incomplete propagation)
  L. Behavior-equivalence for refactors
  M. Producer/consumer cardinality vs collection-type contract
  N. Test-name scenario verifier
  O. Docstring / fixture-prose vs implementation drift
  P. Name / regex / word-list vs behavior-contract precision

  The category list above is a summary. The binding definition of each
  category is its rubric file under $HOME/.claude/audit-rubrics/category_rubrics/
  (ready-to-send prompt variants under $HOME/.claude/audit-rubrics/prompts/).
  Read the rubric files before auditing.
</bug_categories>

<constraints>
  Read-only. Report findings only. Do not modify code, do not propose
  full diffs, do not commit, do not push. Cite file:line for every claim.
  When the diff alone does not provide enough context to confirm or deny
  a bug, list it under "Open questions" rather than asserting.
</constraints>

<output_format>
  Follow the shared audit contract at $HOME/.claude/_shared/pr-loop/audit-contract.md:

  - Severity: P0 = will not run / data corruption; P1 = regression or silent
    failure; P2 = dead code, minor smell.
  - Per category, produce either Shape A (structured finding) or Shape B
    (proof-of-absence). Bare "verified clean" labels are REJECTED.
  - Run the contract's adversarial second pass after the primary list.

  Preamble: `Total: N (P0=N, P1=N, P2=N)`. Emit findings and proof-of-absence
  entries in the JSON shapes defined by the contract. Include an "Open
  questions" section for items the diff alone cannot resolve.
</output_format>
```

### Step 4: Post the audit review

Every `/findbugs` invocation posts one audit review back to the PR. The
unresolved-thread gate counts review threads, so a findbugs pass that
returns findings without posting them as inline comments is invisible
to the gate. Findbugs remains read-only on code — the review post is
the only side effect.

Capture `<head_sha>` once at the start of Step 4 via `git rev-parse
HEAD` in the worktree the diff was scoped against.

After the agent (and Haiku secondary) return and the merge is complete,
apply the `post-audit-findings` skill (`../post-audit-findings/SKILL.md`)
with `--skill findbugs`. That skill owns the findings-JSON mapping, the
anchored-only serialization (unanchored findings surface via Step 5's
user-facing output), the CLEAN/DIRTY decision, the self-PR reviewer
toggle, and the exit codes. On exit 0, surface the emitted review
`html_url` alongside the totals in Step 5. On exit 2, tell the user the
review post failed and that the unresolved-thread gate will not see this
audit pass; do not retry silently.

### Step 5: Surface findings, then clean up

When the agent returns, report concisely:

- One-line totals: `N P0 / N P1 / N P2 — K categories cleared`
- Each finding's `file:line`, category, and one-sentence description
- The cleared categories so the user can see coverage breadth
- Any open questions the agent could not resolve from the diff alone

Offer the next step without auto-executing it: `Want me to run /fixbugs for the P0/P1 findings?`

Delete the scoped temp diff at `<diff_temp_path>` after the audit completes (or moves to a fix flow). Temporary diff files do not belong in the working tree.

Do not paste the full agent transcript or the XML prompt unless the user asks.

## Output Format

```
N P0 / N P1 / N P2 — K categories cleared

P1 — short title
  file/path.py:NN — one-sentence description (category: <name>)

P2 — short title
  file/path.py:NN — one-sentence description (category: <name>)

Verified clean: <category>, <category>, <category>

Open questions:
  <if any>

Want me to run /fixbugs for the P0/P1 findings?
```

## Constraints

- **Read-only on code.** The skill never edits files, never pushes, never commits. One audit review per invocation gets posted back to the PR (Step 4) — that is the only side effect, and it is required so the unresolved-thread gate sees the audit pass.
- **Foreground spawn.** The user is waiting for the result on this turn.
- **PR-scoped, not session-scoped.** The audit covers the entire PR diff regardless of which files were edited in this conversation.
- **Clean-room prompt.** The agent's prompt is self-contained — no references to chat history, no anchoring hints, no expected outcomes.
- **No clean-coder auto-spawn.** Always ask before fixing.
- **Trust the agent's verdict.** Pass through P0/P1/P2 categorizations as the agent assigned them; do not re-rank.
- **Temp file cleanup.** Delete the scoped `<diff_temp_path>` when the audit ends.

## Examples

<example>
User: `/findbugs`
Claude: [resolves PR #42 from current branch, fetches full diff, spawns code-quality-agent foreground with self-contained prompt, returns]

`1 P0 / 2 P1 / 0 P2 — 11 categories cleared`

`P0 — race condition on shared cache write`
`  src/cache.py:88 — concurrent writers can both pass the existence check before either writes (category: I — Concurrency hazards)`

`P1 — silent paste failure`
`  utils/clipboard.py:33 — validated_paste returns success without verifying the post-paste state (category: F — Silent failures)`

`P1 — unbound variable on early-exception path`
`  src/processor.py:283 — scheduling_log referenced after try/finally where it may be unbound (category: D — Variable scoping, ordering, and unbound references)`

`Verified clean: API contract, selector compatibility, resource cleanup, dead code, off-by-one, security boundaries, CODE_RULES.md compliance, codebase conflicts, behavior-equivalence, producer/consumer cardinality, Test-name scenario verifier`

`Open questions: none`

`Want me to run /fixbugs for the P0 + P1s?`
</example>

<example>
User: `/findbugs`
Claude: `No PR or upstream diff. /findbugs needs a target.`
</example>

<example>
User: `/findbugs` (branch with no PR but commits ahead of main)
Claude: [falls back to `git diff origin/main...HEAD`, runs audit on that diff scope]
</example>

## Why this design

Anchoring bias is the failure mode of context-rich audits. An agent that inherits "we just fixed three bugs in clipboard_utils.py" subconsciously scopes its hunt around clipboard_utils.py and pattern-matches on the same bug shapes. A clean-room audit on the full PR diff treats every file equally, considers every category, and surfaces things the orchestrator session never looked at. The diff is the contract; everything else is noise.
