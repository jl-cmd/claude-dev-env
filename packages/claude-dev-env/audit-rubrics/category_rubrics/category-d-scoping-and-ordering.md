# Category D — Variable scoping, ordering, and unbound references

**What this category audits:** closures, variable hoisting, declaration order, late binding in loops, name shadowing, conditional definition, mutable defaults — anything that can cause a name to bind to the wrong value (or to be unbound entirely) at the point of use.

**Examples of Category D findings:**
- A variable is referenced before assignment on one branch of an `if`/`else`.
- A loop closure captures the loop variable by reference where by-value capture is required.
- A name shadows an outer-scope variable the function still relies on.
- A mutable default argument (`def f(x=[])`) accumulates state across calls.
- A module-level import is conditionally executed and the symbol is unbound on some import paths.

**Companion reference:** see `../source-material-section-types.md`.

---

## Sub-bucket decomposition (Category D)

| ID | Axis name | Concrete checks |
|---|---|---|
| D1 | Variable referenced before assignment on a branch | `UnboundLocalError` candidates; partial `try/except` where the target is set only in `try`. |
| D2 | Loop closure capture (by-ref vs by-value) | Lambdas / nested functions in a loop body that close over the loop variable. |
| D3 | Name shadowing of outer-scope symbols | A local name that shadows a builtin, module-level, or class-level symbol still in use. |
| D4 | Conditional definition leaving symbol undefined | `try/except ImportError` blocks; platform-conditional defs without fallbacks. |
| D5 | Mutable default arguments | `def f(x=[])`, `def f(x={})` — bound at definition, shared across calls. |
| D6 | Module-level circular imports / load order | Import-time side effects depending on partial-module state. |
| D7 | Async/sync ordering of side effects | `await` placed where a side effect should have already happened; out-of-order coroutine resolution. |
| D8 | Class-attribute vs instance-attribute confusion | `cls.x` vs `self.x`; attribute defined in `__init__` vs class body. |

---

## Sample prompt

The reusable Variant C template for Category D is in [`../prompts/category-d-scoping-and-ordering.md`](../prompts/category-d-scoping-and-ordering.md). Inline your artifact under `## Source material` and adapt the sub-bucket bullets to your project's scoping conventions.

For a literal worked example using PR #394, see [`category-a-api-contracts.md`](category-a-api-contracts.md). The Category D–relevant pieces of that diff: D1 (the `try: created = os.path.getctime(…) / except OSError: continue` block — `created` only bound inside `try`, but the `if now - created` is *inside* the try so no UnboundLocalError) and D2 (the `for each_directory_path, _, _ in os.walk(…)` — no closures inside, verified clean).
