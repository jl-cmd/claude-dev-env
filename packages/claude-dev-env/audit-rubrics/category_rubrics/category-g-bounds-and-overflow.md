# Category G — Off-by-one, bounds, integer overflow

**What this category audits:** loop bounds, slice indices, signed/unsigned overflow, floating-point comparison, time arithmetic, byte-vs-codepoint length confusion — anything where the boundary or the numeric type is wrong by one or by a factor.

**Examples of Category G findings:**
- `range(len(items) + 1)` walks one element past the end of the array.
- A slice `s[:n+1]` where the intent was `s[:n]`.
- Timestamp arithmetic uses 32-bit integer math on a 64-bit value.
- `==` between floats where epsilon comparison is required.
- `len(string)` used for byte length when the consumer expects codepoints (or vice versa).

**Companion reference:** see `../source-material-section-types.md`.

---

## Sub-bucket decomposition (Category G)

| ID | Axis name | Concrete checks |
|---|---|---|
| G1 | Loop bounds | `range(...)`, `while i < n`, `for i in range(len(x)+1)`; off-by-one inclusive vs exclusive. |
| G2 | Slice / substring indices | `s[i:j]` where `j` can be `len(s)+1`; negative indices clamping unexpectedly. |
| G3 | Array / list indexing with computed offsets | `arr[i + offset]` where `offset` can push past the boundary. |
| G4 | Integer arithmetic overflow | 32-bit vs 64-bit assumptions; PowerShell `[int]` overflow at 2^31; `time.time() * 1000` precision. |
| G5 | Floating-point comparison | `a == b` for floats; `0.1 + 0.2 != 0.3`; epsilon-free comparisons in iterative loops. |
| G6 | Date / time arithmetic | Timezone math; DST transitions; leap seconds; `now - then >= threshold` precision. |
| G7 | Unicode codepoint vs byte length | `len()` returning codepoints in Python; bytes in Go; UTF-16 code units in JS. |
| G8 | Threshold and age comparisons | `>=` vs `>`; inclusive vs exclusive boundary on age / size / count thresholds. |

---

## Sample prompt

The reusable Variant C template for Category G is in [`../prompts/category-g-bounds-and-overflow.md`](../prompts/category-g-bounds-and-overflow.md). Inline your artifact under `## Source material` and adapt the sub-bucket bullets to your project's numeric domain.

For a literal worked example using PR #394, see [`category-a-api-contracts.md`](category-a-api-contracts.md). Category G walks for that diff:
- G6: `now = time.time()` then `now - created >= min_age_seconds` — float minus float, comparison against int. No DST/timezone concerns since `time.time()` is UTC-based monotonic-ish.
- G8: `>=` boundary at exactly `min_age_seconds` — a directory exactly 120s old is deleted. Likely intended.
- G4: `[int]$AgeSeconds = 120` in PowerShell — well within 32-bit int range, no overflow risk for realistic age values.
