Audit [REPO/ARTIFACT] [TARGET_ID] for **Category G only** (off-by-one, bounds, integer overflow). Skip A–F, H–P. Sub-bucket forced-exhaustion mode: Category G is decomposed into 8 sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

[ARTIFACT METADATA]
- Repository / artifact: [REPO_OR_ARTIFACT]
- Target ID (PR / commit / tag / file set): [TARGET_ID]
- Head SHA / revision: [HEAD_SHA]
- Title or summary: [TITLE]
- Languages / runtimes in scope: [LANGS]

ID prefix: `find`.

## Source material

Inline the artifact under this section (full diff for a PR, full file bodies for a file-set audit, or a representative slice for an oversized artifact). For chunking strategy, file inclusion order, and "all lines in scope" framing, follow the companion chunking guide referenced by the rubric (`../source-material-section-types.md`). When a single artifact exceeds the prompt budget, split into ordered chunks and re-run this prompt per chunk; each chunk must independently satisfy the per-sub-bucket Shape A / Shape B requirement against the lines it contains.

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**G1. Loop bounds**
Scope: every `range(...)`, `while i < n`, `for i in range(len(x)+1)`, manual index counters, generator-driven loops, recursion depth bounds, and any inclusive-vs-exclusive iteration boundary in the artifact.
Required output: at least one Shape A finding citing the off-by-one site, OR exactly one Shape B proof-of-absence with ≥3 adversarial probes (e.g., (a) is there an implicit upper bound an iterator could miss — symlink loops, infinite generators, deep recursion? (b) does an empty-collection edge case skip the loop body cleanly? (c) does a manual counter that runs alongside the iterator drift by one when the underlying collection mutates mid-loop?).

**G2. Slice / substring indices**
Scope: every `s[i:j]`, `arr[-n:]`, `split(...)[i]`, character-level indexing, regex match groups treated as substrings, and any computed slice endpoint that could equal `len(x) + 1` or a negative index that clamps unexpectedly.
Required output: Shape A citing the bad slice, OR Shape B with ≥3 adversarial probes (e.g., (a) does any consumer downstream apply a length-dependent truncation? (b) does a path-splitting helper underflow when its input is exactly the root? (c) can a regex group index be `0` for a non-matching capture and still be sliced into?).

**G3. Array / list indexing with computed offsets**
Scope: every `arr[i + offset]`, `dict[computed_key]` where the key is numeric, off-the-end probes (`arr[len(arr)]`), iterator advancement that returns a sentinel the next call dereferences, and PowerShell `$collection[$index]` with computed `$index`.
Required output: Shape A citing the index site, OR Shape B with ≥3 adversarial probes (e.g., (a) can a lookup return `$null` / `None` that the next access dereferences? (b) does an argv-style list ever get indexed past its known length? (c) does a `foreach` element receive a `$null` member from an empty collection?).

**G4. Integer arithmetic overflow**
Scope: 32-bit vs 64-bit assumptions; PowerShell `[int]` overflow at 2^31; `time.time() * 1000` precision loss; multiplication that crosses platform `int` ceilings; counters seeded from user input; ticks / nanoseconds / milliseconds conversions; cross-language defaults that share a magnitude but not a source of truth.
Required output: Shape A citing the overflow site or the duplicated-default drift hazard, OR Shape B with ≥3 adversarial probes (e.g., (a) what happens at `2^31 - 1` and `2^31` for each `[int]`-typed parameter? (b) is `0` accepted as a degenerate value that produces a busy loop or a zero-interval scheduler entry? (c) are equivalent constants declared in two languages without a shared source of truth — and does drift on one side go undetected?).

**G5. Floating-point comparison**
Scope: every `==` / `!=` / `>=` / `<=` between floats; iterative accumulators where epsilon noise compounds; `0.1 + 0.2 != 0.3` patterns; mixed int-float comparison; filesystem-resolution rounding (FAT32 = 2s, NTFS = 100ns, ext4 = ns) interacting with sub-second thresholds.
Required output: Shape A citing the float-equality or epsilon-free comparison, OR Shape B with ≥3 adversarial probes (e.g., (a) is the comparison `==` vs `>=` / `<=` — and does the boundary semantics matter? (b) does sub-second filesystem-resolution rounding on one platform produce stale-equality results that another platform avoids? (c) is the float subtraction monotonic under wall-clock adjustment, or could it produce a negative result that flips the comparison direction?).

**G6. Date / time arithmetic**
Scope: timezone math; DST transitions; leap seconds; `now - then >= threshold` precision; `time.time()` (wall-clock) vs `time.monotonic()` / `time.perf_counter()` selection; Unix epoch vs Windows FILETIME (100ns ticks since 1601); `[DateTime]` cast on strings without timezone suffix; cross-language datetime contracts.
Required output: Shape A citing the timezone-naive arithmetic or the wall-clock-vs-monotonic mismatch, OR Shape B with ≥3 adversarial probes (e.g., (a) is the threshold wide enough to absorb worst-case NTP slew (≤128ms typical) without flipping the comparison? (b) does a cross-language string-based datetime contract silently discard timezone information? (c) does the platform-dependent meaning of "ctime" (creation time on Windows, inode-change time on POSIX) match the test's assumption?).

**G7. Unicode codepoint vs byte length**
Scope: `len()` semantics (Python = codepoints, Go = bytes, JS = UTF-16 code units); UTF-8 encoded byte-length truncation that splits mid-codepoint; surrogate pairs; BMP vs non-BMP characters; argv encoding across `subprocess.run` / `CreateProcessW` / `execve`.
Required output: Shape A citing the codepoint/byte mismatch, OR Shape B with ≥3 adversarial probes (e.g., (a) does any consumer apply a byte-length cap that could split a UTF-8 codepoint? (b) does a directory walker decode names as raw bytes (POSIX `surrogateescape`) vs UTF-16 (Windows) in a way that affects which entries are seen? (c) do non-BMP characters round-trip correctly through subprocess argv encoding?).

**G8. Threshold and age comparisons**
Scope: every `>=` vs `>` boundary on age / size / count thresholds; inclusive-vs-exclusive semantics; docstring/help-text/code disagreement on boundary direction; tests that exercise comfortably-above and comfortably-below cases but skip the exact-boundary case; user-facing copy that uses one symbol while the code uses another.
Required output: Shape A citing the boundary-semantics conflict (code site + docstring/help-text/UI site), OR Shape B with ≥3 adversarial probes (e.g., (a) is the inclusive-vs-exclusive choice safe under sub-second filesystem-resolution rounding that could land a "fresh" value at exactly the boundary? (b) does any test seed a value at exactly the threshold to exercise the boundary? (c) do user-facing strings use `≥` / `>` symbols faithful to the code, and does the docstring agree?).

## Cross-bucket questions to answer at the end

Q1: Are there boundary hazards that span two sub-buckets — e.g., a G6 timestamp imprecision that combines with a G8 inclusive comparison to flip a borderline case, or a G4 overflow that interacts with a G1 loop bound to produce an infinite iteration? Cite the line pair.
Q2: What's the worst boundary hazard introduced by this artifact? Cite `[file]:[line]` (and any companion file:line if the hazard is multi-site).
Q3: Which threshold or constant is most fragile to a future change in input scale (e.g., shifting from minute-scale ages to second-scale, or from 2-minute defaults to 2-millisecond defaults)? Identify the line(s) where the unit assumption is hardcoded.

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket G1-G8, produce Shape A or Shape B (with at least 3 probes). Each Shape A finding must cite the file:line where the boundary or numeric type fails. Cross-bucket Q1-Q3 answers after the per-sub-bucket walk. Report every finding you reach, including uncertain ones and P2 ones, and give each finding a confidence level (high, medium, or low) beside its severity so a later pass can rank and filter them. Open Questions section for ambiguities. Read-only. No edits, no commits.
