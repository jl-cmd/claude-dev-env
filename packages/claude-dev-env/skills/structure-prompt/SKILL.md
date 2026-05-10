---
name: structure-prompt
description: >-
  Restructure any user-provided prompt — order blocks correctly, replace persona
  framing with task constraints, enforce per-category dispositions, replace
  ceremony directives with measurable constraints, expand placeholder tokens
  into real values via the sibling rubric or AskUserQuestion, add file:line
  citations for identifiers that appear in the data body, mark the canonical
  sub-bucket with ⭐, and sharpen generic adversarial-pass phrasing into a
  category-specific failure-mode noun. Trigger when the user invokes
  /structure-prompt, pastes a prompt and asks to optimize it, asks for a
  "minimally invasive edit" to a prompt artifact, or asks to "tighten this
  prompt."
---

# structure-prompt

One pass per invocation. Classify each block of the input prompt, apply the matching spoke rules, and emit the rewritten prompt as a single fenced block (paste mode) or rewrite the file in place (file-path mode).

## Pre-flight

The input prompt arrives as the user's message body, as a fenced block within it, or as a file path argument. Treat the entire input as the artifact under optimization.

## First invocation of a session

Read [`reference/block-classification.md`](reference/block-classification.md), then [`reference/research.md`](reference/research.md), then [`reference/output-contract.md`](reference/output-contract.md).

## Match situation, read spoke

| Situation | Read |
|---|---|
| Starting any optimization | [`reference/block-classification.md`](reference/block-classification.md) |
| A spoke needs information that isn't in the input | [`reference/research.md`](reference/research.md) |
| Input contains a fenced code block, diff, dump, transcript, or single content region ≥ 500 characters, OR blocks appear out of canonical sequence (mission, metadata, framework, questions, output spec, data body) | [`reference/structure.md`](reference/structure.md) |
| Input opens with a role assignment ("You are…", "Act as…", "Imagine you are…", "As a…", "Pretend to be…", "Role:…") | [`reference/persona.md`](reference/persona.md) |
| Input names 2+ categories, surfaces, sub-buckets, items, checks, or criteria the agent processes | [`reference/per-category.md`](reference/per-category.md) |
| Input contains performance directives ("be thorough", "think step by step", "you are an expert", "please", "kindly") | [`reference/directives.md`](reference/directives.md) |
| Input contains narrative directives ("try to", "look at", "make sure", "consider", "be sure to", "think about") | [`reference/constraints.md`](reference/constraints.md) |
| Input contains placeholder tokens (`[REPO/ARTIFACT]`, `[INLINE THE FULL ARTIFACT HERE]`, `[N]`, etc.) | [`reference/instantiation.md`](reference/instantiation.md) |
| Sub-bucket bullets reference identifiers from the data body without `file:line` citations | [`reference/citation-depth.md`](reference/citation-depth.md) |
| Framework has 5+ sub-buckets and no ⭐ canonical-case marker | [`reference/canonical-case.md`](reference/canonical-case.md) |
| Output spec contains generic adversarial-pass phrasing ("missed at least N bugs/findings") | [`reference/adversarial-tuning.md`](reference/adversarial-tuning.md) |
| Input has typos, mixed bullet styles, untagged code blocks, trailing whitespace, blank-line runs, or non-sequential heading levels | [`reference/cleanup.md`](reference/cleanup.md) |
| Situation doesn't match any spoke above | [`reference/examples.md`](reference/examples.md) |
| Emitting the rewritten prompt | [`reference/output-contract.md`](reference/output-contract.md) |

## Folder map

- `SKILL.md` — this hub.
- `reference/` — rule detail per situation.
