# Category P — Name / regex / word-list vs behavior-contract precision

**What this category audits:** identifiers and reference data whose label asserts a contract the body does not deliver. The label may be too broad (`is_inside_function` flag set on def but never reset on scope exit), too narrow (`_is_docstring_section_header` matching only terminating headers), or shaped as one thing while behaving as another (`FILE_PATH_PATTERN` regex matching `client/server` because it lacks path-shape anchors; a hard-deny replacement word list containing ordinary technical English).

The label-vs-body gap is its own failure mode independent of behavior-equivalence (L) because nothing was rewritten — the contract is broken at the moment the name is first chosen. The hook-enforced naming rules (J5 abbreviations, J6 vague nouns) ban specific identifiers but say nothing about precision-of-fit between what a name promises and what its body actually does.

**Examples of Category P findings:**
- A flag `is_inside_function` set on `def` and never reset on scope exit — name asserts state the body fails to keep.
- A helper `_split_module_stem_prefix` returning `code_rules` which substring-matches unrelated stems (`code_ruleset.py`) — name asserts the tighter contract; body delivers a looser one.
- A predicate `_is_docstring_section_header` matching only terminating headers — name asserts the general case; body delivers a specific subset.
- A regex `FILE_PATH_PATTERN = r"(\S+/\S+)"` unanchored — name asserts path-shape; body accepts any `word/word`.
- A hard-deny replacement-by-term list including `command`, `address`, `function`, `subject`, `however`, `forward` — list name asserts "banned heavy words"; entries are ordinary technical vocabulary.

**Companion reference:** see `../source-material-section-types.md`.

---

## Binding counterexample protocol

For every regex, brace or token scanner, or word-list the diff adds or edits, build at least three concrete inputs and trace each one through the pattern by hand before you call the pattern clean:

- **One intended match** — an input the pattern must catch.
- **One near-miss** — an input a quick reading would expect to catch, but the contract says the pattern must reject.
- **One structural edge** — an input whose shape stresses the scanner: a destructured parameter, a quoted key, a nested brace, an escaped delimiter.

Walk each input character by character (or token by token) and write down what the pattern returns. A pattern that returns the wrong answer on any of the three inputs is a Category P finding; cite the input that breaks it. The pattern is clean only after all three inputs return the answer the contract promises.

`hooks/blocking/` is the priority surface. Its patterns gate every write, so a pattern that matches too much or too little there fires on real edits across the whole codebase.

Two canonical failures show why the hand trace is binding:

- **Brace scan that reads a parameter as body.** A scanner counts braces from the signature's opening `(` and treats the first balanced close as the end of the function body. A destructured parameter closes a brace inside the signature — `renderRow({ id, label })` in JavaScript, or a `{a, b}` binding in another language — so the scanner marks the body one token too early and reads the parameter list as body code.
- **`\bschema\b` that matches a value reference.** A `\bschema\b` pattern targets a `schema` declaration, yet it also matches `schema` as the value in `{ label: schema }`, where the word is a reference, not the declaration the pattern means to find. A word boundary alone does not tell a declaration from a key or a value.

---

## Sub-bucket decomposition (Category P)

Decomposition is by the **kind of identifier / reference data** whose label is being audited against its body.

| ID | Axis name | Concrete checks |
|---|---|---|
| P1 | Boolean / flag names assert state the body keeps | A `is_*` / `has_*` / `was_*` / `should_*` flag's lifecycle in the body matches what the name promises: set when the named condition becomes true, reset when it becomes false. Flags set once and never reset are P1 findings. |
| P2 | Predicate-name breadth matches body coverage | A `_is_*` / `_has_*` predicate function — the body covers exactly the input class the name names. Bodies matching a narrower subset ("section header" name matching only terminating section headers) or a broader superset ("shared temp resolution" name matching shared temp AND HOME/TMP env-derived paths) are P2 findings. |
| P3 | Regex name vs regex shape | A `*_PATTERN` / `*_REGEX` constant — the regex includes the anchors (^, $, \b, lookarounds) the name implies. An unanchored regex named `FILE_PATH_PATTERN` matching `word/word` is a P3 finding. |
| P4 | Helper-function name vs return contract | A helper-function name (`_split_module_stem_prefix`, `_resolve_*`, `_extract_*`) — the return shape and matching semantics deliver what the name promises. Helpers whose return value's matching surface is looser than the name suggests (a stem-prefix substring-matching unrelated stems) are P4 findings. |
| P5 | Word-list / replacement-table precision | A reference list named for a specific class of inputs (`HARD_DENY_REPLACEMENT_TERMS`, `BANNED_PROMPT_PHRASES`, `VAGUE_ADJECTIVES`) — every entry must satisfy the named class. Entries that are common in legitimate inputs (`command`, `function`, `however` in a list named "heavy words to ban") are P5 findings. |
| P6 | Class / module name vs scope | A class name (`SingleFileParser`) or module name (`enforcer.py`) — the body's responsibility fits the name's named scope. A class that grew responsibilities outside its name is a P6 finding. |
| P7 | Reverse: name understates what the body does | A name that promises a narrow contract while the body delivers a broader effect — future callers may rely on the narrow contract and be surprised. (Symmetric mirror of P2 / P3.) |

---

## Sample prompt

The reusable Variant C template for Category P is in [`../prompts/category-p-name-vs-behavior-contract.md`](../prompts/category-p-name-vs-behavior-contract.md). Inline every newly-added or renamed identifier alongside the body code that implements its contract under `## Source material`.

## Why Category P matters as its own bucket

Category L (behavior-equivalence) audits a rewrite against a prior implementation — it only fires when there is a `before` state to compare. Category P audits a fresh identifier whose label asserts a contract; the bug is that the body never delivered the named contract, even on the first commit. The hook-enforced J5 / J6 naming rules ban specific identifiers (`ctx`, `cfg`, `data`, `result`, `handle_*`) but say nothing about whether the identifier the author chose actually matches the body's reach. P is the bucket that catches a regex named `FILE_PATH_PATTERN` that accepts `TCP/IP`, a hard-deny word list that bans `function` and `address`, and a predicate named for the general case that only handles a subset — at audit time, before the gate ships and starts producing false positives in production.
