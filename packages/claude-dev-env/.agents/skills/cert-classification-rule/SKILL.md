---
name: cert-classification-rule
description: Add or change a Samsung cert-failure classification rule (fixable, unfixable, mixed). Use when the user says add a fixable item, add an unfixable item, mark this rejection unfixable, add a mixed item, classify this cert rejection, or add a cert rule. Covers the unfixable pattern config, the paired production-path test, and the re-sort recipe for already-filed folders.
---

# Cert-Failure Classification Rule

Add or change how a Samsung Galaxy Store certification rejection is sorted into one of four
buckets: `Fold`, `unfixable`, `mixed`, or `fixable`. A rejection lands in a bucket from its
must-fix issue titles plus a Fold device check, and the bucket decides which subfolder holds
the theme folder.

## Contents

- [When to use](#when-to-use)
- [Procedure checklist](#procedure-checklist)
- [The classification model](#the-classification-model)
- [How to add an unfixable title pattern](#how-to-add-an-unfixable-title-pattern)
- [How to add the paired production-path test](#how-to-add-the-paired-production-path-test)
- [Re-sort already-filed folders for a day](#re-sort-already-filed-folders-for-a-day)
- [Gotchas](#gotchas)
- [File index](#file-index)
- [Folder map](#folder-map)

## When to use

Use this skill when the user asks to:

- add a fixable item, add an unfixable item, or add a mixed item
- mark a rejection unfixable, or classify a cert rejection
- add a cert rule

Almost every such request is one new unfixable title pattern plus its paired test. The
`fixable` and `mixed` buckets are not configured by hand (see the model below), so a request
to "add a fixable item" usually means "stop treating this title as unfixable" or "confirm
this title stays fixable with a guard test".

### When a title pattern cannot help

If the rejection's only unfixable cue lives in the report description (the `L_TESTRESULT`
text, for example `*Not Identifiable`) and no must-fix title carries it, stop and tell the
user this exact point:

> This rejection's only unfixable signal is in the report description, not a must-fix title.
> The classifier reads titles only, so no pattern here will catch it — teaching it to read
> the description is a code change to the classifier, not a config rule.

## Procedure checklist

Copy this and check each item off as you go:

- [ ] Confirm the unfixable cue is in a must-fix **title**, not only the description (see Gotchas).
- [ ] Append the new `{pattern, label, review_note}` after the Gallery entry in `unfixable_patterns.json`.
- [ ] Add a paired production-path test: the live title classifies as `unfixable`, plus a negative guard for an out-of-scope title.
- [ ] Run the tests from the `shared_utils` directory and confirm green.
- [ ] Re-sort the affected day folders with the re-sort recipe (dry run first, then `--apply`).

## The classification model

`classify_failure(issue_titles, unfixable_patterns)` in
`shared_utils/samsung_utils/cert_failure_classifier.py:71` decides the bucket from the
must-fix issue titles:

- **unfixable** — every title matches an unfixable pattern.
- **mixed** — some titles match, some do not. This bucket is **derived**, never configured.
  The classifier returns it once at least one title matches an unfixable pattern and at least
  one does not.
- **fixable** — no title matches any unfixable pattern. This is the **default**: a rejection
  needs no pattern to be fixable.
- **None** — there are no must-fix titles at all.

Only the `unfixable_patterns` list is authored. Adding an unfixable pattern is the only way to
move a title out of the default `fixable` bucket.

**Visibility auto-fix (Stage 1) also gates on these patterns.**
`classify_visibility_failure_title` in `visibility_failure_classifier.py` calls
`get_matched_unfixable_patterns` / `load_unfixable_patterns` so a title that maps to a
curated colour slot still sets `is_blocked_from_auto_fix=True` (and
`can_auto_fix(record)` is False) when it matches Gallery, Clock system-UI, lock-screen
video wallpaper crop, Quick-panel preview mismatch, or any other unfixable pattern.
Changing a pattern here therefore changes both folder sorting and visibility auto-fix
eligibility.

**Lock-screen video wallpaper crop stays UNFIXABLE.** Pad-to-canvas (`lock_wallpaper_cover`,
#1449) and tall-aspect image-gen outpaint (`lock_aspect_regen`, #1454) were tried and
abandoned; Themes Studio automation for this class was cancelled. Do not reopen a crop,
outpaint, pad, or Primary/color autofix for Blue Edge-style "cut on both side(s)" titles.

The categorizer (`FailureCategorizer.categorize_and_move` in
`shared_utils/samsung_utils/cert_failure_processor/failure_categorizer.py:65`) runs the Fold
device check and the classifier, then resolves a single bucket in
`_resolve_category_priority` (`failure_categorizer.py:105`):

- An `unfixable` or `mixed` classification overrides the detector — these are the
  `severity_priority_buckets` in
  `shared_utils/samsung_utils/config/cert_failure.py:76` (`("unfixable", "mixed")`).
- A `Fold` detector category is kept only when the classification is `fixable`.
- A `fixable` classification applies only when no detector matched.

`FoldDetector` (`failure_categorizer.py:37`) matches the device regex `SM-F[79]\d{2}[A-Z]?` or
the keyword `fold` (config in `cert_failure.py:52`).

## How to add an unfixable title pattern

Patterns live in `shared_utils/samsung_utils/config/unfixable_patterns.json` as a JSON list
under the `unfixable_patterns` key. Each entry is `{pattern, label, review_note}`.

**The Gallery entry stays first (index 0).** The tests in
`test_cert_failure_classifier.py::TestDefaultConfigPath` assert `result[0]` is the Gallery
pattern. Append every new pattern after it; never insert ahead of it.

Live pattern shape, anchored on the rejected surface (Gallery is the shipped example):

```json
{
  "pattern": "(?i)<surface>.*poor visibility|poor visibility.*<surface>",
  "label": "<Surface> visibility",
  "review_note": "<honest note about the issue>"
}
```

`(?i)` is case-insensitive. The two-sided alternation matches the surface either before or
after the "poor visibility" phrase, because Samsung phrases the same title both ways. Replace
`<surface>` with the lowercase app or screen name (`settings`, `clock`, `calculator`). Match
against the **title** text the report shows, not the description.

### Writing the review_note honestly

`review_note` is the message the per-pattern explanation would carry in a review reply.
`DEFAULT_THEME_REVIEW_NOTES` still calls `compose_review_notes` with an empty matched-pattern
list. Devices-only, Quick-panel, and sound-preview labels in `cert_portal_notes_update_config.all_labels`
are the exception: `resubmit_via_notes_only_update` APPENDs those `review_note` sentences on
the existing ThemeUpdateProcessor path (search → Re-register → Certification Notes). Write a
truthful note, because it becomes the pasted sentence for those classes.

Do **not** fabricate a "Samsung confirmed" claim. State only what is true. The shipped Gallery
note is true because Samsung Support did confirm that issue; a new pattern for a different
issue must not borrow that wording unless the confirmation actually happened.

## How to add the paired production-path test

Every new unfixable pattern gets a paired test in
`shared_utils/samsung_utils/tests/test_cert_failure_classifier.py` that drives the production
path:

1. Load the real patterns with `load_unfixable_patterns()` (no path argument, so it reads the
   shipped config).
2. Build the report HTML with the live must-fix title text, run it through
   `extract_issue_titles`, then `classify_failure`, and assert the result is `unfixable`.
3. Add a negative guard: an out-of-scope "poor visibility" title (a surface with no pattern)
   classifies as `fixable`, so a future broad regex cannot silently swallow unrelated
   rejections.

Use the exact title strings Samsung's report produces. The existing
`TestClassifyFailure::test_gallery_regex_matches_all_known_variants` shows the shape: a list of
real title variants, each asserted as `unfixable` through `classify_failure`.

Run the tests from the `shared_utils` directory (its pytest config is anchored there):

```bash
cd shared_utils && C:\Python313\python.exe -m pytest samsung_utils/tests/test_cert_failure_classifier.py -q
```

## Re-sort already-filed folders for a day

After adding a pattern, theme folders filed for an earlier day still sit in their old bucket.
Run `scripts/resort_cert_folders.py` to recompute each theme's bucket with the new patterns and
move any folder whose current bucket differs from the computed one. The script reuses the
production `FailureCategorizer` decision helpers (`_parse_rejection_text`, `_detect_category`,
`_classify_from_html`, `_resolve_category_priority`), so it stays in step with the live
categorizer. It runs dry by default and moves only on `--apply`.

Set `PYTHONPATH` to the repo root so the import resolves the edited `shared_utils` tree rather
than a pip-editable install:

```bash
set PYTHONPATH=Y:\Information Technology\Scripts\Automation\Python
C:\Python313\python.exe .claude\skills\cert-classification-rule\scripts\resort_cert_folders.py "<cert base path>" June 18 PRIMARY
C:\Python313\python.exe .claude\skills\cert-classification-rule\scripts\resort_cert_folders.py "<cert base path>" June 18 PRIMARY --apply
```

Cert-failure folders live at `<base>\<Month>\<day>\<account_folder>\<bucket>\<theme>`, where
`<account_folder>` is `Themes` for PRIMARY and `Theme Editor Themes` for SECONDARY
(`AccountFolderConfig` in `shared_utils/web_automation/config/account.py:91`).

`scripts/resort_cert_folders.py` passes the repo `code_rules_enforcer` Write hook: output goes
through a `logger` with %-style format strings (no bare `print()`), the base path is an
argument, every named value is a typed `dataclass` field rather than a module-level
`UPPER_SNAKE` constant, and loop variables carry the `each_` prefix.

## Gotchas

- **Only titles are matched, never the description.** The classifier reads the must-fix issue
  **titles** via the `L_TITLE` regex in `extract_issue_titles`
  (`cert_failure_classifier.py:40`). The rejection description text — the `L_TESTRESULT` span,
  for example a `*Not Identifiable` note — is **not** read by the classifier. A signal that
  lives only in the description will not flag a title unless that title also matches a pattern.
  When a rejection's only "unfixable" cue is in the description, no title pattern can catch it.
- **Do not reopen crop autofix.** Lock-screen video wallpaper "cut on both side(s)" is
  UNFIXABLE. Closed #1449 (pad-to-canvas) and #1454 (tall outpaint) must stay closed.
- **The Gallery entry stays at index 0** of `unfixable_patterns.json`. Tests assert
  `result[0]` is Gallery; append new patterns after it.
- **"-" placeholders are excluded.** Recommended-table rows show a `-` title; `extract_issue_titles`
  drops them, so they never count toward a classification.
- **Run tests from the `shared_utils` directory.** Its pytest config (`testpaths`,
  `asyncio_mode`) is anchored there. A run from the repo root will not collect the tests
  correctly.
- **Use `C:\Python313\python.exe`.** The repo-root `.venv` is a Linux/NAS virtual environment
  with no `Scripts\python.exe` on Windows.
- **Set `PYTHONPATH` to the repo root for the re-sort.** Without it, the import can resolve a
  pip-editable install of `shared_utils` whose config lacks the freshly added pattern, so the
  new pattern does not take effect.

## File index

| File | Purpose |
|------|---------|
| `SKILL.md` | This hub — the classification model, the add-a-rule procedure, the test recipe, and gotchas. |
| `scripts/resort_cert_folders.py` | Re-sorts already-filed cert-failure folders for a day after a pattern change. Execute it (see the re-sort section); set `PYTHONPATH` to the repo root first. Dry-run by default, moves on `--apply`. |

## Folder map

- `SKILL.md` — hub.
- `scripts/` — the re-sort utility, executed rather than read into context.
