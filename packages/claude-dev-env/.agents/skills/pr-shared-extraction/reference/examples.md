# Audit examples (this repo)

## cert_fix_queue — PR #1965

**Goal:** `cert_fix_queue` holds orchestration only; general cert-fix utilities in `shared_utils`.

**Done well:**
- `locate_cert_folder_for_row`, `select_production_stp`, atomic copy, drive staged upload → shared_utils
- Deleted `fix_one.py`, `promote_one.py`, `backup_upload.py` from pipeline

**Offenses found and fixed:**
- `_default_db_flipper` in `fix_theme.py` → wire `db_flipper=promote_theme_to_status` at the call site; delete the wrapper
- `production_backup.py` under cert_closeout → `shared_utils/files/drive_production_backup.py`
- Duplicate test `support.py` → `shared_utils/theme_assets/testing/cert_fix_test_support.py`
- `fix_queue_constants.py` misnamed → `fix_outcomes.py`
- `_account_by_fixed_stps_folder` → `cert_failure_folder_to_theme_account_map()` in `account_adapter`
- `_fresh_run_directories` / scratch helpers → `allocate_timestamp_run_directory()`

**Pipeline after:**
```
cert_fix_queue/pipeline/
  queue_run.py
  promote_run.py
run_cli.py
```

---

## background_removal — PR #1954

**Goal:** One BiRefNet CPU path in `shared_utils/theme_assets/background_removal.py`.

**Done well:**
- Deleted `clean_room_theme_icons/chroma.py`, dialer `art_masks.py`, `png_io.py`
- Added `pixel_masks.py`, `png_canonical.py`
- Clean-room and dialer call `extract_foreground` / `extract_foreground_file`

**Remaining offenses (audit):**
- P0: Residual gates in `theme_dialer_pipeline/pipeline/chroma_extract.py` (shared algorithm output)
- P0: `_extract_component_foreground` wrapper; same pattern inlined in `compose_from_masters.py`
- P0: Parallel rembg in `misc-asset-remaster/scripts/generated_alpha_mask.py`
- P1: Duplicate extraction test fixtures (dialer conftest vs clean-room conftest)
- P1: `ALPHA_CHANNEL_INDEX` duplicated across dialer/clean-room/color_constants
- P2: Atomic write helpers inside 723-line `background_removal.py`; PNG path vs `png_canonical`

**Suggested fix order:** residual gates → shared test fixtures → dedupe constants → migrate misc rembg → I/O split (optional).
