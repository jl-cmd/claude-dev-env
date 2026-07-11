# Audit contract

Shared output schema and audit-loop contract used by `/bugteam`, `/qbug`, `/findbugs`, and `/fixbugs`. Changing a shape here is a breaking change for every consuming skill.

## Contents

- Finding schema (Shape A, Shape B)
- Adversarial second pass
- Haiku secondary auditor
- Post-fix self-audit
- De-dup and merge
- Persistence (loop-<L>-audit.json, loop-<L>-diagnostics.json)

## Finding schema

Each finding an audit produces MUST be one of exactly two shapes.

### Shape A — structured finding

```json
{
  "id": "loop<L>-<K>",
  "file": "path/relative/to/repo/root.py",
  "line": 123,
  "category": "A | B | C | D | E | F | G | H | I | J | K | L | M | N | O | P",
  "severity": "P0 | P1 | P2",
  "excerpt": "verbatim code snippet from the offending line(s)",
  "failure_mode": "one sentence describing what goes wrong and when",
  "evidence_files": ["additional/files/opened.py"]
}
```

`id` is `loop<L>-<K>` where `L` is the loop counter (1-based) and `K` is the 1-based index within the loop. For `/findbugs` which runs once, use `find<K>`.

### Shape B — structured proof-of-absence

Used when an audit investigates a category and does NOT find a bug. Bare "verified clean" claims are REJECTED because they hide shallow reading.

```json
{
  "category": "A | B | C | D | E | F | G | H | I | J | K | L | M | N | O | P",
  "files_opened": ["file1.py", "file2.py"],
  "lines_quoted": [
    {"file": "file1.py", "line": 88, "text": "verbatim line content"}
  ],
  "adversarial_probes": [
    "what failure mode was tested for and how it was ruled out"
  ]
}
```

Every category an audit touches MUST have either at least one Shape A finding OR at least one Shape B proof-of-absence entry. A category with neither is a protocol violation.

### Example — Shape A

```json
{
  "id": "loop1-1",
  "file": "scripts/db/neon.py",
  "line": 43,
  "category": "C",
  "severity": "P1",
  "excerpt": "load_dotenv(env_path, override=False)",
  "failure_mode": "Called on every connect() — repeats file I/O per connection in scripts that open multiple short-lived connections.",
  "evidence_files": ["scripts/db/neon.py", "scripts/update_new_releases.py"]
}
```

### Example — Shape B

```json
{
  "category": "H",
  "files_opened": ["scripts/db/neon.py", "scripts/db/config.py"],
  "lines_quoted": [
    {"file": "scripts/db/neon.py", "line": 30, "text": "dsn = os.environ.get(\"DATABASE_URL\")"}
  ],
  "adversarial_probes": [
    "Checked whether DATABASE_URL is interpolated into a shell — it is passed to psycopg.connect() directly with no shell involvement.",
    "Checked whether the env path is user-controlled — it is derived from a fixed Y: drive constant, not user input."
  ]
}
```

## Adversarial second pass

After the primary finding list is complete, every audit runs a second pass against itself with the prompt:

> Assume your first pass missed at least 3 P1 bugs. Where are they?

The audit must either produce new Shape A findings citing new file:line references not present in the first pass, or cite explicit Shape B adversarial-probe entries for each category it re-examined. An adversarial pass that returns "nothing new, confident first pass was complete" is REJECTED — produce evidence or findings, not confidence.

## Haiku secondary auditor

For single-subagent skills (`/qbug`, `/findbugs`) the LEAD spawns two `Agent()` calls in one message:

- **Primary** — `subagent_type=clean-coder`, `model=sonnet` (for qbug cycle) or `subagent_type=code-quality-agent`, `model=sonnet` (for findbugs clean-room).
- **Secondary (Haiku)** — `subagent_type=code-quality-agent`, `model=haiku`, same self-contained clean-room prompt shape used by `/findbugs`.

Both audit the same diff. The secondary returns findings to the LEAD only — never posted to the PR.

Merge rules — applied whenever the LEAD combines findings from multiple sources (primary auditor, Haiku secondary auditor, adversarial pass):

- **De-dup key**: `(file, line, category)`. Two findings sharing the same `(file, line, category)` tuple are the same finding and collapse into one entry.
- **Severity conflict**: max wins (`P0 > P1 > P2`). When sources disagree on severity for the same de-dup key, the merged entry keeps the highest severity.
- **Unique-to-secondary findings**: added to the merged set with the secondary's severity and source annotation.
- **Unique-to-primary findings**: kept as-is.
- **Zero secondary findings**: the primary set is trusted and the audit moves on.
- **Malformed or non-parseable secondary output**: lead trusts the primary set and logs the event in `loop-<L>-diagnostics.json` under `haiku_findings` as `[{"parse_error": "<message>"}]`.

For `/bugteam`, the single audit agent provides per-category coverage by walking all A–P rubrics in one invocation.

## Post-fix self-audit

Audit-and-fix skills (`/qbug`, `/bugteam`) MUST re-audit modified files between `py_compile` and `git add`. This catches fix-induced regressions in the same loop that introduced them rather than on loop N+1.

Sequence:

1. Capture pre-fix file contents for every file this FIX will touch.
2. Apply edits.
3. Run `py_compile` (or language-equivalent) on each modified file.
4. Compute `fix_diff` against pre-fix contents for the modified set.
5. Run `bugteam_code_rules_gate.py` with explicit paths for every modified file.
6. Spawn a scoped audit of `fix_diff` with full A–P rigor, Shape A/B contract, adversarial pass, AND Haiku secondary in parallel (paranoid mode on post-fix).
7. Read the previous loop's outcome XML (`<worktree_path>/.bugteam-pr<N>-loop<L-1>.outcomes.xml`) and obtain its total finding count. If this is the first loop (L <= 1) or the file does not exist, skip this comparison. Compute the post-fix total: previous total minus bugs fixed in this round plus new violations found in the post-fix audit (step 6). If the post-fix total exceeds the previous total, flag all new findings as same-loop fix-targets and revise. An increase in total findings across loop transitions is a regression.
8. Any new findings become same-loop fix-targets. Internal iteration count increments by one.
9. After 3 internal iterations with fresh findings each time, exit `stuck: post-fix audit not converging`.
10. Only when `gate_findings` empty AND `post_fix_findings` empty: `git add`, commit, push.

`converged` exit condition: `primary_audit_clean AND post_fix_audit_clean` for the committing loop.

## De-dup and merge

Findings from primary, adversarial, Haiku secondary, and post-fix passes are merged into a single deduped finding list before persistence.

- **De-dup key:** `(file, line, category)`. Two findings sharing the same `(file, line, category)` tuple collapse into a single deduped entry.
- **Severity conflict resolution:** `max wins`. When merged findings disagree on severity, the deduped entry carries the highest severity (`P0 > P1 > P2`).
- **Excerpt and failure_mode:** the deduped entry inherits these fields from the highest-severity contributing finding. Ties keep the first observed contributor.
- **`evidence_files`:** the deduped entry carries the union of every contributor's `evidence_files`, deduplicated and sorted.

The merged list lands in `loop-<L>-diagnostics.json` under both `merged` (one entry per contributing finding) and `deduped` (one entry per unique `(file, line, category)` tuple).

## Persistence

Every audit loop writes two JSON files under the skill's scoped temp directory (resolved via `tempfile.gettempdir()`):

### `loop-<L>-audit.json`

```json
{
  "findings": [],
  "proof_of_absence": [],
  "source": "primary | haiku | adversarial | merged"
}
```

### `loop-<L>-diagnostics.json`

```json
{
  "loop": 1,
  "gate_findings": [],
  "primary_findings": [],
  "adversarial_findings": [],
  "haiku_findings": [],
  "post_fix_findings": [],
  "merged": [],
  "deduped": []
}
```

All eight keys MUST be present. Missing keys break convergence debugging.
