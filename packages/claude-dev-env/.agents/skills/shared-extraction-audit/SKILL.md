---
name: shared-extraction-audit
description: >-
  Use when auditing PRs for helpers living in workflow packages instead of
  shared_utils — extraction audit, shared_utils migration, orchestration-only
  packages, thin wrappers, or layer inversions.
---
# Shared Extraction Audit

Audit-first, fix-second workflow for keeping **orchestration packages thin** and **shared_utils canonical**.

## When to use

- User points at a PR (e.g. `#1954`, `#1965`) and asks for the same review loop
- A package grew `fix_one`, `_default_*`, backup upload, rembg session, or residual gates alongside orchestration
- Before merge: confirm consumers are adapters, not second implementations

## Target architecture

| Layer | Holds | Examples |
|-------|--------|----------|
| **shared_utils** | Reusable actions, I/O, DB flips, inference, constants used by 2+ workflows | `status_promotion`, `background_removal`, `drive_production_backup`, `stp_filenames` |
| **Workflow package** | Orchestration, CLI, sweep loops, workflow-specific constants only | `cert_fix_queue/pipeline/queue_run.py`, `theme_dialer_pipeline` compose runners |
| **Skills / scripts** | Operator entrypoints that **delegate** to shared_utils | No parallel rembg/session stacks |

**Load-bearing rule:** If another package would import it, put it in `shared_utils`. After the move, every former caller imports the shared symbol and the old module is deleted.

## Audit workflow

Copy to TodoWrite:

```
Shared extraction audit:
- [ ] 1. Scope the PR (base branch, changed packages, stated goal)
- [ ] 2. Map canonical homes already in shared_utils
- [ ] 3. Grep for offense patterns (see reference/offense-taxonomy.md)
- [ ] 4. Write prioritized findings (P0–P3)
- [ ] 5. User confirms fix band (audit-only vs implement)
- [ ] 6. Extract in small CLs (~100 lines) + move/adjust tests
- [ ] 7. Run scoped pytest, commit, push, update PR
```

### Step 1 — Scope

```bash
git fetch origin pull/<N>/head:pr-<N>   # or checkout feature branch
git diff <base>...<head> --stat
git diff <base>...<head> --name-only | rg 'shared_utils|cert_fix_queue|theme_dialer|clean_room|\.claude/skills'
```

Read the PR summary, then verify **what landed correctly** before listing offenses.

### Step 2 — Search patterns

Run these greps on the PR diff scope:

```bash
# Rename-only seams and re-export facades
rg '_default_|def _.*_flipper|def _.*_one\b|promote_one|fix_one|backup_upload' <package> shared_utils
rg '^from shared_utils\..* import \w+$' <package>

# Layer inversions (shared importing consumer)
rg 'from (cert_fix_queue|theme_dialer_pipeline|clean_room_theme_icons)\.' shared_utils/

# Parallel stacks (second session/cache for same concern)
rg 'new_session|lru_cache.*session|rembg\.remove' .claude/skills shared_utils

# Duplicate constants
rg 'ALPHA_CHANNEL_INDEX|RGBA_ALPHA|DEFAULT_.*_PREFIX|ONEUI_STP_BASENAME' --glob '*.py'

# Duplicate test support
rg 'fail_if_called|build_rejected_theme_row|preserve_supplied_alpha' --glob '**/tests/**'
```

### Step 3 — Classify offenses

Use `reference/offense-taxonomy.md` beside this skill. Assign priority:

| Priority | Meaning |
|----------|---------|
| **P0** | Layer inversion or duplicate production stack (must fix before merge) |
| **P1** | General helper/constants/tests still in consumer package |
| **P2** | Module shape, I/O overlap, monolith size |
| **P3** | Stale names, docstrings, test attribute bugs |

### Step 4 — Report template

```markdown
## PR #<N> extraction audit

### Done well
- [canonical modules and deletions]

### P0 — …
| Offense | Where | Target module | Tests |
|---------|-------|---------------|-------|

### Suggested fix order
1. …
```

**Audit-only:** stop after the report unless the user asks to implement.

## Fix workflow (when implementing)

### Extraction rules

1. **Move behavior** — delete the consumer copy; every caller imports the shared symbol
2. **Wire shared APIs at the call site** — e.g. `db_flipper=promote_theme_to_status` with `filename_prefix=...`
3. **Retarget every caller, then delete the old module** — grep the old import path; remove re-export facades
4. **Constants:** one source; workflow CLI keeps only workflow-specific names (`LEDGER_FILENAME`, exit codes)
5. **Tests move with behavior** — shared module gets shared tests; orchestration keeps integration tests only
6. **Small CLs** — one concern per commit (~100 lines); run scoped pytest after each

### Canonical target map (this repo)

| Need | Home |
|------|------|
| Theme DB status flip | `shared_utils/theme_db/status_promotion.py` |
| Account folder ↔ ThemeAccount | `shared_utils/theme_persistence/account_adapter.py` |
| STP basename parsing | `shared_utils/samsung_utils/stp_filenames.py` |
| Drive backup upload | `shared_utils/files/drive_production_backup.py` |
| Timestamp scratch dirs | `shared_utils/files/timestamp_directory_retention.py` |
| Foreground extraction | `shared_utils/theme_assets/background_removal.py` |
| Cert fix / promote actions | `shared_utils/theme_assets/cert_closeout/` |
| Fixed-STP promotion sweep | `shared_utils/samsung_utils/promote_fixed_stp_sweep.py` |
| Cert queue orchestration only | `cert_fix_queue/pipeline/` (`queue_run`) and `run_cli` |

See also `.claude/rules/reuse-existing-tooling.md` before adding helpers.

### Verification

```bash
cd shared_utils && python -m pytest path/to/tests -n 0 -q
cd cert_fix_queue && python -m pytest tests/ -n 0 -q
```

Provide evidence: pytest output counts, not "should work".

### Git / PR

- Branch: `cursor/<topic>-593d` or existing PR branch
- Commit message: `Extract <what> from <package> into shared_utils`
- Update PR body: architecture table + test counts
- Do not merge; draft PR unless user says otherwise

## Anti-patterns (flag these)

- `_default_*` adapter around a shared_utils function in a consumer module
- Workflow module that only does `from shared_utils... import foo as foo`
- `fix_one.py` / `promote_one.py` / `promote_run.py` / `backup_upload.py` in orchestration packages
- `shared_utils` importing `theme_dialer_pipeline` or `cert_fix_queue`
- Second rembg/BiRefNet session in a skill while `background_removal` exists
- Identical `tests/support.py` in two packages
- `config/constants.py` that only aliases extracted helpers

## Examples

See `reference/examples.md` for cert_fix_queue (#1965) and background_removal (#1954) audits.

## File index

| File | Purpose |
|------|---------|
| `SKILL.md` | Hub |
| `reference/offense-taxonomy.md` | O1–O10 offenses + priority guide |
| `reference/examples.md` | Repo-specific audit examples |
