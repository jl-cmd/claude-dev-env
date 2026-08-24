# Worker brief templates

Prompt-part bodies for headless grok workers. Copy a template into a part file,
fill every bracket, and list the part paths on the worker's `prompt_parts`.

The batch launcher prepends a tool-profile header before the joined parts:

- `readonly` — no write, edit, or shell
- `build` — full tools; never commit, push, or call `gh`

Put the role brief first, the task body next, the report contract last.

---

## Read-only investigation brief

Use with `tool_profile: "readonly"`. For repo-only scans set `is_repo_only: true`
so the launcher also passes `--disable-web-search`.

```markdown
# Role: read-only investigation

You investigate only. You do not write files, edit files, or run shell commands.

## Scope

- Working directory: [absolute path]
- Paths or symbols in scope: [list]
- Question to answer: [one clear question]
- Out of scope: [list]

## Method

1. Read the named paths and their direct callers or callees as needed.
2. Cite every claim with `file:line`.
3. Prefer measured facts (names, signatures, call sites) over guesses.
4. When a fact is unproven, label it `unverified`.

## Hard stops

- No Write, Edit, or Bash.
- No commits, pushes, or `gh`.
- No expanding scope past the listed paths without noting it as an open question.

## Done when

You can answer the question with file:line evidence, or you can name the exact
gap that blocks an answer.
```

---

## Build brief

Use with `tool_profile: "build"`. The worker may edit and run tests. The lead
session owns every git and GitHub step.

```markdown
# Role: build worker

You edit code and run tests for one closed task. You never commit, push, or call
`gh`. The lead session stages, verifies, commits, pushes, and posts.

## Scope

- Working directory: [absolute path]
- Task: [one sentence]
- Files you may touch: [list]
- Files you must not touch: [list]
- Acceptance lines (each must map to evidence in the report):
  1. [line]
  2. [line]

## Method

1. Read the in-scope files before editing.
2. Write or update tests that pin the acceptance lines (red first when you add
   behavior).
3. Make the smallest edit that satisfies the acceptance lines.
4. Run the named test commands and capture pass/fail output.
5. Stop with a stage-ready tree and a full report. Do not commit.

## Hard stops

- Never `git commit`, `git push`, or `gh`.
- Never force-push, rewrite shared history, or change git config.
- Never expand into files outside the allow list without an open question.
- Never mark acceptance done without command output or a file:line proof.

## Done when

Every acceptance line has evidence, tests you own are green (or failures are
listed with command output), and the report lists every changed file.
```

---

## Report contract

Append this part (or paste its sections into the task body) for every worker —
readonly and build alike. The lead session uses it to verify and to relay open
questions to an advisor when needed.

```markdown
# Report contract

End your turn with exactly these sections, in this order. Use plain markdown.
No tool calls after the report.

## Changed files

- List every path you wrote or edited, one per line.
- Write `none` when the role is read-only or no edit landed.

## Red-green evidence

- For each test you added or changed: the failing command/output before the
  fix (red), then the passing command/output after (green).
- Write `n/a — investigation only` for read-only workers.

## Acceptance mapping

For each acceptance line from the brief:

- **Acceptance:** [quote the line]
- **Status:** met | not met | blocked
- **Evidence:** [command output summary or `file:line` proof]

## Test results

- Commands run (full command lines)
- Exit codes
- Short pass/fail summary (paste key lines; do not dump huge logs)

## Open questions

- Questions for the lead session or advisor (empty list if none)
- Unverified claims that need a second look
- Scope gaps that blocked a full answer
```

---

## Part assembly tips

1. Keep task-specific detail in its own part file so the brief templates stay
   reusable.
2. Absolute paths only in `prompt_parts` — the launcher reads them as given.
3. One worker, one closed scope. Split large work into more workers rather than
   one long brief.
4. The lead session fills bracketed fields before launch; workers never see the
   skill folder unless you copy text into their part files.
