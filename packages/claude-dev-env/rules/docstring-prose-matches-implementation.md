# Docstring Prose Matches Implementation

**When this applies:** Any Write or Edit to a public function, method, class, or module whose docstring prose makes an enumerable claim about behavior — a list of inputs the code handles, the conditions it treats as a match, the cases it skips, or the order of its steps. It applies equally to a skill's companion `SKILL.md` (or any sibling `.md`) that describes a producer the skill's `scripts/` carry out: a doc sentence that claims a produced artifact's ordering or content is the prose this rule governs, and it tracks the producer function's own docstring and body.

## Rule

When a docstring enumerates the behaviors a body applies, the enumeration covers every behavior the body applies. A reader trusts the list to be complete: an item the code applies but the prose omits is a silent gap that misleads every future reader and reviewer.

The gate validator `check_docstring_args_match_signature` covers the `Args:` section parameter names. Three more gate validators each cover one deterministic slice of the free-form prose. `check_docstring_fallback_branch_coverage` covers a summary that scopes a fallback to a single condition (`only when`, `falls back to ... when`) while the body routes to that same fallback call from two or more distinct early-return guards. `check_class_docstring_names_public_methods` covers a class whose docstring is a single summary line while the class exposes two or more public methods whose names the summary never spells out — the drift where a one-line class summary keeps naming its first feature after the class grows a second public entry point. `check_docstring_no_consumer_claim` covers a producer docstring asserting that no consumer reads its output yet (`producer-only artifact`, `no submission-run consumer reads it yet`) — a transitional claim that drifts the moment a reader lands and contradicts any companion `SKILL.md` that documents the consumer; this is the deterministic slice of the O8 companion-doc producer/consumer drift below. The remaining free-form prose — `"a field counts as read when ..."`, `"resolves to shared temp only"`, `"strip ceremony, then drop blockquotes"`, and module-level responsibility paragraphs — has no signature, method roster, or single structural shape to compare against, so the gate cannot catch its drift. This rule is the judgment standard for that prose; the audit lane below is the enforcement for everything outside the four gated slices.

## What to check before you write the docstring

Read the body and the docstring side by side:

- **Read-source / match-source unions.** A body that computes `read_names = a | b | c` (or any union of "what counts") names each union member in the prose enumeration. A union member the code applies but the prose omits is a gap.
- **Suppressor / skip lists.** A body with several early returns that suppress the check names each suppressor in the prose.
- **Shared fallback routes.** A summary that scopes a fallback call to one condition names every condition that reaches that call. When the body routes to the same fallback from two or more early-return guards (`if a is None: fallback(); return` and `if random() < p: fallback(); return`), the prose enumerates both guards. The `check_docstring_fallback_branch_coverage` gate blocks the single-condition form of this drift at Write/Edit time.
- **Step order.** A docstring that says `A then B then C` matches the call order in the body. A step enumeration that names the body's linear steps also names every corrective step the body guards inside an `if`/`elif` branch (`if not await cancel_and_reinitiate_update(...): return`). The `check_docstring_step_enumeration_dispatch_coverage` gate blocks the branch-guarded-dispatch form of this drift — a step-enumeration docstring that omits a two-or-more-token dispatch step the body guards inside a branch — at Write/Edit time.
- **Predicate breadth.** A boolean helper whose prose promises a narrow check accepts only the inputs the prose names — no broader input class the name and prose do not mention.
- **Companion-doc ordering and content claims.** A `SKILL.md` (or sibling `.md`) sentence that names a produced artifact and claims its order (`sorted`, `alphabetical`, `in sorted order`) or its content (`the at-risk names`, `just the current set`) matches the producer function's docstring and body for that same artifact. A producer that builds the artifact by merging stored names with new names and appending — preserving file order, not re-sorting the union — leaves a doc that still says `sorted` drifted on both counts: the order claim is wrong, and the content claim hides the merged-in prior entries. When the producer's ordering or union changes, the same change updates the companion doc. The two move together in one commit, even when the producer edit does not touch the `.md` file.

When the body changes the set of behaviors it applies, the same edit updates the prose enumeration. The two move together in one commit.

## Worked example

A `@dataclass` dead-field check builds its set of "field counts as read" sources by union:

```python
read_names = (
    attribute_read_names
    | dynamic_literal_names
    | _match_pattern_attribute_names(tree)
    | _exported_names(tree)
)
```

A docstring that enumerates "attribute read, augmented-assignment target, class-pattern keyword, literal `getattr`/`attrgetter`" but omits the `__all__` source (`_exported_names`) is drifted: a field whose name appears in `__all__` is treated as read, and the prose hides that. The fix adds the missing source to the enumeration so the list matches the union.

## Enforcement (audit lane)

This drift class is sub-bucket **O6** in `packages/claude-dev-env/audit-rubrics/category_rubrics/category-o-docstring-vs-impl-drift.md` (free-form `Note:` / `Returns:` / responsibility-list claims). The audit teammate lists every prose enumeration in a changed docstring and verifies each item against the body, and lists every union member / suppressor / step in the body and verifies each appears in the prose. A union member or suppressor in the body that the prose omits is an O6 finding. The single-condition shared-fallback shape of this drift is gated deterministically by `check_docstring_fallback_branch_coverage` (`packages/claude-dev-env/hooks/blocking/code_rules_docstrings.py`); the audit lane covers every O6 shape the gate cannot match.

When a changed PR touches a producer function whose ordering or union shifts, the O8 audit lane also reads that skill's companion `SKILL.md` and sibling `.md` docs for any sentence naming the same produced artifact. A doc sentence that claims the artifact is `sorted` or holds `just the at-risk names` while the producer merges prior names and appends without re-sorting is an O8 finding, even when the PR diff never touched the `.md` file — the behavior change orphaned the doc claim.

## Why

A docstring enumeration earns its place by being trustworthy. A complete list lets a reader reason about the function without scanning the body; a list missing one item is worse than no list, because it asserts completeness it does not have. Naming this standard makes the gap a first-class finding at write time and at audit, rather than a surprise a reader hits months later.
