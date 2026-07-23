# Epic and sub-issue model

One **epic** issue holds a whole work-stream. Each unit of work under it is a native GitHub **sub-issue**. The epic carries the `epic` label; each sub-issue carries a `type:` label. The epic body mirrors its children as a checklist, and every issue — epic and sub-issue alike — carries a status section. Both sections live between marker comments so a body edit can replace one section and leave the rest untouched.

## The two marker pairs

- `<!-- issue-tracker:status -->` … `<!-- /issue-tracker:status -->` — on every issue. Holds the current status line.
- `<!-- issue-tracker:children -->` … `<!-- /issue-tracker:children -->` — on the epic only. Holds the checklist of sub-issues.

An edit reads the whole body, swaps only the text between one marker pair, and writes the whole body back. Text outside the markers stays byte-for-byte the same.

## Epic body skeleton

```markdown
## Epic — <work-stream label>

<One sentence naming the work-stream and its goal.>

<!-- issue-tracker:status -->
Status: in progress — 1 of 3 children closed.
<!-- /issue-tracker:status -->

<!-- issue-tracker:children -->
- [x] owner/repo#12 — parser rejects an empty path
- [ ] owner/repo#13 — attach reads the display number
- [ ] owner/repo#14 — label create skips an existing label
<!-- /issue-tracker:children -->
```

## Sub-issue body skeleton

```markdown
## <sub-issue title>

<One sentence: what the work is.>

<!-- issue-tracker:status -->
Status: open.
<!-- /issue-tracker:status -->

## Detail

<The evidence, where, impact, and proposed fix — self-contained.>
```

## Refresh the epic checklist

After you create a sub-issue or close one, refresh the epic's `children` section so it matches the children:

1. Read the epic body.
2. Add a `- [ ] owner/repo#<N> — <title>` line for a newly created sub-issue, or flip a line to `- [x]` for a closed one.
3. Update the epic's status line to name the closed count against the total.
4. Write the whole body back with the issue-update op, replacing only the two marker sections you touched.

A created or closed sub-issue always triggers this refresh, so the epic checklist stays in step with the sub-issues at every step.
