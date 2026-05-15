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

## When this skill applies

User types `/findbugs` or asks for a bug audit on the current branch's PR. Typical moment: PR is up (draft or ready), and the user wants an independent second pair of eyes before merge or before requesting human review.

If the current branch has no associated PR and no diff against the default branch, say so and stop. Do not invent scope.

## The Process

### Step 1: Resolve PR scope

Determine the audit target in this order:

1. **Open PR for current branch.** Call `pull_request_read(method="get", pullNumber=N, owner=O, repo=R)` for the current branch (`N` comes from the parent skill's context, or fall back to `search_issues` MCP with the current branch name to recover the PR number). If a PR exists, capture its number, base ref, head ref, and URL.
2. **No PR but a remote default branch exists.** Diff against the default branch's merge-base: `git merge-base HEAD origin/<default>` then `git diff <merge-base>...HEAD`. Treat this as the audit scope.
3. **Neither.** Respond exactly: `No PR or upstream diff found. Push the branch or open a PR first.` and stop.

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
  A. API contract verification (signatures, return types, async/await correctness)
  B. Selector / query / engine compatibility
  C. Resource cleanup and lifecycle (file handles, connections, processes, locks)
  D. Variable scoping, ordering, and unbound references
  E. Dead code and unused imports
  F. Silent failures (catch-all excepts, unconditional success returns, missing error propagation)
  G. Off-by-one, bounds, and integer overflow
  H. Security boundaries (injection, path traversal, auth bypass, secret leakage)
  I. Concurrency hazards (race conditions, missing awaits, shared mutable state)
  J. Magic values and configuration drift
</bug_categories>

<constraints>
  Read-only. Report findings only. Do not modify code, do not propose
  full diffs, do not commit, do not push. Cite file:line for every claim.
  When the diff alone does not provide enough context to confirm or deny
  a bug, list it under "Open questions" rather than asserting.
</constraints>

<output_format>
  Follow the shared audit contract at ../bugteam/reference/audit-contract.md:

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

**Self-PR precondition.** GitHub rejects both `APPROVE` and
`REQUEST_CHANGES` reviews when the authenticated identity matches the
PR author with HTTP 422; `post_audit_thread.py` retries and then exits 2.
To run findbugs on a PR you authored, switch `gh auth` to an alternate
reviewer identity (a separate GitHub account) BEFORE invoking the skill.
Without this switch, exit 2 is a hard halt — there is no automated
fallback path. The script does not auto-downgrade on the self-PR case.

After the agent (and Haiku secondary) return and the merge is complete,
serialize the merged findings to a JSON file and call
`post_audit_thread.py`:

```
python "${CLAUDE_SKILL_DIR}/../../_shared/pr-loop/scripts/post_audit_thread.py" \
  --skill findbugs \
  --owner <owner> \
  --repo <repo> \
  --pr-number <N> \
  --commit <head_sha> \
  --state <CLEAN|DIRTY> \
  --findings-json <path>
```

The findings JSON root is a list of objects shaped
`{path, line, side, severity, description, fix_summary}`. Before
serializing, partition the merged findings into anchored (line appears
in the captured diff) and unanchored (line is not in the diff) buckets.
Only anchored findings are serialized to the JSON — the GitHub reviews
API rejects the entire POST if any inline comment in `comments[]`
targets a line not in the diff at `--commit`, so a single unanchored
entry breaks the whole review. Unanchored findings are surfaced via
Step 5's user-facing output rather than as inline anchored comments.
For each anchored finding, map `file` → `path`; split the finding's
`failure_mode` at the literal `Fix:` heading so the failure narrative
becomes `description` and the suffix beginning at `Fix:` (including
the trailing `Validation:` clause) becomes `fix_summary` (the
`failure_mode` field carries the full audit-to-fix handoff per
[`agents/code-quality-agent.md`](../../agents/code-quality-agent.md)).
When a finding's `failure_mode` omits the `Fix:` heading, write the
full text to BOTH `description` and `fix_summary`. Set `side="RIGHT"`
for every entry. Zero anchored findings → `--state CLEAN` with the
findings file holding an empty array (`[]`); one or more anchored
findings → `--state DIRTY` with the full list. CLEAN posts an APPROVE review (the
request event; GitHub stores it as `state=APPROVED`) with a "no
findings" summary; DIRTY posts a REQUEST_CHANGES review with one inline
anchored comment per finding (each becomes its own resolvable thread on
the PR).

Capture `<head_sha>` once at the start of Step 4 via `git rev-parse
HEAD` in the worktree the diff was scoped against.

Exit codes: `0` on success (emits the new review's `html_url` to
stdout, surface alongside the totals in Step 5); `1` on user input
error; `2` on retry exhaustion (1s / 4s / 16s backoff across four
attempts). On exit 2, tell the user the review post failed and that
the unresolved-thread gate will not see this audit pass; do not retry
silently.

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

`1 P0 / 2 P1 / 0 P2 — 7 categories cleared`

`P0 — race condition on shared cache write`
`  src/cache.py:88 — concurrent writers can both pass the existence check before either writes (category: concurrency)`

`P1 — silent paste failure`
`  utils/clipboard.py:33 — validated_paste returns success without verifying the post-paste state (category: silent failure)`

`P1 — unbound variable on early-exception path`
`  src/processor.py:283 — scheduling_log referenced after try/finally where it may be unbound (category: scoping)`

`Verified clean: API contract, selector compatibility, resource cleanup, dead code, off-by-one, security boundaries, magic values`

`Open questions: none`

`Want me to run /fixbugs for the P0 + P1s?`
</example>

<example>
User: `/findbugs`
Claude: `No PR or upstream diff found. Push the branch or open a PR first.`
</example>

<example>
User: `/findbugs` (branch with no PR but commits ahead of main)
Claude: [falls back to `git diff origin/main...HEAD`, runs audit on that diff scope]
</example>

## Why this design

Anchoring bias is the failure mode of context-rich audits. An agent that inherits "we just fixed three bugs in clipboard_utils.py" subconsciously scopes its hunt around clipboard_utils.py and pattern-matches on the same bug shapes. A clean-room audit on the full PR diff treats every file equally, considers every category, and surfaces things the orchestrator session never looked at. The diff is the contract; everything else is noise.
