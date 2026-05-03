---
name: resume-review
description: >-
  Audit a resume for nitty-gritty offenses that bury signal. Resumes are
  overviews scanned in 6-30 seconds, not detailed proof artifacts. This skill
  identifies bullets that drift into workflow internals, multi-item technical
  lists, library names, mechanism narration, or implementation detail, and
  proposes tighter rewrites that keep the proof points (numbers, scope,
  outcomes) while dropping the granular how-it-works text. Triggers:
  "/resume-review", "review my resume", "audit this resume", "is my resume too
  detailed", "tighten my resume bullets".
---

# Resume Review

A resume is an **overview**. Hiring managers scan a resume in 6-30 seconds on
first pass. Granular technical detail buries the signal. Stats, scope, and
quantified outcomes belong on the resume; workflow internals, multi-item
technical lists, and how-it-works narration belong in the interview.

## Source authority

Three established sources govern this skill. When a bullet violates one of
these principles, cite the source in the review comment.

- **Laszlo Bock**, *Work Rules!* (2015), Twelve Books, p. 71 (Bock served as
  SVP People Operations at Google, 2006-2016): bullets describe "what you
  accomplished, not what you did." Quantified outcomes beat task descriptions.
- **Steve Dalton**, *The 2-Hour Job Search* (2012), Ten Speed Press, Ch. 3:
  hiring managers initially scan a resume in 6-30 seconds. Granular technical
  detail buries the signal in that scan.
- **Lou Adler**, *Hire With Your Head* (4th ed., 2021), Wiley: bullets convey
  **scope and impact**, not tools and tasks.

## The principle

Every bullet earns its place by carrying one of three things:

1. **Scope** — what surface area of work this covered (catalog size, team
   size, user count, transaction volume, geographic reach).
2. **Impact** — the outcome the work produced (revenue, time saved, error
   rate reduced, problem prevented, capability unlocked).
3. **Quantified proof** — a single number that anchors scope or impact and
   makes the bullet harder to dismiss as boilerplate.

Bullets that describe the **mechanism** of how the work was done (workflow
steps, internal architecture, library choices, sequencing of operations) fail
the overview test. Move that content to the interview.

## Offense categories

The audit walks every bullet and flags any of these patterns. Each pattern
has a fix template.

### 1. Multi-item parenthetical lists

A parenthetical that enumerates 3+ named items (tools, systems, features,
sub-tasks).

> **Offender:** "Built and maintain three production Python automation
> systems (theme submission, theme exports, certification failure
> processing) backed by a shared utility library."

> **Fix:** Drop the parenthetical. Keep the count. "Built and maintain three
> production Python automations handling [scope]."

### 2. Workflow-step narration

The bullet describes the sequence of operations the work performs.

> **Offender:** "Manage Samsung's annual catalog-update cycle when 2,800+
> themes must each be updated, exported, and resubmitted one by one within a
> 1-2 month window."

> **Fix:** Drop the workflow steps. Keep the scope numbers. "Manage Samsung's
> annual catalog-update cycle: 2,800+ themes refreshed within a 1-2 month
> window."

### 3. Engineering-pattern jargon for non-engineering audience

Multiple named technical patterns in one bullet, written for an audience
that does not share the domain (e.g., infrastructure terms in an operations
or trust-and-safety resume).

> **Offender:** "Turn recurring failures into stronger error classification
> (transient vs. permanent), circuit breakers, and checkpoint/resume
> recovery."

> **Fix:** Replace the pattern enumeration with a single capability noun.
> "Turn recurring failures into reusable error-handling patterns so the same
> failure does not happen twice."

### 4. Mechanism narration

The bullet explains how a tool or system internally works.

> **Offender:** "Author and maintain pr-converge, a Claude Code skill that
> automates the pull request review-and-fix loop until reviewers converge on
> ready, with three open pull requests (11,000+ lines) actively extending
> it."

> **Fix:** State the outcome the skill produces. Drop the loop description.
> "Author and maintain pr-converge, an open-source Claude Code skill that
> drives draft pull requests to merge-ready autonomously."

### 5. Library or tool names embedded mid-bullet

A library, framework, or tool name appears inside a sentence about
capability. Library names belong in the dedicated Tools section, not in
capability bullets.

> **Offender:** "Implemented authenticated workflows end-to-end: account
> creation, token handling, local-first data with IndexedDB/Dexie, and
> conflict-aware sync between client and server."

> **Fix:** Drop the library names. State the capabilities. "Implemented
> authentication, local-first data persistence, and conflict-aware
> client-server sync end-to-end."

### 6. Redundant statistics

Two numbers in the same bullet that express the same quantity at different
granularities.

> **Offender:** "Roughly 30 new theme submissions per day (150 per week)."

> **Fix:** Pick one. The daily number is usually the strongest scan signal.

### 7. Implementation detail

Phrases that describe how the work was built rather than what it does.

> **Offender:** "Backed by a shared utility library, with zero manual
> intervention beyond starting the script."

> **Fix:** Drop the implementation phrase entirely. The capability statement
> should stand on its own.

### 8. Two-sentence bullets

A bullet that requires two sentences usually carries one bullet of scope and
one bullet of mechanism. The mechanism sentence should be removed, not
combined.

> **Offender:** "Author and maintain pr-converge, a Claude Code skill
> that... [first sentence describes what]. Recent work adds mergeability
> gates, GitHub Copilot reviewer integration, and post-convergence Copilot
> follow-up across three open pull requests (11,000+ lines)."

> **Fix:** Keep the capability sentence. Move the second sentence to a cover
> letter or interview talking point.

## Review protocol

Walk this protocol against every bullet on the resume. Mark each bullet
PASS, MINOR, or MAJOR.

### Step 1: Scope check

Read the bullet aloud in 4 seconds or less. If you cannot finish in 4
seconds, the bullet is too long. **Action:** trim to one sentence under 25
words unless the bullet carries a justified centerpiece (and centerpiece
bullets stay under 40 words).

### Step 2: Offense scan

For each bullet, scan for the eight offense categories above. Record any
hits with the category number.

### Step 3: Verify proof points

Every numeric claim in a bullet must be verifiable. If a number cannot be
sourced, drop it. Hedging numbers ("roughly", "around", "approximately")
are acceptable when the underlying number is verifiable but variable.

### Step 4: Audience alignment

For each bullet, ask: would the hiring manager for **this specific role**
recognize the terms used? If the bullet uses domain language outside the
target role's vocabulary (engineering jargon on a trust-and-safety resume,
finance acronyms on an engineering resume), rewrite using domain-neutral
capability nouns.

### Step 5: Mechanism removal pass

For each bullet that survived steps 1-4, ask: does this bullet describe
**what** the work accomplished, or **how** the work was done? If it
describes **how**, rewrite to describe **what** and move the **how** to
interview prep notes.

### Step 6: Section-level coherence

After per-bullet review, scan each section. Check for:

- **Bullet count consistency** — sections with similar weight should have
  similar bullet counts. A 5-bullet section next to a 1-bullet section
  signals imbalance.
- **Voice consistency** — verb tense, sentence structure, and bullet length
  should match across sections.
- **Relevance ordering** — the most-relevant-to-the-target-role section
  should appear first within its time band (Steve Dalton, *The 2-Hour Job
  Search* §6: relevance over strict chronology when chronology does not
  conflict).

## Output format

The audit produces a markdown report with this structure:

```markdown
# Resume Audit Report

## Top offenders (worst first)

### #1 — [Section] bullet [N]. [Severity]

[Quote of current bullet]

**Offenses:** [comma-separated category numbers]

**Proposed rewrite:** [tighter version]

**Words saved:** [N words → M words]

(repeat for each offender)

## Sections that pass

- [Section name]: [bullet count] bullets, all PASS
- (repeat)

## Section-level findings

[Coherence issues from Step 6, if any]

## Sources cited

- Bock, *Work Rules!* (2015), p. 71 — for offenses [N]
- Dalton, *2-Hour Job Search* (2012), Ch. 3 — for offenses [N]
- Adler, *Hire With Your Head* (2021) — for offenses [N]
```

## When this skill applies

- User asks to review or audit a resume
- User asks "is my resume too detailed"
- User asks for tighter resume bullets
- A resume document is shared and the user wants feedback
- Before submitting a resume to a target role

## When this skill does not apply

- Cover letter review (use a separate cover-letter-review skill if needed)
- Resume formatting fixes (font, spacing, layout) — this skill audits
  content only
- Resume creation from scratch — this skill assumes a draft exists

## Triggers

`/resume-review`, "review my resume", "audit this resume", "is my resume
too detailed", "tighten my resume bullets", "what offenses do you see in my
resume", "are my bullets too granular".
