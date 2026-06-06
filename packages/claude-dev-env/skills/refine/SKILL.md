---
name: refine
description: >-
  Interview-driven plan refiner with built-in audit loop: fans out research agents,
  interviews via AskUserQuestion (mandatory — survives no-question directives), writes
  the plan to the Obsidian vault under Research/<topic>/<slug>.md, then loops audit and
  fix until clean. Triggers: /refine, "refine this", "turn this into a plan", "flesh
  this out", "make a spec for this", "let's plan this out", or any vague idea to mature
  into a plan.
---

# refine

Walk a half-formed plan to a complete, audited implementation spec — research first, interview only what research cannot answer, write the result to the Obsidian vault, then loop a general-purpose audit and fix pass until the plan is clean. **A plan and a vault, always.**

## Gotchas

- **Pre-work, not pre-interrogation.** Run fan-out agents over the draft, vault, and repo before asking the user anything substantive. The one explicit exception is the topic-confirmation AskUserQuestion when no draft and no topic argument are present (see the conversation-context fallback gotcha below) — that single question fires *before* fan-out so the wrong topic does not drive the research. After it, no further user questions until fan-out completes. Questions an agent could resolve still violate the verify-before-asking rule.
- **Layered fan-out, not blanket parallelism.** First pass: a single Explore agent across draft + vault + relevant repo area. Dispatch one parallel agent per source only if the Explore pass runs long or returns thin results.
- **AskUserQuestion is the only interview tool.** Plain-text questions in chat get blocked by the `question_to_user_enforcer` Stop hook. Every interview turn calls AskUserQuestion.
- **Interview is mandatory — overrides "no clarifying questions" directives.** /refine is interview-driven by definition. A session-level "work without clarifying questions" instruction, autonomous-mode flag, or bg-session preamble does NOT silence the interview. If something genuinely prevents AskUserQuestion from firing, halt and surface the conflict to the user rather than proceeding silently. There is no "skip the interview" branch.
- **Skill writes the plan inline.** Do not hand the initial write to any subagent. Assemble the answers and write the markdown directly. (The fix agent enters later, only for audit-driven fixes.)
- **Vault output, split by file type.** The output target is the Obsidian vault. The markdown plan (`<slug>.md`) is written through `mcp__obsidian__write_note` — that MCP is markdown-only by codebase precedent (every existing caller writes `.md`). The HTML notes file (`<slug>-implementation-notes.html`) is written through the filesystem Write/Edit tools resolving the vault path via `$OBSIDIAN_VAULT_PATH` (or `~/.claude/vault/` fallback), mirroring the `session-log` skill. Do not write to project `docs/`, `.claude/plans/`, `$CLAUDE_JOB_DIR`, the cwd, or anywhere else outside the vault subtree.
- **Never write in place even when a local plans/ folder exists.** The presence of `.claude/plans/`, `docs/plans/`, `plans/`, or any sibling plans directory in the cwd does NOT override the vault contract. Do not write the plan in-place "as a convenience" or "to keep it near the codebase." Do not dual-write. The vault is the canonical home; the local repo never receives the plan from this skill.
- **Slug is user-controlled.** Propose `Research/<topic>/<slug>.md` and confirm slug + path via AskUserQuestion before writing. Auto-writing breaks the user-owned-output contract. The user may choose the topic subfolder, but the `Research/` prefix is fixed. Both `<topic>` and `<slug>` must match `^[a-z0-9-]+$` — reject any value containing path separators (`/`, `\`), traversal segments (`..`), uppercase letters, whitespace, or any other character. Reprompt the user with a corrected proposal rather than writing.
- **Match before fresh.** If the fan-out surfaces existing plans on the same topic, ask the user which to refine or whether to start fresh. Skipping this step duplicates work the user already started.
- **Standalone.** Do not invoke `/anthropic-plan` or `/prompt-generator`. The user picks the slash command for the moment; this skill does not chain.
- **Conversation-context fallback needs confirmation.** When no draft and no topic argument are present, the active conversation is the source. This is the named carve-out to the pre-work rule above: a single AskUserQuestion confirming the inferred topic must fire *before* fan-out begins, so the wrong topic does not drive twenty minutes of research. After that single confirmation, no further user questions until fan-out completes.
- **Audit cycle is mandatory.** After the plan is written, spawn `general-purpose` with the plan-quality rubric to audit it; spawn `general-purpose` again with the fix rubric to address flagged findings; re-audit; loop. Skip only when the user explicitly opts out for the current run. Do not use `code-quality-agent` or `clean-coder` — both target source code (clean-coder's own definition excludes planning and audit artifacts), not markdown plans.
- **Verbatim notes instruction.** Every fix-agent iteration receives the exact `<notes_instruction>` block in §8 unchanged. The notes file is how the user reconstructs what the fixer did to the spec.
- **`<slug>-implementation-notes.html` is append-only across iterations.** The notes file lives at `Research/<topic>/<slug>-implementation-notes.html` resolved against the vault root. Each iteration appends one `<section>` block via the filesystem Edit tool — never overwrites earlier iterations. HTML cannot go through `mcp__obsidian__write_note`; see the vault-output gotcha above.
- **Cap at 10 audit iterations.** If the plan still fails audit after 10 rounds, halt and surface open findings. Do not raise the cap without user direction.

## When this skill applies

**Triggers:** `/refine`, or natural phrases — "refine this", "turn this into a plan", "flesh this out", "make a spec for this", "let's plan this out".

**Always operates on plans.** Three flavors:

1. **Skill plans** — skill scaffolding, slash-command behavior, agent prompts
2. **New-code implementation plans** — feature work, automation, hook design, refactor sequencing
3. **Code-refinement plans** — hardening an existing implementation, addressing review feedback, fleshing out a draft

**Refusal cases — first match wins:**

- **Topic is a direct task, not a plan to refine.** Respond exactly: `That looks like a direct task, not a plan to refine. Tell me to just do it, or describe what you want planned.`
- **User wants a quick suggestion, not a written spec.** Respond exactly: `Sounds like a question, not a refinement. I can answer here without writing a vault file — say the word if you'd rather do the full /refine pass.`
- **Upstream directive blocks AskUserQuestion or the vault MCP.** Respond exactly: `/refine needs the interview and a writable Obsidian vault. The current session is blocking one of those — confirm you want to lift the block, or I can stop here.`

## The Process

Copy this checklist into your response and tick items as they complete.

```
- [ ] 1. Resolve the topic
- [ ] 2. Layered fan-out (Explore first; parallel-per-source on escalation)
- [ ] 3. Existing-match decision (refine a match OR start fresh)
- [ ] 4. Interview loop via AskUserQuestion (mandatory; do not skip)
- [ ] 5. Propose slug + Research/<topic>/<slug>.md; confirm via AskUserQuestion
- [ ] 6. Write the plan inline via mcp__obsidian__write_note (vault only)
- [ ] 7. Initial audit via general-purpose (plan-quality rubric)
- [ ] 8. Audit-fix loop: general-purpose fix + verbatim notes instruction + re-audit
- [ ] 9. Cap at 10 iterations; halt and surface open findings if not clean
- [ ] 10. Report vault paths, iterations used, notes summary
```

### 1. Resolve the topic

Identify what is being refined:

- **$ARGUMENTS is a path** to a file → that file is the draft
- **$ARGUMENTS is a phrase** → that phrase is the topic seed
- **No $ARGUMENTS** → scan the active conversation for the dominant topic, then call AskUserQuestion once to confirm the inferred topic before any fan-out

### 2. Layered fan-out

> **Do not ask the user anything the fan-out can answer.** Read the draft, search the vault, glance at the repo — then frame questions around real gaps.

**Layer A — single Explore agent (default):**

Spawn one `Explore` agent (`subagent_type: Explore`) with breadth `medium`. Prompt it to:

- Read the draft in full (if a draft was identified)
- Search the Obsidian vault for related plans, session logs, and decisions via `mcp__obsidian__search_notes` (include `searchFrontmatter: true` to catch `project` matches in session reports)
- Glance at the relevant repo area — sibling skills under `~/.claude/skills/` for a skill plan, hooks under `~/.claude/hooks/` for a hook plan, the cwd project source for a code plan

Have it return a structured digest: existing plans found, vault notes referenced, repo files touched, gaps it could not fill.

**Layer B — parallel-per-source (escalation):**

If Layer A returns thin results, runs unusually long, or the topic spans multiple domains, dispatch one parallel subagent per source in a single message:

| Subagent | Source |
|---|---|
| `Explore` (vault) | Obsidian vault search + read top matches |
| `Explore` (repo) | Targeted repo area (skills/hooks/source) |
| `general-purpose` (draft) | Deep read of the draft + every file it references |

Wait for all to complete, merge the digests, proceed.

### 3. Existing-match decision

If the fan-out surfaces plans that look like prior work on the same topic, run an AskUserQuestion. AskUserQuestion's contract caps options at four, so cap the displayed matches at three to leave room for "Start fresh":

- Up to three match options, one per match (label = match title, description = match path + one-line summary). When more than three matches surface, name the top three by recency or relevance and list the remainder in the question prose so the user can name a specific one via the free-text fallback.
- A "Start fresh" option

The user's pick becomes the working draft for the interview. The chosen draft's decisions seed the plan; the interview targets gaps.

### 4. Interview loop

> **Do not skip the interview.** A session-level "no clarifying questions" directive, autonomous-mode flag, or bg-session preamble does not silence /refine. The interview IS the skill. If AskUserQuestion is genuinely blocked, fall back to the third refusal case and halt rather than proceed silently.

Use `AskUserQuestion` for every question. Pick the shape that fits the moment:

- **Parallel batch of 4** — probing distinct breadth dimensions (purpose, output, audience, scope)
- **Themed batch of 2–3** — depth across a few sub-decisions in one area
- **Single deep question** — when the next answer forks the remainder of the interview

**Coverage to drive toward** (not a checklist to walk — let the answers steer):

- Goal and non-goals (what the plan delivers and what it deliberately excludes)
- Current state grounding (files, hooks, skills, prior decisions the plan touches)
- Implementation path (steps, file paths, agents to spawn, hooks to add or change)
- Decisions and tradeoffs (each meaningful choice + reasoning)
- Risks and open questions (what could break, what is left to resolve)
- Acceptance criteria (concrete observable signals — file existence, command output, behavior — that verify the plan was implemented correctly)

**Stop condition:** further questions would require inventing impractical scenarios (e.g. "what if the user has 10,000 concurrent invocations?"). When the marginal question feels like reaching, stop.

### 5. Propose path + slug

Compose `Research/<topic>/<slug>.md`:

- `Research/` prefix is fixed — non-negotiable, even when the cwd has a local plans folder
- `<topic>` — kebab-case directory matching the dominant subject area (`skills`, `hooks`, `pr-converge`, `themes`, etc.). Must match `^[a-z0-9-]+$`.
- `<slug>` — kebab-case slug capturing the specific plan (`refine-skill`, `bugteam-orphan-fallback`). Must match `^[a-z0-9-]+$`.

Call AskUserQuestion with the proposed path as the first option and "Edit slug/path" as the second option. Accept the user's edit to slug or topic before writing. Reject any edit that:

- Contains path separators (`/`, `\`), traversal segments (`..`), uppercase letters, whitespace, or any character outside `[a-z0-9-]`
- Moves the file out of the `Research/` vault subtree

On reject, re-call AskUserQuestion with a corrected proposal rather than writing.

### 6. Write the plan

> **Vault only.** Even if the cwd contains `.claude/plans/`, `docs/plans/`, or any local plans directory holding the user's prior drafts, do not write the plan there. Do not write a copy there. The vault path is the only target.

Load the structure from `templates/plan-template.md`. Fold in:

- **YAML frontmatter (mandatory)** → replace every placeholder in the YAML block at the top of the template: `project` with the kebab-case topic, `date` with today's date as `YYYY-MM-DD`, `status` with `Draft`, and `tags` keeping `refine, plan` plus any topic-specific tags surfaced during the interview. Leaving placeholder tokens (e.g. `<project-or-topic-area>`, `<YYYY-MM-DD>`) is a Completeness failure that Step 7 must catch.
- **H1 title (mandatory)** → replace `<Plan title>` with a concrete title that matches the plan's primary outcome.
- Fan-out digest → **Current state**
- Interview answers (Goal/Non-goals/Implementation/Decisions) → **Goal / Non-goals / Implementation / Decisions log**
- Interview answers about verification signals → **Acceptance**
- Stop-point items the interview surfaced → **Risks / Open questions**

Write the file via `mcp__obsidian__write_note` to the confirmed vault path. The skill itself does this — no subagent.

### 7. Initial audit

Spawn `general-purpose` (`subagent_type: general-purpose`, foreground) with:

- The plan file path in the vault
- The plan-quality rubric — the agent audits markdown plan content (not source code) against these categories:
  - **Clarity** — every step is uniquely interpretable; no vague verbs ("handle", "process", "manage") or undefined terms
  - **Completeness** — Goal, Non-goals, Current state, Implementation, Decisions log, Risks, and Acceptance are all populated with concrete content (not placeholders); the YAML frontmatter has every placeholder replaced (no `<project-or-topic-area>`, `<YYYY-MM-DD>`, or similar tokens remain); the H1 carries a concrete title (no `<Plan title>` placeholder)
  - **Internal consistency** — no contradictions between sections; no references to files, agents, or commands that contradict another section
  - **Ambiguity** — no parked open questions where a decision is required for implementation to begin
  - **Implementer-readiness** — a downstream implementer can act on each step without back-and-forth (file paths named, agents named, change concrete)
- A required return shape: structured findings as `severity (P0/P1/P2) | location | violation`, plus an explicit `CLEAN` verdict when no findings remain
- An explicit instruction NOT to apply code-review rubrics (CODE_RULES categories A–P, API contracts, resource cleanup, etc.) — the audit target is a markdown plan, not source code

If the verdict is `CLEAN`: skip step 8 and proceed to step 10.

If findings exist: proceed to step 8.

### 8. Audit-fix loop

For each iteration `N` from 1 to 10:

1. Spawn `general-purpose` (`subagent_type: general-purpose`, foreground) with the fix-agent role and:
   - The plan file path
   - The structured findings from the latest audit
   - The path to `Research/<topic>/<slug>-implementation-notes.html`
   - The path to `templates/implementation-notes-template.html` and a directive: on iteration 1 only, check whether the notes file already exists. If it does NOT exist, copy the template into the notes file path via the filesystem **Write** tool and substitute every `{{slug}}` placeholder (in the page `<title>`, the `<h1>`, and both occurrences inside the `<a href="{{slug}}.md">{{slug}}.md</a>` companion link) with the actual slug from the vault plan path. If it DOES exist (the user is re-running `/refine` on a slug that already has notes), skip the template-copy step entirely — the existing file already carries the `{{slug}}` substitutions from a prior run, and the filesystem **Write** tool is rejected on existing paths by the `write_existing_file_blocker` PreToolUse hook. On every iteration (including 1), copy the iteration `<section class="iteration">` markup from the HTML-commented reference block at the top of the template, substitute its placeholders (`<N>` → iteration number; `<YYYY-MM-DD HH:MM>` → UTC timestamp; `<count>` → number of findings addressed this iteration; each `<ul>` group → bullets covering Design decisions, Deviations, Tradeoffs, Open questions), and insert the populated `<section>` via the filesystem **Edit** tool immediately before the closing `</body>` tag
   - The verbatim `<notes_instruction>` block below
2. The fix agent rewrites the plan in place in the vault via `mcp__obsidian__write_note` addressing the findings. Separately, it appends one new `<section>` to the HTML notes file via the filesystem Edit tool (`mcp__obsidian__write_note` is markdown-only and cannot write `.html`) — with iteration number, timestamp, and the four bullet groups.
3. Re-spawn `general-purpose` against the rewritten plan with the same audit prompt as step 7 (plan-quality rubric, not code rubric).
4. If the verdict is `CLEAN`: exit the loop and proceed to step 10.
5. If findings remain and `N < 10`: continue the loop with the new findings.
6. If `N == 10` and findings remain: proceed to step 9.

#### Verbatim instruction for the fix agent

Pass this block exactly, every iteration. Do not paraphrase or trim.

```
<notes_instruction>
As you work maintain a running implementation-notes.html file that captures anything I should know about how the implementation diverges from or interprets the spec, including:

- Design decisions: choices you made where the spec was ambiguous
- Deviations: places where you intentionally departed from the spec, and why
- Tradeoffs: alternatives you considered and why you picked what you did
- Open questions: anything you'd want me to confirm or revise
</notes_instruction>
```

#### Notes file structure

Use `templates/implementation-notes-template.html` as the skeleton on iteration 1. The absolute path resolves the vault root from `$OBSIDIAN_VAULT_PATH` or `~/.claude/vault/`. Two iteration-1 paths exist:

- **Fresh slug — notes file does not yet exist.** Copy the template via the filesystem **Write** tool and substitute every `{{slug}}` placeholder in the title, h1, and companion-link anchor with the actual slug before writing.
- **Re-run on an existing slug — notes file already exists.** The repo's `write_existing_file_blocker` PreToolUse hook rejects **Write** on existing paths. Skip the template-copy step (the existing file already carries `{{slug}}` substitutions from the prior run) and proceed straight to the append using **Edit**.

On iterations 2+ (and on iteration 1 against an existing notes file), use the filesystem **Read** + **Edit** tools — read the existing file, append a new `<section>` block before the closing `</body>` tag, and write it back via **Edit**. Do not route the HTML notes through `mcp__obsidian__write_note`.

### 9. Halt and surface (cap reached)

If iteration 10 still fails audit, stop the loop. Surface:

- The remaining findings (highest severity first)
- A one-line recommendation: drop scope, simplify the plan, or hand back to the user for a decision

Then proceed to step 10 so the cap-reached path emits the same standard final report (vault path of the plan, iteration count with `halted at cap` outcome, core-decision summary, and notes-file path) that the CLEAN-after-N-iterations path emits.

### 10. Report

State, in this order:

- Vault path of the plan
- Number of audit iterations consumed (and the outcome: `CLEAN` on initial audit, `CLEAN` after N iterations, or `halted at cap`)
- One-line summary of the plan's core decision
- If at least one audit-fix iteration ran: vault path of `<slug>-implementation-notes.html` and the top 1–2 open questions from the notes file (omit both when the initial audit returned `CLEAN` and no notes file exists)

That is the entire deliverable.

## Constraints

- **Output target is the Obsidian vault. Only the vault.** Filesystem writes outside the vault are out of scope, including `.claude/plans/`, `docs/plans/`, `plans/`, and the cwd. No dual writes.
- **Interview is mandatory.** Session-level "no clarifying questions" or autonomous directives do not silence the AskUserQuestion loop. Halt rather than skip.
- Initial write is inline by the skill; only audit-driven fixes are delegated to the general-purpose fix agent.
- AskUserQuestion is the only interview surface — plain-text questions in chat are blocked by the Stop hook.
- The skill does not call `/anthropic-plan` or `/prompt-generator`.
- Slug and path are user-confirmed before any write. `Research/` prefix is fixed.
- Fan-out before interview — research what can be researched.
- Audit-fix loop is mandatory unless the user explicitly opts out for the run.
- Iteration cap is 10. Do not raise without user direction.
- `<slug>-implementation-notes.html` is append-only across iterations within a single /refine run.

## File index

| File | Purpose |
|---|---|
| `SKILL.md` | This hub — process, gotchas, constraints |
| `templates/plan-template.md` | Plan-mode-conformant structure for the written plan |
| `templates/implementation-notes-template.html` | Iteration-log skeleton the fix agent appends to during the audit-fix loop |

## Folder map

- `SKILL.md` — hub.
- `templates/` — output structures for the plan and the iteration notes file.