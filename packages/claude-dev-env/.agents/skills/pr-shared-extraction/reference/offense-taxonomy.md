# Offense taxonomy

## O1 — General action in workflow package

**Signal:** Per-item function named `*_one`, `fix_*`, `promote_*`, `upload_*` in orchestration tree.

**Example:** `cert_fix_queue/pipeline/fix_one.py` → `shared_utils/.../fix_theme.py` (`fix_cert_rejected_theme`).

**Fix:** Move module; consumer passes workflow-specific `filename_prefix` / folder ids at call site.

---

## O2 — Thin wrapper / default seam / re-export facade

**Signal:** `_default_db_flipper`, `_default_*` that only renames kwargs and calls shared_utils. Also: a workflow module that only re-exports a shared symbol under the old path.

**Example:** Wrapper around `promote_theme_to_status` with `db_flip_log_filename_prefix`. After a move, `clean_room_theme_icons.rebuild_nine_patch` still contains `from shared_utils... import rebuild_nine_patch`.

**Fix:** Update every caller to the shared symbol (`filename_prefix`, `shared_utils.theme_assets.nine_patch_rebuild`, etc.) and delete the wrapper or facade.

---

## O3 — Layer inversion

**Signal:** `shared_utils/...` imports from `cert_fix_queue`, `theme_dialer_pipeline`, `clean_room_theme_icons`, or `.claude/skills/...`.

**Fix:** Move imported symbol into shared_utils; consumer imports shared.

---

## O4 — Parallel production stack

**Signal:** Second implementation of same concern (rembg session, despill, STP walk, DB flip) in skill or sibling package.

**Example:** `misc-asset-remaster/.../generated_alpha_mask.py` vs `background_removal.py`.

**Fix:** Delegate to canonical module; delete duplicate constants and session cache.

---

## O5 — Validation/gates on shared output in consumer

**Signal:** Functions that only inspect output of shared algorithm (residual alpha, edge green excess) live in dialer/clean-room.

**Example:** `theme_dialer_pipeline/pipeline/chroma_extract.py` using `edge_green_excess_mask` from shared.

**Fix:** `shared_utils/theme_assets/background_removal/residual_gates.py` (or sibling); optional `extract_foreground_gated`.

---

## O6 — Duplicate constants

**Signal:** Same literal or semantic constant in workflow `config/constants.py` and shared config.

**Examples:** `ALPHA_CHANNEL_INDEX`, `ONEUI_STP_BASENAME_RE`, two `DEFAULT_*_DB_FLIP_*` with same value.

**Fix:** Single definition in shared config; delete consumer copies.

---

## O7 — Misplaced config module

**Signal:** Constants named for workflow A live under package B's config (e.g. `fix_queue_constants` under `cert_closeout`).

**Fix:** Rename/move to owning workflow or shared outcomes module; drop re-export-only facades.

---

## O8 — Duplicate test support

**Signal:** Identical or near-identical `tests/support.py`, conftest bypass fixtures, synthetic PNG writers in multiple packages.

**Fix:** `shared_utils/theme_assets/testing/` or `shared_utils/.../tests/fixtures.py`; one import path.

---

## O9 — General I/O in domain module

**Signal:** Atomic staged writes, Drive upload, UTC helpers duplicated inside a 700-line domain file.

**Fix:** `shared_utils/files/` (e.g. `drive_production_backup`, `timestamp_directory_retention`, `record_persist`).

---

## O10 — Stale identifiers

**Signal:** Docstrings/tests still say `fix_one`, `promote_one`, `backup_upload` after rename.

**Fix:** Update docs; no behavior change.

---

## Priority guide

| Offense | Typical priority |
|---------|------------------|
| O3, O4 | P0 |
| O1, O2, O5, O6, O7, O8 | P1 |
| O9, monolith size | P2 |
| O10 | P3 |
