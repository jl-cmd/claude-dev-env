---
name: "source-command-update-theme-db"
description: "Weekly theme database update with orphan detection. Detects new themes from Excel, processes assets, syncs release dates from Google Sheets, updates revenue."
---

# source-command-update-theme-db

Use this skill when the user asks to run the migrated source command `update-theme-db`.

## Command Template

Run complete weekly theme database update including orphan asset recovery.

**Problem this solves:** The standard update script only detects themes from Samsung Excel exports. Themes can exist as assets (from prior processing) without being in the themes table. This command runs standard update THEN recovers orphan themes with release dates from Google Sheets.

**When to run:** Weekly, after downloading fresh Applications.xls from Samsung Seller Portal (both accounts).

## Context

Project: `Y:\Design\Samsung Theme Development\Theme Planning`

**Key files:**
- `scripts/update_theme_db/main.py` — Standard 5-step update orchestrator
- `scripts/update_theme_db/config.py` — **Single source of truth** for all paths, thresholds, sheet coordinates
- `data/theme_asset_database.sqlite` — Theme database

**Before starting:** Read `scripts/update_theme_db/config.py` for current values. Do NOT use hardcoded paths or row numbers from this command — config.py is authoritative.

## Process

### 1. Pre-flight Check

Verify Excel files exist using the paths from config.py (`downloads_path` + `excel_pattern`):

```bash
python -c "from scripts.update_theme_db.config import CONFIG; files = list(CONFIG.downloads_path.glob(CONFIG.excel_pattern)); print('\n'.join(str(f) for f in files) if files else 'NO_EXCEL_FOUND')"
```

**If no Excel files:**
```
PRE-FLIGHT FAILED

No Applications.xls files found.

Download from Samsung Seller Portal:
1. Primary: seller.samsungapps.com → Accounting → Application List → Export
2. Secondary: Same steps on secondary account
3. Save to downloads folder (see CONFIG.downloads_path)

Then re-run: /update-theme-db
```
Exit.

### 2. Run Standard Update

```bash
cd "Y:\Design\Samsung Theme Development\Theme Planning"
python -m scripts.update_theme_db.main
```

This runs 5 steps:
1. **Detect** — Scans Excel for Premium AOD themes, compares to DB
2. **Insert** — Adds new themes with season + release_date from Google Sheets
3. **Assets** — Locates HomeScreen.png/Static.png, resizes to cache
4. **Analyze** — Codex vision generates keywords (batch_size from config, min_keywords+ each)
5. **Revenue** — Imports new sales CSVs, updates total_revenue and monthly averages

Capture counts from output.

### 3. Detect Orphan Assets

Check if orphan detection already exists in the codebase (grep for "orphan" in `scripts/update_theme_db/`). If not, query assets without matching themes:

```python
cur.execute('''
    SELECT DISTINCT SUBSTR(a.asset_id, 1, 12) as content_id, a.file_path
    FROM assets a
    WHERE NOT EXISTS (
        SELECT 1 FROM themes t WHERE t.content_id = SUBSTR(a.asset_id, 1, 12)
    )
    AND a.asset_id LIKE "%_home"
    AND SUBSTR(a.asset_id, 1, 12) GLOB '[0-9]*'
''')
orphans = cur.fetchall()
```

**If 0 orphans:** Skip to Step 5.

### 4. Add Orphan Themes

For each orphan:
1. Extract clean_name from file path (`Bookworm_Owl_home.png` → `Bookworm Owl`)
2. Determine account using `CONFIG.secondary_marker_id` threshold
3. Look up release date from Google Sheets (Previous Releases first, then primary/secondary sheets per config.py coordinates)
   - `lookup_release_date()` auto-converts US format → ISO (e.g., "1/29/2026" → "2026-01-29")
4. Insert with `status='active'` (NOT 'For Sale' — constraint violation)

```python
cur.execute('''
    INSERT INTO themes (theme_id, theme_name, content_id, account, status,
                       clean_name, release_date, total_revenue, created_at, updated_at)
    VALUES (?, ?, ?, ?, 'active', ?, ?, 0, ?, ?)
''', (content_id, clean_name, content_id, account, clean_name, release_date, now, now))
```

### 5. Report Results

```
UPDATE THEME DB COMPLETE

Standard Update:
  Themes detected: {n}
  Themes inserted: {n} ({skipped} skipped - no assets)
  Assets processed: {n}
  AI analysis: {n}
  Revenue updated: {n} themes

Orphan Recovery:
  Orphans found: {n}
  Themes added: {n}
  With dates: {n}
  Without dates: {n}

Database:
  Total themes: {n}
  Total assets: {n}
  Missing dates: {n}
```

### 6. Check Missing Release Dates

```python
cur.execute('SELECT COUNT(*) FROM themes WHERE release_date IS NULL')
```

**If > 0:** List theme names missing dates and remind user to add them to Google Sheets (primary or secondary sheet per config.py).

## Anti-patterns

**The orphan problem (critical):**
Standard update only reads Excel exports. Themes can exist as assets without being in themes table. ALWAYS run orphan detection after standard update — even if update says "0 added".

**Status constraint:**
`themes.status` must be 'active', 'retired', or 'draft'. Using 'For Sale' causes IntegrityError.

**Release date format:**
Dates from Google Sheets (US format "1/29/2026") are automatically converted to ISO format ("2026-01-29") by `lookup_release_date()`. This enables proper `ORDER BY release_date DESC` sorting.

**Account detection:**
Use `CONFIG.secondary_marker_id` from config.py to determine account. Do not hardcode the threshold.

**Legacy US-format dates:**
If you see dates like "1/29/2026" in the database (not sorting properly), run this fix:
```python
cur.execute("SELECT theme_id, release_date FROM themes WHERE release_date LIKE '%/%'")
for theme_id, date_str in cur.fetchall():
    m, d, y = date_str.split('/')
    cur.execute('UPDATE themes SET release_date = ? WHERE theme_id = ?',
                (f'{y}-{int(m):02d}-{int(d):02d}', theme_id))
conn.commit()
```

## Troubleshooting

**"No Excel files found"**
- Download Applications.xls from Samsung Seller Portal (both accounts)
- Save to downloads folder (check `CONFIG.downloads_path`)

**"Assets not found" for a theme**
- Verify folder exists under `CONFIG.primary_assets` or `CONFIG.secondary_assets`
- Check HomeScreen.png and Static.png exist

**AI analysis fails**
- Check Codex API accessible
- Verify images are valid PNGs

**IntegrityError on insert**
- Check status is 'active', 'retired', or 'draft'
- Check content_id not already in themes table

## Success Criteria

- [ ] Excel files found and validated
- [ ] Standard 5-step update completed
- [ ] Orphan assets detected and counted
- [ ] Missing themes added with release dates where available
- [ ] Summary displayed with all counts
- [ ] User informed of themes missing release dates

## Next Steps

- `/batch-wallpaper-analysis` — Run AI keyword analysis on new wallpapers (clear context first)
- `python cli/theme_gen.py stats` — View theme statistics
