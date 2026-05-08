# Bugteam constraints

## Non-Negotiable

- **Pre-flight is mandatory.** `preflight.py` must exit 0 before Step 0. If it fails for `core.hooksPath`, auto-remediate with `fix_hookspath.py`. All other failures require manual fixes.
- **Looping against a fixed known count.** 10 audit loops hard cap. No exceptions. The cap is a safety value, set high enough to converge on most non-trivial PRs while preventing infinite loops.
- **`loop_count` is the iteration counter.** It increments before each AUDIT in Step 3. A FIX without a preceding AUDIT does not advance `loop_count`. The `loop_count > 10` check runs before each AUDIT. After 10 AUDITs, the cycle exits regardless of remaining FIX rounds. Standards-fix passes before an audit do not advance `loop_count`.
- **One review per loop, findings as child comments of that review.** Each loop posts a single pull-request review whose body is the loop header and whose `comments[]` are the anchored findings. Each loop's review stands alone — one review created per loop, fully self-contained on the PR conversation.
- **PR description rewrite on every exit.** Step 4.5 runs on `converged`, `cap reached`, and `stuck`. On `error`, the rewrite is best-effort; if it fails, surface the error in the final report and continue to revoke.
- **Outcome XML, not JSON.** The AUDIT subagent writes findings to `.bugteam-pr<N>-loop<L>.outcomes.xml` and the FIX subagent writes fix outcomes to `.bugteam-pr<N>-loop<L>.fix-outcomes.xml`. The lead reads these files between actions. Separate paths prevent the FIX output from overwriting the AUDIT's findings file. XML chosen for parser robustness against multi-line, special-character, and quoted reason fields.

## Why this design

### Why retry with fix — why not just reject and move on

Bugteam's purpose is to make real PRs better before they ship, not to just point out problems. A review that says "fix this bug" without giving the author&#60;subagent&#62; a chance to fix it in the same session would be a weaker intervention — the PR author still has to go back, figure out the fix, apply it, re-push, and re-trigger review. By bundling fix attempts into the same loop, bugteam reduces round-trips from N audits + N manual fix cycles to N audits + N automated fix attempts, with no human context-switching.

### Why 10 loops — why not unlimited

A PR that needs more than 10 audit-fix rounds has deeper problems than bugteam can address. The 10-loop cap is a forcing function: after 10 rounds, escalate to `/findbugs` or human review rather than grinding on diminishing returns.

### Why outcome XML — why not JSON

JSON escapes `\n` inside `"reason": "could not address: some\nmulti-line\ntext"`, making the file hard to read and grep. XML preserves the raw text as element content, so `&#60;reason&#62;could not address: some&#10;multi-line&#10;text&#60;/reason&#62;` renders legibly in every markdown-capable viewer. The choice is ergonomic, not technical — both formats carry the same information.

### Why sibling auditor paths diverge (worktree vs temp)

Only the -a validator writes to the worktree `.bugteam-pr&#60;N&#62;-loop&#60;L&#62;.outcomes.xml` path, which the lead reads. Sibling auditors (-b through -k) write to unique paths under `&#60;run_temp_dir&#62;` to avoid collisions. Without this split, parallel haiku auditors writing to the same path would clobber each other's output, and the lead consuming one path would see only whichever writer finished last.
