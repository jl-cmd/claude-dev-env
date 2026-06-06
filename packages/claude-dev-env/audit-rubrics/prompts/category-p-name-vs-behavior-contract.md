Audit [REPO/ARTIFACT] [TARGET_ID] for **Category P only** (name / regex / word-list vs behavior-contract precision). Skip A–O. Sub-bucket forced-exhaustion mode: Category P is decomposed into 7 sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

[ARTIFACT METADATA — every newly-added or renamed identifier plus the body code that implements its contract]

- Title / one-line summary: [TITLE]
- Head ref / SHA at audit time: [HEAD_SHA]
- New / renamed boolean flags (file:line + identifier + lifecycle sites): [NEW_FLAGS]
- New / renamed predicate helpers (file:line + identifier + body + return contract): [NEW_PREDICATES]
- New / renamed regex constants (file:line + identifier + regex source + anchors): [NEW_REGEXES]
- New / renamed word-lists or replacement tables (file:line + identifier + entries): [NEW_LISTS]
- New / renamed helper-function names (file:line + identifier + signature + return): [NEW_HELPERS]
- Stated intent of each new identifier: [INTENT]

ID prefix: `find`.

[ONE-PARAGRAPH FRAME: list every fresh identifier introduced by the diff. State the audit goal: for each identifier, verify the body's behavior matches the contract the name asserts — not broader, not narrower.]

## Source material ([N] files/sections, all lines in scope)

[INLINE each fresh identifier in context — the constant declaration with the value, the function signature with the body, the flag with every assignment / reset site, the regex source with surrounding usage.]

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**P1. Boolean / flag names assert state the body keeps**
- For every new `is_*` / `has_*` / `was_*` / `should_*` flag, trace the body. Every set site must be paired with a reset site that fires when the named condition becomes false.
- Adversarial probes: (a) grep every assignment to the flag — count set-true vs set-false; (b) for AST-driven flags, walk the visit method and confirm scope-exit semantics (def visited → flag set; dedent / function-exit → flag reset); (c) construct an input where the flag should be false after a prior true region — does the code agree.

**P2. Predicate-name breadth matches body coverage**
- For every new `_is_*` / `_has_*` / `_can_*` predicate function, list the body's `return True` branches. The named predicate must hold on the union of those branches and nothing else.
- Adversarial probes: (a) construct an input that satisfies the name but returns False — that is a P2 narrowness finding; (b) construct an input that does not satisfy the name but returns True — that is a P2 breadth finding; (c) check neighbor predicates — is the body's actual contract the responsibility of a different helper.

**P3. Regex name vs regex shape** ⭐ canonical P case
- For every new `*_PATTERN` / `*_REGEX` constant, read the regex source. Confirm the anchors (`^`, `$`, `\b`, lookarounds) match the name's promised shape. `FILE_PATH_PATTERN` implies path shape; the regex must include path-shape anchors (slash count, segment shape, length bounds) enough to reject non-path inputs.
- Adversarial probes: (a) construct 3 non-matching inputs that the regex's name says it should reject — does the regex reject them; (b) construct 3 inputs that satisfy the regex but violate the name — those are P3 findings; (c) check sibling regexes in the same module — is the new regex anchored consistently with them.

**P4. Helper-function name vs return contract**
- For every new helper function, compare the name to the return shape AND the matching semantics. `_split_module_stem_prefix` should split on a stem-prefix boundary; if the returned prefix substring-matches unrelated stems, the matching semantics diverge from the name.
- Adversarial probes: (a) feed the helper an input class the name names — is the return what the name implies; (b) feed it an input the name excludes — does the helper still produce output; (c) check downstream callers — do they consume the return on the contract the name implies.

**P5. Word-list / replacement-table precision**
- For every new reference list, walk each entry. Every entry must satisfy the named class. A list named `HEAVY_WORDS_TO_REPLACE` may not contain words that are ordinary in legitimate user inputs.
- Adversarial probes: (a) for each entry, construct 3 legitimate-looking inputs containing it — would the gate fire on legitimate writing; (b) check entry density against the named class — is the list curated or kitchen-sink; (c) propose 3 entries that fit the named class better and 3 entries that do not fit — does the list match the proposed-good or the proposed-bad set.

**P6. Class / module name vs scope**
- For every new class or module, list the responsibilities (exported symbols, dispatched calls). Confirm each fits the named scope.
- Adversarial probes: (a) list exported symbols and ask whether each matches the named scope; (b) check imports — does the module pull in unrelated subsystems; (c) check call-graph centrality — does the class own one thing or many.

**P7. Reverse: name understates what the body does**
- For every new identifier, ask whether the body produces effects the name does not promise (side effects, more return values, broader input acceptance, hidden state mutation). A future caller relying on the narrow name will be surprised.
- Adversarial probes: (a) walk side effects (writes, network calls, global mutation) — are they named in the contract; (b) walk return tuples / objects — is every component named; (c) walk input acceptance — does the helper silently accept inputs outside its named class.

## Cross-bucket questions to answer at the end

Q1: Across all 7 sub-buckets, which identifier's name-vs-body gap is most likely to cause false positives in a production gate? Cite the identifier and the input class that trips it.

Q2: Which identifier is at highest risk of being relied on by a future caller based on the name alone, with the broader / narrower body causing a regression? Cite the identifier and the assumed contract.

Q3: Which identifier most clearly shows the body should be renamed (the name is honest about intent and the body is wrong) vs the name should be tightened (the body is the contract and the name overpromises)? Cite the identifier and the recommended direction.

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket P1-P7, produce Shape A or Shape B (with ≥3 probes). Each Shape A finding must cite (a) the identifier file:line, (b) one concrete input that shows the name-vs-body gap, and (c) the recommended fix direction (rename vs body-tighten). Cross-bucket Q1-Q3 answers after the per-sub-bucket walk. Adversarial second pass: "assume your first pass missed at least 3 identifiers whose names overstate what the body actually does — find them." Open Questions section for ambiguities. Read-only. No edits, no commits.

---

# Worked example: jl-cmd/claude-code-config PR #508

Audit jl-cmd/claude-code-config PR #508 for **Category P only** (name / regex / word-list vs behavior-contract precision). Skip A-O.

PR #508 ships the plain-language blocker hook. Two fresh identifiers in `plain_language_blocker_constants.py` show the canonical P shapes:

- `FILE_PATH_PATTERN` (line 286) — a regex of shape `(\S+/\S+)` named for file paths but unanchored. Probes: `client/server`, `and/or`, `TCP/IP`, `lookup/replace` all match and are silently exempted from the plain-language scan even though none is a file path. **P3 finding.**
- `HARD_DENY_REPLACEMENT_TERMS` (line 247) — a hard-deny replacement-by-term list named for ban-worthy heavy words but containing `command`, `address`, `function`, `subject`, `same`, `such`, `said`, `it is`, `there is`, `however`, `forward`. Each entry trips on ordinary technical English (`run the command`, `the address bar`, `validate the function`). **P5 finding.**

Expected output: two P-class findings with cited file:line of the constant, cited example inputs (`client/server`, `run the command`), and recommended direction (anchor the regex to need repo-relative paths; curate the deny-list to drop dev-domain false positives).
