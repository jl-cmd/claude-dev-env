# Add file:line citations on identifier mentions

When a sub-bucket bullet names an identifier (a function, variable, cmdlet, file path) that also lives in the data body, the bullet earns more value with a `file:line` citation appended.

## Detection

Two separate paths, evaluated for every backtick-wrapped identifier in each bullet:

**Citation-candidate path.** An identifier is a citation candidate when all three hold:
- The bullet contains a backtick-wrapped identifier (e.g., `os.walk`, `New-ScheduledTaskTrigger`, `_log_walk_error`)
- The identifier also appears in the data body
- No `file:line` citation already follows that identifier within the bullet

**Citation-unavailable path.** An identifier triggers the unavailable path when all three hold:
- The bullet contains a backtick-wrapped identifier
- The identifier does NOT appear in the data body — its file is not included in the diff or the identifier is external (e.g., a stdlib symbol, a framework API)
- No `(citation unavailable: <reason>)` marker already follows that identifier within the bullet

Both paths fire independently per identifier. A bullet can contain both citable and unciteable identifiers.

## Procedure

**For citation candidates:**
1. For each citation candidate, search the data body for the identifier.
2. Find every occurrence of the identifier in the data body. When the data body uses explicit line numbers (e.g., a code block prefixed with file:line annotations or a diff), use those. When the data body has no line numbers (e.g., a raw pasted dump), use the 1-based line index within the data-body block as `<line>`. Apply the multiple-occurrence policy below to determine which lines to cite.
3. Append the citation in this format immediately after the backtick-wrapped identifier: `` `identifier` (`<file>:<line>`)``. When the bullet contains multiple identifiers, cite each one inline after its owning backtick span. The `<file>` value comes from the data-body block's heading or label (e.g., the filename in a `### file.py` heading, the diff header, or the code block's language tag). When the data body has no file identity at all (a raw paste with no heading or label), use `data-body:<line>`. The examples below illustrate both single-identifier and multi-identifier bullets.

## Multiple occurrences

When the identifier appears one or more times across the data body:

- 1–3 occurrences → cite all of them: `(file_a.py:42, file_a.py:88, file_b.ps1:12)`
- 4 or more → cite the first and last with `…` between: `(file_a.py:42, …, file_b.ps1:200)`

## Examples

Before:
```
- uses `os.walk` with `_log_walk_error` — `_log_walk_error` matches the exact signature stdlib calls.
```

After (2 occurrences: definition plus one call site):
```
- uses `os.walk` (`sweep_empty_dirs.py:23`) with `_log_walk_error` (`sweep_empty_dirs.py:23, sweep_empty_dirs.py:33`) — `_log_walk_error` matches the exact signature stdlib calls.
```

Before:
```
- `Get-ScheduledTask`, `New-ScheduledTaskTrigger`, `New-ScheduledTaskAction`, `Register-ScheduledTask`, `Unregister-ScheduledTask` — verify each call's parameter shape.
```

After (one occurrence per cmdlet):
```
- `Get-ScheduledTask` (`Install-SweepEmptyDirs.ps1:248`), `New-ScheduledTaskTrigger` (`Install-SweepEmptyDirs.ps1:297`), `New-ScheduledTaskAction` (`Install-SweepEmptyDirs.ps1:296`), `Register-ScheduledTask` (`Install-SweepEmptyDirs.ps1:300`), `Unregister-ScheduledTask` (`Install-SweepEmptyDirs.ps1:267`) — verify each call's parameter shape.
```

## What stays put

When the identifier is a generic concept (e.g., `if version`, `if FLAG`) rather than a real symbol in the data body, the bullet stays as-written. Citations apply to actual identifiers, not category-shaped placeholders.

When the identifier sits in a file the data body doesn't include (e.g., the bullet mentions `os.walk` but the diff doesn't define it), the citation skips that identifier. The skipped citation MUST emit BOTH:

1. An inline gap marker adjacent to the identifier: `(citation unavailable: <reason>)` — so the bullet is not visually identical to a successful citation when read in isolation.
2. A gap note via the paste-mode or file-path-mode gap-report mechanism that [`output-contract.md`](output-contract.md) defines for the active emission mode.

Both records are required by the [no silent action](output-contract.md#disposition-invariants) invariant: the reader of the bullet alone must see the gap, and the reader of the output as a whole must see the gap.

## Disposition reporting

Every outcome emits an action note via the mechanism that [`output-contract.md`](output-contract.md) defines. When citations were added: `> Gap: Citations added — <N> identifier(s) cited at file:line.` When no citation candidates exist: `> Gap: Citation-depth verified — no uncited identifiers found.` When a citation was unavailable: `> Gap: Citation unavailable for "<identifier>" — <reason>.` Silent pass is forbidden — see the [no silent action](output-contract.md#disposition-invariants) invariant.
