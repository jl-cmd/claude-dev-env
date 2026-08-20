# Runner selection (medium review)

How `/e-code-review medium` (and loop) should pick a **harness runner** for
finder/verify work. This file is the map; `SKILL.md` only points here.

## What lives here

| Topic | Content |
|---|---|
| Goal | One skill surface; many possible runners (Grok, Codex, Claude headless, …) |
| Today | `scripts/grok_code_review.py` is the Grok medium orchestration module |
| Target | A thin selector chooses a runner by availability and task flags |
| Non-goals | Reimplementing every harness inside this skill |

## Today

- Medium procedure: `reference/medium.md` (angles, verify, output fields).
- Grok orchestration API: `scripts/grok_code_review.py` (discovery, dedupe,
  retain, head-drift).
- Constants: `scripts/e_code_review_scripts_constants/`.

## Target shape (tracked separately)

1. **Runner protocol** — shared inputs (diff base, head, angles) and outputs
   (candidates, verdicts, severities).
2. **Detection** — which runners are installed/configured (PATH, skills,
   account chain).
3. **Selection** — pick one runner without baking a single vendor into
   `SKILL.md` process steps.
4. **Adapters** — thin wrappers: Grok (current module), Codex, Claude, …

Open issue for implementation work should link this file and keep PRs small
(Google small-CL practice: one concern per PR).

## Related always-on docs

- Skill hub: `../SKILL.md` (levels, fix, loop — not runner internals).
- Medium procedure: `medium.md`.
- Shared worker spawn (when applicable):
  `packages/claude-dev-env/_shared/pr-loop/worker-spawn.md` in the package tree.
