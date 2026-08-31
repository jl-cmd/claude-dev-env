---
name: review-tier
description: >-
  Classify `review_tier_constants` from change axes, hard triggers, and user overrides. Triggers: /review-tier, tier override, and review classification.
---

# Review Tier

Classify one current change surface into T1, T2, or T3 using `reference/tier-policy.json` and `scripts/review_tier.py`.

## Composition

| Skill | When | Produces |
|---|---|---|
| `/review-router` | After classification | Current decision route and guarded execution |
| `/task-build` | At workflow start | Registered classification tasks |

If `/review-router` is unavailable, return the current classification.

## When this applies

Use for `/review-tier` and automatic review classification. Refuse execution requests with: `This is a route execution request — use /review-router.` Refuse malformed policy with: `The review-tier policy is invalid; repair the policy before classification.`

## Process

1. Register `reference/task-seeds.md` with the host task tool.
2. Run `scripts/review_tier.py` and record the current decision fields.
3. Hand the current decision to `/review-router` when route execution is requested.

## Examples

Input `{"files": 0, "lines": 0}` produces `T1`. Input `{"hard_triggers": ["migration"]}` produces `T3`. Input `{"files": 0}` with override `T2` produces calculated `T1` and effective `T2`.

## Dependencies

Requires Python 3.11+ and the standard library only. Treat a non-zero script exit as a failed classification.

## File index

| File | Purpose |
|---|---|
| `SKILL.md` | Classification workflow and boundaries |
| `reference/tier-policy.json` | Versioned axes, thresholds, and hard triggers |
| `reference/task-seeds.md` | Ordered classification tasks |
| `scripts/review_tier.py` | Deterministic classifier |
| `scripts/test_review_tier.py` | Classifier behavior tests |
| `scripts/test_generation.py` | Inventory generation tests |
| `scripts/conftest.py` | Test import setup |
| `scripts/review_tier_constants/__init__.py` | Constants package |
| `scripts/review_tier_constants/config/__init__.py` | Runtime configuration package |
| `scripts/review_tier_constants/config/constants.py` | Portable tier constants |

## Folder map

- `reference/` — policy and task data.
- `scripts/` — executable classifier and paired tests.
