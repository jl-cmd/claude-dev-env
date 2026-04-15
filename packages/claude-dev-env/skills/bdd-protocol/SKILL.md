---
name: bdd-protocol
description: >-
  On-demand BDD depth aligned with jl-cmd/claude-code-config#82: Example Mapping (Smart &
  Molak §6.4), scenario quality and anti-patterns (§7.6), solo minimal BDD, outside-in test
  layout. Use when expanding `<behavior_protocol>` in the system prompt, writing executable
  specifications, or when the user asks for discovery, "the one where" examples, or BDD
  scenario quality. Triggers: bdd-protocol, Example Mapping, BDD anti-patterns, §7.6.
---
@~/.claude/skills/bdd-protocol/references/example-mapping.md
@~/.claude/skills/bdd-protocol/references/anti-patterns.md

# BDD protocol (on-demand)

The always-on sequence lives in `.claude/system-prompts/software-engineer.xml` under `<behavior_protocol>` (Deliberate Discovery → Illustrate → Formulate → Automate). This skill adds **depth** you load when you need algorithms, catalogs, or layout guidance.

## When to use this skill

- The user or task needs **Example Mapping** steps, parking-lot questions, or "the one where …" phrasing.
- You are writing or reviewing **scenarios** and need the **§7.6** quality bar and anti-patterns.
- You are organizing **tests by behavior** (describe / when / should) or using **soap-opera personas** for solo work.

## Authority

- John Ferguson Smart & Jan Molak, *BDD in Action* 2e (Manning, 2023) — §2.3.7 outside-in, §5.4 Deliberate Discovery, §6.4 Example Mapping, §7.6 scenario quality, §16.5.5 test layout.
- Dan North, "Introducing BDD" (2006).
- John Ferguson Smart, Minimal BDD (learnbdd.com; Wayback-cited in tracking issue).

## What stays in the system prompt

Do not duplicate the four-phase sequence here; keep a single source of truth in `<behavior_protocol>`.
