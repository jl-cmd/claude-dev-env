# Runner selection (medium review)

How `/e-code-review medium` (and loop) picks a harness runner for finder and
verify work. `SKILL.md` points here.

| Topic | Content |
|---|---|
| Goal | One skill surface, many runners (Grok, Codex, Claude headless, and others) |
| Today | `scripts/grok_code_review.py` is the Grok medium orchestration module |
| Target | A thin selector chooses a runner by availability and task flags |

## Today

- Medium procedure: `reference/medium.md` (angles, verify, output fields).
- Grok orchestration API: `scripts/grok_code_review.py` (discovery, dedupe,
  retain, head-drift).
- Constants: `scripts/e_code_review_scripts_constants/`.

## Target shape (tracked separately)

1. **Runner protocol.** Shared inputs (diff base, head, angles) and outputs
   (candidates, verdicts, severities).
2. **Detection.** Which runners are installed or configured (PATH, skills,
   account chain).
3. **Selection.** Pick one runner. Keep vendor choice out of `SKILL.md`
   process steps.
4. **Adapters.** Thin wrappers: Grok (current module), Codex, Claude, and
   others.

Link this file from the tracking issue.

## Related

- Skill hub: `../SKILL.md` (levels, fix, loop).
- Preflight proposal: `preflight-proposal.md` (immutable range, local runner, proposal evidence).
- Medium procedure: `medium.md`.
