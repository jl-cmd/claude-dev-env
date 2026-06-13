# Docstring Prose Matches Implementation

**When this applies:** Any Write or Edit to a public function, method, class, or module whose docstring prose makes an enumerable claim about behavior — a list of inputs the code handles, the conditions it treats as a match, the cases it skips, or the order of its steps.

## Rule

When a docstring enumerates the behaviors a body applies, the enumeration covers every behavior the body applies. A reader trusts the list to be complete: an item the code applies but the prose omits is a silent gap that misleads every future reader and reviewer.

The gate validator `check_docstring_args_match_signature` covers the `Args:` section parameter names. Free-form prose — `"a field counts as read when ..."`, `"resolves to shared temp only"`, `"strip ceremony, then drop blockquotes"` — has no signature to compare against, so the gate cannot catch its drift. This rule is the judgment standard for that prose. It carries documented-but-pending hook coverage; the audit lane below is the enforcement until a deterministic gate check exists.

## What to check before you write the docstring

Read the body and the docstring side by side:

- **Read-source / match-source unions.** A body that computes `read_names = a | b | c` (or any union of "what counts") names each union member in the prose enumeration. A union member the code applies but the prose omits is a gap.
- **Suppressor / skip lists.** A body with several early returns that suppress the check names each suppressor in the prose.
- **Step order.** A docstring that says `A then B then C` matches the call order in the body.
- **Predicate breadth.** A boolean helper whose prose promises a narrow check accepts only the inputs the prose names — no broader input class the name and prose do not mention.

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

This drift class is sub-bucket **O6** in `packages/claude-dev-env/audit-rubrics/category_rubrics/category-o-docstring-vs-impl-drift.md` (free-form `Note:` / `Returns:` / responsibility-list claims). The audit teammate lists every prose enumeration in a changed docstring and verifies each item against the body, and lists every union member / suppressor / step in the body and verifies each appears in the prose. A union member or suppressor in the body that the prose omits is an O6 finding.

## Why

A docstring enumeration earns its place by being trustworthy. A complete list lets a reader reason about the function without scanning the body; a list missing one item is worse than no list, because it asserts completeness it does not have. Naming this standard makes the gap a first-class finding at write time and at audit, rather than a surprise a reader hits months later.
