# Category A — API contract verification

**What this category audits:** function signatures, return types, async/await correctness, callback shape compatibility, positional-vs-keyword arg mismatches at call sites, declared-vs-actual return types, and cross-module/cross-language argument shape contracts.

**Examples of Category A findings:**
- A call site passes positional arguments that the callee expects as keyword arguments.
- `await` is missing on a function that returns a coroutine.
- Return type annotated as `bool` while a code path returns `None`.
- A callback handed to `os.walk(onerror=…)` has the wrong arity.
- A PowerShell cmdlet is invoked with a parameter that belongs to a different parameter set.
- A new gate-time validator omits the `all_changed_lines` parameter that peer span-based validators accept, so the dispatcher cannot plumb diff scope through and the check silently over- or under-blocks.
- A new span-based check applies its result cap before honoring `defer_scope_to_caller=True`, while peer checks return all violations in that mode and let the caller cap; this leaves the new sibling stale against the established pattern.
- A call passes `PollingIntervals.resume_check` (a poll interval — how often to re-check) into a `progress_check_timeout` parameter (a timeout — how long to wait). The value's role does not match the parameter's role, so the call type-checks while the behavior is wrong.

**Companion reference:** see `../source-material-section-types.md` for guidance on how to chunk the artifact under audit.

---

## Sub-bucket decomposition (Category A)

Use 5–10 sub-buckets. Each bucket must be **disjoint** from the others and **collectively exhaustive** of the dimension. Numbered with stable IDs (A1, A2, …) so findings can reference the bucket they belong to.

The decomposition that worked best for PR #394 (a Python+PowerShell scheduled-task installer):

| ID | Axis name | Concrete checks |
|---|---|---|
| A1 | Python function signatures vs internal call sites | Parameter count, names, defaults, kw-only barriers; every internal call binds correctly. Is the symbol `async def`? Confirm the exact access path a caller uses: free function vs instance method reached through an object attribute vs import path. A keyword-only parameter with no default is required; omitting it raises `TypeError`. When a call passes a config value as an argument, confirm the value's documented role matches the parameter's role — a poll interval is not a timeout, and a timeout is not a budget. |
| A2 | Python return-type annotation vs every code path | Each function's return annotation is satisfied by every path: explicit `return X`, fall-through, exception-handler exit. The full failure contract is the return value AND every exception raised — trace the body and the docstring `Raises:` for each `raise`, including custom errors. A `-> bool` function that also raises is not fully described by "returns bool". |
| A3 | argparse parser → Namespace contract | Every `add_argument(...)` produces the exact dest name accessed downstream; `type=` matches downstream usage; switches produce bools. |
| A4 | Stdlib callback contracts | `os.walk(onerror=...)` callback shape; `os.path.getctime` / `os.rmdir` argument and exception contracts; `time.sleep` argument types. Catch-site precision: for any claim that code "catches X", confirm the exact catch site and scope — an `except` around only a rollback inside `finally` does not catch the same error raised in the `with` body. |
| A5 | subprocess invocation contract | `subprocess.run` kwargs valid for the targeted Python; `args=[list]` shape; exception propagation under `check=True`. |
| A6 | PowerShell cmdlet parameter sets and binding | `param(...)` with `ParameterSetName=`; `[CmdletBinding(DefaultParameterSetName=…)]` presence; cmdlet parameter combinations valid per Microsoft docs. |
| A7 | Cross-language argv boundary | The `-Argument` string composition → Windows process loader → C-runtime argv parser → Python `sys.argv` → argparse. Trailing-backslash and embedded-space hazards. |
| A8 | Documented API/tool calls vs official API documentation | Every API, MCP tool, SDK method, or CLI command documented in the diff. Look up the official documentation for that API. Verify parameter names, types, and required-ness match the documented call. Make a safe, read-only API call to confirm the documented invocation succeeds. Address any mismatch. |
| A9 | Intra-module sibling-helper API parity | When the diff adds a new check / validator / parser / handler alongside existing sibling checks in the same module, the new one matches the sibling cohort's signature (every parameter peer checks accept), scoping semantics (whole-file vs fragment, diff-line filtering via `all_changed_lines`), and result-shape contract (caps pre-scope vs post-scope, `defer_scope_to_caller` honored, return type). When the new helper omits a sibling-established parameter, runs on a different content surface, or applies the result cap at a different point in the pipeline than its siblings, the audit teammate names this as an A9 finding. |

Adapt these axes for your artifact. For a pure Python codebase, drop A6 and A7 and add (e.g.) "type-stub vs runtime divergence" or "C-extension boundary." For a pure PowerShell codebase, drop A1–A5 and split A6 into "param-set declaration" / "cmdlet invocation" / "type coercion at param boundary."

---

### Documentation as contract: verifying a doc claim about code

When the audited artifact is documentation — a CLAUDE.md, a rule file, a README, a table mapping symbols to behavior — that asserts facts about the codebase, API-contract verification means checking every assertion against the current code, not just confirming the symbol exists and its return type matches. A doc that passes the happy-path contract can still be wrong on any of the seven checks below. Run all seven up front. Checks 1, 2, and 6 are the full-contract sharpening of sub-buckets A1, A2, and A4 applied to a doc claim; checks 3, 4, 5, and 7 are specific to documentation artifacts.

1. **Full failure contract** — the failure signals of a function are its return value AND every exception it raises; trace the body and the docstring `Raises:` for every `raise`. _Example:_ a docs PR says a UI helper "returns `bool`", but it also raises a custom not-found error, and a database writer documented by its return type also raises `ValueError` / `RuntimeError` / a driver error, so "returns bool" understates the contract.
2. **Call shape** — required versus optional parameters (a keyword-only parameter with NO default is required; omitting it raises `TypeError`), sync versus async, and the exact access path (free function versus instance method reached through an object attribute versus import path). _Example:_ a doc presents a helper as a free function, but it is an `async` instance method reached through an object attribute and one keyword-only parameter has no default, so the call example in the doc would raise `TypeError`.
3. **Reuse-first** — before a doc endorses a hand-written snippet, search for a dedicated helper that already does it. _Example:_ a doc endorses hand-composing `normalize(name).lower()` inline while a dedicated `normalize_for_matching()` helper already does exactly that, contradicting the reuse-before-building rule the doc itself states.
4. **Path resolution** — every file or directory path a doc cites resolves from the repository root. _Example:_ a doc cites a bare `snapshots/` directory as if it sat at the repo root, but the tree lives under `subsystem/snapshots/`.
5. **Cross-entry consistency** — scan parallel rows, sections, and table entries for claims that contradict each other. _Example:_ two adjacent table rows map the same subsystem to two different exception base classes.
6. **Catch-site precision** — when a doc claims code "catches X", confirm the exact site and scope of the catch. _Example:_ a doc says a context manager catches a driver error, but the `except` wraps only the rollback inside `finally`, so an error raised in the `with` body propagates uncaught.
7. **Citation freshness** — re-derive every `file:line` claim against the current code; never trust a prior "verified" assertion or wording borrowed from a comment. _Example:_ an attribute name carried over from a review comment names a member the class does not define; the current code exposes it under a different name.

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
