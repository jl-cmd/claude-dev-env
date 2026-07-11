# PR Description Guide

Authoritative reference for the `pr-description-writer` agent and the `pr_description_enforcer` PreToolUse hook. PR bodies that match this guide pass the enforcer on first attempt.

## Anthropic style basis

The shape rules and header vocabulary derive from a 120-PR sample. Sources: `anthropics/claude-code` (40 PRs), `anthropics/claude-code-action` (40 PRs), and `anthropics/claude-code-sdk-python` (40 PRs). The corpus was sampled from merged PRs.

Key signals from the corpus:

- **Shape distribution.** Trivial (≤ 10 lines): 32.5% — median body 288 chars. Small (11–100 lines): 41.7% — median 1,105 chars. Medium (101–500 lines): 20.0% — median 940 chars. Large (> 500 lines): 5.8% — median 2,441 chars.
- **Modal headers.** `## Summary` 43, `## Problem` 20, `## Test plan` 20, `## Fix` 18, `## Changes` 14, `## Tests` 11, `## Testing` 10, `## Root cause` 5, `## Approach` 2.
- **Opening style.** 46.7% open with a header, 53.3% with an unmarked paragraph. 51% of prose-opening Small/Medium PRs open with an imperative verb. `This PR` appears in 1 of 120 PRs.
- **Issue references.** 27.5% of PRs use `Fixes #N`, `Closes #N`, or `Resolves #N`.
- **Sentence length.** First-paragraph mean 15.2 words; median 14.5. Sentences over 28 words are uncommon.
- **Em-dashes.** Appear in 48% of bodies as parenthetical separators.
- **Backtick identifiers in intros.** Routine — filenames, function names, env vars, and CLI flags appear in opening paragraphs.

## The three shapes

### Trivial

- **Guidance.** Diff ≤ 10 lines changed (the agent picks shape by diff size; the hook cannot see the diff).
- **Hook enforcement.** Substantive prose under `TRIVIAL_BODY_CHAR_THRESHOLD` (200 chars). The hook blocks any ATX heading at any depth (`#`, `##`, `###`, ...) in a Trivial-sized body — the ceremony-on-Trivial check uses `HEADING_LINE_PATTERN`, not just `##`.
- **Body.** 1–3 sentences of prose. Zero headings of any level.
- **Forbidden.** Any heading (`# Anything`, `## Summary`, `### Detail`, ...). Triggers the hook's ceremony-on-Trivial check.

Example:

```markdown
Bump bun to 1.3.14. Picks up the bugfix for the runtime panic on empty stdin.
```

### Standard

- **Guidance.** Diff 11–500 lines (agent-side; hook infers shape from body length).
- **Hook enforcement.** Substantive prose between `TRIVIAL_BODY_CHAR_THRESHOLD` (200) and `HEAVY_MIN_BODY_CHARS_FOR_CLASSIFICATION` (500). No required headers.
- **Body.** Imperative-verb intro paragraph. Optional headers drawn from the Anthropic set.
- **Optional headers.** `## Summary`, `## Problem`, `## Fix`, `## Changes`, `## Test plan`, `## Tests`, `## Testing`, `## Approach`, `## Root cause`.

Example:

```markdown
Adds a syllable-counted Flesch reading score to the PR description enforcer. Bodies above the readability ceiling surface a targeted block message before the strike counter increments.

## Test plan

- [ ] `pytest packages/claude-dev-env/hooks/blocking/test_pr_description_enforcer.py`
- [ ] Open a draft PR with a 45-word sentence and confirm the metric block fires
```

### Heavy

- **Criterion.** Diff > 500 lines, or a cross-cutting bug fix that touches multiple subsystems.
- **Body.** At least one of `## Problem` or `## Summary`. At least one of `## Test plan`, `## Testing`, `## Tests`, `## Verification`, or `## Validation`. Plus any additional Anthropic headers the change earns.
- **Hook enforcement.** Missing either required category triggers a Heavy-required-headers block message naming the absent category.

Example:

```markdown
## Problem

Long-running `gh api` review fetches drop pages silently when the reviewer count crosses 30. Bugbot findings on PRs past the first review cycle stay hidden.

## Fix

Routes every `gh api .../reviews` and `.../comments` call through `--paginate --slurp | jq` so the cross-page filter sees the full set.

## Test plan

- [ ] Mock paginated API and assert `jq` filter operates on the merged stream
- [ ] Replay PR #467 review history and confirm the late bugbot comment surfaces
```

## Header vocabulary

| Header | Corpus count | Typical use |
|---|---:|---|
| `## Summary` | 43 | High-level overview, often two or three sentences |
| `## Problem` | 20 | Bug context — what broke, who hit it |
| `## Test plan` | 20 | Reviewer checklist of verification steps |
| `## Fix` | 18 | How the change addresses the problem |
| `## Changes` | 14 | Bulleted catalog of code-level updates |
| `## Tests` | 11 | New or expanded test coverage |
| `## Testing` | 10 | Manual or CI verification notes |
| `## Root cause` | 5 | Underlying defect analysis |
| `## Approach` | 2 | Design rationale for non-obvious solutions |

`## Test plan` and `## Root cause` use sentence-case in the corpus. The enforcer regex matches case-insensitively.

## Readability targets

The enforcer measures three metrics on the intro paragraph and first body section combined.

| Metric | Target |
|---|---|
| Longest sentence | ≤ 28 words |
| Average sentence | ≤ 18 words |
| Flesch Reading Ease | ≥ 50 |

The Flesch score uses `206.835 - 1.015 × (words/sentences) - 84.6 × (syllables/words)`. The hook implements the formula in pure stdlib with a vowel-group syllable heuristic.

Hit the targets by writing short sentences in common Anglo-Saxon words. The corpus first-paragraph average of 14.5 words is the target to beat.

## Escape hatch

The hook tracks a per-user readability strike counter at `~/.claude/state/pr_description_readability_strikes.json`. Counter increments on every triggering violation. The first two failures emit metric-specific block messages. The third triggering failure fires the escape-hatch message with four recovery actions.

### Action 1 — loosen thresholds 10%

```bash
python <enforcer-path> --readability-loosen
```

Scales the three thresholds. Flesch floor × 0.9 (rounded down). Max-sentence ceiling × 10/9 (rounded up). Avg-sentence ceiling × 10/9 (rounded up). Cascades on repeat — the second loosen applies the same scaling to the already-loosened values.

Caps:

- Max 3 successive loosens (`READABILITY_LOOSEN_CAP = 3`). A fourth `--readability-loosen` errors with `loosen cap reached; use --readability-disable or --readability-reset`.
- Flesch floor of 30 (`READABILITY_MIN_FLESCH_FLOOR`). Once `flesch_min` reaches 30 the loosen action errors.
- Max-sentence ceiling of 60 (`READABILITY_MAX_SENTENCE_WORDS_CEILING`). Once `max_sentence_words` reaches 60 the loosen action errors.
- Avg-sentence ceiling of 40 (`READABILITY_AVG_SENTENCE_WORDS_CEILING`). Once `avg_sentence_words` reaches 40 the loosen action errors.

### Action 2 — disable readability entirely

```bash
python <enforcer-path> --readability-disable
```

Writes `{"enabled": false}` to `~/.claude/state/pr_description_readability_enabled.json`. Shape detection, Heavy required-headers, ceremony-on-Trivial, self-closing reference, `This PR` opening, vague-language, and minimum-length checks all stay active. The readability check is the only one silenced.

Re-enable with:

```bash
python <enforcer-path> --readability-enable
```

### Action 3 — reset the strike counter

```bash
python <enforcer-path> --readability-reset
```

Zeroes the strike counter at `~/.claude/state/pr_description_readability_strikes.json`. Clears `loosens_used` and threshold overrides at `~/.claude/state/pr_description_readability_overrides.json`. The readability check returns to default thresholds and a clean strike count.

### Action 4 — report a false positive

Reply with the PR body and your intended commit message. The maintainer tunes the thresholds or refines the regex.

## What to avoid

- **Vague language.** `fix bug`, `update code`, `minor changes`, `various improvements`. Each trips the `VAGUE_LANGUAGE_PATTERN` check.
- **`This PR` openings.** Hard block. Open with an imperative verb.
- **Self-closing references.** `Fixes #<this PR>` in a `gh pr edit` body. Self-reference adds zero context. Triggers a block on `gh pr edit` and `gh pr comment` invocations where the PR number is known.
- **Code snippets in prose.** The diff shows the code. Bodies describe intent.
- **Implementation-detail dumping.** Reviewers do not need every parameter name and call site. Describe the behavior change.
- **Filler.** `In this PR I have made the following changes:` adds zero signal. Start with the action.