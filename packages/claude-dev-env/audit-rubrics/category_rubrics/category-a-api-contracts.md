# Category A — API contract verification

**What this category audits:** function signatures, return types, async/await correctness, callback shape compatibility, positional-vs-keyword arg mismatches at call sites, declared-vs-actual return types, and cross-module/cross-language argument shape contracts.

**Examples of Category A findings:**
- A call site passes positional arguments that the callee expects as keyword arguments.
- `await` is missing on a function that returns a coroutine.
- Return type annotated as `bool` while a code path returns `None`.
- A callback handed to `os.walk(onerror=…)` has the wrong arity.
- A PowerShell cmdlet is invoked with a parameter that belongs to a different parameter set.

**Companion reference:** see `../source-material-section-types.md` for guidance on how to chunk the artifact under audit.

---

## Sub-bucket decomposition (Category A)

Use 5–10 sub-buckets. Each bucket must be **disjoint** from the others and **collectively exhaustive** of the dimension. Numbered with stable IDs (A1, A2, …) so findings can reference the bucket they belong to.

The decomposition that worked best for PR #394 (a Python+PowerShell scheduled-task installer):

| ID | Axis name | Concrete checks |
|---|---|---|
| A1 | Python function signatures vs internal call sites | Parameter count, names, defaults, kw-only barriers; every internal call binds correctly. |
| A2 | Python return-type annotation vs every code path | Each function's return annotation is satisfied by every path: explicit `return X`, fall-through, exception-handler exit. |
| A3 | argparse parser → Namespace contract | Every `add_argument(...)` produces the exact dest name accessed downstream; `type=` matches downstream usage; switches produce bools. |
| A4 | Stdlib callback contracts | `os.walk(onerror=...)` callback shape; `os.path.getctime` / `os.rmdir` argument and exception contracts; `time.sleep` argument types. |
| A5 | subprocess invocation contract | `subprocess.run` kwargs valid for the targeted Python; `args=[list]` shape; exception propagation under `check=True`. |
| A6 | PowerShell cmdlet parameter sets and binding | `param(...)` with `ParameterSetName=`; `[CmdletBinding(DefaultParameterSetName=…)]` presence; cmdlet parameter combinations valid per Microsoft docs. |
| A7 | Cross-language argv boundary | The `-Argument` string composition → Windows process loader → C-runtime argv parser → Python `sys.argv` → argparse. Trailing-backslash and embedded-space hazards. |

Adapt these axes for your artifact. For a pure Python codebase, drop A6 and A7 and add (e.g.) "type-stub vs runtime divergence" or "C-extension boundary." For a pure PowerShell codebase, drop A1–A5 and split A6 into "param-set declaration" / "cmdlet invocation" / "type coercion at param boundary."

---

## Sample prompt

The literal text used in the May 2026 audit experiment is in [`../prompts/category-a-api-contracts.md`](../prompts/category-a-api-contracts.md). It produced 8–10 findings (P0=1–2, P1=2–6, P2=2–5) across two runs. Inline the full diff verbatim — do not ask the agent to fetch it.

---

## What stays verbatim across topics (do not change)

- The opening "Sub-bucket forced-exhaustion mode" sentence
- "REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket"
- "A sub-bucket returning neither is a protocol gap"
- The verbatim adversarial-pass phrasing: `"assume your first pass missed at least 3 P1 [findings] across these [N] sub-buckets — find them"`
- The preamble line format: `Total: N (P0=N, P1=N, P2=N)`
- Source material inlined verbatim, not fetched

## What you fill in

- Dimension and exclusion list (e.g. "Skip B–J")
- 5–10 sub-bucket axes specific to your dimension
- 3–6 concrete checks per sub-bucket
- Cross-bucket Q1–Q3 phrased to your domain
- Verbatim source material inlined

## Calibration parameters

| Knob | Lower | Higher | Effect (from limited experiment data) |
|---|---|---|---|
| Sub-bucket count | 5 | 10 | More buckets = deeper coverage; returns appeared to flatten past ~8 |
| Probes per Shape B | 3 | 5 | More probes = more proof; quality dropped past 5 |
| Adversarial quota | "at least 1" | "at least 5" | A quota of 3 produced the best signal-to-noise; 5+ produced noise findings |
| Cross-bucket questions | 2 | 5 | 3 was sufficient; 5 produced redundant answers |
| Severity tiers | P0/P1/P2 | P0–P4 | Three tiers concentrate reasoning; more tiers fragment it |

## Reproducibility caveat

Run-to-run variance was significant in the experiment. Across two runs, ~5 of ~9 findings were stable; the rest of the long tail varied. To capture the union of findings, run multiple times and merge. A single-run output is a snapshot, not a complete audit. The sample size (n=2 per variant on one PR) is too small to draw firm conclusions; the format is the best of three tested but not proven optimal.
