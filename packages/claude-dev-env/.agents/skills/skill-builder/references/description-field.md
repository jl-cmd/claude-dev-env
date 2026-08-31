# Description field (trigger catalog)

Source: [Anthropic — Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) (Writing effective descriptions; metadata pre-load), [Claude Code Skills](https://docs.anthropic.com/en/docs/claude-code/skills), Thariq lessons (`thariq-x-post-skills.json`).

## Role

At session start, **only** each skill’s `name` and `description` load into context. The body loads after selection.

The description is **selection metadata**, not a summary of the skill and not process documentation. It answers: *should Claude load this skill for this user turn?*

> "The description field is not a summary — it’s a description of when to trigger."

> "The description is critical for skill selection: Claude uses it to choose the right Skill from potentially 100+ available Skills."

## Hard limits

| Rule | Value |
|---|---|
| Voice | Third person only (no I/you) |
| Max length | 1024 characters |
| XML | Forbidden |
| Empty | Forbidden |

## Required shape: trigger catalog

Two parts, dense, no story prose:

1. **Capability stem** (what) — 5–20 words of capability tokens. Fragments or semicolon-separated verbs. No motivation, no audience address, no “helps you”.
2. **Triggers** (when) — concrete phrases, slash-commands, file types, and domain nouns the user or model might emit. Prefer a labeled `Triggers:` segment.

### Canonical template

```yaml
description: >-
  <capability tokens>. Triggers: <phrase>, <phrase>, <slash>, <filetype>, <near-miss exclusion if needed>.
```

### Good

```yaml
description: >-
  Extract PDF text/tables; fill forms; merge docs. Triggers: PDF, .pdf, forms, document extraction, fill this form, merge PDFs.
```

```yaml
description: >-
  Skill lifecycle: classify, scaffold, write via the skill-writer-agent, self-audit, compose sub-skills, polish description triggers. Triggers: build a skill, new skill workflow, improve this skill, optimize skill description, skill development lifecycle, skill modularity.
```

```yaml
description: >-
  Generate commit messages from git diffs. Triggers: commit message, write a commit, staged changes, git commit help.
```

### Bad (story / waste)

```yaml
# Narrative — burns always-on tokens, weak for matching
description: >-
  This skill helps you work with PDF files by guiding Claude through a careful
  process of extraction and form filling so you get reliable results every time.
```

```yaml
# Vague — no match surface
description: Helps with documents
```

```yaml
# Implementation dump — body material, not metadata
description: >-
  Uses pdfplumber and a five-step validate loop. See scripts/ for helpers.
```

```yaml
# First/second person
description: I can help you process Excel files
description: You can use this to process Excel files
```

## Authoring steps

1. List **capability tokens** (what the skill owns in one breath).
2. List **10+ user phrasings** that should select this skill (formal, casual, slash, file-type).
3. List **near-misses** that must *not* select it (sibling skills). Fold only the shortest distinguishing tokens into Triggers if needed.
4. Assemble stem + `Triggers:` list. Strip adjectives, benefits, and process narrative.
5. Count characters (≤1024). Prefer under ~400 when possible — every skill’s description is always loaded.
6. Register the task seeds below on the session task list (`TaskCreate` / `TodoWrite`); complete each with evidence. Do not use markdown checkboxes as the tracker.

## Description task seeds

- Third person; no I/you
- Capability stem present (what), ≤20 words of tokens
- Triggers: segment (or equivalent dense when-list) with concrete phrases
- No story prose, benefits language, or implementation steps
- No XML; length ≤1024
- Distinguishable from sibling skills in the same domain
- Body holds process detail — not the description

## Where process lives

| Content | Location |
|---|---|
| When to select the skill | `description` frontmatter |
| How to run the skill | SKILL.md body + companions |
| Refusal / boundary narrative | When-this-applies section in body |
| Sub-skill invocation | Body Sub-skills table (`skill-modularity.md`) |

## Polish workflow

`workflows/polish-skill.md` Step 1 is the dedicated description pass: rewrite any story description into a trigger catalog and re-check discovery against phrase lists.
