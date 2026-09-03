Audit [REPO/ARTIFACT] [TARGET_ID] for **Category L only** (behavior-equivalence for refactors). Skip A–K, M–P. Sub-bucket forced-exhaustion mode: Category L is decomposed into 8 sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

When a change touches code that an existing comment describes or is attached to, remove that comment in the same change and carry its meaning through clear names and structure. Leave comments tied to untouched code unchanged. Keep comment cleanup inside the requested task.
Production and tests follow one rule. Changed directive, TODO, FIXME, HACK, XXX, and type-ignore comments are removed rather than added or justified.

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
- Marker-shaped comments are findings when changed; verify whitespace variants against the changed-code rule.

**L3. Adjacent-form regressions**
- Does the AFTER implementation use a looser pattern than the BEFORE (e.g., `startswith("## Problem")` where the BEFORE used `re.match(r"^## Problem\b")`)? A loose pattern accepts inputs the original rejected.
- Marker-shaped comments are findings when changed; verify whitespace variants against the changed-code rule.
- Adversarial probes: (a) construct inputs that satisfy the AFTER pattern but NOT the BEFORE — these are inputs the rewrite silently accepted; (b) construct inputs that satisfy the BEFORE pattern but NOT the AFTER — these are inputs the rewrite silently rejected; (c) walk the BEFORE pattern's anchors (`^`, `\b`, `\s`) and the AFTER pattern's anchors — does every BEFORE anchor have a semantic equivalent in the AFTER pattern?

**L4. Empty / boundary inputs**
- For empty string, single character, single-newline, single-line, EOF-without-newline — does the AFTER implementation produce the same accept/reject decision as the BEFORE?
- Adversarial probes: compare empty and single-line inputs under the original and changed-code paths; both preserve the same handling.

**L5. Invariant preservation**
- Does the BEFORE implementation enforce an invariant (early-exit on first match, idempotence under repeated invocation, stable iteration order, ordering of returned items)? Does the AFTER preserve each invariant?
- Adversarial probes: (a) call AFTER twice on the same input — is the second call's output identical to the first? (b) for a function that walks a list of patterns and returns on first match, does AFTER terminate at the same index BEFORE did, or does it walk past and return the LAST match? (c) for a function whose return type is `list[X]`, is the AFTER's ordering stable across runs?

**L6. Implementation-tag parity**
- The BEFORE implementation used [TAG_BEFORE] (regex / tokenize / str-method / library). The AFTER uses [TAG_AFTER]. For each input shape the BEFORE-tag accepted (e.g., a regex pattern accepted inline `#!` because the `re.MULTILINE` flag matched at any line start), does the AFTER-tag accept the same shape via a different mechanism?
- Adversarial probes: (a) enumerate the BEFORE-tag's capabilities that the AFTER-tag does not natively have (e.g., regex `\b` boundaries vs tokenize stream events) — has the AFTER implementation added compensating logic? (b) enumerate the AFTER-tag's capabilities that the BEFORE-tag did not have — are any of them silently expanding the accept set? (c) construct an input shape that the BEFORE-tag rejected only because of its tag's limitations — does the AFTER accept now and is that intentional?

**L7. Skipped-category exhaustion**
- Marker-shaped comments are findings when changed; verify whitespace variants against the changed-code rule.
- Adversarial probes: compare shebang and docstring handling with the changed marker-comment result across the original and changed-code paths.

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

# Worked example: jl-cmd/claude-dev-env PR #479

Audit jl-cmd/claude-dev-env PR #479 for **Category L only** (behavior-equivalence for refactors). Skip A–K, M, N. Sub-bucket forced-exhaustion mode: Category L is decomposed into 8 sub-buckets below.

PR: refactor(hooks): tokenize-based comment recognition
Base SHA: (the commit before the tokenize-based rewrite landed)
Head SHA at audit time: (the commit that landed the rewrite)
ID prefix: `find`.

- Marker-shaped comments are findings when changed; verify whitespace variants against the changed-code rule.

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**L1. KNOWN_GOOD_INPUTS table presence**
- Marker-shaped comments are findings when changed; verify whitespace variants against the changed-code rule.
- Marker-shaped comments are findings when changed; verify whitespace variants against the changed-code rule.

**L2. Whitespace / separator variants**
- Marker-shaped comments are findings when changed; verify whitespace variants against the changed-code rule.
- Marker-shaped comments are findings when changed; verify whitespace variants against the changed-code rule.
- Marker-shaped comments are findings when changed; verify whitespace variants against the changed-code rule.
- The CRLF / tab variants pass through the AFTER tokenizer identically.

**L3. Adjacent-form regressions**
- Marker-shaped comments are findings when changed; verify whitespace variants against the changed-code rule.
- Marker-shaped comments are findings when changed; verify whitespace variants against the changed-code rule.

**L4. Empty / boundary inputs**
- Empty input: BEFORE's `startswith` returns False on empty string. AFTER's `tokenize.COMMENT` token list is empty for an empty source; the iteration body never runs; the function returns False. Equivalent.
- Single character marker text remains a regular comment candidate under the changed-code rule. Equivalent.

**L5. Invariant preservation**
- Marker-shaped comments are findings when changed; verify whitespace variants against the changed-code rule.

**L6. Implementation-tag parity**
- Marker-shaped comments are findings when changed; verify whitespace variants against the changed-code rule.
- Marker-shaped comments are findings when changed; verify whitespace variants against the changed-code rule.

**L7. Skipped-category exhaustion**
- Marker-shaped comments are findings when changed; verify whitespace variants against the changed-code rule.

**L8. Sibling-implementation comparison**
PR: refactor(hooks): tokenize-based comment recognition

## Cross-bucket questions to answer at the end

- Marker-shaped comments are findings when changed; verify whitespace variants against the changed-code rule.

- Marker-shaped comments are findings when changed; verify whitespace variants against the changed-code rule.

- Marker-shaped comments are findings when changed; verify whitespace variants against the changed-code rule.

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket L1-L8, produce Shape A or Shape B (with ≥3 probes). Cross-bucket Q1-Q3 answers after the per-sub-bucket walk. Adversarial second pass: "assume your first pass missed at least 3 input classes where BEFORE and AFTER implementations disagree — find them." Open Questions section for ambiguities. Read-only. No edits, no commits.
