---
paths:
  - "**/*.py"
  - "**/*.md"
---

# Docstring Prose Matches Implementation

**When this applies:** Any Write or Edit to a public function, method, class, or module whose docstring prose makes an enumerable claim about behavior — a list of inputs the code handles, the conditions it treats as a match, the cases it skips, or the order of its steps. It applies equally to a skill's companion `SKILL.md` (or any sibling `.md`) that describes a producer the skill's `scripts/` carry out: a doc sentence that claims a produced artifact's ordering or content is the prose this rule governs, and it tracks the producer function's own docstring and body.

## Rule

When a docstring enumerates the behaviors a body applies, the enumeration covers every behavior the body applies. A reader trusts the list to be complete: an item the code applies but the prose omits is a silent gap that misleads every future reader and reviewer.

When the body changes the set of behaviors it applies, the same edit updates the prose enumeration. The two move together in one commit.

## Write-time checks

Read the body and the docstring side by side. Apply each check that matches the prose:

- **Unions / match sources** — every member of a "what counts" union appears in the prose.
- **Suppressors / skip lists** — every early-return suppressor appears in the prose.
- **Step order** — named order matches call order; branch-guarded corrective steps are named too.
- **Shared fallbacks** — every condition that reaches a fallback call is named.
- **Predicate breadth** — the body accepts only the inputs the prose names.
- **Exclusion axis** — an exclusion clause keys on the same axis the body classifies on.
- **Companion docs** — a `SKILL.md` (or sibling) order/content claim matches the producer body.
- **Gate-outcome status flags** — an outcome routed through `break` reads as blocked everywhere, never as a bypass.
- **Returns / Raises / Note claims** — each free-form claim matches the body.

Many deterministic shapes of this drift have Write/Edit gates in `packages/claude-dev-env/hooks/blocking/code_rules_docstrings.py` (and the JS/`.mjs` slices in `code_rules_imports_logging.py`). Free-form rest is judgment.

## Full standard

The full Category O judgment standard — sub-buckets O1–O9, the complete write-time gate inventory, free-form checklists, and worked examples — lives in:

`packages/claude-dev-env/audit-rubrics/category_rubrics/category-o-docstring-vs-impl-drift.md`

## Division of labor

| Surface | Role |
|---|---|
| **This rule** | Always-on write-time policy and the compact checklist above. |
| Category O rubric | Single thick source for the full standard (on demand). |
| Category O prompt | Audit template; points at the rubric for judgment. |
