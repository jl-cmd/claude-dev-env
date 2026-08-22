---
name: eli5
description: >-
  Create concise beginner-friendly HTML explanations with large visuals and minimal text. Triggers: ELI5, explain like I am 5, explain this simply, beginner explanation, every user-facing response.
---

# eli5

All user-facing responses follow this skill.

## Contents

- [Principle](#principle)
- [When this applies](#when-this-applies)
- [Skill classification](#skill-classification)
- [Authority boundaries](#authority-boundaries)
- [Composition boundary](#composition-boundary)
- [Gotchas](#gotchas)
- [Task seeding](#task-seeding)
- [Process](#process)
- [File index](#file-index)
- [Folder map](#folder-map)

## Principle

Explain the current topic for a complete beginner with plain language, large
visuals, and very few words. Keep the explanation concise, friendly, useful,
self-contained, and browser-ready.

ELI5 owns the HTML presentation envelope. Use one stable self-contained HTML
artifact for the active task or conversation. Keep update-in-place continuity as
the conversation continues, and share the current artifact after each update.

## When this applies

Apply ELI5 to every user-facing response, including responses that present a
capability-specific artifact. Raw tool output, machine payloads, code, and
native repository artifacts retain their required formats. Present their human
explanation inside the HTML presentation envelope when the response is user-facing.

### First-match refusal condition

Evaluate this condition before task seeding. When no task tool is available,
reply exactly: `ELI5 requires a session task tool. The artifact flow is paused.`

## Skill classification

**Dominant type:** Business Process & Team Automation.

**Folder rationale:** `SKILL.md` holds the global artifact workflow, and
`reference/task-seeds.md` holds its ordered session tasks. The leaf keeps its
presentation capability local.

## Authority boundaries

| Owner | Owns | ELI5 action |
|---|---|---|
| ELI5 | Beginner framing, visual expectation, minimal content, HTML continuity, and sharing | Keep the response in one useful, stable artifact. |
| `~/.claude/rules/asd-ste100-language.md` | Word choice, sentence structure, terminology, punctuation, procedural instructions, and safety text | Read and apply it before writing or updating any page or response prose. |
| The named capability skill | Native data, evidence, workflow, and file-format requirements | Preserve its contract inside the HTML presentation envelope. |
| User instructions and safety requirements | Task boundary, audience, confidentiality, and permitted result | Treat them as the controlling scope for the page. |
| Human review | Technical accuracy, terminology, safety, confidentiality, intended meaning, and rendered usefulness | Review the completed artifact before delivery. |

## Composition boundary

ELI5 is a leaf skill. Explanation and visual composition remain one user-facing
capability. ELI5 invokes zero presentation sub-skills. Named capability skills
keep ownership of their native artifact rules while ELI5 supplies the global
 HTML presentation envelope.

## Gotchas

- Keep the HTML presentation envelope active when another capability skill creates the page.
- Keep sentence-level prose under `~/.claude/rules/asd-ste100-language.md`.
- Preserve an explicit user-supplied output path and an existing artifact path.
- Keep one artifact path across all updates in the active task or conversation.
- Keep every page self-contained and browser-ready.
- Preserve native wrapper, payload, evidence, and file-format contracts owned by
  the named capability skill.
- Use human review for accuracy, terminology, safety, confidentiality, meaning,
  and rendered legibility.

## Task seeding

At skill start, register every item in `reference/task-seeds.md` as a session
task through `TaskCreate`, `TodoWrite`, or the host task equivalent. Work from
that task list. Mark each item complete with `PASS`, `FAIL` plus file evidence,
or `N/A` plus the reason. When no task tool is available, use the exact refusal
under [When this applies](#when-this-applies) before authoring the artifact.

## Process

1. **Deterministic — locate the current HTML artifact or create the first one.** Find the active
   artifact, preserve an explicit user path, or create a clear self-contained
   browser-ready HTML artifact when no path exists. Keep the chosen path for the
   rest of the active task or conversation.
2. **Borderline — add the current explanation to that artifact.** Read and apply
   `~/.claude/rules/asd-ste100-language.md` to every sentence. Frame the topic
   for a beginner, use a large useful visual, keep the text minimal, and update
   the same artifact in place.
3. **Judgment — share the updated artifact with the user.** Review technical meaning,
   terminology, safety, confidentiality, accessibility, browser readiness, and
   visual legibility. When a check reports a defect, repair the artifact, repeat
   the review, and share after all checks pass.

### Examples

- **Creation:** Input — `Explain DNS for a beginner` with no artifact path.
  Output — `dns-explanation.html` with one self-contained page and a large visual.
- **Update and share:** Input — `Add why DNS caching helps` in the same
  conversation. Output — the same `dns-explanation.html` path updated and shared.

## File index

| Path | Purpose |
|---|---|
| `SKILL.md` | Global ELI5 presentation contract, authority boundaries, gotchas, and artifact flow. |
| `reference/task-seeds.md` | Ordered process items to register as session tasks. |

## Folder map

```text
eli5/
├── SKILL.md
└── reference/
    └── task-seeds.md
```
