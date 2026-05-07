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

cd into `<worktree_path>` before any git, gh, or file operation.

<scope>
  <diff_path>Absolute path to the per-PR patch file: <run_temp_dir>/pr-<N>/loop-<L>.patch (same path as gh pr diff redirect in AUDIT)</diff_path>
  <scope_rule>Audit only lines added or modified in the diff. Pre-existing code on untouched lines is out of scope.</scope_rule>
</scope>

<bug_categories>
  Investigate each category explicitly. For each, return either at least
  one finding OR a verified-clean entry with the evidence used to clear it:
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
</bug_categories>

<constraints>
  - Read-only on source code: the audit does not modify any source file.
  - Cite file:line for every finding.
  - When the diff alone does not provide enough context to confirm a bug,
    list it under "Open questions" rather than assert it.
</constraints>

<posting>
  Sibling auditors (-b through -k): run only steps 1–3 (audit, assign IDs,
  capture excerpt, validate anchors), then write outcome XML per <output_format> and return.
  Skip steps 4–8 — sibling auditors do not post PR reviews.

  Validator (-a) and single-opus auditors: run all steps below. Posting is
  done via scripts under <script_dir>; raw jq pipelines are permitted only
  in step 7's issue-comment fallback.

  1. Audit the diff against the 10 categories above. Buffer the findings
     in memory; all posting happens at step 6 once anchors are validated.
  2. Assign each finding a stable finding_id of exactly the form `loop<L>-<K>`
     where <K> is 1-based within this loop.
  3. For each finding, capture a verbatim excerpt from the target file at the cited line. Populate the `<excerpt>` element in the outcome XML with it. Validate every finding's (file, line) against the captured diff. Split
     findings into two buckets: anchored (line is in the diff) and
     unanchored (line is not in the diff — goes into the review body's
     "Findings without a diff anchor" section per Step 2.5).
  4. Build the review summary markdown. Write to a temp file:

       ## /bugteam loop <L> Audit — Merged Findings
       **Total: N (P0=X, P1=Y, P2=Z)**  (append ` → clean` when N=0)

       When the total finding count is zero, append ` → clean` to the Total
       line so the re-invocation scan recognizes the prior audit as clean.

       ### Findings without a diff anchor
       (only if unanchored findings exist)
       - **[severity] title** — <file>:<line> — <one-line description>

     The review body is a summary header. Every anchored finding becomes
     its own review comment (step 6).

  5. For each anchored finding, write its body to a temp file:

       **[severity] one-line title**
       Category: <letter> (<category name>)
       <2-3 sentence description with concrete trace>
       File: <path>:<line>

       _From /bugteam audit loop <L>._

  6. Post the review + finding comments via the script:

       python <script_dir>/post_audit_review.py \
         --owner <owner> --repo <repo> --number <number> \
         --commit-id "$(git rev-parse HEAD)" \
         --body-file <temp_review_summary.md> \
         --finding-file <temp_finding_1.md> --path <file> --line <N> \
         ...

     Capture review_url and comment ids/urls from stdout JSON.
     API reference: https://docs.github.com/en/rest/pulls/comments

  7. If the script exits non-zero, fall back to a single issue comment:
       jq -Rs '{body: .}' < <temp_fallback.md> \
       | gh api repos/<owner>/<repo>/issues/<number>/comments -X POST --input -
     Include the review summary + all findings inline.
     Every finding gets used_fallback="true", finding_comment_url set
     to the issue-comment URL.

  8. Write outcome XML. Populate finding_comment_id and finding_comment_url
     from script output (or fallback URL).

  <script_dir> = absolute path to _shared/pr-loop/scripts/.
</posting>

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

cd into `<worktree_path>` before any git, gh, or file operation.

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
  4. git add by explicit path, then git commit with a message summarizing the bugs fixed.
     - If the commit fails because a git hook (pre-commit, commit-msg, etc.) blocked it,
       capture the hook's stderr, write status=hook_blocked for every finding in this loop
       (the commit was atomic; if it failed, no finding was applied), populate hook_output
       on each outcome, and return WITHOUT retrying. The lead will treat this loop as no-progress.
  5. git push with a plain fast-forward push (the default, no flag overrides).
  6. For each bug, post a fix reply to its finding_comment_id via the
     Step 2.5 reply CLI shape:
     - "Fixed in <commit_sha>" if the bug was addressed by your commit
     - "Could not address this loop: <one-line reason>" if you skipped or failed it
     - "Hook blocked the fix commit: <one-line summary>" if the commit was hook-blocked
     Use the Fix reply CLI shape from Step 2.5 (`jq -Rs | gh api .../comments/<id>/replies --input -`). Write every reply body to a temp file first.
  7. Write `.bugteam-pr<N>-loop<L>.outcomes.xml` inside `<worktree_path>` (schema below) and return its path.
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
</constraints>
```
