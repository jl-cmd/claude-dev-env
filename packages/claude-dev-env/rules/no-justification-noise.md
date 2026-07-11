---
paths:
  - "**/*.md"
---

# No Justification Noise in Documentation

**When this applies:** Any Write or Edit to a `.md` file.

## Rule

Markdown states what the system is and does, in facts a reader can act on. Cut any sentence whose only job is to say why a choice is good, or to restate a gain the reader already works out from the stated behavior or from a rule a hook or another file enforces. A sentence like that carries no new fact — it repeats one the reader already holds, so it earns no space.

## The test

For each sentence, ask: **does it state a fact the reader can act on that they could not already work out from the behavior around it or from a rule enforced elsewhere?** If no, cut the sentence.

## Two shapes to catch

### Pure noise — cut the whole sentence

A sentence whose only job is to point out a result that follows from a fact the doc already states.

> Autoconverge's bug-audit and self-review lenses and pr-converge's CODE_REVIEW step point at this file and read it when they run; they do not carry its text in their spawn prompts, so the checklist stays out of the per-round token budget.

The doc already states the lenses read the file. The "so it stays out of the token budget" tail is a result the reader works out alone, so it carries nothing. Cut the sentence.

### Load-bearing first, noise after — keep the fact, cut the rest

A sentence that states a real fact, trailed by prose that only re-argues it or restates its payoff.

> The pre-catch stage drives the code to clean against these five lanes before any external reviewer sees it. External reviewers (Cursor Bugbot, GitHub Copilot) are terminal confirmation gates that run only after every lane below is clean, and they are expected to return zero findings.

Keep the first sentence — it states what the stage does. Cut the second: "run only after every lane below is clean" repeats the first sentence's claim, and "expected to return zero findings" is a hoped-for result, not a fact the reader acts on.

## What stays

- A fact the reader acts on: an input a piece of code takes, an order a producer emits, a path a script writes.
- A rule's one-line reason stated in terms of present behavior — `--jq` runs per page, so cross-page sorts give wrong results — because that reason names a fact the reader needs to pick the right call.
- A tradeoff or a constraint the reader weighs before choosing a path.

## Sibling rules

This rule sits beside three others; each cuts a different kind of dead prose.

| Rule | Cuts |
|---|---|
| `no-historical-clutter.md` | references to old state (`previously`, `migrated from`) |
| `self-contained-docs.md` | references to the chat that produced the doc |
| `plain-language.md` | heavy words with an everyday swap |
| `no-justification-noise.md` | a present-tense sentence that only justifies or restates a fact the reader already holds |

`no-historical-clutter.md` keeps a rule's reason when the reason names present behavior; this rule keeps the same reason for the same test. The two agree: a reason that names a fact the reader acts on stays, and a sentence that only re-argues a stated fact goes.

## Enforcement

The AI review lane carries this rule: `AGENTS.md` names it as a finding an agent applies to the `.md` lines a PR changes. No hook backs it, because telling a justification sentence from a load-bearing one needs meaning a regex cannot read.

## Why

A sentence that repeats a fact the reader already holds costs reading time and pays back nothing.
