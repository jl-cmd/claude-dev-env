# Superseded language specifiers

Record date: 2026-08-22

Status: Reference-only archive.

Active owner: `packages/claude-dev-env/rules/asd-ste100-language.md`

The active rule is the repository's sole general user-facing language authority.
The four source files below are preserved as complete source bodies. Their active
package paths are retired. The canonical rule installs at
`~/.claude/rules/asd-ste100-language.md`.

## Inventory

| Source path | Source lines | Runtime destination | Replacement | Git blob |
|---|---:|---|---|---|
| `packages/claude-dev-env/rules/plain-language.md` | 9 | `~/.claude/rules/asd-ste100-language.md` | `asd-ste100-language.md` | `572eb76447017ab8a9380249ec5a61b77640be18` |
| `packages/claude-dev-env/rules/eli11-replies.md` | 36 | `~/.claude/rules/asd-ste100-language.md` | `asd-ste100-language.md` | `1e5216a271b2e7148ae4407b0fb19322818d3a87` |
| `packages/claude-dev-env/rules/opus5-communication-contract.md` | 45 | `~/.claude/rules/asd-ste100-language.md` | `asd-ste100-language.md` | `5f8716876a61dac7fdbfc7e95763d2739ad80b91` |
| `packages/claude-dev-env/rules/doc-prose-cuts.md` | 58 | `~/.claude/rules/asd-ste100-language.md` | `asd-ste100-language.md` | `68a0ad3c81c6f78e4bb9a49c3b33280155adc7e3` |

## Source-preserving records

## packages/claude-dev-env/rules/plain-language.md

Source path: `packages/claude-dev-env/rules/plain-language.md`

Replacement: `packages/claude-dev-env/rules/asd-ste100-language.md`

The four-backtick body preserves the complete source text captured at the recorded
Git blob.

````markdown
# Plain Language

All prose a person reads (chat, `AskUserQuestion`, docs, PR/issue bodies, commits): everyday words, short active sentences, lead with the answer, define jargon on first use, and give only the detail the reader needs to act (progressive disclosure). Aim for first-pass readability by a non-specialist. Exact identifiers, file paths, and API names stay exact; code is out of scope.

The `plain_language_blocker` PreToolUse hook (AskUserQuestion + `.md` Write/Edit/MultiEdit) names an everyday swap for a heavy word when `CLAUDE_PROSE_STYLE_ENFORCEMENT` is on (default off). That path is **allow with a systemMessage advisory** — it does not deny the write. AskUserQuestion lean-block structure stays always on and still denies chat detail. When the flag is off, heavy-word hits only emit privacy-safe advisory candidates (see [`docs/references/prose-style-enforcement.md`](../docs/references/prose-style-enforcement.md)). Code fences, inline code, blockquotes, URLs, and file paths are skipped.

[`eli11-replies`](eli11-replies.md) governs reply length and shape; [`opus5-communication-contract`](opus5-communication-contract.md) governs progress and finals; this rule governs word choice.

A project can keep its own domain words out of the check with a `.claude/plain-language-allow.json` file: a JSON array of terms. An exact, case-insensitive, whole-word match on any term passes. The hook reads this file only from inside the project tree, up to the repository root, so each project's allowlist stays with its own code.
````

## packages/claude-dev-env/rules/eli11-replies.md

Source path: `packages/claude-dev-env/rules/eli11-replies.md`

Replacement: `packages/claude-dev-env/rules/asd-ste100-language.md`

The four-backtick body preserves the complete source text captured at the recorded
Git blob.

````markdown
# ELI11 Replies

**Users read about 20% of your words, and 79% of them scan.** Write every reply so the bold words alone tell the whole story.

## Four skim mechanics

1. **Bold keyword first** — open every line and bullet with its load-bearing words in bold. Eyes land on the first words of a line, then fall down the left edge — the [F-pattern](https://www.nngroup.com/articles/f-shaped-pattern-reading-web-content-discovered/).
2. **One idea per line** — a second idea in the same line is invisible to a skimmer.
3. **Conclusion first** — the outcome goes in sentence one. Detail sits below it, or gets cut.
4. **Half the words** — write it, halve it, halve it again. Stay brief by default; a requested full report may run long.

**Measured gains** ([NN/g eyetracking](https://www.nngroup.com/articles/how-users-read-on-the-web/)): concise +58%, scannable layout +47%, both together +124%.

## Reply shape

1. **Action first** — when the user must act, open with "Do N things" and numbered click-by-click steps, one short line each.
2. **Outcome first** — when nothing is needed, open with the outcome in one sentence.
3. **Findings** — at most 3 short bullets.
4. **Detail** — only when the user asks.

## Rules

- **One command per block** — a command the user runs goes in its own `bash`-tagged fenced block, so the Run button appears. That tag gives the user a Run button; [`shell-invocation-policy`](shell-invocation.md) stays in charge of the agent's own Bash-tool calls, which run pwsh-only.
- **One line per status** — each background-work update gets a single line.
- **Cut findings first** — when a reply runs long, drop findings and keep the action steps.
- **Skim test** — reading only the bold words tells the whole story.

## Progress and finals

Mid-run and closing narration follow [`opus5-communication-contract.md`](opus5-communication-contract.md) (`opus5-communication-contract-v1`): first progress update is one sentence; later updates only for important discoveries or direction changes; the final starts with the outcome.

## Relationship to other rules

- **[`plain-language`](plain-language.md)** owns word choice; this rule owns reply length and shape.
- **[`opus5-communication-contract`](opus5-communication-contract.md)** owns progress updates, outcome-first finals, and thinking-disabled tool narration.
- **`AskUserQuestion`** carries every question to the user, in the same short style.
````

## packages/claude-dev-env/rules/opus5-communication-contract.md

Source path: `packages/claude-dev-env/rules/opus5-communication-contract.md`

Replacement: `packages/claude-dev-env/rules/asd-ste100-language.md`

The four-backtick body preserves the complete source text captured at the recorded
Git blob.

````markdown
# Opus 5 communication contract

**Marker:** `opus5-communication-contract-v1`

Positive contract for visible replies. Complements [`eli11-replies.md`](eli11-replies.md) (shape) and [`plain-language.md`](plain-language.md) (word choice).

## Visible output

1. **Concise by default.** A simple answer stays brief. When the user asks for a full audit or deep dump, the reply may run long enough to cover the substance.
2. **First progress update is one sentence.** After the first tool batch on a multi-step task, one short status line is enough.
3. **Later updates only for important change.** Further mid-run narration marks only important discoveries or a direction change — not every tool call.
4. **Final starts with the outcome.** The closing message leads with what happened; artifacts scale to their substance.
5. **Material corrections only.** Narrate a correction only when it changes code, a conclusion, or a decision.

## Thinking-disabled tool narration

When thinking is disabled in the harness:

1. Speak one brief natural-language sentence before a tool call that needs user-visible context.
2. When no fitting tool exists, say so in plain language.
3. Never put internal-system XML in visible output.

## Positive examples

### Short answer

User: "What is the default branch?"
Reply: "**Default branch** is `main`."

### Requested full audit

User: "Audit every hook registration and list gaps."
Reply: Outcome first, then a structured audit long enough to cover each gap — ELI11 caps still guide skim shape, not a hard character ceiling when depth was asked.

### First progress update

After the first tool batch: "**Checked** `hooks.json` registration paths."

### Important discovery mid-run

"**Blocker:** the package suite shadows `config` — running as two sessions."

### Outcome-first final

"**Shipped** draft PR #123. CI green on head `abc1234`. Merge still needs your OK."
````

## packages/claude-dev-env/rules/doc-prose-cuts.md

Source path: `packages/claude-dev-env/rules/doc-prose-cuts.md`

Replacement: `packages/claude-dev-env/rules/asd-ste100-language.md`

The four-backtick body preserves the complete source text captured at the recorded
Git blob.

````markdown
# Documentation Prose Cuts

Prose a reader acts on states settled facts, decisions, and behavior directly. Four sentence shapes carry no fact the reader can act on. Cut each on sight, in `.md` files, in code comments, and in docstrings alike.

A detail earns its place by mattering now, or by being timeless enough to matter for future work. Everything else is noise.

## The four cut shapes

### 1. Exclusion claims — state the claim itself

Establishing a claim by naming what it is not, or by walking rejected candidates to reach the answer. Replace with the claim and the evidence behind it.

> This is not Option A from the original framing.

Cut it. Write what the approach is.

### 2. Justification sentences — state the fact, drop the payoff

A sentence whose only job is to say why a stated choice is good, or to restate a gain the reader already works out from the behavior around it or from a rule enforced elsewhere.

> The lenses point at this file and read it when they run; they do not carry its text in their spawn prompts, so the checklist stays out of the per-round token budget.

Keep the first clause. Cut the tail — the reader reaches it alone.

For each sentence, ask: **does it state a fact the reader can act on that they could not already work out from the behavior around it?** If no, cut it.

A rule's one-line reason stated in present behavior stays — `--jq` runs per page, so cross-page sorts give wrong results — because that reason names a fact the reader needs to pick the right call. A tradeoff or constraint the reader weighs before choosing a path stays too.

### 3. Conversation references — write for a reader who saw nothing

Every document stands alone. A reader with zero prior context understands every statement without the conversation that produced it.

| Shape | Example | Fix |
|---|---|---|
| Options discussed in chat | "This is not Option A from the original framing" | State the decision on its own terms |
| "As discussed" / "as we decided" | "As discussed, we'll use embeddings" | "Sref matching uses sentence-transformer embeddings" |
| Pronouns pointing at chat | "This addresses the concerns raised earlier" | Name the concerns inline, or cut |
| Relative framing on unseen alternatives | "Instead of the three options considered" | State the chosen approach directly |
| Session sequencing | "After Round 3 we decided…" | State the decision as a fact |

Obsidian session logs are the exception — they are conversation-scoped on purpose.

### 4. Time references — describe current state only

Never reference removed implementations, old defaults, prior behaviors, or earlier contracts. A module or function docstring carries the same current-state-only contract as a `.md` file.

Comparisons to alternatives that still exist stay allowed ("use `--paginate --slurp | jq`, not `--jq` alone"), as do references to external defects that still exist (gh CLI #10459).

After writing, ask: read a year from now by someone who knew no earlier state, does every sentence still make sense? If a sentence only helps someone who knew an earlier state, cut it.

## Enforcement

- **Write-time.** `state_description_blocker` (PreToolUse on Write|Edit) blocks historical and comparative phrases in `.md` prose, code comments, and Python docstrings. A phrase wrapped in double quotes or backticks inside a docstring counts as a mention and is skipped. The denial names the matched phrases and shows a rewrite.
- **AI review.** The claude-dev-env repository's `.cursor/BUGBOT.md` names the other three shapes as findings an agent applies to the `.md` lines a PR changes. Judgment-based review covers these shapes because a regex cannot read sentence meaning.

## Sibling rule

[`plain-language.md`](plain-language.md) governs word choice — heavy words swapped for everyday ones. This rule governs which sentences survive at all.
````
## Package hub language sections captured from origin/main

Source: `packages/claude-dev-env/AGENTS.md`

Origin blob: `0347061dd514b789ee3a332eac2bae83afeb0f68`

These source ranges carry the authored language guidance replaced by the integrated ELI5 presentation and ASD-STE100 sentence policy.

### Origin source lines 1-5

The body below is the exact source text from `origin/main`.

````markdown
# Scope

  Every rule in this file governs all text everywhere: chat replies, tool-call sentences, plans, questions you ask, code, code comments, test names, commit subjects, pull request and issue bodies, documentation, and every file you write. No rule stops at the edge of a chat message.

  A rule that names a form in order to forbid it passes its own check, and so does a two-column table that teaches a rewrite.
````

### Origin source lines 9-11

The body below is the exact source text from `origin/main`.

````markdown
## Documentation

Describe only the current system state. Keep documentation self-contained and free of historical, transitional, conversational, or version-transition language. Never use negative prose or antipatterns. Always state what to do, specifically.
````

### Origin source lines 40-101

The body below is the exact source text from `origin/main`.

````markdown
  # Response and working style

  Mid-run and closing narration follow `rules/opus5-communication-contract.md` (`opus5-communication-contract-v1`): first progress update is one sentence; later updates only for important discoveries or direction changes; the final starts with the outcome.

  Keep responses focused, brief, and concise. Keep disclaimers and caveats short, and spend most of the response on the main answer. When asked to explain something, give a high-level summary unless an in-depth explanation is specifically requested.

  # Word budget

  Say it in the fewest words that stay accurate and complete. Before sending, cut every sentence that does not change what the reader thinks or does.

  Cut these on sight:

  - Deliberation. State the decision, not the reasoning that reached it, unless the reader has to weigh it themselves.
  - Why you did not do something. Say what you did; add the reason only if the reader must decide whether to do it.
  - Incidental findings from your own process. Report one only when the reader must act on it, and give it one line.
  - Any sentence that restates a fact already stated in a heading, a list, or an earlier line.

  When you have more than two facts of the same kind, use a list or a table. Prose paragraphs hide facts; rows expose them.

  # No contrast framing

  Write the claim. Never prop it up against what it is not.

  The banned shape is a claim paired with a rejected alternative, in any wording:

  | Banned | Write instead |
  |---|---|
  | Verified against the remote, not just locally | Verified against the remote |
  | This is a design flaw, not a typo | This is a design flaw |
  | Not a copy of the shared script, but an ad |
  | Rather than patching the caller, the fix moves into the helper | The fix moves into the helper |
  | Instead of three passes, it runs one | It runs one pass |
  | It is not only faster; it is correct | It is correct and faster |
  | This is less a bug than a missing feature
  | Let me read the log rather than guessing | Reading the log. |
  | I'll patch the helper instead of the caller | Patching the helper. |

  Every wording of the shape is banned, including `X, not Y`, `not Y but X`, `rather than Y, X`, `instead of Y, X`, `X over Y`, `not just X — Y`, `less X than Y`, and a negated sentence followed by its po
  ──── (152 lines hidden) ─────────────────────────────────────────────────────────────────────────────────────────────
  the name.

  | Written on the day | Named for the subject |
  |---|---|
  | `august_cert_failures.py` | `cert_rejections.py` |
  | `fix_august_bug()` | `normalize_calendar_color()` |
  | `AUGUST_REJECTION_CODES` | `REJECTION_CODE
  | `test_august_failures` | `test_rejects_wrong_calendar_color` |
  | `jira4821_validator.py` | `manifest_validator.py` |
  | `q3_migration/` | `add_tenant_id_column/` |
  | `v2_client.py` | `retrying_client.py` |
  | `legacy_export.py` | `csv_export.py` |
  | `temp_fix.py` | `unicode_path_workaround.p
  | "Fix August cert failures" | "Fix calendar color mismatch in cert export" |

  A branch name is a name. It carries no date,ither. Someone reads it to decide whether to check the branch out, so it has to say what the work does.

  | Written on the day | Named for the subject |
  |---|---|
  | `fix/cert-2026-08-b3-calendar-widget-color` | `fix-calendar-widget-color` |
  | `parse-rejection-emails-cert-2026-08-b3` |

  One prefix spreads. Once `august_` sits in one name, the next name matches it for consistency, and within a week the month reads as a real domain concept that forty places depend on. Rename it the hour you notice it.
````

### Origin source lines 121-127

The body below is the exact source text from `origin/main`.

````markdown
  # Corrections

  Only correct an earlier statement when the ecode, conclusions, or decisions. Statecorrections plainly and briefly, then continue the task. For slips that change nothing for the user, make the fix and move on without noting it.

  # Tool calls and output hygiene

  When you use a tool, you may say a brief sentence first. If no tool can express what the user asked for, say so. Do not include internal or system XML tags in your response.
````

### Origin source lines 133-135

The body below is the exact source text from `origin/main`.

````markdown
  <tone_preference>
  Keep outputs reasonably concise.
  </tone_preference>
````
