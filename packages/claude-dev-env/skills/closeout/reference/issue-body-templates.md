# Issue body templates

Body shapes for the parent tracking issue and its child issues, plus a worked example. Every body is self-contained: a reader with zero session context understands it. Every body carries a quoted line of evidence captured this session. Write each body to a temp file and pass it with `gh issue create --body-file <path>`.

## Contents

- [Child issue body](#child-issue-body)
- [Parent tracking issue body](#parent-tracking-issue-body)
- [Worked example — child](#worked-example--child)
- [Worked example — parent](#worked-example--parent)
- [Body rules](#body-rules)

## Child issue body

One obstacle per child. Fill every section:

```markdown
## What happened

<One sentence: the failure mode, in plain terms.>

## Evidence

<The verbatim line captured this session — error text, command, or log line — in a fenced block.>

```
<exact quoted text>
```

## Where

<The file, hook, gate, or tool the evidence names. Path relative to the repo root.>

## Impact

<What the obstacle cost: work blocked, count of times hit, workaround forced.>

## Proposed fix

<The specific change. Name the failure mode and the condition, not "improve error handling".>
```

## Parent tracking issue body

The parent gathers the children. Its body is a checklist, one line per child created:

```markdown
## Session closeout — <short session label>

Obstacles this session, filed as child issues:

- [ ] owner/repo#<N> — <child title>
- [ ] owner/repo#<N> — <child title>
- [ ] owner/repo#<N> — <child title>

## Handoff

A cloud handoff prompt for these issues was printed in the closing session. It carries the safety boundaries, base branch, per-package verification commands, and the dependency order among the children.
```

## Worked example — child

```markdown
## What happened

The code_rules_enforcer hook blocked a valid list literal in a test file, where test files are exempt from the magic-value gate.

## Evidence

```
BLOCKED: [MAGIC_VALUE] Inline list literal [200, 404, 500] in a function body -- extract to a named constant in config/.
```

## Where

packages/claude-dev-env/hooks/blocking/code_rules_enforcer.py — the inline-collection check.

## Impact

Hit 3 times in one session on three test files. Forced a workaround: moving each literal to a module constant the test did not need.

## Proposed fix

Extend the test-file exemption that already covers the magic-value gate to also cover the inline-collection check, so list and set literals in test bodies pass.
```

## Worked example — parent

```markdown
## Session closeout — hook exemptions for test files

Obstacles this session, filed as child issues:

- [ ] jl-cmd/claude-dev-env#101 — inline-collection gate fires in exempt test files
- [ ] jl-cmd/claude-dev-env#102 — boolean-naming gate flags a fixture variable

## Handoff

A cloud handoff prompt for these issues was printed in the closing session. It carries the safety boundaries, base branch, per-package verification commands, and the dependency order among the children.
```

## Body rules

- **Quoted evidence is required.** No child ships without a fenced block holding a line captured this session.
- **No volatile paths.** No temp dirs, worktrees, `$CLAUDE_JOB_DIR`, `.claude-editor/jobs`, or `.claude/worktrees` paths in any body. Paste text inline; for a binary artifact, upload it to a durable release and link that URL.
- **No chat references.** Drop "as discussed" and "the choice we picked". State each fact on its own.
- **Specific over vague.** "The gate fires on `[200, 404, 500]` in a test body" beats "the gate is too strict".
- **PII stripped.** Run the PII pass (see the PII redaction checklist) over every body before it reaches the confirmation gate.
