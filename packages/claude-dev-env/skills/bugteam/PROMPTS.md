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
  Investigate each of the eleven categories (A–K) explicitly. For each,
  return either at least one finding OR a verified-clean entry with the
  evidence used to clear it. A category is verified-clean only when one
  complete execution path through the changed code has been traced from
  entry to exit. Surface-level scanning is insufficient evidence. The
  evidence field must name (1) the specific function examined, (2) the
  code path traced from entry to exit, and (3) the specific check performed.
  Generic phrases such as "verified clean", "no issues found",
  "pattern appears correct", "looks good", "seems fine", and
  "no problems detected" do not satisfy the verified-clean requirement.
  When evidence contains any of these phrases, the category is not
  verified-clean -- re-audit with a concrete trace.

  Categories A–K (one-line summary; full rubric and sub-bucket decomposition
  for each is in `packages/claude-dev-env/audit-rubrics/category_rubrics/`;
  ready-to-send Variant C prompts — each with a PR/repo-independent
  generalized skeleton above a `---` separator and a worked example against
  an authentic PR below — are in
  `packages/claude-dev-env/audit-rubrics/prompts/`):

  A. API contract verification (signatures, return types, async/await correctness)
  B. Selector / query / engine compatibility
  C. Resource cleanup and lifecycle (file handles, connections, processes, locks)
  D. Variable scoping, ordering, and unbound references
  E. Dead code: dead parameters, dead locals, dead imports, dead branches, dead returns, and unused imports
  F. Silent failures (catch-all excepts, unconditional success returns, missing error propagation)
  G. Off-by-one, bounds, and integer overflow
  H. Security boundaries (injection, path traversal, auth bypass, secret leakage)
  I. Concurrency hazards (race conditions, missing awaits, shared mutable state)
  J. Magic values and configuration drift
  K. Codebase conflicts — a change updates one site of a pattern but a parallel
     site in unchanged code stays stale, producing contradictory behavior;
     the diff is internally consistent, the bug emerges only against unchanged
     code (canonical example: jl-cmd/claude-code-config PR #397 r3210166636)
</bug_categories>

<constraints>
  - Read-only on source code: the audit does not modify any source file.
  - Cite file:line for every finding.
  - When the diff alone does not provide enough context to confirm a bug,
    list it under "Open questions" rather than assert it.
  - For every finding, search `git grep` for all callers of the targeted function. When the obvious fix would silently change behavior for other call paths, include a fix constraint that preserves them.
</constraints>

<comment_posting>
  Sibling auditors (-b through -k): run only steps 1–2 (audit, assign IDs,
  capture excerpt, validate anchors), then write outcome XML per <output_format> and return.
  Skip steps 3–5 — sibling auditors do not post PR reviews.

  Validator (-a) and single-opus auditors: run all steps below.

  1. Audit the diff against the 11 categories above. Buffer the findings
     in memory; all posting happens at step 4 once anchors are validated.
  2. Assign each finding a stable finding_id of exactly the form `loop<L>-<K>`
     where <K> is 1-based within this loop.
  3. For each finding, capture a verbatim excerpt from the target file at the cited
     line. Populate the `<excerpt>` element in the outcome XML with it. Validate
     every finding's (file, line) against the captured diff. Split findings into two
     buckets: anchored (line is in the diff) and unanchored (line is not in the diff
     — goes into the review body's "Findings without a diff anchor" section per
     Step 2.5). Format each finding body as:

       **[severity] one-line title**
       Category: <letter> (<category name>)
       <2-3 sentence description with concrete trace>

       _From /bugteam audit loop <L>._

  4. Post ONE review via `pull_request_review_write(method="create",
     event="COMMENT", body=<review_body>, owner=<O>, repo=<R>,
     pullNumber=<N>, comments=[...])`. See Step 2.5 in SKILL.md for the full
     parameter shape. Harvest the parent review `html_url` from the response
     and the `comments[]` child entries (each with its own `id` and `html_url`).
     Match child entries to anchored findings in index order.
  5. If the review POST fails, use `add_issue_comment(owner=<O>, repo=<R>,
     issueNumber=<N>, body=<full_text>)` as fallback.
  Body text is passed directly as string parameters to the MCP tool calls —
  no temp files, no jq, no shell pipes.
</comment_posting>

<output_format>
  For the (-a) validator: write the outcome XML below to .bugteam-pr<N>-loop<L>.outcomes.xml inside
  the PR's worktree directory (<worktree_path>). For sibling auditors (-b through -k): write to <run_temp_dir>/pr-<N>/loop-<L>-<letter>.outcomes.xml (absolute path passed in prompt). Sibling auditors do not post PR reviews; set review_url, finding_comment_id, and finding_comment_url to empty strings, and used_fallback to "false". Omit unanchored findings from sibling output — only the validator handles those. Return only that path on stdout. The schema:
</output_format>
```

## AUDIT outcome XML schema (bugfind writes this)

```xml
<bugteam_audit loop="<L>" review_url="<url>">
  <finding
    finding_id="loop<L>-<K>"
    severity="P0|P1|P2"
    category="<letter>"
    file="<path>"
    line="<int>"
    finding_comment_id="<gh child comment id, or empty if unanchored/review-fallback>"
    finding_comment_url="<url of child comment, OR review_url if unanchored, OR fallback issue comment URL>"
    used_fallback="true|false"
  >
    <title>one-line title</title>
    <excerpt>verbatim source line or snippet from the file at the cited line</excerpt>
    <description>2-3 sentence description with concrete trace</description>
  </finding>
  <verified_clean>
    <category letter="<letter>" name="<name>" evidence="brief evidence + cleared conclusion"/>
  </verified_clean>
</bugteam_audit>
```

After the teammate writes the XML and returns, the lead reads `.bugteam-pr<N>-loop<L>.outcomes.xml` from the PR's worktree directory with the `Read` tool, parses it, and populates `loop_comment_index` from `<finding>` elements.

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
    finding_comment_id="<id>"
    finding_comment_url="<url>"
  >
    <description>...</description>
  </bug>
</bugs_to_fix>

<execution>
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
  8. For each bug, post a fix reply to its finding_comment_id via
     `add_reply_to_pull_request_comment(commentId=<id>, body=<reply_text>,
     owner=<O>, repo=<R>, pullNumber=<N>)`:
     - "Fixed in <commit_sha>" if the bug was addressed by your commit
     - "Could not address this loop: <one-line reason>" if you skipped or failed it
     - "Hook blocked the fix commit: <one-line summary>" if the commit was hook-blocked
     Body text is passed directly as string parameters -- no temp files, no jq, no shell pipes.
  9. Write `.bugteam-pr<N>-loop<L>.fix-outcomes.xml` inside `<worktree_path>` (schema below) and return its path.
</execution>

<outcome_xml_schema>
  <bugteam_fix loop="<L>" commit_sha="<sha or empty if no commit>">
    <outcome
      finding_id="loop<L>-<K>"
      status="fixed|could_not_address|hook_blocked"
      commit_sha="<sha if fixed, empty otherwise>"
      reply_comment_id="<id of the reply posted>"
      reply_comment_url="<url of the reply posted>"
    >
      <reason>only present when status=could_not_address; one-line reason text</reason>
      <hook_output>only present when status=hook_blocked; verbatim stderr from the blocked hook</hook_output>
    </outcome>
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
