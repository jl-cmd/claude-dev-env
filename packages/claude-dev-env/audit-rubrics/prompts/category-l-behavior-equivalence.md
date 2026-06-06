Audit [REPO/ARTIFACT] [TARGET_ID] for **Category L only** (behavior-equivalence for refactors). Skip A–K, M–P. Sub-bucket forced-exhaustion mode: Category L is decomposed into 8 sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

[ARTIFACT METADATA — include the BEFORE state of the rewritten function so the agent can compare BEFORE vs AFTER behavior on the same input corpus]

- Title / one-line summary: [TITLE]
- Base ref / SHA (state BEFORE the rewrite): [BASE_SHA]
- Head ref / SHA at audit time (state AFTER the rewrite): [HEAD_SHA]
- Rewritten function(s) (file + line range + symbol name): [REWRITTEN_FUNCTIONS]
- BEFORE state of each rewritten function (the literal pre-rewrite implementation): [BEFORE_SNIPPETS]
- AFTER state of each rewritten function (the literal post-rewrite implementation): [AFTER_SNIPPETS]
- KNOWN_GOOD_INPUTS — the corpus of canonical inputs the BEFORE implementation accepted: [KNOWN_GOOD_INPUTS_TABLE]
- Stated intent of the rewrite (what change the author claimed to land): [INTENT]

ID prefix: `find`.

[ONE-PARAGRAPH FRAME: describe what the rewrite changed in plain English, including which implementation tag (regex / tokenize / str-method / library-call) the BEFORE state used and which the AFTER state uses. State the equivalence claim: the AFTER state accepts every input the BEFORE state accepted and rejects every input the BEFORE state rejected. State the audit goal: identify any input from the BEFORE-accepted corpus that the AFTER state misclassifies, OR any new input class that the rewrite accepts but the BEFORE state rejected.]

## Source material ([N] files/sections, all lines in scope)

[INLINE the BEFORE state and AFTER state of each rewritten function side-by-side. Include the KNOWN_GOOD_INPUTS table the audit will use to drive the equivalence check. For a check function, the table includes every literal input that production code or tests carry across the codebase.]

[ALSO INCLUDE any sibling implementation that exists at the same SHA (Python + PowerShell, regex + tokenize, etc.) so L8 has both sides to compare.]

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**L1. KNOWN_GOOD_INPUTS table presence**
- Does the PR ship a parametric test, table-driven fixture, or sibling-comparison harness enumerating the canonical inputs the BEFORE implementation accepted?
- If yes, does the table cover every input class the BEFORE implementation discriminated on (whitespace variants, prefix shapes, empty inputs, multi-line inputs)?
- Adversarial probes when no table is present: (a) scan the BEFORE implementation for every `startswith` / `re.match` / `in (` literal — each one is an implicit input class that needs a table entry; (b) scan the test corpus for assertions that exercise the BEFORE state's edge cases — these are the table entries the rewrite must continue to pass; (c) scan production code for literal inputs that flow into the function — these are the runtime KNOWN_GOOD_INPUTS the table must include.

**L2. Whitespace / separator variants**
- For every input the BEFORE implementation accepted, does the AFTER implementation also accept the variant with: no space where the BEFORE allowed space, leading whitespace, trailing whitespace, multiple internal spaces, tab vs single space, CRLF vs LF?
- Adversarial probes: (a) construct inputs identical to KNOWN_GOOD_INPUTS but with the space stripped (`#noqa` vs `# noqa`) — does the AFTER state still accept? (b) construct inputs with trailing whitespace and CRLF — does the AFTER state strip them the same way the BEFORE state did? (c) construct inputs with a tab where the BEFORE allowed a space — does the AFTER state's tokenizer / regex treat them identically?

**L3. Adjacent-form regressions**
- Does the AFTER implementation use a looser pattern than the BEFORE (e.g., `startswith("## Problem")` where the BEFORE used `re.match(r"^## Problem\b")`)? A loose pattern accepts inputs the original rejected.
- Does the AFTER implementation use a tighter pattern than the BEFORE (e.g., `re.match(r"^# noqa\b")` where the BEFORE used `startswith("# noqa")`)? A tight pattern rejects inputs the original accepted.
- Adversarial probes: (a) construct inputs that satisfy the AFTER pattern but NOT the BEFORE — these are inputs the rewrite silently accepted; (b) construct inputs that satisfy the BEFORE pattern but NOT the AFTER — these are inputs the rewrite silently rejected; (c) walk the BEFORE pattern's anchors (`^`, `\b`, `\s`) and the AFTER pattern's anchors — does every BEFORE anchor have a semantic equivalent in the AFTER pattern?

**L4. Empty / boundary inputs**
- For empty string, single character, single-newline, single-line, EOF-without-newline — does the AFTER implementation produce the same accept/reject decision as the BEFORE?
- Adversarial probes: (a) does the AFTER tokenizer raise on an empty input where the BEFORE returned False? (b) does the AFTER regex match on a single-newline input where the BEFORE skipped? (c) does the AFTER state handle the EOF-without-newline edge that the BEFORE state's `splitlines()` call did?

**L5. Invariant preservation**
- Does the BEFORE implementation enforce an invariant (early-exit on first match, idempotence under repeated invocation, stable iteration order, ordering of returned items)? Does the AFTER preserve each invariant?
- Adversarial probes: (a) call AFTER twice on the same input — is the second call's output identical to the first? (b) for a function that walks a list of patterns and returns on first match, does AFTER terminate at the same index BEFORE did, or does it walk past and return the LAST match? (c) for a function whose return type is `list[X]`, is the AFTER's ordering stable across runs?

**L6. Implementation-tag parity**
- The BEFORE implementation used [TAG_BEFORE] (regex / tokenize / str-method / library). The AFTER uses [TAG_AFTER]. For each input shape the BEFORE-tag accepted (e.g., a regex pattern accepted inline `#!` because the `re.MULTILINE` flag matched at any line start), does the AFTER-tag accept the same shape via a different mechanism?
- Adversarial probes: (a) enumerate the BEFORE-tag's capabilities that the AFTER-tag does not natively have (e.g., regex `\b` boundaries vs tokenize stream events) — has the AFTER implementation added compensating logic? (b) enumerate the AFTER-tag's capabilities that the BEFORE-tag did not have — are any of them silently expanding the accept set? (c) construct an input shape that the BEFORE-tag rejected only because of its tag's limitations — does the AFTER accept now and is that intentional?

**L7. Skipped-category exhaustion**
- Inputs the BEFORE explicitly skipped — shebang on line 1 only, exempt markers without trailing prose, free-form `# type:` directives carrying a trailing justification — does the AFTER state continue to skip them?
- Adversarial probes: (a) does the AFTER state's skip-list match the BEFORE state's skip-list literally? (b) for each skip rule, construct an input the BEFORE skipped — does the AFTER also skip? (c) for each skip rule, construct an input one character off from the skip pattern — does the AFTER fall through to the main check or also skip?

**L8. Sibling-implementation comparison**
- If a parallel implementation exists in another language or paradigm (Python + PowerShell hook, regex + tokenize, JavaScript + Go), does the AFTER implementation produce the same accept/reject decisions as the sibling for shared inputs?
- Adversarial probes: (a) take the sibling's test corpus, run each input through the AFTER implementation, compare results — any disagreement is a finding; (b) walk the sibling's decision tree branch by branch — does the AFTER implementation have an equivalent branch for each; (c) check for divergent skip-lists between the two implementations.

## Cross-bucket questions to answer at the end

Q1: Across all 8 sub-buckets, is there a single input class that the BEFORE state accepted but the AFTER rejects (or BEFORE rejected but AFTER accepts)? Cite the input literal and the file:line where the BEFORE and AFTER implementations diverge.

Q2: What's the worst behavior-equivalence break introduced by the rewrite? Evaluate by (a) whether the missed input class appears in production code at the audit SHA, (b) whether the change silently breaks an exemption rather than blocks; (c) whether a test would have caught it. Decide P1 vs P2 explicitly.

Q3: Which input class is most likely to drift between the AFTER state and the next refactor? Identify the input shape with the loosest pattern in the AFTER implementation — that's where the next behavior-equivalence break will happen.

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket L1-L8, produce Shape A or Shape B (with ≥3 probes). Cross-bucket Q1-Q3 answers after the per-sub-bucket walk. Adversarial second pass: "assume your first pass missed at least 3 input classes where the BEFORE and AFTER implementations disagree — find them." Open Questions section for ambiguities. Read-only. No edits, no commits.

---

# Worked example: jl-cmd/claude-code-config PR #479

Audit jl-cmd/claude-code-config PR #479 for **Category L only** (behavior-equivalence for refactors). Skip A–K, M, N. Sub-bucket forced-exhaustion mode: Category L is decomposed into 8 sub-buckets below.

PR: refactor(hooks): tokenize-based exempt-marker recognition for the no-new-comments gate
Base SHA: (the commit before the tokenize-based rewrite landed)
Head SHA at audit time: (the commit that landed the rewrite)
ID prefix: `find`.

The rewrite changed `_is_exempt_python_comment` from a normalization-based check (it ran `comment_string[1:].lstrip()` to strip the leading `#` and surrounding whitespace, then tested the body against the exempt-marker set) to a tokenize-based recognizer that tests each raw `tokenize.COMMENT` token string against `startswith("# noqa")`. The wider hook structure was left unchanged. The audit goal: identify any input shape the normalization-based BEFORE implementation accepted that the tokenize-based AFTER implementation now misclassifies as a non-exempt comment, OR any input the BEFORE rejected that the AFTER now accepts.

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**L1. KNOWN_GOOD_INPUTS table presence**
- The PR ships `test_code_rules_enforcer_exempt_marker_chained.py` with 14 parametric inputs covering `# noqa`, `# pylint:`, `# pragma:`, `# type:`, `# TODO`, `# FIXME`, shebang at line 1, and a chained-comment variant. The table does NOT include the no-space variant `#noqa` — this is the first L1 gap.
- Adversarial probes: scan the BEFORE implementation for the literal `"# noqa"` — production files at the base SHA carry `#noqa: F401` (no space) on at least three import lines. These are KNOWN_GOOD_INPUTS the table is missing.

**L2. Whitespace / separator variants**
- The BEFORE state stripped the leading `#` and surrounding whitespace from the comment text, then tested the body against the exempt-marker set — both `# noqa: F401` and `#noqa: F401` reduce to the body `noqa: F401`, which the set contains, so the BEFORE accepts both. The tokenize-based AFTER tests each raw `tokenize.COMMENT` token string against `startswith("# noqa")`, which matches only when a space separates `#` from `noqa`; `#noqa: F401` fails the prefix check. The AFTER therefore drops `#noqa` while the BEFORE accepts it — a behavior regression on the no-space axis.
- Adversarial probe: construct `#noqa: F401` and trace through both. The BEFORE's strip-`#`-and-whitespace step yields body `noqa: F401`, which IS in the exempt-marker set, so the BEFORE returns True. The AFTER's `startswith("# noqa")` against the raw token `"#noqa: F401"` returns False (no space separating `#` from `noqa`) — the AFTER returns False. L2 detects a dropped accept on the no-space variant.
- Per Category L's stated equivalence rule, a dropped accept is a regression: an exempt marker the BEFORE recognizes falls through to the main check under the AFTER, so the no-new-comments gate blocks writes carrying `#noqa: F401` that the BEFORE passed. Flag it P1 because the regression silently re-enables blocking on inputs production code carries.
- The CRLF / tab variants pass through the AFTER tokenizer identically.

**L3. Adjacent-form regressions**
- The BEFORE pattern `startswith("# noqa")` is a 6-character prefix check. The AFTER's tokenize-based check strips `#` and surrounding whitespace, then tests the body against the exempt-marker set. The AFTER's pattern is therefore looser on the leading whitespace axis (accepts `#  noqa` and `# noqa`) but no looser on the body content. Verified clean.
- Adversarial probe: construct `# noqa-but-not-really: F401` — does the BEFORE startswith accept (yes, prefix match) and the AFTER's token-body check also accept (yes, the body starts with `noqa`)? Both accept; no regression.

**L4. Empty / boundary inputs**
- Empty input: BEFORE's `startswith` returns False on empty string. AFTER's `tokenize.COMMENT` token list is empty for an empty source; the iteration body never runs; the function returns False. Equivalent.
- Single character `#`: BEFORE's startswith returns False (length 1 < 6 prefix); AFTER's tokenize emits a COMMENT token with string `"#"`, which the AFTER's strip-and-compare reduces to empty string, which fails the exempt-marker set membership test. Equivalent.

**L5. Invariant preservation**
- BEFORE's chain `startswith("# noqa") or startswith("# pylint:") or ...` short-circuits on first match. AFTER's set-membership lookup is O(1); no iteration order. Both return True on first match. Verified clean.

**L6. Implementation-tag parity**
- BEFORE tag: `str.startswith` chain. AFTER tag: `tokenize.tokenize` + set-membership. The token-based AFTER picks up `# noqa` inside a string literal — wait, does it? The `tokenize.COMMENT` token type fires only for actual comment tokens, not for `#` characters inside string literals. So a string `"foo # noqa bar"` does NOT emit a COMMENT token. BEFORE's `startswith` would not have matched either (the line starts with a string literal). Verified clean.
- Adversarial probe: construct an input where the comment is at end-of-line after a string literal (`x = "foo"  # noqa: F401`). BEFORE's `startswith` operates on `comment.string` (the part after `#`), so it would have accepted. AFTER's tokenize emits a COMMENT token for the same trailing comment. Both accept.

**L7. Skipped-category exhaustion**
- BEFORE skipped: shebang at line 1 column 0, `# type:` with trailing justification. AFTER's skip logic must continue to apply these. The PR ships `_build_comment_token` test fixtures that exercise shebang-at-line-1 and shebang-elsewhere; the AFTER skip-list matches the BEFORE skip-list. Verified clean.

**L8. Sibling-implementation comparison**
- No sibling implementation of exempt-marker recognition exists at this SHA. L8 is verified clean — no parallel implementation.

## Cross-bucket questions to answer at the end

Q1: Yes — there is a single input class that the BEFORE accepted and the AFTER rejects: `#noqa: F401` (no space after the leading `#`). The BEFORE's `_is_exempt_python_comment` strips the leading `#` and surrounding whitespace from the comment text, yielding body `noqa: F401`, which the exempt-marker set contains, so the BEFORE returns True. The AFTER's `startswith("# noqa")` against the raw `tokenize.COMMENT` token `"#noqa: F401"` returns False (the literal prefix `"# noqa"` requires the space separating `#` from `noqa`), so the AFTER returns False. The divergence lives at the AFTER's prefix-only `startswith("# noqa")` check in `code_rules_enforcer.py::_is_exempt_python_comment` against the BEFORE's strip-and-compare step. The same L1 KNOWN_GOOD_INPUTS gap — the no-space variant absent from the table — masks this divergence at audit time, since the rewrite's parametric tests never probe it.

Q2: Worst behavior-equivalence break candidate: the dropped accept for the no-space `#noqa` variant — the BEFORE's strip-`#`-and-whitespace logic reduces both `# noqa: F401` and `#noqa: F401` to the same body `noqa: F401` and accepts both, while the AFTER's `startswith("# noqa")` rejects `#noqa` (without the space separating `#` from `noqa`). Mark this P1 because production code at the audit SHA carries `#noqa: F401` on real import lines, so the regression silently re-enables the no-new-comments gate against writes the BEFORE passed; downgrade to P2 only when no production input carries the no-space variant.

Q3: The next-likely behavior-equivalence break is the `# pylint:` family — the AFTER's set-membership test uses literal strings, but `pylint:` directives can carry comma-separated options that the BEFORE startswith would have accepted unchanged. Future tightening of the AFTER's set lookup could silently reject `pylint: disable=line-too-long,too-many-arguments`.

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket L1-L8, produce Shape A or Shape B (with ≥3 probes). Cross-bucket Q1-Q3 answers after the per-sub-bucket walk. Adversarial second pass: "assume your first pass missed at least 3 input classes where BEFORE and AFTER implementations disagree — find them." Open Questions section for ambiguities. Read-only. No edits, no commits.
