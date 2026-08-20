---
name: small-cl
description: >-
  Scope or split a pull request into a self-contained reviewable increment. Use
  when a user asks to "split this PR", "make this change smaller", or "small CL".
---

# Focused Pull Request Guide

## When to Use This Guide

Use this guide to plan, assess, or split a pull request into a reviewable unit.
The pull request boundary is conceptual: one coherent outcome that a reviewer
can understand with its context and verification.

## What a Focused Pull Request Contains

A focused pull request contains the implementation, related tests, documentation,
and configuration needed for one outcome. It leaves the system in a usable state
and gives the reviewer the information needed to assess the change.

Use the [description guide](../descriptions/SKILL.md#required-content) to record
the scope, verification, risks, and follow-up work.

## Splitting a Change

Choose a split that gives each increment a coherent purpose and a clear test
boundary. Useful seams include:

- Preparation refactors followed by behavior changes.
- Independent vertical features that each deliver a user-visible capability.
- Layer-specific work when each layer remains independently understandable.
- Stacked changes when each earlier change supplies the next change's stable
  foundation.

State dependencies between related pull requests and keep each increment safe to
merge or revert on its own.

## Reviewable Scope

Ask to split a change when its breadth prevents a reliable assessment of design,
behavior, or verification. Identify the first coherent increment and the
remaining increments so the author has an actionable path forward.

Use [reviews](../reviews/SKILL.md#evaluation-criteria) to evaluate the resulting
scope and [emergencies](../emergencies/SKILL.md#emergency-classification) when an
active incident sets the immediate boundary.

## Responding to Review

Use the [comment guide](../comments/SKILL.md#responding-to-feedback) to respond
to feedback and resolve pushback.
