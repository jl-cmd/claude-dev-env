# Effort evaluation sweep (Opus)

Offline-first harness for choosing e-code-review effort and publishing cited skill defaults.

## What it holds

| Piece | Path |
|---|---|
| Fixtures | `scripts/fixtures/{easy,medium,demanding}.json` |
| Schema + recommend | `scripts/effort_evaluation.py` |
| Constants | `scripts/config/e_code_review_effort_constants/` |
| Tests | `scripts/test_effort_evaluation.py` |

## How to run offline tests

```
python -m pytest packages/claude-dev-env/skills/e-code-review/scripts/test_effort_evaluation.py -q
```

## Skill defaults (OP-02C — e-code-review family)

Committed evidence: `scripts/effort_defaults_evidence.json`.

- `resolve_skill_effort_for_band("easy"|"medium"|"demanding")` → `low`|`medium`|`xhigh`
- Evaluation `high` / `max` map to skill `xhigh` (skill surface has three levels only)
- Every skill default cites a completed evaluation row with `thinking_enabled: true`

## Paid / live runs (optional)

1. For each fixture, run the matching e-code-review level at each CLI-supported effort (`low` … `max`) with thinking on.
2. Score quality, finding recall, finding precision; record visible tokens and latency.
3. Feed completed rows into `recommend_effort_by_band` and `skill_defaults_from_recommendation`.
4. Replace `effort_defaults_evidence.json` when live rows supersede the offline baseline.

Stop if the Opus 5 CLI model is unavailable, or if results cannot separate quality from cost/latency.
