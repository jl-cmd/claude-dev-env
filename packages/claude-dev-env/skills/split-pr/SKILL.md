---
name: split-pr
description: >-
  Autonomous file-based PR split into a stacked dependency chain; analyze, propose via AskUserQuestion, execute on approval.
  Triggers: /split-pr, split pr, split this PR, split large PR, break up PR, stacked PRs from one PR, file-based PR split, PR too large.
---

# split-pr

Autonomously split one large pull request into a **file-based stacked chain** of smaller draft PRs. The agent analyzes, proposes one plan, waits for `AskUserQuestion` approval, then executes. No multi-turn “chat me through the split” loop.

**Announce at start:** `Splitting PR #<N> into a stacked file-based chain.`

**Source concept:** file-layer PR chains (database → contracts → backend → frontend → tests → config) as in [Being Nice to Reviewers: Splitting Large PRs in the AI Era](https://seriousben.com/posts/2025-07-splitting-large-prs-ai-era/). Judgment is automated; the user only approves or adjusts the plan.

## Gotchas

- **Do not chat the split step-by-step.** Run analyze → verify → one proposal → execute. The article’s interactive script-writing flow is replaced by this skill’s scripts.
- **Coverage before execute.** Every source file must land in exactly one slice. Run `verify_plan.py`; never open PRs with missing or duplicate paths.
- **Source branch stays intact.** Execution creates new `split/<pr>/…` branches via `git checkout <source> -- <files>`. Never rewrite or force-push the original head.
- **Stacked bases, not all-off-main.** Slice 2’s base is slice 1’s branch (and so on). Opening every PR against `main` loses the dependency story.
- **Clean tree required for real execute.** Dirty worktree → stop. Prefer a dedicated worktree if the session cwd is dirty; do not silently stash.
- **Shared files (lockfiles, package.json).** Heuristics put them in `config`. If a later slice needs them earlier, move those paths in the plan **before** approval — do not invent second copies of the same path.
- **`other` layer is a smell.** Re-bucket `other` paths by reading the file’s role before proposing. Empty `other` is ideal.
- **Decision brief before the gate.** Print how the split looks and what re-bucket decisions you made in chat **before** `AskUserQuestion`. The question is the approval control, not the first place the plan appears.
- **Draft PRs only.** Always `--draft`. Never mark ready from this skill.
- **Proof-of-work is human-owned.** The skill leaves every split PR in **draft** and does **not** post a five-part proof comment. Before `gh pr ready` on any slice, a human (or a later skill) must post proof per `proof-of-work-pr-comments`. Silent ready is the failure mode.
- **Bodies use `--body-file`.** Never `gh … --body` with markdown (hook + backtick corruption).
- **Grouping is path-layer heuristics, not an import graph.** seriousben’s method is file-based; `categorize_files.py` uses path rules as the deterministic proxy. Import/require edges are out of scope for v1 — re-bucket paths in the plan when a heuristic miss is obvious.
- **Plan files come from `gh pr view` file list**, not a local stale `main` diff. Offline `--files-json` is tests only.

## When this applies

- User runs `/split-pr <pr#>` or asks to split a large PR into smaller stacked PRs.
- A single feature PR is too large for a human review pass (rough default: ≥8 files or multi-layer mix).

**Refuse (exact line, first match wins):**

- No PR number and no identifiable open PR → `Name a PR number: /split-pr <n>.`
- PR already merged or closed → `Only open PRs can be split; reopen or pick an open PR.`
- User wants line-level `git add -p` commits only → `This skill does file-based stacked PRs; use interactive patch staging for line-level splits.`
- User wants review/converge of existing PRs → `Use /pr-converge or /autoconverge; /split-pr only excises a stacked chain.`

## Task seeding

Before Phase 1, register every item in [reference/task-seeds.md](reference/task-seeds.md) as a session task (`TodoWrite` / `TaskCreate`). Work only from that list. Mark complete with evidence (exit code, path, PASS/FAIL).

## Process

### Phase 1 — Resolve target

1. Parse `<pr#>` from the user (or the only open PR they named).
2. Confirm repo: current git toplevel unless `--repo owner/name` is given.
3. **Execute:**  
   `python "${CLAUDE_SKILL_DIR}/scripts/analyze_pr.py" --pr <N> --pretty`  
   Optional: `--repo owner/name`.
4. On non-zero exit, print the JSON `error` and stop.
5. Write the plan JSON to a temp path (e.g. `$TEMP/split-pr-<N>-plan.json`).

Load [reference/splitting-principles.md](reference/splitting-principles.md) only if you need to re-rank slices after heuristics look wrong.

### Phase 2 — Refine plan (judgment, minimal)

1. Read `proposed_slices`, `warnings`, and any `other`-layer files.
2. Optionally re-bucket paths (edit the plan JSON). Do **not** drop files.
3. Adjust titles/stories so each slice has one review focus.
4. **Execute:**  
   `python "${CLAUDE_SKILL_DIR}/scripts/verify_plan.py" --plan <plan.json> --pretty`  
   Exit must be 0 (`is_valid: true`). If not, fix the plan and re-run.

Path rules: [reference/path-layers.md](reference/path-layers.md).

### Phase 3 — Propose (mandatory gate)

1. Build the proposal per [reference/proposal-format.md](reference/proposal-format.md).
2. **Print the decision brief in chat** (required before the tool call): source PR, re-bucket decisions, slice table, merge order, execute mode, source branch intact. See proposal-format § Decision brief.
3. Call **`AskUserQuestion`** with a short confirm and:
   - Recommended: **Approve recommended split**.
   - **Approve local branches only**.
   - **Abort**.
4. On Abort → stop without git mutations.
5. On Adjust (Other) → edit plan, re-verify, print a fresh decision brief, re-ask (still one coherent proposal each time).
6. On Approve → Phase 4.

### Phase 4 — Execute

1. Working tree must be clean. If the session cwd is dirty, switch execute to a clean worktree that already has the source branch (invoke `/fresh-branch` only when you need a disposable tree; otherwise use a clean clone path via `--repo-path`).
2. Prefer `--dry-run` once when the chain has ≥4 slices; then run the real command without a second approval if the user already chose Approve.
3. **Execute (dry-run):**  
   `python "${CLAUDE_SKILL_DIR}/scripts/execute_split.py" --plan <plan.json> --dry-run --pretty`
4. **Execute (real, local branches only):**  
   `python "${CLAUDE_SKILL_DIR}/scripts/execute_split.py" --plan <plan.json> --pretty`
5. **Execute (push + draft PRs) — default after Approve recommended:**  
   `python "${CLAUDE_SKILL_DIR}/scripts/execute_split.py" --plan <plan.json> --push --create-prs --pretty`
6. On failure, the JSON includes `error` plus `created_slices` / `pr_urls` for slices that already landed — report that partial stack; do not invent recovery pushes.
7. **Verification honesty:** this skill does not run the repo’s full test suite on each slice. Each draft PR body must state that gap (the script’s short body does). Do not claim per-slice CI green unless you ran checks yourself.
8. **Do not** run `gh pr ready` on split PRs from this skill.

PR body template: [templates/pr-body.md](templates/pr-body.md).

### Phase 5 — Report

State: source PR number, slice branches, draft PR URLs (if any), merge order (`1 → 2 → …`), and that the original branch is unchanged.

## Constraints

- One capability: **excise a stacked file-based split from one PR**.
- Approval before any non-dry-run execute.
- Draft stacked PRs; dependency bases preserved.
- Scripts own git/gh mechanics; the agent owns plan judgment and `AskUserQuestion`.
- No force-push. No ready. No delete of the source branch.

## Sub-skills

| Skill | When | Produces | If missing |
|---|---|---|---|
| `fresh-branch` | Session cwd is dirty and real execute needs a clean tree for experiments | Isolated worktree path | Run execute only in a clean clone/worktree; do not reimplement worktree create ad hoc if `fresh-branch` is available |

## File index

| File | Purpose |
|---|---|
| `SKILL.md` | Hub: gotchas, phases, constraints |
| `CLAUDE.md` | Package map for this skill folder |
| `reference/task-seeds.md` | Ordered work items to register on the task tool |
| `reference/splitting-principles.md` | Empathic file-based chain rules |
| `reference/path-layers.md` | Layer catalog and heuristic notes |
| `reference/proposal-format.md` | AskUserQuestion proposal shape |
| `templates/pr-body.md` | Draft PR body skeleton |
| `templates/plan.example.json` | Example plan shape |
| `scripts/analyze_pr.py` | **Execute** — gh PR → plan JSON |
| `scripts/categorize_files.py` | Library — path → layer, slice builder |
| `scripts/verify_plan.py` | **Execute** — coverage gate |
| `scripts/execute_split.py` | **Execute** — branches / optional draft PRs |
| `scripts/split_pr_scripts_constants/` | Named constants |
| `scripts/test_*.py` | Paired tests |

## Folder map

- `reference/` — on-demand principles, layers, proposal, task seeds
- `templates/` — PR body and example plan
- `scripts/` — analyze, verify, execute + tests + constants
