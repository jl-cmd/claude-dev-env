# Bugteam — spawn-prompt XML templates and outcome XML schemas

## AUDIT spawn-prompt XML (bugfind teammate)

Keep the spawn prompt self-contained: reference only the PR scope, audit rubric, and this loop number. Write each instruction as a standalone statement so the teammate reads the prompt as a fresh brief and every audit starts from first principles.

```xml
<context>
  <repo>owner/repo</repo>
  <branch>head ref</branch>
  <base_branch>base ref</base_branch>
  <pr_url>full URL</pr_url>
  <loop>N</loop>
  <pr_number>N</pr_number>
  <worktree_path>absolute path from Step 1 per-PR workspace</worktree_path>
</context>

cd into `<worktree_path>` before any git, gh, or file operation.

<scope>
  <diff_path>Absolute path to the per-PR patch file: <team_temp_dir>/pr-<N>/loop-<L>.patch (same path as gh pr diff redirect in AUDIT)</diff_path>
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

<comment_posting>
  1. Audit the diff against the 10 categories above. Buffer the findings
     in memory; all posting happens at step 6 once anchors are validated.
  2. Assign each finding a stable finding_id of exactly the form `loopN-K`
     where K is 1-based within this loop.
  3. Validate every finding's (file, line) against the captured diff. Split
     findings into two buckets: anchored (line is in the diff) and
     unanchored (line is not in the diff — goes into the review body's
     "Findings without a diff anchor" section per Step 2.5).
  4. Build the review body per Step 2.5's review-body shape, filling in the
     P0/P1/P2 counts and the unanchored-findings list (if any).
  5. For each anchored finding, write its body to its own temp file:

       **[severity] one-line title**
       Category: <letter> (<category name>)
       <2-3 sentence description with concrete trace>

       _From /bugteam audit loop N._

  6. Post ONE review via Step 2.5's per-loop review CLI shape. Harvest the
     parent review `html_url` from the response JSON and the `comments[]`
     child entries (each with its own `id` and `html_url`). Match child
     entries to anchored findings in index order.
  7. If the review POST itself fails, use Step 2.5's Review POST failure
     fallback (single issue comment with full body and all findings inline).
  8. Write every body (review body, each finding body, any fallback body)
     to its own temp file. Load each file into the JSON payload via jq's
     `--rawfile` or `-Rs`, then pipe the jq output to `gh api ... --input -`
     so every body reaches GitHub as file contents inside the JSON payload.
</comment_posting>

<output_format>
  Write the outcome XML below to .bugteam-pr<N>-loop<L>.outcomes.xml inside
  the PR's worktree directory (<worktree_path>). Return only that path on stdout. The schema:
</output_format>
```

## AUDIT outcome XML schema (bugfind writes this)

```xml
<bugteam_audit loop="<N>" review_url="<url>">
  <finding
    finding_id="loop<N>-<index>"
    severity="P0|P1|P2"
    category="<letter>"
    file="<path>"
    line="<int>"
    finding_comment_id="<gh child comment id, or empty if unanchored/review-fallback>"
    finding_comment_url="<url of child comment, OR review_url if unanchored, OR fallback issue comment URL>"
    used_fallback="true|false"
  >
    <title>one-line title</title>
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
  <loop>N</loop>
  <pr_number>N</pr_number>
  <worktree_path>absolute path from Step 1 per-PR workspace</worktree_path>
</context>

cd into `<worktree_path>` before any git, gh, or file operation.

<bugs_to_fix>
  [for each P0/P1/P2 finding from last_findings:]
  <bug
    finding_id="loop<N>-<index>"
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
  <bugteam_fix loop="<N>" commit_sha="<sha or empty if no commit>">
    <outcome
      finding_id="loop<N>-<index>"
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
