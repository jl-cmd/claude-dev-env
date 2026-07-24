# Pre-catch lens checklist

The shared checklist the internal pre-catch lenses read on demand. 

## Lane 1 — Deterministic sweep

The mechanical, static, and test classes belong to a deterministic run. The static-sweep 
step owns them: it runs the CODE_RULES gate (`code_rules_gate.py --base origin/main`), 
`ruff`, `mypy`, and stem-matched `pytest` over the changed files. A reading lens trusts the 
sweep to have cleared them and reviews sweep-clean code.

- Every CODE_RULES violation the gate reports is a finding.
- Every `ruff` and `mypy` diagnostic on a changed file is a finding.
- Every failing test in a changed production module's paired test is a finding.
- **Proof of absence:** the gate exits 0, `ruff` and `mypy` report no diagnostic
  on the changed files, and the stem-matched tests pass.

## Lane 2 — Doc-vs-code parity

Every doc claim in the diff matches the code it describes. Reuse the
`pr-consistency-audit` skill's canonical-source cross-reference method
(`~/.claude/skills/pr-consistency-audit/SKILL.md`, canonical source first) and the
drift rubric at
`~/.claude/audit-rubrics/category_rubrics/category-o-docstring-vs-impl-drift.md`.

- Every line citation resolves to the line it names.
- Every referenced file or script path exists.
- Every symbol is attributed to the file that defines it.
- Every inventory table, env-var table, count claim, and ordering claim matches
  the code.
- **Proof of absence:** each referenced path, citation, symbol, and table checked
  against its source and found in step.

## Lane 3 — Test-assertion completeness

Every changed or new production path carries a test that exercises its behavior.

- Every changed or new production path has a paired test that calls it and asserts
  on its return value or side effect.
- A changed test pins the behavior it covers rather than hiding it behind a mock.
- **Proof of absence:** each changed production path paired with a behavior test
  that fails when the path regresses.

## Lane 4 — PR-description-vs-diff two-way parity

The PR body and the diff describe the same change, both directions.

- Every claim in the PR body maps to a hunk in the diff.
- Every hunk in the diff maps to a claim in the PR body.
- Flag any invented path, invented count, or out-of-scope change.
- **Proof of absence:** the two-way map complete — every claim has a hunk and
  every hunk has a claim.

## Lane 5 — Adversarial audit

The bug-audit lens runs the adversarial second pass the audit contract specifies
(`~/.claude/skills/_shared/pr-loop/audit-contract.md`): assume the first A-P pass missed
at least three P1 bugs, then find them.

- Return new file:line findings for the bugs the first pass missed.
- Or return a per-category proof-of-absence entry naming each re-examined category
  and why it holds.
- A bare "nothing new" is not an acceptable result for this pass.
- **Proof of absence:** a per-category adversarial-probe entry for each re-examined
  A-P category with no new finding.
