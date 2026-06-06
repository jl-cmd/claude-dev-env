# Bugteam — spawn-prompt XML templates and outcome XML schemas

## AUDIT spawn-prompt XML (bugfind teammate)

Keep the spawn prompt self-contained: reference only the PR scope, audit rubric, and this loop number. Write each instruction as a standalone statement so the teammate reads the prompt as a fresh brief and every audit starts from first principles.

```xml
<context>
  <repo>owner/repo</repo>
  <branch>head ref</branch>
  <base_branch>base ref</base_branch>
  <pr_url>full URL</pr_url>
  <loop>L</loop>
  <pr_number>N</pr_number>
  <worktree_path>absolute path from Step 1 per-PR workspace</worktree_path>
</context>

cd into `<worktree_path>` before any git or file operation.

<scope>
  <diff_path>Absolute path to the per-PR patch file: <run_temp_dir>/pr-<N>/loop-<L>.patch (same path as gh pr diff redirect in AUDIT)</diff_path>
  <scope_rule>Audit only lines added or modified in the diff. Pre-existing code on untouched lines is out of scope.</scope_rule>
  <changed_files_rule>Build the list of changed file paths from the diff. Open each one with Read and audit cross-file consistency. Read every changed test file and cross-reference test assertions, expected values, and mock setup against the production code's config constants and function signatures. When a test file asserts a value that diverges from config, file a finding under category J.</changed_files_rule>
</scope>

<bug_categories>
  Investigate each of the sixteen categories (A–P) explicitly. For each,
  return either at least one finding OR a verified-clean entry with the
  evidence backing the verdict. A category is verified-clean only when one
  complete execution path through the changed code has been traced from
  entry to exit. Surface-level scanning is insufficient evidence. The
  evidence field must name (1) the specific function examined, (2) the
  code path traced from entry to exit, and (3) the specific check performed.
  Generic phrases such as "verified clean", "no issues found",
  "pattern appears correct", "looks good", "seems fine", and
  "no problems detected" do not satisfy the verified-clean requirement.
  When evidence contains any of these phrases, the category is not
  verified-clean -- re-audit with a concrete trace.

  Categories A–P (one-line summary; full rubric and sub-bucket
  decomposition for each is in
  `$HOME/.claude/audit-rubrics/category_rubrics/`; ready-to-send Variant
  C prompts — each with a PR/repo-independent generalized skeleton above
  a `---` separator and a worked example against an authentic PR below —
  are in `$HOME/.claude/audit-rubrics/prompts/`):

  A. API contract verification
  B. Selector / query / engine compatibility
  C. Resource cleanup and lifecycle
  D. Variable scoping, ordering, and unbound references
  E. Dead code and unused imports
  F. Silent failures
  G. Off-by-one, bounds, integer overflow
  H. Security boundaries
  I. Concurrency hazards
  J. CODE_RULES.md compliance
  K. Codebase conflicts (incomplete propagation)
  L. Behavior-equivalence for refactors
  M. Producer/consumer cardinality vs collection-type contract
  N. Test-name scenario verifier
  O. Docstring / fixture-prose vs implementation drift
  P. Name / regex / word-list vs behavior-contract precision
</bug_categories>

<rubric_reference>
  The category list above is a summary. The binding definition of each
  category is its rubric file under
  `$HOME/.claude/audit-rubrics/category_rubrics/` (ready-to-send prompt
  variants under `$HOME/.claude/audit-rubrics/prompts/`). Read the rubric
  files before auditing.
</rubric_reference>

<constraints>
  - Read-only on source code: the audit does not modify any source file.
  - Cite file:line for every finding.
  - When the diff alone does not provide enough context to confirm a bug,
    list it under "Open questions" rather than assert it.
  - For every finding, search `git grep` for all callers of the targeted function. When the obvious fix would silently change behavior for other call paths, include a fix constraint that preserves them.
</constraints>

<comment_posting>
  Load all A–P rubrics from
  `$HOME/.claude/audit-rubrics/{category_rubrics,prompts}/`. The prompt file
  is a template for output shape, not a straitjacket — reorganize when the
  diff demands it. The diff supplies the findings; the rubric supplies the
  sub-bucket decomposition and decision criteria. Both must be loaded.

  Before starting, create one task per checklist item via TaskCreate. Use
  TaskUpdate to mark each in_progress as you begin it and completed when
  done.

  <self_audit_checklist>
    [ ] Walk all 16 categories (A–P), each with Shape A or Shape B
    [ ] Assign finding IDs (loop<L>-<K>)
    [ ] Capture excerpts, validate anchors, format finding bodies
    [ ] Build findings JSON, invoke post_audit_thread.py, capture html_url
    [ ] Harvest child-comment ids/urls AND thread_node_ids; populate loop_comment_index
    [ ] Write outcome XML
  </self_audit_checklist>

  1. Audit the diff against the 16 categories above. Buffer the findings
     in memory; all posting happens at step 4 once anchors are validated.
  2. Assign each finding a stable finding_id of exactly the form `loop<L>-<K>`
     where <K> is 1-based within this loop.
  3. For each finding, capture a verbatim excerpt from the target file at the cited
     line. Populate the `<excerpt>` element in the outcome XML with it. Validate
     every finding's (file, line) against the captured diff. Split findings into two
     buckets: anchored (line is in the diff) and unanchored (line is not in the diff
     — surfaced in the calling skill's user-facing output rather than as inline
     anchored comments).

     Each anchored finding contributes one entry to the JSON payload built
     in step 4. The payload schema is
     `{path, line, side, severity, description, fix_summary}`; the audit
     teammate populates `description` (the failure narrative) and
     `fix_summary` (the `Fix:` / `Validation:` text) from the
     finding's `failure_mode` per the mapping in step 4. The audit
     teammate does NOT author the inline-comment body directly:
     `post_audit_thread.py` renders every body from
     `INLINE_COMMENT_BODY_TEMPLATE` (defined in
     [`_shared/pr-loop/scripts/pr_loop_shared_constants/post_audit_thread_constants.py`](../../_shared/pr-loop/scripts/pr_loop_shared_constants/post_audit_thread_constants.py))
     — the template prepends `**[<severity>] <Skill> audit finding**`
     and renders the suggested-fix block, so a teammate who hand-formats
     a title or footer wastes the work.

  4. **Before posting, read the full review once as if you were the PR
     author.** Ask: would I understand what to fix and why? Do any two
     findings describe the same problem in different words — merge them. Does
     any finding miss its mark — rewrite or drop it. Does the review feel
     coherent as a whole? The review's job is to make the PR author want to
     fix these bugs, not to demonstrate that the rubric ran. Rearrange,
     merge, or rephrase anything that would confuse the author. Then
     proceed with the mechanical script invocation below.

     Post ONE review per loop via `post_audit_thread.py` per
     [SKILL.md § Audit posting](SKILL.md#audit-posting). Serialize the
     anchored findings to a JSON file shaped as a list of
     `{path, line, side, severity, description, fix_summary}` entries.
     Map each finding's `file` → `path`; split each finding's
     `failure_mode` at the literal `Fix:` heading so the failure
     narrative becomes `description` and the suffix beginning at `Fix:`
     (including the trailing `Validation:` clause) becomes
     `fix_summary`. When the agent omits the `Fix:` heading on a given
     finding, write the full `failure_mode` text to BOTH `description`
     and `fix_summary`. Set `side="RIGHT"` for every entry. Zero
     anchored findings → `--state CLEAN` with the findings file holding
     an empty array (`[]`); one or more → `--state DIRTY` with the full
     list.

     ```
     python "${CLAUDE_SKILL_DIR}/../../_shared/pr-loop/scripts/post_audit_thread.py" \
       --skill bugteam \
       --owner <O> \
       --repo <R> \
       --pr-number <N> \
       --commit <head_sha> \
       --state <CLEAN|DIRTY> \
       --findings-json <path>
     ```

     The script POSTs a single review with `event=APPROVE` on CLEAN
     (the request event; GitHub stores it as `state=APPROVED`; empty
     `comments[]`, body documents "no findings") or
     `event=REQUEST_CHANGES` on DIRTY (one inline anchored comment per
     finding; each becomes its own resolvable thread on the PR). It
     handles retries internally (1s / 4s / 16s backoff across four
     attempts). Exit codes:

     - `0` — review posted; the new review's `html_url` is on stdout.
       Capture this URL as the parent review URL.
     - `1` — user input error (bad arguments, malformed findings JSON,
       missing template).
     - `2` — retry exhaustion. Hard blocker; halt and exit
       `error: post_audit_thread retry exhausted` without retrying and
       without falling back to a flat issue comment. There is no
       fallback path — a hard blocker on the audit-posting path is a
       halt condition.

     Exit 0 emits the new review's `html_url` on stdout. Extract the
     numeric review id from that URL's `#pullrequestreview-<id>` suffix
     (the trailing URL fragment, the part after `#`). Then harvest child-comment URLs
     **and PR review thread node ids** via
     `pull_request_read(method="get_review_comments", owner=<O>,
     repo=<R>, pullNumber=<N>)` filtered to that review id.
     Match children to findings in the order they appear in the findings
     JSON. Each `loop_comment_index[finding_id]` entry must carry both
     `finding_comment_id` (numeric, used by `add_reply_to_pull_request_comment`)
     and `thread_node_id` (e.g. `PRRT_kwDOxxx`, used by
     `resolve_thread`) so the FIX teammate can reply and resolve.

  The findings JSON is serialized to a temp file and passed by path; the
  review-body content is read from `audit-reply-template.md` at runtime by
  `post_audit_thread.py`, not passed in by the caller. No body-content
  temp files, no jq, no shell pipes.
</comment_posting>

<output_format>
  Run `python scripts/write_audit_outcomes.py` to write the outcome XML.
  The script owns the canonical path, filename, and format.
</output_format>
```

## AUDIT outcome XML schema

`write_audit_outcomes.py` reads the findings JSON (list of finding dicts) and
emits this shape. Scalar finding fields become XML attributes on
`<finding>`; the body fields `title`, `excerpt`, and `description` become
child elements. The root carries `pr`, `loop`, and `review_url` as
attributes.

```xml
<bugteam_audit pr="<N>" loop="<L>" review_url="<url>">
  <findings>
    <finding
      finding_id="loop<L>-<K>"
      severity="P0|P1|P2"
      category="<letter>"
      file="<path>"
      line="<int>"
      finding_comment_id="<gh child comment id, or empty if unanchored>"
      finding_comment_url="<url of child comment, OR review_url if unanchored>"
      thread_node_id="<PR review thread node id (PRRT_kwDOxxx), or empty if unanchored>"
    >
      <title>one-line title</title>
      <excerpt>verbatim source line or snippet from the file at the cited line</excerpt>
      <description>2-3 sentence description with concrete trace</description>
    </finding>
  </findings>
</bugteam_audit>
```

Verified-clean evidence per A–P category is surfaced in the agent's text-mode
final report, not in this outcome XML (the writer accepts a flat findings list
only).

## FIX spawn-prompt XML (bugfix teammate)

```xml
<context>
  <repo>owner/repo</repo>
  <branch>head</branch>
  <base_branch>base</base_branch>
  <pr_url>url</pr_url>
  <loop>L</loop>
  <pr_number>N</pr_number>
  <worktree_path>absolute path from Step 1 per-PR workspace</worktree_path>
</context>

cd into `<worktree_path>` before any git or file operation.

<bugs_to_fix>
  [for each P0/P1/P2 finding from last_findings:]
  <bug
    finding_id="loop<L>-<K>"
    severity="P0|P1|P2"
    file="<path>"
    line="<int>"
    category="<letter>"
    finding_comment_id="<numeric comment id>"
    finding_comment_url="<url>"
    thread_node_id="<PR review thread node id (PRRT_kwDOxxx)>"
  >
    <description>...</description>
  </bug>
</bugs_to_fix>

<execution>
  Before starting, create one task per checklist item via TaskCreate. Use
  TaskUpdate to mark each in_progress as you begin it and completed when
  done.

  <self_audit_checklist>
    [ ] Read each referenced file
    [ ] Apply all addressable fixes
    [ ] py_compile on every modified file
    [ ] Test suite passes
    [ ] Post-fix violation count ≤ previous loop total (skip on L=1)
    [ ] git add + commit
    [ ] git push
    [ ] Per finding: atomically post the unified-template reply, then call resolve_thread (no yield between them)
    [ ] Publish fix summary via /doc-gist, capture URL
    [ ] Append fix summary URL to parent review via add_reply_to_pull_request_comment
    [ ] Write fix outcomes XML
  </self_audit_checklist>

  1. Read each referenced file before editing.
  2. Apply each fix you can address.
  3. Run `python -m py_compile` (or language-equivalent) on every modified file.
  4. Run the project's test suite and confirm all existing tests pass. If a test fails, diagnose the regression and fix it before committing.
  5. Read the previous loop's outcome XML (`<worktree_path>/.bugteam-pr<N>-loop<L-1>.outcomes.xml`) and obtain its total finding count. If this is the first loop (L <= 1) or the file does not exist, skip this comparison. Otherwise, re-read each changed file and count any new violations. Compute the post-fix total: previous total minus bugs fixed in this round plus new violations. If the post-fix total exceeds the previous total, flag all new findings as same-loop fix-targets and revise before committing.
  6. git add by explicit path, then git commit with a message summarizing the bugs fixed.
     - If the commit fails because a git hook (pre-commit, commit-msg, etc.) blocked it,
       capture the hook's stderr, write status=hook_blocked for every finding in this loop
       (the commit was atomic; if it failed, no finding was applied), populate hook_output
       on each outcome, and return WITHOUT retrying. The lead will treat this loop as no-progress.
  7. git push with a plain fast-forward push (the default, no flag overrides).
  8. For each finding, atomically (a) post the fix reply and
     (b) call `resolve_thread`. The two calls form one logical action
     per thread — do not yield to the lead between them, and do not
     batch all replies before any resolves.

     (a) Reply via
     `add_reply_to_pull_request_comment(commentId=<finding_comment_id>,
     body=<reply_body>, owner=<O>, repo=<R>, pullNumber=<N>)`. The
     reply body uses the unified template at
     [`../../_shared/pr-loop/audit-reply-template.md`](../../_shared/pr-loop/audit-reply-template.md).
     Skeleton (identical across all paths):

     ```
     **Claude finished @<reviewer>'s task** —— <status_line>

     ---
     ### <action_heading> ✅

     <1–2 paragraph plain-language explanation>

     **`<file>:<line>`:**
     - <bullet describing change or rationale>
     - <bullet describing change or rationale>

     <closing paragraph>
     ```

     Per-path `<status_line>` / `<action_heading>`:
     - `status=fixed`: `Fixed in <short_sha>` (first 7 chars) /
       finding-specific action verb (e.g.,
       `Replaced Any with concrete type`).
     - `status=could_not_address`: `Could not address this loop` /
       one-line reason text.
     - `status=hook_blocked`: `Hook blocked the fix commit` /
       one-line hook summary.

     Body text is passed directly as string parameters — no temp files,
     no jq, no shell pipes.

     (b) Immediately call
     `pull_request_review_write(method="resolve_thread",
     threadId=<thread_node_id>, owner=<O>, repo=<R>, pullNumber=<N>)`
     for the same thread (this is the PR review thread node ID —
     `PRRT_kwDOxxx` — distinct from the numeric comment ID; the AUDIT
     teammate captures it at audit time when calling
     `get_review_comments` and stores it on each
     `loop_comment_index` entry alongside `finding_comment_id`, see
     [reference/obstacles/fix-resolve-thread.md](reference/obstacles/fix-resolve-thread.md)).

  9. Publish the fix summary gist via `/doc-gist`. Pass the fix report
     (what was fixed, what was skipped, what was left unaddressed) as the
     gist body. Capture the returned gist URL.

  10. Append the fix summary gist URL (from step 9) to the parent review
      via `add_reply_to_pull_request_comment(commentId=<id>, body=...,
      owner=<O>, repo=<R>, pullNumber=<N>)`. The body carries the
      gist URL plus a one-line summary of fixes applied this loop.

  11. Write `.bugteam-pr<N>-loop<L>.fix-outcomes.xml` inside
      `<worktree_path>` (schema below) and return its path.
</execution>

<outcome_xml_schema>
  <bugteam_fix pr="<N>" loop="<L>" commit_sha="<sha or empty if no commit>">
    <outcomes>
      <outcome
        finding_id="loop<L>-<K>"
        status="fixed|could_not_address|hook_blocked|unverified_fixed"
        commit_sha="<sha if fixed, empty otherwise>"
        reply_comment_id="<id of the reply posted>"
        reply_comment_url="<url of the reply posted>"
      >
        <reason>only present when status=could_not_address; one-line reason text</reason>
        <hook_output>only present when status=hook_blocked; verbatim stderr from the blocked hook</hook_output>
      </outcome>
    </outcomes>
  </bugteam_fix>
</outcome_xml_schema>

<constraints>
  - Modify only files referenced in bugs_to_fix.
  - One commit on the existing branch, then push.
  - Keep the branch linear and the PR base fixed; append one new commit per
    loop and fast-forward push only.
  - Let every git hook run on every commit.
  - git add by explicit path — name each file being staged.
  - Preserve existing comments on lines you do not modify.
  - Type hints on every signature you touch.
  - **Narrow scope.** Fix only the exact defect at the specified file:line. No restructuring, no inlining helpers, no renames, no "while I'm here" cleanup.
  - **Preserve helpers.** Do not remove or inline existing helper functions unless the finding explicitly names the helper as the problem.
  - **No regression.** Before committing, re-read each changed file and count any new violations. Compare the post-fix total (previous total minus bugs fixed plus new violations) against the previous loop's total finding count (from `<worktree_path>/.bugteam-pr<N>-loop<L-1>.outcomes.xml`). On the first loop (L <= 1) or when the file does not exist, skip this guard. The post-fix total must be flat or decreased relative to the previous loop. An increase means the fix introduced new bugs — revise before committing. Do not commit a regression.
</constraints>
```
