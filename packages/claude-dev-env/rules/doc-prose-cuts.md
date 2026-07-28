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
- **AI review.** The claude-dev-env repository's root `AGENTS.md`, the AI-review fan-out source, names the other three shapes as findings an agent applies to the `.md` lines a PR changes. No hook backs them: telling a justification sentence from a load-bearing one needs meaning a regex cannot read.

## Sibling rule

[`plain-language.md`](plain-language.md) governs word choice — heavy words swapped for everyday ones. This rule governs which sentences survive at all.
