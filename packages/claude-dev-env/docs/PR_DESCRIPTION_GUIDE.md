# PR Description Guide

This guide describes the PR-body shape that the `pr-description-writer` agent produces and that the `pr_description_enforcer` PreToolUse hook validates against. The style mirrors merged pull requests in `anthropics/claude-code`, `anthropics/claude-code-action`, and `anthropics/claude-cli-internal`.

## Three shapes, picked from the diff

Pick the shape from the size and risk of the change, not from a template.

| Signal | Shape |
|---|---|
| 1-3 files, mechanical change (pin bump, link fix, typo, single-line config), no behavior change | **Trivial** -- one declarative sentence, no headers |
| Behavior change, bug fix, small feature; under ~15 files | **Standard** -- intro paragraph + `## Changes` + `## Test plan` (or `## Validation`) |
| New subsystem, refactor across many files, schema or contract change, anything with a caveat | **Heavy** -- intro + `## Problem` + `## Fix` (or `## Changes`) + `## Verification` + extra sections as needed |

Prefer the smaller shape when in doubt.

## Shape 1: Trivial

One sentence. No Markdown headers. Optional `Fixes #N` line.

```
Pin third-party GitHub Actions references to immutable commit SHAs.
```

```
Bump pinned Bun from 1.3.6 to 1.3.14.

Fixes #1311.
```

## Shape 2: Standard

```
<One short intro paragraph stating the change and why it matters.
 Reference the failure mode or user-visible symptom when there is one.>

Fixes #<n>.

## Changes

- `path/to/file.ext`: short clause describing the change
- `path/to/other.ext`: short clause
- `tests/foo.test.ts`: 2 new cases for X

## Test plan

- `bun test test/foo.test.ts`
- `bun run typecheck`
- Manual: reproduce on a branch named `feature/a,b`; confirm no rejection
```

The intro paragraph carries the Why -- no `## Why` header needed when one paragraph is enough.

## Shape 3: Heavy

```
<Two- to four-sentence intro: scope, motivation, user-visible effect.
 Link to the prior PR or issue that motivates this one if applicable.>

Fixes #<n>.

## Problem

<Concrete description of the failure mode or gap. Include the actual
 error text, a reproduction, or the symptomatic log line in a fenced
 code block when it helps.>

```
<example error or reproduction>
```

## Fix

<What the change does at the level a reviewer needs to evaluate it.
 Reference the file or function by path/name. Don't restate the diff
 line-by-line -- the reviewer can read the code.>

- `src/path/file.ts`: brief description
- `src/path/other.ts`: brief description

## Verification

- Command 1
- Command 2 (with output count when useful: "666 pass, 0 fail")
- Manual scenarios walked through

## Caveat

<Anything a reviewer or downstream user needs to know that isn't in
 the diff. Omit this section when there is no caveat.>
```

Optional heavy-shape sections, used when they earn their place:

- `## Runtime behavior` -- when the change preserves behavior but moves it.
- `## Components` -- a small table when the PR introduces multiple named artifacts.
- `## Backward compatibility` -- when an older consumer might still hit this code path.
- `## Context` -- background a reviewer outside the area would need.

## Section vocabulary

Pick from these. Don't invent new ones, and don't use synonyms within one PR:

| Intent | Header (pick one) |
|---|---|
| What this PR is and why | `## Summary` -- or no header (preferred when 1-3 sentences) |
| The failure being fixed | `## Problem` -- or no header when the intro paragraph carries it |
| The change itself | `## Changes` or `## Fix` |
| How it was verified | `## Test plan`, `## Validation`, `## Verification`, or `## Testing` |
| Things to know | `## Caveat`, `## Runtime behavior`, `## Backward compatibility`, `## Context` |

## File reference style

- Always backtick file paths: `` `src/github/operations/branch.ts` ``.
- Use the full path from repo root, not just the basename, unless the basename is unambiguous within the PR.
- Bullet lists describing per-file changes lead with the backticked path and a colon:
  - `` `src/foo.ts`: whitelists `,` in branch names ``
  - `` `test/foo.test.ts`: 3 new cases for comma-bearing branches ``
- Prose calling out a single primary file bolds the backticked filename plus a colon: `` **`branch.ts`**: ... ``.

## Cross-references

- Issue/PR shorthand: `#1311` (same repo), `anthropics/claude-code#40576` (cross-repo).
- `Fixes #N` and `Closes #N` close the linked issue on merge -- use them deliberately.
- `Linear: CC-1723` -- one line, no Markdown, after the intro paragraph or at the bottom.
- "Same change as <repo>#<n>" / "Follow-up to #<n>" -- one-liners that orient a reviewer.

## Markers and footers

- `<!-- NO CHANGELOG -->` on its own line, at the very end, for docs-only or CI-only PRs in repos that auto-generate changelogs from PR titles.
- Don't add a "Generated with Claude Code" footer -- merged Anthropic PRs don't use one consistently, and the repo's commit trailer covers attribution.

## What the hook checks

`pr_description_enforcer.py` runs on `gh pr create` and `gh pr edit` invocations that include a body. It blocks when any of the following are true:

- The body, after stripping Markdown ceremony (headers, code fences, bullet markers, bold/emphasis, link text), contains fewer than 40 characters of prose. A skeleton of `## Summary` + `## Changes` + bullets with no Why paragraph fails here.
- The body contains vague phrases like `fix bug`, `update code`, `minor changes`, or `various fixes`.

The hook does not require any specific section headers -- `## Summary`, `## Problem`, `## Fix`, `## Changes`, `## Test plan` are all optional, including any combination of them. A single substantive sentence ("Pin third-party GitHub Actions references to immutable commit SHAs.") satisfies the check.

When the hook blocks, it points the caller at the `pr-description-writer` agent and at this guide.

## Tone

- Plain language. "The pull engine would blindly overwrite any record marked as 'synced'" -- not "PullEngine.run() exhibited non-idempotent behavior".
- Active voice. "Add `,` to the whitelist" -- not "`,` was added to the whitelist".
- No filler. Start with the content, not "This PR..." or "In this change...".
- No restating the diff. Trust the reviewer to read the code; explain the parts they can't infer.
- No hedging ("should", "might", "I think") unless the uncertainty is real -- in which case say "not yet verified" and call it out.

## What to avoid

- Code snippets that simply repeat the diff. Code blocks are for error reproductions, failing commands, or before/after when the contrast is the point.
- Technical jargon for non-obvious internals ("Dexie transaction" -> "database transaction").
- Multi-line preamble. The PR title already says what the change is.
- Section headers over empty content. If `## Caveat` would be empty, drop the header.
- Second-person commentary directed at the reviewer ("please review carefully"). The reviewer knows their job.
