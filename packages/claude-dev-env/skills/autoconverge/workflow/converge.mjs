/**
 * Autoconverge convergence-loop workflow driver.
 *
 * SINGLE-FILE CONTRACT — keep this file self-contained. The Workflow runtime
 * wraps this body in a function (so top-level await and return work) and rejects
 * static import statements, and `export const meta` must be the first statement.
 * Every decision and prompt helper lives here as a local function; a sibling
 * import makes the workflow unlaunchable, so keep helpers inline even when file
 * length suggests a split.
 */

export const meta = {
  name: 'autoconverge',
  description: 'Drive one draft PR to convergence in a single autonomous run: parallel Bugbot + code-review + bug-audit lenses on the same HEAD each round, dedup findings, fix once, re-verify, then a Copilot wait-gate and a final convergence check that marks the PR ready.',
  whenToUse: 'Launched by the /autoconverge skill after it resolves PR scope, enters a worktree, and grants project .claude permissions.',
  phases: [
    { title: 'Reuse', detail: 'Before convergence, one reuse lens scans the full diff for reuse improvements that are certain, behaviorally identical, and autonomously implementable, and applies the qualifying ones in one commit' },
    { title: 'Converge', detail: 'Bugbot + code-review + bug-audit in parallel each round; one clean-coder applies all fixes; loop until all three are clean on a stable HEAD' },
    { title: 'Copilot gate', detail: 'When the quota pre-check reports Copilot out of premium-request quota or unavailable, skip the gate with no agent spawned; otherwise request a Copilot review and poll up to three times, route findings back into Converge, and when Copilot is down or out of quota log a notice and mark the PR ready with the gate bypassed' },
    { title: 'Finalize', detail: 'Run check_convergence.py; mark draft=false on a full pass' },
  ],
}

const CONFIG = {
  maxIterations: 20,
  copilotMaxPolls: 8,
  sharedScripts: '$HOME/.claude/skills/pr-converge/scripts',
  prLoopScripts: '$HOME/.claude/_shared/pr-loop/scripts',
  bugteamRubric: '$HOME/.claude/skills/bugteam/reference/audit-contract.md',
}

const HEADLESS_SAFETY_PREAMBLE =
  'HEADLESS RUN — you run unattended: no human can answer a permission or confirmation prompt, and any such prompt stalls the entire convergence run. The destructive_command_blocker hook matches dangerous patterns (rm -rf, git reset --hard, dd, mkfs, chmod -R, fork bombs) as raw text anywhere in a Bash command, with no quote-awareness — so a destructive string stalls you even when it is only data you never execute. Therefore:\n' +
  '- Never place a destructive-command literal inside a Bash command — not in echo, not in a heredoc, and not as an argument to python -c, node -e, or awk. To exercise or verify destructive_command_blocker (or any hook) behavior, run the committed test suite, e.g. python -m pytest <test_file>, which passes the command strings as in-language data rather than as a shell command.\n' +
  '- When a commit message, or a PR / issue / review-comment body, must describe destructive-command behavior, write that text to a file and pass it by path (git commit -F <file>, gh ... --body-file <file>); never inline it with git commit -m or gh ... -b, where the literal lands in the Bash command and stalls you.\n' +
  '- Keep scratch files and cleanup inside the OS temp dir; never target a repository or worktree path.\n' +
  '- rm shape rules — the hook grants several rm auto-allow paths. The simplest one accepts a standalone Bash call whose target resolves inside the ephemeral namespace (/tmp, /temp, the OS temp root, or the run worktree); a compound path accepts an rm joined with benign reporting segments when every rm target is an absolute ephemeral path. Both of those paths fail closed on $(...) command substitution and on backtick subshells. The compound path additionally fails closed on any $ in the target — including $CLAUDE_JOB_DIR. The standalone path declines a $-bearing target only when the literal path is not already under an ephemeral root, so it does not by itself stop a $VAR that expands inside an ephemeral root. A third, broad path matches only when the command itself declares an ephemeral working directory (it cds into one, or runs under one): that cwd-scoped path resolves the target against the declared cwd, fails closed on $(...) , backticks, and unknown variables, and resolves the known temporary variables TEMP, TMP, TMPDIR, and CLAUDE_JOB_DIR to the OS temp root, so under that declared ephemeral cwd a bare $CLAUDE_JOB_DIR/tmp/<name> target and a relative target after a cd are auto-allowed. Even so, prefer a Python helper for any cleanup whose path is variable-built or whose setup/teardown spans multiple steps: author the helper file and run it as python <file>.py, which keeps every destructive literal out of a Bash command string entirely and never depends on which auto-allow path matches.\n' +
  '- If a step appears to require a real destructive command, use a non-destructive equivalent or report it as a blocker instead of running it.\n\n'

let activeRepoPath = null

/**
 * Build the per-agent worktree directive for a path-scoped run.
 *
 * A multi-PR parent run drives several converge children from one shared
 * working directory, so each child pins its own agents to the worktree its PR
 * is checked out in; without that pin every child's git, gh, diff, edit,
 * commit, and test commands would run in the shared launch directory rather
 * than the PR's own checkout. The parent hands the worktree path in as
 * input.repoPath, which sets activeRepoPath. A single-PR run carries no
 * repoPath, so this returns an empty string and every agent keeps its own
 * working directory — behavior identical to a run with no path scoping.
 * @param {string|null} repoPath the PR worktree absolute path, or null for the single-PR default
 * @returns {string} the worktree directive to prepend, or an empty string when repoPath is null
 */
const worktreeDirective = (repoPath) =>
  repoPath
    ? `WORKTREE — this PR is checked out at ${repoPath}. Unless a step explicitly names a different repository directory (for example an environment-hardening repo checkout, which you cd into exactly as that step directs), run every git, gh, diff, edit, commit, push, and test command for this PR in that worktree: cd "${repoPath}" before any such command, and resolve repository roots from there.\n\n`
    : ''

/**
 * Spawn a workflow agent with the headless-safety preamble prepended to its
 * prompt. Every agent in this convergence loop runs unattended, so each one is
 * routed through here to inherit the same no-confirmation-prompt guidance. On a
 * path-scoped run the worktree directive is prepended too, so every agent runs
 * in the PR's own worktree (activeRepoPath); on a single-PR run that directive
 * is empty and the agent keeps its own working directory.
 * @param {string} prompt the agent's role-specific instruction body
 * @param {object} options the agent() options (label, phase, schema, agentType, model)
 * @returns {Promise<*>} the agent() result
 */
const convergeAgent = (prompt, options) =>
  agent(`${HEADLESS_SAFETY_PREAMBLE}${worktreeDirective(activeRepoPath)}${prompt}`, options)

/**
 * Spawn a fresh git-utility Explore agent for a specific task. 'resolve-head'
 * prints the PR HEAD SHA, 'prefetch-main' fetches origin main so the review
 * lenses diff against an up-to-date base, and any other task reports whether the
 * branch has merge conflicts. The agent never edits code.
 * @param {string} task the short task name
 * @param {string} head optional HEAD SHA for conflict checks
 * @returns {Promise<object|string>} the structured output, or the transcript string when the 'prefetch-main' resume runs schema-less
 */
function runGitTask(task, head) {
  if (task === 'resolve-head') {
    return convergeAgent(
      `Print the current HEAD SHA of ${prCoordinates}. Run exactly:\n` +
        `gh api repos/${input.owner}/${input.repo}/pulls/${input.prNumber} --jq .head.sha\n` +
        `Return the full 40-character SHA in the sha field. Do not modify any files.`,
      { label: 'git-utility', phase: 'Converge', schema: HEAD_SCHEMA, agentType: 'Explore' },
    )
  }
  if (task === 'prefetch-main') {
    return convergeAgent(
      `Refresh the base ref for ${prCoordinates} so the parallel review lenses can diff against an up-to-date origin/main without each running its own fetch. Run exactly:\n` +
        `git fetch origin main\n` +
        `Do not edit, commit, push, rebase, or modify any files — fetch only.`,
      { label: 'git-utility', phase: 'Converge', agentType: 'Explore' },
    )
  }
  return convergeAgent(
    `Report whether ${prCoordinates} (HEAD ${head}) has merge conflicts with its base branch. Do not edit, commit, push, or rebase — read only.\n\n` +
      `GitHub computes mergeability asynchronously, so .mergeable is null right after a push until it finishes. Poll until it resolves: run\n` +
      `   gh api repos/${input.owner}/${input.repo}/pulls/${input.prNumber} --jq '{mergeable: .mergeable, state: .mergeable_state}'\n` +
      `up to 5 times, 5 seconds apart (delay each retry with "sleep 5", or the PowerShell alternative "Start-Sleep -Seconds 5"), stopping as soon as mergeable is true or false.\n\n` +
      `Return conflicting:true when mergeable is false or state is "dirty" (the branch conflicts with the base). Return conflicting:false when mergeable is true, or when mergeable stays null after the full poll budget — mergeability is unknown, so let the bug checks proceed rather than rebase on a guess.`,
    { label: 'git-utility', phase: 'Converge', schema: MERGE_CONFLICT_SCHEMA, agentType: 'Explore' },
  )
}

/**
 * Spawn a fresh fixer clean-coder agent for a commit or recovery edit. The fixer
 * never verifies; a separate verifier agent emits the verdict, so the verdict
 * that gates the commit comes from a different agent than the one that commits
 * and recovers.
 * @param {string} task the short task name
 * @param {object} context task-specific context
 * @returns {Promise<object>} the structured output
 */
function runFixerTask(task, context) {
  const label = `fixer:${context.sourceLabel}`
  if (task === 'commit') {
    return convergeAgent(
      `You are the COMMIT step for fixes (${context.sourceLabel}) on ${prCoordinates}, HEAD ${context.head}. The edit step left fixes in the working tree and the verify step passed, so a verifier verdict already binds to this exact working tree.\n\n` +
        `Rules:\n` +
        `- Make NO further file edits of any kind. Any edit changes the surface and invalidates the verdict that unlocks the commit gate, so the commit would be blocked. Do not run a formatter, do not touch a test, do not re-fix anything — only commit and push what is already there.\n` +
        `- Make ONE commit for all the working-tree fixes, then push to the PR branch.\n\n` +
        `Return values:\n` +
        `- On a successful push: newSha=the new HEAD SHA after your push, pushed=true, resolvedWithoutCommit=false, blockedNeedingEdit=false, blockerDetail="", and a one-line summary.\n` +
        `- When a commit-time hook or gate (for example code_rules_gate, the CODE_RULES commit gate) rejects the commit because the fix needs a code change: keep the no-edit rule, return newSha=${context.head}, pushed=false, resolvedWithoutCommit=false, blockedNeedingEdit=true, blockerDetail=<the verbatim hook message naming the file and rule>, and a summary. A recovery fixer runs after you to clear it.\n` +
        `- On a transient or non-code failure (auth, network, a non-fast-forward, a lock): newSha=${context.head}, pushed=false, resolvedWithoutCommit=false, blockedNeedingEdit=false, blockerDetail="", and a summary naming the failure.`,
      { label, phase: 'Converge', schema: FIX_SCHEMA, agentType: 'clean-coder' },
    )
  }
  if (task === 'commit-recover') {
    const attempt = context.attempt || 1
    return convergeAgent(
      `You are the COMMIT-RECOVERY fixer (attempt ${attempt}) for fixes (${context.sourceLabel}) on ${prCoordinates}, HEAD ${context.head}. A prior commit step was blocked by a commit-time hook or gate that requires a code change. A separate verify step then a separate commit step run after you.\n\n` +
        `The blocking hook or gate said:\n${context.blockerDetail}\n\n` +
        `Rules:\n` +
        `- Confirm the working tree is on the PR branch at HEAD ${context.head} with the prior fixes still present.\n` +
        `- Fix ONLY the violation named above, test-first (failing test, then minimum code to pass) per CODE_RULES. Do not re-open the original findings, and do not touch GitHub review threads — the edit step already handled those.\n` +
        `- Leave the corrected fixes in the working tree. Do NOT commit and do NOT push — the verify step re-binds a verdict and the commit step pushes after you.\n\n` +
        `Return values: edited=true with a one-line summary when you changed code to clear the block; edited=false, resolvedWithoutCommit=false when the block cannot be cleared with a code change.` +
        PRE_COMMIT_GATE_STEP,
      { label, phase: 'Converge', schema: EDIT_SCHEMA, agentType: 'clean-coder' },
    )
  }
  const objection = context.objection || VERIFY_OBJECTION_FALLBACK
  const attempt = context.attempt || 1
  return convergeAgent(
    `You are the VERIFY-RECOVERY fixer (attempt ${attempt}) for fixes (${context.sourceLabel}) on ${prCoordinates}, HEAD ${context.head}. The verify step rejected the working-tree fixes; its verdict named what is still unresolved. A separate verify step then a separate commit step run after you.\n\n` +
      `The verify step's objections:\n${objection}\n\n` +
      `Rules:\n` +
      `- Confirm the working tree is on the PR branch at HEAD ${context.head} with the prior fixes still present.\n` +
      `- Address every objection above test-first (failing test, then minimum code to pass) per CODE_RULES, so each named concern is genuinely resolved the way the verdict requires. Do not touch GitHub review threads — the edit step already handled those.\n` +
      `- Leave the corrected fixes in the working tree. Do NOT commit and do NOT push — the verify step re-binds a verdict and the commit step pushes after you.\n\n` +
      `Return values: edited=true with a one-line summary when you changed code to address the objections; edited=false, resolvedWithoutCommit=false when the objections cannot be cleared with a code change.` +
      PRE_COMMIT_GATE_STEP,
    { label, phase: 'Converge', schema: EDIT_SCHEMA, agentType: 'clean-coder' },
  )
}

/**
 * Joined fixer recovery loop: the verify step spawns a code-verifier agent to
 * grade the working-tree fixes while the commit and recovery steps spawn
 * clean-coder fixer agents, so the verdict that gates the commit comes from a
 * different agent than the one that edits and pushes — the same editor/verifier
 * separation the repair and conflict paths use. The verify step routes through
 * verifyWithRecovery (verify on the verifier, recover on the fixer); the commit
 * step routes through commitWithRecovery (commit and commit-recover on the fixer,
 * re-verify on the verifier). A failed verdict returns the unchanged HEAD so the
 * round reads as not-progressed.
 * @param {string} head PR HEAD SHA
 * @param {Array<object>} findings the findings to fix
 * @param {string} sourceLabel short description of where the findings came from
 * @returns {Promise<object>} FIX_SCHEMA result
 */
async function fixerWithRecovery(head, findings, sourceLabel) {
  const verifyTranscript = await verifyWithRecovery({
    runVerify: () => runVerifierTask('fix-verify', { head, findings, sourceLabel }),
    runRecoverEdit: (objection, attempt) => runFixerTask('verify-recover', { head, findings, sourceLabel, objection, attempt }),
  })
  if (!verdictPassed(verifyTranscript)) {
    return {
      newSha: head,
      pushed: false,
      resolvedWithoutCommit: false,
      summary: `verify step did not pass the working-tree fixes for ${findings.length} finding(s) — not committing`,
      blockedNeedingEdit: false,
      blockerDetail: '',
    }
  }
  return commitWithRecovery({
    runCommit: () => runFixerTask('commit', { head, findings, sourceLabel }),
    runVerify: () => runVerifierTask('fix-verify', { head, findings, sourceLabel }),
    runRecoverEdit: (detail, attempt) => runFixerTask('commit-recover', { head, findings, sourceLabel, blockerDetail: detail, attempt }),
  })
}

/**
 * Spawn a fresh code-editor clean-coder agent for a specific edit task (fix-edit,
 * conflict-edit, repair-edit, repair-commit, standards-edit,
 * standards-resolve-threads, hardening-commit, commit-recover, verify-recover).
 * Each task carries its own edit instructions.
 * @param {string} task the short task name
 * @param {object} context task-specific context
 * @returns {Promise<object|string>} the structured output, or the transcript string when a schema-less task ('standards-resolve-threads') runs
 */
function runCodeEditorTask(task, context) {
  const label = `code-editor:${task}`
  if (task === 'fix-edit') {
    const findingsBlock = renderFindingsBlock(context.findings)
    const threadIds = context.findings
      .flatMap((each) => collectFindingThreadIds(each))
      .filter((each) => typeof each === 'number')
    return convergeAgent(
      `You are the EDIT step fixing ${context.findings.length} finding(s) (${context.sourceLabel}) on ${prCoordinates}, HEAD ${context.head}. A separate verify step then a separate commit step run after you.\n\n` +
        `Findings:\n${findingsBlock}\n\n` +
        `Rules:\n` +
        `- Confirm the working tree is on the PR branch at HEAD ${context.head} with no unrelated edits before you start.\n` +
        `- Fix every finding test-first (failing test, then minimum code to pass) per CODE_RULES. Verify each concern against current code; a finding whose concern no longer applies needs no code change but still needs its thread resolved.\n` +
        `- Leave all fixes in the working tree. Do NOT commit and do NOT push — the commit step does that after verification. Committing or pushing here would change the surface the verifier binds to.\n` +
        `- For each finding that carries a GitHub review comment id (${threadIds.length ? threadIds.join(', ') : 'none this batch'}): post an inline reply with python "${CONFIG.sharedScripts}/post_fix_reply.py" --owner ${input.owner} --repo ${input.repo} --pr-number ${input.prNumber} --in-reply-to <id> --body "<what changed>". Then resolve the PR review thread by thread node id (PRRT_...): look up the thread id for that comment via GraphQL (match on comment databaseId == <id> in the pull request's reviewThreads), then call the github MCP pull_request_review_write method=resolve_thread with threadId=<PRRT_...> (not the numeric comment id), or run the resolveReviewThread GraphQL mutation with the same threadId.\n` +
        `- Findings with replyToCommentId null are in-memory audit findings: fix them, no reply needed.\n\n` +
        `Return values:\n` +
        `- When you edited code to fix at least one finding: edited=true, resolvedWithoutCommit=false.\n` +
        `- When every finding was already addressed so no code change was needed — yet you still resolved each GitHub review thread above: edited=false, resolvedWithoutCommit=true. Only set this when every thread that carries a comment id is resolved; otherwise the round is treated as stalled.\n` +
        `Always include a one-line summary.` +
        PRE_COMMIT_GATE_STEP,
      { label, phase: 'Converge', schema: EDIT_SCHEMA, agentType: 'clean-coder' },
    )
  }
  if (task === 'conflict-edit') {
    return convergeAgent(
      `You are the EDIT step resolving merge conflicts for ${prCoordinates}, HEAD ${context.head}, before the bug checks run. The PR branch conflicts with origin/main. A separate verify step then a separate commit step run after you.\n\n` +
        `Rules:\n` +
        `- Confirm the working tree is on the PR branch at HEAD ${context.head} with no unrelated edits before you start.\n` +
        `- Rebase the branch onto origin/main and resolve every conflict so the tree is clean and conflict-free: git fetch origin main; git rebase origin/main; resolve each conflict, preserving the intent of both the PR's change and the incoming base change. A rebase creates local commits, which is fine.\n` +
        `- Do NOT push and do NOT force-push — the commit step force-pushes after the verify step binds a verdict. Pushing here would change the surface the verifier binds to.\n\n` +
        `Return rebased=true with a one-line summary when you rebased onto origin/main and resolved the conflicts; rebased=false with a summary when the branch did not actually need a rebase or you could not complete it.`,
      { label, phase: 'Converge', schema: CONFLICT_EDIT_SCHEMA, agentType: 'clean-coder' },
    )
  }
  if (task === 'repair-edit') {
    const failureBlock = context.failures.length
      ? context.failures.map((each, position) => `${position + 1}. ${each}`).join('\n')
      : 'none reported'
    return convergeAgent(
      `You are the EDIT step repairing the convergence gates that failed for ${prCoordinates} on HEAD ${context.head}. A separate verify step then a separate commit step run after you.\n\n` +
        `Failing gates:\n${failureBlock}\n\n` +
        `Address only the failing gates, and make NO commit and NO push — leave every code change in the working tree (a rebase necessarily creates local commits, which is fine; just do not push them):\n` +
        `- Unresolved bot review threads: fetch the threads where isResolved is false (gh api graphql, or the github MCP pull_request_read get_review_comments), then keep only the bot-authored ones — a thread whose root comment author login contains "cursor", "claude", or "copilot" (case-insensitive substring). Explicitly skip every human reviewer thread; the convergence gate counts only unresolved bot threads, so touching a human thread is out of scope. For each bot thread, verify the concern against current code; if it still applies, fix it test-first in the working tree and leave the fix uncommitted; either way post an inline reply and resolve the thread by its PRRT_ node id (GraphQL lookup matching the comment databaseId, then resolveReviewThread or the github MCP pull_request_review_write method=resolve_thread — not the numeric comment id).\n` +
        `- PR not mergeable: rebase onto origin/main FIRST, before applying any uncommitted bot-thread fix, so the rebase runs on a clean tree (git fetch origin main; git rebase origin/main; resolve conflicts). Do NOT force-push — the commit step does that after verification.\n` +
        `- A dirty bot review or a still-pending requested reviewer: leave it; the next round re-runs that reviewer.\n\n` +
        `Return values:\n` +
        `- edited=true when you changed code in the working tree to fix a bot-thread concern.\n` +
        `- rebased=true when you rebased the branch onto origin/main.\n` +
        `- resolvedWithoutCommit=true only when you addressed the gates with neither a code change nor a rebase (bot threads resolved only), so there is nothing for the commit step to push.\n` +
        `Always include a one-line summary.` +
        PRE_COMMIT_GATE_STEP,
      { label, phase: 'Finalize', schema: REPAIR_EDIT_SCHEMA, agentType: 'clean-coder' },
    )
  }
  if (task === 'repair-commit') {
    const pushInstruction = context.wasRebased
      ? 'The edit step rebased the branch, so push with git push --force-with-lease.'
      : 'Push to the PR branch with a plain git push.'
    return convergeAgent(
      `You are the COMMIT step for the convergence repair on ${prCoordinates}, HEAD ${context.head}. The edit step left its repair in the working tree and the verify step passed, so a verifier verdict already binds to this exact working tree.\n\n` +
        `Rules:\n` +
        `- Make NO further file edits of any kind. Any edit changes the surface and invalidates the verdict that unlocks the commit gate, so the push would be blocked. Do not run a formatter, do not re-fix anything — only commit and push what is already there.\n` +
        `- Commit any uncommitted bot-thread fix in ONE commit (skip the commit when the working tree carries only already-committed rebase results). ${pushInstruction}\n\n` +
        `Return values:\n` +
        `- On a successful push: newSha=the new HEAD SHA after your push, pushed=true, resolvedWithoutCommit=false, blockedNeedingEdit=false, blockerDetail="", and a one-line summary.\n` +
        `- When a commit-time hook or gate (for example code_rules_gate, the CODE_RULES commit gate) rejects the commit because the fix needs a code change: keep the no-edit rule, return newSha=${context.head}, pushed=false, resolvedWithoutCommit=false, blockedNeedingEdit=true, blockerDetail=<the verbatim hook message naming the file and rule>, and a summary. A recovery fixer runs after you to clear it.\n` +
        `- On a transient or non-code failure (auth, network, a non-fast-forward, a lock): newSha=${context.head}, pushed=false, resolvedWithoutCommit=false, blockedNeedingEdit=false, blockerDetail="", and a summary naming the failure.`,
      { label, phase: 'Finalize', schema: FIX_SCHEMA, agentType: 'clean-coder' },
    )
  }
  if (task === 'standards-edit') {
    const findingsBlock = renderFindingsBlock(context.findings)
    const threadIds = context.findings
      .flatMap((each) => collectFindingThreadIds(each))
      .filter((each) => typeof each === 'number')
    return convergeAgent(
      `You are the EDIT step deferring a code-standard-only round on ${prCoordinates}, HEAD ${context.head} (${context.sourceLabel}). The round surfaced ONLY code-standard violations (CODE_RULES/style, no behavioral impact); the run treats it as passed and defers the fixes to follow-up work, which you now stage. A separate verify step then a separate commit step open the hardening PR after you. Do NOT commit or push to the PR's own branch.\n\n` +
        `Findings:\n${findingsBlock}\n\n` +
        `1. Follow-up fix issue: file a GitHub issue on ${input.owner}/${input.repo} (gh issue create --body-file with a temp file) titled "Deferred code-standard fixes from PR #${input.prNumber}". The body references the PR and lists each finding with its file:line, severity, and detail. The issue carries the fix work; do not open a fix PR. Capture the issue URL.\n` +
        `2. Stage the environment-hardening change: in the Claude environment config repo (the repo owning ~/.claude hooks and rules — JonEcho/llm-settings for hooks, jl-cmd/claude-code-config for rules/skills; pick whichever owns the surface that would block these violation classes), find or clone a local checkout, fetch origin, and create a branch off origin/main. Edit the hooks/rules in that checkout's WORKING TREE so each violation class found here is blocked at Write/Edit time, before code is written. Do NOT commit and do NOT push — the commit step does that after the verify step binds a verdict to the working tree. Return the checkout's absolute path in hardeningRepoPath, the branch name in hardeningBranch, and set hardeningEdited=true. When no hardening is feasible for these classes, leave hardeningRepoPath and hardeningBranch empty and hardeningEdited=false; the follow-up issue still stands.\n` +
        `3. For each finding that carries a GitHub review comment id (${threadIds.length ? threadIds.join(', ') : 'none this batch'}): post an inline reply via python "${CONFIG.sharedScripts}/post_fix_reply.py" --owner ${input.owner} --repo ${input.repo} --pr-number ${input.prNumber} --in-reply-to <id> --body "Code-standard-only finding — deferred to follow-up issue <url>." Then resolve the thread by its PRRT_ node id (GraphQL lookup on comment databaseId, then resolveReviewThread or the github MCP pull_request_review_write method=resolve_thread — not the numeric comment id).\n\n` +
        `Return the issue URL in issueUrl (empty string when it could not be filed), the hardening checkout path and branch, hardeningEdited, and a one-line summary.` +
        PRE_COMMIT_GATE_STEP,
      { label, phase: 'Converge', schema: STANDARDS_EDIT_SCHEMA, agentType: 'clean-coder' },
    )
  }
  if (task === 'standards-resolve-threads') {
    const findingsBlock = renderFindingsBlock(context.findings)
    const threadIds = context.findings
      .flatMap((each) => collectFindingThreadIds(each))
      .filter((each) => typeof each === 'number')
    return convergeAgent(
      `You are the THREAD-RESOLUTION step for a code-standard-only round on ${prCoordinates}, HEAD ${context.head} (${context.sourceLabel}). This run already filed the deferred-fix follow-up issue ${context.issueUrl}, so this batch's code-standard findings defer to that same issue. Make NO code edits, NO commit, and NO push — only reply to and resolve the review threads this batch carries.\n\n` +
        `Findings:\n${findingsBlock}\n\n` +
        `For each finding that carries a GitHub review comment id (${threadIds.length ? threadIds.join(', ') : 'none this batch'}): post an inline reply via python "${CONFIG.sharedScripts}/post_fix_reply.py" --owner ${input.owner} --repo ${input.repo} --pr-number ${input.prNumber} --in-reply-to <id> --body "Code-standard-only finding — deferred to follow-up issue ${context.issueUrl}." Then resolve the thread by its PRRT_ node id (GraphQL lookup on comment databaseId, then resolveReviewThread or the github MCP pull_request_review_write method=resolve_thread — not the numeric comment id).\n\n` +
        `Return a one-line summary naming the threads you resolved.`,
      { label, phase: 'Converge', agentType: 'clean-coder' },
    )
  }
  if (task === 'hardening-commit') {
    return convergeAgent(
      `You are the COMMIT step opening the environment-hardening PR (${context.sourceLabel}) for the change staged in ${context.hardeningRepoPath} on branch ${context.hardeningBranch}. The edit step left the hooks/rules edits in the working tree and the verify step passed, so a verifier verdict already binds to this exact working tree. Do NOT touch the PR's own branch.\n\n` +
        `Rules:\n` +
        `- Make NO further file edits of any kind. Any edit changes the surface and invalidates the verdict that unlocks the commit gate, so the push would be blocked. Only commit and push what is already there.\n` +
        `- In ${context.hardeningRepoPath}: make ONE commit of the staged hooks/rules change on branch ${context.hardeningBranch}, push it, then open a DRAFT PR. The PR body references the follow-up issue ${context.issueUrl || '(none)'} and states the PR hardens the environment so the deferred violation classes are blocked at Write/Edit time. Honor the gh-body-file rule: write a BOM-free temp file and pass --body-file.\n` +
        `- Title the PR as a Conventional Commit — a type prefix (feat, fix, chore, docs, refactor, perf, ci, style, test, build, revert), an optional scope in parentheses, then a colon and a short summary, e.g. "feat(hooks): block the deferred violation class". The target repo's CI validates the PR title as a semantic commit and rejects a non-conforming title.\n\n` +
        `Return the full https URL of the DRAFT hardening PR in hardeningPrUrl (empty string when no PR was opened) and a one-line summary.`,
      { label, phase: 'Converge', schema: HARDENING_COMMIT_SCHEMA, agentType: 'clean-coder' },
    )
  }
  if (task === 'commit-recover') {
    const attempt = context.attempt || 1
    return convergeAgent(
      `You are the COMMIT-RECOVERY fixer (attempt ${attempt}) for fixes (${context.sourceLabel}) on ${prCoordinates}, HEAD ${context.head}. A prior commit step was blocked by a commit-time hook or gate that requires a code change. A separate verify step then a separate commit step run after you.\n\n` +
        `The blocking hook or gate said:\n${context.blockerDetail}\n\n` +
        `Rules:\n` +
        `- Confirm the working tree is on the PR branch at HEAD ${context.head} with the prior fixes still present.\n` +
        `- Fix ONLY the violation named above, test-first (failing test, then minimum code to pass) per CODE_RULES. Do not re-open the original findings, and do not touch GitHub review threads — the edit step already handled those.\n` +
        `- Leave the corrected fixes in the working tree. Do NOT commit and do NOT push — the verify step re-binds a verdict and the commit step pushes after you.\n\n` +
        `Return values: edited=true with a one-line summary when you changed code to clear the block; edited=false, resolvedWithoutCommit=false when the block cannot be cleared with a code change.` +
        PRE_COMMIT_GATE_STEP,
      { label, phase: 'Converge', schema: EDIT_SCHEMA, agentType: 'clean-coder' },
    )
  }
  // verify-recover
  const attempt = context.attempt || 1
  const objection = context.objection || VERIFY_OBJECTION_FALLBACK
  return convergeAgent(
    `You are the VERIFY-RECOVERY fixer (attempt ${attempt}) for fixes (${context.sourceLabel}) on ${prCoordinates}, HEAD ${context.head}. The verify step rejected the working-tree fixes; its verdict named what is still unresolved. A separate verify step then a separate commit step run after you.\n\n` +
      `The verify step's objections:\n${objection}\n\n` +
      `Rules:\n` +
      `- Confirm the working tree is on the PR branch at HEAD ${context.head} with the prior fixes still present.\n` +
      `- Address every objection above test-first (failing test, then minimum code to pass) per CODE_RULES, so each named concern is genuinely resolved the way the verdict requires. Do not touch GitHub review threads — the edit step already handled those.\n` +
      `- Leave the corrected fixes in the working tree. Do NOT commit and do NOT push — the verify step re-binds a verdict and the commit step pushes after you.\n\n` +
      `Return values: edited=true with a one-line summary when you changed code to address the objections; edited=false, resolvedWithoutCommit=false when the objections cannot be cleared with a code change.` +
      PRE_COMMIT_GATE_STEP,
    { label, phase: 'Converge', schema: EDIT_SCHEMA, agentType: 'clean-coder' },
  )
}

/**
 * Spawn a fresh verifier code-verifier agent for a specific verify task
 * (fix-verify, repair-verify, hardening-verify). The agent makes no edits —
 * verification only — and ends its message with a fenced verdict block.
 * @param {string} task the short task name
 * @param {object} context task-specific context
 * @returns {Promise<string>} the verifier transcript carrying the verdict fence
 */
function runVerifierTask(task, context) {
  const label = `verifier:${task}`
  if (task === 'fix-verify') {
    const findingsBlock = renderFindingsBlock(context.findings)
    return convergeAgent(
      `You are the VERIFY step for ${context.findings.length} finding(s) (${context.sourceLabel}) on ${prCoordinates}, HEAD ${context.head}. The edit step left fixes in the working tree, uncommitted. Do NO edits of any kind — verification only; any edit invalidates the verdict you are about to emit.\n\n` +
        `Findings the working-tree fixes must address:\n${findingsBlock}\n\n` +
        `Steps:\n` +
        `1. Resolve the worktree repo root for running tests: REPO=$(git rev-parse --show-toplevel).\n` +
        `2. Verify the uncommitted working-tree changes resolve every finding above: run the relevant tests and the named gates against the working tree. Read the diff (git diff) and confirm each finding is fixed test-first per CODE_RULES.\n` +
        `3. ${buildVerdictFenceSteps(input.owner, input.repo, input.prNumber)}`,
      { label, phase: 'Converge', agentType: 'code-verifier' },
    )
  }
  if (task === 'repair-verify') {
    const failureBlock = context.failures.length
      ? context.failures.map((each, position) => `${position + 1}. ${each}`).join('\n')
      : 'none reported'
    return convergeAgent(
      `You are the VERIFY step for the convergence repair on ${prCoordinates}, HEAD ${context.head}. The edit step left its repair in the working tree (a bot-thread fix uncommitted, and/or a rebase onto origin/main), unpushed. Do NO edits of any kind — verification only; any edit invalidates the verdict you are about to emit.\n\n` +
        `Concerns the working-tree repair must resolve (the gates the convergence check flagged):\n${failureBlock}\n\n` +
        `Steps:\n` +
        `1. Resolve the worktree repo root for running tests: REPO=$(git rev-parse --show-toplevel).\n` +
        `2. Verify the working tree against origin/main: any bot-thread code fix is correct test-first per CODE_RULES, and a rebase (if any) left a clean, conflict-free tree. Read the diff (git diff origin/main) and run the relevant tests and named gates.\n` +
        `3. ${buildVerdictFenceSteps(input.owner, input.repo, input.prNumber)}`,
      { label, phase: 'Finalize', agentType: 'code-verifier' },
    )
  }
  return convergeAgent(
    `You are the VERIFY step for an environment-hardening change (${context.sourceLabel}) staged in the working tree of ${context.hardeningRepoPath}. The edit step left the hooks/rules edits uncommitted there. Do NO edits of any kind — verification only; any edit invalidates the verdict you are about to emit.\n\n` +
      `Concern the working-tree change must resolve: the edited hooks/rules block the code-standard violation classes from the deferred round at Write/Edit time, and a hook change carries a passing test per CODE_RULES.\n\n` +
      `Steps:\n` +
      `1. cd into ${context.hardeningRepoPath}, then resolve its repo root: REPO=$(git rev-parse --show-toplevel).\n` +
      `2. Verify the uncommitted working-tree change in REPO: read the diff (git diff) and run the hook/rule tests in that repo, confirming each violation class is now blocked.\n` +
      `3. Compute the binding hash for the live surface:\n` +
      `   The hardening branch is: ${context.hardeningBranch}\n` +
      `   Run exactly:\n` +
      `      "C:\\Python313\\python.exe" "<REPO>/packages/claude-dev-env/hooks/blocking/verification_verdict_store.py" --manifest-hash-for-branch "${context.hardeningBranch}"\n` +
      `   (substitute the REPO path you resolved for the script path). That prints a single 64-char hex hash on stdout — capture it.\n` +
      `   Then END your message with a fenced verdict block exactly in this shape, on its own, carrying that hash:\n` +
      "      ```verdict\n" +
      `      {"all_pass": true, "findings": [], "manifest_sha256": "<that hash>"}\n` +
      "      ```\n" +
      `      When verification fails, set all_pass to false and list the unresolved concerns in findings; still include the manifest_sha256. The verdict fence must be the last thing in your message.`,
    { label, phase: 'Converge', agentType: 'code-verifier' },
  )
}

/**
 * Spawn a fresh general-utility general-purpose agent for one of its two
 * administrative tasks: 'post-clean-audit' posts the terminal CLEAN bugteam
 * review, and 'mark-ready' marks the PR ready and confirms it left draft state.
 * The agent edits no code.
 * @param {'post-clean-audit'|'mark-ready'} task the short task name
 * @param {object} context task-specific context
 * @returns {Promise<object>} the task result
 */
function runGeneralUtilityTask(task, context) {
  const label = `general-utility:${task}`
  if (task === 'post-clean-audit') {
    return convergeAgent(
      `Post a CLEAN bugteam audit review on ${prCoordinates} at commit ${context.head}. All review lenses are clean on this HEAD.\n\n` +
        `Write an empty findings file: create a temp file containing exactly [] (an empty JSON array). Then run:\n` +
        `python "${CONFIG.prLoopScripts}/post_audit_thread.py" --skill bugteam --owner ${input.owner} --repo ${input.repo} --pr-number ${input.prNumber} --commit ${context.head} --state CLEAN --findings-json <temp-file>\n` +
        `Run the script with --help first if any flag name differs. This posts the APPROVE review body that check_convergence.py reads for the bugteam gate. Do not edit code, commit, or push.\n\n` +
        `Report whether the review landed. When the script prints a review URL, return {posted:true, reviewUrl:<that URL>, reason:""}. When the script is denied (a permission prompt or auto-mode-classifier block), errors, or prints anything other than a review URL, return {posted:false, reviewUrl:"", reason:<the denial message or error as one line>}. Do not retry a denied post.`,
      { label, phase: 'Converge', schema: CLEAN_AUDIT_SCHEMA, agentType: 'general-purpose' },
    )
  }
  if (task === 'mark-ready') {
    const copilotOptOut = context.copilotDown
      ? `0. Copilot is down this run, so opt the independent mark-ready blocker hook out of the Copilot gate before step 1. Export the token in the same shell session as step 1 so the hook's convergence re-check inherits it:\n   bash: export CLAUDE_REVIEWS_DISABLED="copilot"   (PowerShell: $env:CLAUDE_REVIEWS_DISABLED = "copilot")\n`
      : ''
    return convergeAgent(
      `All convergence gates pass for ${prCoordinates} on HEAD ${context.head}. Mark the PR ready, then confirm it left draft state. Do not edit code.\n\n` +
        copilotOptOut +
        `1. Run: gh pr ready ${input.prNumber} --repo ${input.owner}/${input.repo}\n` +
        `2. Re-query the draft state: gh api repos/${input.owner}/${input.repo}/pulls/${input.prNumber} --jq .draft\n` +
        `Return {ready:true} only when step 2 prints false (the PR is no longer a draft). If step 1 errors or step 2 still prints true, return {ready:false}.`,
      { label, phase: 'Finalize', schema: READY_SCHEMA, agentType: 'general-purpose' },
    )
  }
  throw new Error(`runGeneralUtilityTask: unknown task ${task}`)
}

/**
 * Spawn a fresh convergence-check Explore agent for the convergence check.
 * @param {object} context carries bugbotDown and copilotDown
 * @returns {Promise<object>} CONVERGENCE_SCHEMA result
 */
function runConvergenceCheck(context) {
  const label = 'check-convergence'
  const bugbotDownFlag = context.bugbotDown ? ' --bugbot-down' : ''
  const copilotDownFlag = context.copilotDown ? ' --copilot-down' : ''
  return convergeAgent(
    `Run the convergence gate for ${prCoordinates} and report the result. Do not edit code.\n\n` +
      `Run: python "${CONFIG.sharedScripts}/check_convergence.py" --owner ${input.owner} --repo ${input.repo} --pr-number ${input.prNumber}${bugbotDownFlag}${copilotDownFlag}\n\n` +
      `Exit 0 -> every gate passed: return {pass:true, failures:[]}.\n` +
      `Exit 1 -> return {pass:false, failures:[<each printed FAIL line verbatim>]}.\n` +
      `Exit 2 -> retry once; if it still errors, return {pass:false, failures:["check_convergence gh error"]}.`,
    { label, phase: 'Finalize', schema: CONVERGENCE_SCHEMA, agentType: 'Explore' },
  )
}

const PRE_COMMIT_GATE_STEP =
  `\n\nFINAL STEP — pre-commit gate check (do NOT commit): before your turn ends, prove your working-tree changes CAN be committed by dry-running the CODE_RULES commit gate that gates git commit (precommit_code_rules_gate). From inside the checkout that holds your changes, resolve its root with git rev-parse --show-toplevel, stage your changes with git add -A, then run exactly:\n` +
  `   python "${CONFIG.prLoopScripts}/code_rules_gate.py" --repo-root "<that root>" --staged\n` +
  `Exit 0 means the commit gate would accept the commit. On any non-zero exit, read every violation it prints, fix each one test-first per CODE_RULES, and re-run the gate until it exits 0. Then unstage with git restore --staged . so the verify step reads the working-tree diff. Make NO git commit and NO git push here — this is a dry committability check; the separate verify and commit steps run after you, and the verified-commit gate is their job, not yours. Your turn does not end while the commit gate would reject the commit.`

const LENS_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    sha: { type: 'string', description: 'PR HEAD SHA this lens evaluated' },
    clean: { type: 'boolean', description: 'true when this lens found no findings on sha' },
    down: { type: 'boolean', description: 'true when the reviewer is opted out or unreachable and is bypassed' },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          file: { type: 'string' },
          line: { type: 'integer' },
          severity: { type: 'string', enum: ['P0', 'P1', 'P2'] },
          category: { type: 'string', enum: ['bug', 'code-standard'], description: 'code-standard for pure CODE_RULES/style violations with no behavioral impact; bug otherwise' },
          title: { type: 'string' },
          detail: { type: 'string' },
          replyToCommentId: { type: ['integer', 'null'], description: 'GitHub review comment id to reply to and resolve, or null when the finding has no thread' },
        },
        required: ['file', 'line', 'severity', 'category', 'title', 'detail', 'replyToCommentId'],
      },
    },
  },
  required: ['sha', 'clean', 'down', 'findings'],
}

const COPILOT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    sha: { type: 'string' },
    clean: { type: 'boolean' },
    down: { type: 'boolean', description: 'true when Copilot is down or out of quota — it posts an out-of-usage notice or never surfaces a review on HEAD after the poll cap; the gate is bypassed and the run proceeds to mark-ready' },
    findings: LENS_SCHEMA.properties.findings,
  },
  required: ['sha', 'clean', 'down', 'findings'],
}

const HEAD_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: { sha: { type: 'string' } },
  required: ['sha'],
}

const FIX_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    newSha: { type: 'string', description: 'HEAD SHA after the fix commit was pushed, or the unchanged HEAD when no commit was needed' },
    pushed: { type: 'boolean' },
    resolvedWithoutCommit: { type: 'boolean', description: 'true when every finding was already addressed so no code change was made, yet each finding thread was still resolved — the round advances rather than stalling' },
    summary: { type: 'string' },
    blockedNeedingEdit: { type: 'boolean', description: 'true only when the commit or push was rejected by a commit-time hook or gate whose message requires a code change (for example a CODE_RULES violation the fix introduced), not a transient or auth failure' },
    blockerDetail: { type: 'string', description: 'verbatim hook or gate rejection text naming the file and rule that must change, or an empty string when no edit-requiring block occurred' },
  },
  required: ['newSha', 'pushed', 'resolvedWithoutCommit', 'summary', 'blockedNeedingEdit', 'blockerDetail'],
}

const EDIT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    edited: { type: 'boolean', description: 'true when the step edited code to fix at least one finding' },
    resolvedWithoutCommit: { type: 'boolean', description: 'true when every finding was already addressed so no code change was made, yet each finding thread was still resolved' },
    summary: { type: 'string' },
  },
  required: ['edited', 'resolvedWithoutCommit', 'summary'],
}

const REPAIR_EDIT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    edited: { type: 'boolean', description: 'true when a still-applicable bot-thread concern was fixed test-first in the working tree' },
    rebased: { type: 'boolean', description: 'true when the branch was rebased onto origin/main to restore mergeability' },
    resolvedWithoutCommit: { type: 'boolean', description: 'true when the failing gates were addressed with neither a code change nor a rebase — bot threads resolved only, so there is nothing for the commit step to push' },
    summary: { type: 'string' },
  },
  required: ['edited', 'rebased', 'resolvedWithoutCommit', 'summary'],
}

const MERGE_CONFLICT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    conflicting: {
      type: 'boolean',
      description: 'true only when GitHub reports the PR branch conflicts with its base (mergeable:false or mergeable_state:dirty); false when it merges cleanly or mergeability could not be computed',
    },
  },
  required: ['conflicting'],
}

const CONFLICT_EDIT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    rebased: { type: 'boolean', description: 'true when the branch was rebased onto origin/main and every conflict resolved in the working tree' },
    summary: { type: 'string' },
  },
  required: ['rebased', 'summary'],
}

const STANDARDS_EDIT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    issueUrl: { type: 'string', description: 'the follow-up fix issue URL, or an empty string when the issue could not be filed' },
    hardeningRepoPath: { type: 'string', description: 'absolute path of the environment-config repo checkout the hardening branch was edited in, or an empty string when no hardening edit was made' },
    hardeningBranch: { type: 'string', description: 'the hardening branch name created in that repo, or an empty string when no hardening edit was made' },
    hardeningEdited: { type: 'boolean', description: 'true when hooks or rules were edited in the working tree of the hardening repo, uncommitted, so the verify and commit steps have a surface to bind and push' },
    summary: { type: 'string' },
  },
  required: ['issueUrl', 'hardeningRepoPath', 'hardeningBranch', 'hardeningEdited', 'summary'],
}

const HARDENING_COMMIT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    hardeningPrUrl: { type: 'string', description: 'the full https URL of the DRAFT environment-hardening PR the commit step opened, or an empty string when no PR was opened' },
    summary: { type: 'string' },
  },
  required: ['hardeningPrUrl', 'summary'],
}

/**
 * Build the verdict-fence step instructions for a verify agent, binding the
 * surface hash by branch name rather than by a self-resolved cwd. Resolving
 * the branch via `gh pr view` is cwd-immune: it does not matter which worktree
 * the verify agent runs in, so a launcher session whose cwd is a different
 * worktree cannot poison the binding hash.
 * @param {string} prOwner GitHub owner of the repo that holds the branch
 * @param {string} prRepo GitHub repo name
 * @param {number|string} prNumber PR number used to resolve the head branch
 * @returns {string} binding-hash and verdict-fence instructions for a verify prompt
 */
function buildVerdictFenceSteps(prOwner, prRepo, prNumber) {
  return (
    `Compute the binding hash for the live surface:\n` +
    `   a. Resolve the PR head branch (cwd-immune): run exactly\n` +
    `         gh pr view ${prNumber} --repo ${prOwner}/${prRepo} --json headRefName -q .headRefName\n` +
    `      Capture the branch name printed on stdout.\n` +
    `   b. Run exactly:\n` +
    `         "C:\\Python313\\python.exe" "<REPO>/packages/claude-dev-env/hooks/blocking/verification_verdict_store.py" --manifest-hash-for-branch "<that branch>"\n` +
    `      (substitute the REPO path you resolved for the script path, and the branch name for <that branch>). That prints a single 64-char hex hash on stdout — capture it.\n` +
    `Then END your message with a fenced verdict block exactly in this shape, on its own, carrying that hash:\n` +
    "   ```verdict\n" +
    `   {"all_pass": true, "findings": [], "manifest_sha256": "<that hash>"}\n` +
    "   ```\n" +
    `   When verification fails, set all_pass to false and list the unresolved concerns in findings; still include the manifest_sha256. The verdict fence must be the last thing in your message.`
  )
}

const CONVERGENCE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    pass: { type: 'boolean', description: 'true only when check_convergence.py exits 0' },
    failures: { type: 'array', items: { type: 'string' }, description: 'FAIL lines from check_convergence.py when pass is false' },
  },
  required: ['pass', 'failures'],
}

const READY_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    ready: { type: 'boolean', description: 'true only when isDraft is confirmed false after gh pr ready' },
  },
  required: ['ready'],
}

const CLEAN_AUDIT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    posted: { type: 'boolean', description: 'true only when post_audit_thread.py printed the review URL confirming the CLEAN bugteam review landed on HEAD' },
    reviewUrl: { type: 'string', description: 'the posted review URL when posted is true, otherwise an empty string' },
    reason: { type: 'string', description: 'when posted is false, the one-line reason the post did not land (a permission denial, a classifier block, or a script error)' },
  },
  required: ['posted', 'reviewUrl', 'reason'],
}

const SEVERITY_RANK = { P0: 0, P1: 1, P2: 2 }
const SHA_COMPARISON_PREFIX_LENGTH = 7

/**
 * Dedup findings across lenses by file + line + lowercased title, reconciling
 * severity to the most severe duplicate, unioning detail text, and collecting
 * every distinct bot thread id so a collision never strands a review thread or
 * understates severity.
 * @param {Array<object>} allFindings concatenated lens findings
 * @returns {Array<object>} unique findings keyed by file:line:title
 */
function dedupeFindings(allFindings) {
  const keptByFingerprint = new Map()
  const orderedFingerprints = []
  for (const eachFinding of allFindings) {
    const fingerprint = `${eachFinding.file}:${eachFinding.line}:${(eachFinding.title || '').toLowerCase()}`
    const alreadyKept = keptByFingerprint.get(fingerprint)
    if (alreadyKept === undefined) {
      keptByFingerprint.set(fingerprint, seedKeptFinding(eachFinding))
      orderedFingerprints.push(fingerprint)
      continue
    }
    mergeDuplicateInto(alreadyKept, eachFinding)
  }
  return orderedFingerprints.map((eachFingerprint) => keptByFingerprint.get(eachFingerprint))
}

/**
 * Build the first-seen finding for a fingerprint, seeding a thread-id list that
 * later duplicates extend.
 * @param {object} firstFinding the earliest finding at this fingerprint
 * @returns {object} a kept finding carrying a replyToCommentIds array
 */
function seedKeptFinding(firstFinding) {
  const seededThreadIds =
    firstFinding.replyToCommentId == null ? [] : [firstFinding.replyToCommentId]
  return { ...firstFinding, replyToCommentIds: seededThreadIds }
}

/**
 * Reconcile a dropped duplicate into the kept finding: raise severity to the
 * more severe of the two, union detail text, preserve the earliest thread id,
 * and append every distinct thread id for resolution.
 * @param {object} keptFinding the finding retained for this fingerprint
 * @param {object} droppedFinding the later duplicate being collapsed
 * @returns {void}
 */
function mergeDuplicateInto(keptFinding, droppedFinding) {
  if (isMoreSevere(droppedFinding.severity, keptFinding.severity)) {
    keptFinding.severity = droppedFinding.severity
  }
  if (keptFinding.replyToCommentId == null && droppedFinding.replyToCommentId != null) {
    keptFinding.replyToCommentId = droppedFinding.replyToCommentId
  }
  if (droppedFinding.replyToCommentId != null && !keptFinding.replyToCommentIds.includes(droppedFinding.replyToCommentId)) {
    keptFinding.replyToCommentIds.push(droppedFinding.replyToCommentId)
  }
  const droppedDetail = droppedFinding.detail || ''
  const keptDetail = keptFinding.detail || ''
  if (droppedDetail && !keptDetail.includes(droppedDetail)) {
    keptFinding.detail = keptDetail ? `${keptDetail}\n${droppedDetail}` : droppedDetail
  }
}

/**
 * Collect every distinct GitHub review thread id a finding carries, preferring
 * the deduped replyToCommentIds list and falling back to the scalar
 * replyToCommentId for findings that never passed through dedupeFindings.
 * @param {object} finding a single finding
 * @returns {Array<number>} distinct non-null thread ids to reply to and resolve
 */
function collectFindingThreadIds(finding) {
  if (Array.isArray(finding.replyToCommentIds)) {
    return finding.replyToCommentIds.filter((eachId) => eachId != null)
  }
  return finding.replyToCommentId == null ? [] : [finding.replyToCommentId]
}

/**
 * Decide whether a candidate severity outranks the current one (P0 > P1 > P2).
 * @param {string} candidateSeverity the duplicate's severity
 * @param {string} currentSeverity the kept finding's severity
 * @returns {boolean} true when the candidate is strictly more severe
 */
function isMoreSevere(candidateSeverity, currentSeverity) {
  const candidateRank = SEVERITY_RANK[candidateSeverity]
  const currentRank = SEVERITY_RANK[currentSeverity]
  if (candidateRank === undefined) return false
  if (currentRank === undefined) return true
  return candidateRank < currentRank
}

/**
 * Decide whether the convergence check should bypass the Bugbot gate this round,
 * recomputed from the current Bugbot lens result rather than latched across the
 * run, so a recovered Bugbot re-arms the gate. A dead lens agent (null/undefined
 * result) produces no Bugbot verdict on this HEAD, so it is treated as down to
 * keep the convergence gate from demanding a verdict that cannot exist.
 * @param {object|null|undefined} bugbotLens the current round's Bugbot lens result
 * @param {boolean} bugbotDisabled true when Bugbot is opted out for the whole run
 * @returns {boolean} true when the Bugbot gate is bypassed for the current HEAD
 */
function resolveBugbotDown(bugbotLens, bugbotDisabled) {
  if (bugbotDisabled) return true
  if (bugbotLens == null) return true
  return bugbotLens.down === true
}

/**
 * Decide whether a single surviving lens calls the HEAD clean. A lens is clean
 * when it explicitly reports clean:true, or when it is bypassed (down:true) so it
 * has no verdict to withhold. A lens reporting clean:false with no findings — a
 * Bugbot lens awaiting a pending CI verdict, or a reviewer that reports 'not
 * clean' without pinning a file:line — keeps the round in the converge phase.
 * @param {object} lens a surviving LENS_SCHEMA result
 * @returns {boolean} true when this lens does not hold the round back
 */
function lensCallsHeadClean(lens) {
  return lens.clean === true || lens.down === true
}

/**
 * Decide the outcome of a converge round from its raw parallel lens results:
 * whether every lens agent died (a failed round that must not post a clean
 * artifact), the deduped findings from the surviving lenses, and whether the
 * round is clean. A round is clean only when at least one lens survived, every
 * surviving lens calls the HEAD clean, and the deduped findings are empty — so a
 * clean:false lens with zero findings keeps the round converging rather than
 * advancing to the Copilot gate on a HEAD a lens did not call clean.
 * @param {Array<object|null>} lensResults raw parallel results, null per dead lens
 * @returns {{allLensesDead: boolean, findings: Array<object>, roundClean: boolean}} round outcome
 */
function resolveRoundOutcome(lensResults) {
  const liveLenses = lensResults.filter(Boolean)
  const findings = dedupeFindings(liveLenses.flatMap((eachLens) => eachLens.findings || []))
  const allLensesDead = liveLenses.length === 0
  const everyLensClean = liveLenses.every(lensCallsHeadClean)
  const roundClean = !allLensesDead && everyLensClean && findings.length === 0
  return { allLensesDead, findings, roundClean }
}

/**
 * Reduce a SHA to a case-folded common prefix so a full 40-char HEAD and an
 * abbreviated SHA reported by a fix agent (git rev-parse --short) for the same
 * commit compare equal. A non-string SHA folds to the empty string.
 * @param {string} sha a full or abbreviated commit SHA
 * @returns {string} the lowercased leading prefix used for comparison
 */
function normalizeShaForComparison(sha) {
  if (typeof sha !== 'string') return ''
  return sha.slice(0, SHA_COMPARISON_PREFIX_LENGTH).toLowerCase()
}

/**
 * Parse the LAST ```verdict ...``` fenced JSON block from a transcript.
 * Guards against non-string input, iterates all fence matches for the last one,
 * parses the JSON, and returns the object or null on any failure.
 * @param {string|null|undefined} transcript the agent transcript text
 * @returns {object|null} the parsed verdict object, or null when absent or malformed
 */
function parseLastVerdictFence(transcript) {
  if (typeof transcript !== 'string') return null
  const fencePattern = /```verdict\s*\n([\s\S]*?)```/g
  let lastFenceBody = null
  let eachMatch
  while ((eachMatch = fencePattern.exec(transcript)) !== null) {
    lastFenceBody = eachMatch[1]
  }
  if (lastFenceBody === null) return null
  try {
    return JSON.parse(lastFenceBody)
  } catch {
    return null
  }
}

/**
 * Decide whether a workflow code-verifier transcript ended in a passing
 * verdict. Reads the LAST ```verdict ...``` fenced JSON block via the shared
 * parser and returns true only when it parses to an object with all_pass true.
 * @param {string|null|undefined} verifyTranscript the verifier's transcript text
 * @returns {boolean} true only when the last verdict fence reports all_pass true
 */
function verdictPassed(verifyTranscript) {
  const verdictRecord = parseLastVerdictFence(verifyTranscript)
  return verdictRecord != null && verdictRecord.all_pass === true
}

const VERIFY_OBJECTION_FALLBACK = 'The verify step rejected the working-tree fixes without a parseable verdict; re-read the fix-verify transcript above and address every concern it raised.'

/**
 * Render one verdict finding as a single objection line, tolerant of the shapes a
 * verifier realistically emits: a bare string, an object keyed by any of
 * check/title/message/description/issue for the headline and detail/description
 * for the body, or any other object (stringified so its content survives). A
 * headline and a detail render as "headline — detail"; a headline alone renders
 * as the headline; an entry that yields no usable text returns null so the caller
 * can fall back rather than emit a content-free placeholder.
 * @param {unknown} eachFinding one entry from the verdict findings array
 * @returns {string|null} the rendered objection line, or null when unusable
 */
function renderVerifyObjectionLine(eachFinding) {
  if (typeof eachFinding === 'string') {
    const trimmedFinding = eachFinding.trim()
    return trimmedFinding.length > 0 ? trimmedFinding : null
  }
  if (eachFinding === null || typeof eachFinding !== 'object') return null
  const headline =
    eachFinding.check || eachFinding.title || eachFinding.message || eachFinding.description || eachFinding.issue
  const detail = eachFinding.detail || (headline === eachFinding.description ? '' : eachFinding.description)
  if (typeof headline === 'string' && headline.length > 0) {
    return typeof detail === 'string' && detail.length > 0 ? `${headline} — ${detail}` : headline
  }
  const stringifiedFinding = JSON.stringify(eachFinding)
  return stringifiedFinding === '{}' ? null : stringifiedFinding
}

/**
 * Pull the verifier's stated objections out of a failed verify transcript so the
 * re-fix step knows what the verdict rejected. Reads the last fenced verdict JSON
 * (the same block verdictPassed reads) and renders each finding through
 * renderVerifyObjectionLine into a numbered list. A missing fence, a parse
 * failure, an empty findings list, or a findings list where no entry yields
 * usable text falls back to a generic re-read instruction, so the re-fix step
 * always receives actionable text.
 * @param {string|null|undefined} verifyTranscript the failed verifier transcript text
 * @returns {string} a human-readable block of the verifier's objections
 */
function extractVerifyObjection(verifyTranscript) {
  const verdictRecord = parseLastVerdictFence(verifyTranscript)
  if (verdictRecord == null) return VERIFY_OBJECTION_FALLBACK
  const allObjections = Array.isArray(verdictRecord?.findings) ? verdictRecord.findings : []
  const renderedObjections = allObjections
    .map((eachFinding) => renderVerifyObjectionLine(eachFinding))
    .filter((eachLine) => eachLine !== null)
  if (renderedObjections.length === 0) return VERIFY_OBJECTION_FALLBACK
  return renderedObjections.map((eachLine, position) => `${position + 1}. ${eachLine}`).join('\n')
}

/**
 * Decide whether a fix lens actually advanced the round: a pushed fix that moved
 * HEAD progressed, and so did an all-stale round whose findings were every one
 * already addressed — the fix lens makes no commit but resolves each thread and
 * reports resolvedWithoutCommit:true, leaving HEAD unchanged on purpose. That
 * unchanged-HEAD resolve counts as progress only when the round carried at least
 * one thread-bearing finding to resolve; an all-null-thread round whose fix
 * reports resolvedWithoutCommit:true moved nothing and bounded nothing — its
 * vacuously-satisfied resolve would otherwise re-converge on the same HEAD until
 * the iteration cap — so it does not progress and surfaces a fix-stalled blocker.
 * A null result, a no-push round that did not resolve every thread, or a SHA
 * equal to the prior HEAD on a case-folded common prefix likewise did not
 * progress. Comparing on a normalized prefix keeps a no-op fix that reports an
 * abbreviated SHA of the unchanged HEAD from masquerading as a moved-HEAD push.
 * @param {object|null} fixResult the FIX_SCHEMA result, or null on agent failure
 * @param {string} priorHead the HEAD the fix was applied against
 * @param {boolean} hadThreadBearingFinding true when at least one finding in the round carried a GitHub thread id
 * @returns {{progressed: boolean, newSha: string}} progress decision and resulting HEAD
 */
function detectFixProgress(fixResult, priorHead, hadThreadBearingFinding) {
  if (fixResult == null) return { progressed: false, newSha: priorHead }
  const newSha = fixResult.newSha || priorHead
  if (fixResult.resolvedWithoutCommit === true) {
    return { progressed: hadThreadBearingFinding === true, newSha: priorHead }
  }
  const movedHead = normalizeShaForComparison(newSha) !== normalizeShaForComparison(priorHead)
  const progressed = fixResult.pushed === true && movedHead
  return { progressed, newSha }
}

/**
 * Decide whether a commit step was blocked by a commit-time hook or gate that
 * requires a code change, so the recovery loop should route back to a fixer. A
 * null result, a successful push, a transient failure (blockedNeedingEdit
 * false), or a flagged block carrying no detail all read as not-needing-recovery,
 * so only a flagged block with a concrete message routes to the fixer.
 * @param {object|null} commitResult the FIX_SCHEMA result, or null on agent failure
 * @returns {boolean} true only when the commit needs a code-edit recovery pass
 */
function commitNeedsCodeRecovery(commitResult) {
  if (commitResult == null) return false
  if (commitResult.pushed === true) return false
  return (
    commitResult.blockedNeedingEdit === true &&
    typeof commitResult.blockerDetail === 'string' &&
    commitResult.blockerDetail.length > 0
  )
}

/**
 * Decide whether a resolved HEAD SHA is safe to spawn lenses against. A dead
 * resolve-head agent or a malformed result yields a falsy SHA; spawning lenses
 * against it interpolates the literal string 'HEAD undefined' into their prompts
 * and produces a spurious clean verdict on a non-existent commit.
 * @param {string|null|undefined} resolvedHead the SHA from the git-utility 'resolve-head' task
 * @returns {boolean} true only when the SHA is a non-empty string
 */
function isResolvedHeadUsable(resolvedHead) {
  return typeof resolvedHead === 'string' && resolvedHead.length > 0
}

/**
 * Decide whether the pre-flight merge-conflict check found the PR branch in
 * conflict with its base. A dead check agent (null/undefined result) reports
 * not-conflicting so the run proceeds straight to the bug checks rather than
 * force-pushing a rebase on a verdict that does not exist — a transient check
 * failure must never trigger a destructive rebase.
 * @param {object|null|undefined} mergeState the git-utility 'check-merge-conflicts' task result
 * @returns {boolean} true only when the check reported conflicting:true
 */
function isMergeConflicting(mergeState) {
  return mergeState != null && mergeState.conflicting === true
}

/**
 * Decide whether the mark-ready step actually cleared the draft state. The run
 * reports converged only when the mark-ready agent confirms ready:true; a dead
 * agent (null result) or a ready:false report means `gh pr ready` did not land
 * (auth or token drift, a transient gh failure), so the PR is still a draft and
 * the run must surface a blocker rather than claim success.
 * @param {object|null|undefined} readyResult the READY_SCHEMA result, or null on agent failure
 * @returns {{converged: boolean, blocker: string|null}} convergence decision
 */
function classifyReadyOutcome(readyResult) {
  if (readyResult != null && readyResult.ready === true) {
    return { converged: true, blocker: null }
  }
  return {
    converged: false,
    blocker: 'mark-ready step did not confirm the PR left draft state (gh pr ready failed or the agent died)',
  }
}

/**
 * Classify a Copilot gate result into the loop's next action. A dead gate agent
 * (null result) is a retry rather than an approval, mirroring the converge
 * lenses' dead-agent convention so a failed gate is never mistaken for a clean
 * Copilot review. A down result — Copilot out of quota or unreachable, so it
 * posts an out-of-usage notice or never surfaces a review after the poll cap —
 * routes to the 'down' kind, which logs a notice and proceeds to mark-ready with
 * the Copilot gate bypassed, the same way a down Bugbot lens is bypassed; this is
 * checked first so an outage proceeds rather than waiting on a review that will
 * not arrive. Findings route to a fix step. The gate otherwise approves only when
 * it explicitly reports clean:true with no findings — a clean:false result with
 * zero findings is an unreliable or malformed gate response and retries rather
 * than advancing to Finalize, so a PR never goes ready on a HEAD Copilot did not
 * call clean.
 * @param {object|null|undefined} copilot the Copilot gate result, or null on agent failure
 * @returns {{kind: string, findings?: Array<object>}} the next action
 */
function classifyCopilotOutcome(copilot) {
  if (copilot == null) return { kind: 'retry' }
  if (copilot.down === true) return { kind: 'down' }
  if (copilot.findings.length > 0) return { kind: 'fix', findings: copilot.findings }
  if (copilot.clean === true) return { kind: 'approved' }
  return { kind: 'retry' }
}

/**
 * Decide whether the Copilot review gate is bypassed for this COPILOT pass from
 * the gate outcome, mirroring resolveBugbotDown so the flag is recomputed every
 * pass rather than left sticky. Only a 'down' outcome (Copilot out of quota or
 * unreachable after the poll cap) bypasses the convergence Copilot gate; an
 * 'approved', 'fix', or 'retry' outcome means Copilot answered this pass, so the
 * gate must be evaluated against its review and is never bypassed. Recomputing
 * from the current outcome is what lets a recovered Copilot — one that returns
 * standards-only findings after an earlier down pass — reach FINALIZE without
 * the stale bypass that would skip its non-clean review.
 * @param {{kind: string}} copilotOutcome a classifyCopilotOutcome result
 * @returns {boolean} true only when this pass's Copilot gate is bypassed
 */
function resolveCopilotDown(copilotOutcome) {
  return copilotOutcome.kind === 'down'
}

/**
 * Classify a convergence-check result into the loop's next action. A dead check
 * agent (null/undefined result) is a retry rather than a failure: with no FAIL
 * lines to act on, running the convergence repair (which may rebase and
 * force-push) would be a destructive response to a transient agent death. A
 * genuine pass marks the PR ready; a real failure carrying FAIL lines routes to
 * repair; a pass:false report with no failure lines is an unreliable check and
 * retries rather than triggering a repair with nothing concrete to fix.
 * @param {object|null|undefined} convergence the convergence-check result, or null on agent failure
 * @returns {{kind: string, failures?: Array<string>}} the next action
 */
function classifyConvergenceOutcome(convergence) {
  if (convergence == null) return { kind: 'retry' }
  if (convergence.pass === true) return { kind: 'ready' }
  const failures = convergence.failures || []
  if (failures.length === 0) return { kind: 'retry' }
  return { kind: 'repair', failures }
}

/**
 * Normalize the workflow's raw args global into a run-coordinates object. The
 * Workflow runtime delivers args as a JSON-encoded string, so a string payload
 * is parsed; an object payload passes through unchanged. A non-JSON or empty
 * string yields null rather than throwing, so a malformed payload becomes a
 * structured blocker instead of aborting the run. Reading args.owner off an
 * unparsed string yields undefined and strands every GitHub call on invalid
 * coordinates, so every entry point reads coordinates through this function.
 * @param {string|object} rawArgs the workflow args global (JSON string or object)
 * @returns {object|null} the run coordinates, or null when a string payload fails to parse
 */
function normalizeRunInput(rawArgs) {
  if (typeof rawArgs !== 'string') return rawArgs
  try {
    return JSON.parse(rawArgs)
  } catch {
    return null
  }
}

/**
 * Validate the normalized run input into either usable coordinates or a
 * structured blocker. The run cannot build a single GitHub call without owner,
 * repo, and prNumber, so a null payload (failed parse or missing args) or a
 * payload missing any coordinate yields a blocker the top-level run reports as
 * {converged:false, blocker} rather than throwing on input.owner at startup.
 * @param {string|object} rawArgs the workflow args global (JSON string or object)
 * @returns {{input: object|null, blocker: string|null}} usable coordinates or a blocker
 */
function classifyRunInput(rawArgs) {
  const candidate = normalizeRunInput(rawArgs)
  const hasUsableCoordinates =
    candidate != null && candidate.owner && candidate.repo && candidate.prNumber
  if (hasUsableCoordinates) return { input: candidate, blocker: null }
  return {
    input: null,
    blocker:
      'invalid run coordinates: the workflow args did not parse into an object carrying owner, repo, and prNumber',
  }
}

const runInput = classifyRunInput(args)
if (runInput.blocker) {
  return { converged: false, rounds: 0, finalSha: null, blocker: runInput.blocker }
}
const input = runInput.input
activeRepoPath = typeof input.repoPath === 'string' && input.repoPath ? input.repoPath : null
const prCoordinates = `owner=${input.owner} repo=${input.repo} PR #${input.prNumber} (https://github.com/${input.owner}/${input.repo}/pull/${input.prNumber})`

/**
 * Bugbot lens: ensure Cursor Bugbot has rendered a verdict on the given HEAD,
 * triggering and polling its CI check run when needed, and return its findings.
 * @param {string} head PR HEAD SHA to evaluate
 * @returns {Promise<object>} LENS_SCHEMA result
 */
function runBugbotLens(head) {
  if (input.bugbotDisabled) {
    return Promise.resolve({ sha: head, clean: true, down: true, findings: [] })
  }
  return convergeAgent(
    `You are the Cursor Bugbot lens for ${prCoordinates}, HEAD ${head}. Cursor Bugbot participates this run.\n\n` +
      `Goal: return Bugbot's verdict on HEAD ${head}. Do not edit code, commit, or push. You may post the literal trigger comment described below.\n\n` +
      `Procedure (use the existing scripts; each step below shows the exact flags that script accepts):\n` +
      `1. Opt-out: python "${CONFIG.prLoopScripts}/reviews_disabled.py" --reviewer bugbot. Exit 0 means disabled -> return {sha, clean:true, down:true, findings:[]}.\n` +
      `2. Silent pass: python "${CONFIG.sharedScripts}/check_bugbot_ci.py" --owner ${input.owner} --repo ${input.repo} --sha ${head} --check-clean. Exit 0 means the CI check completed clean with no review -> return clean with no findings.\n` +
      `3. Fetch any Bugbot review + inline comments on HEAD ${head} with gh api (Bugbot's GitHub login contains "cursor", case-insensitive). Use --paginate --slurp piped to external jq:\n` +
      `   gh api "repos/${input.owner}/${input.repo}/pulls/${input.prNumber}/reviews" --paginate --slurp  (top-level review body + state)\n` +
      `   gh api "repos/${input.owner}/${input.repo}/pulls/${input.prNumber}/comments" --paginate --slurp  (inline review comments + their ids)\n` +
      `   Only count entries whose commit_id starts with ${head}.\n` +
      `   - If findings exist on HEAD -> return them (each with its inline comment id in replyToCommentId when present, else null).\n` +
      `   - If a clean review exists on HEAD -> return clean.\n` +
      `4. No review yet on HEAD: check_bugbot_ci.py --check-active. If active (exit 0), poll: repeat check_bugbot_ci.py --check-clean / --check-active every 60 seconds (delay each iteration with "sleep 60", or the PowerShell alternative "Start-Sleep -Seconds 60") for up to 25 iterations, then re-fetch the review. If not active (exit 1), post the literal comment "bugbot run" (no @mention, no other text) via python "${CONFIG.sharedScripts}/post_fix_reply.py" --owner ${input.owner} --repo ${input.repo} --pr-number ${input.prNumber} --body "bugbot run", delay 8 seconds with "sleep 8" (PowerShell alternative "Start-Sleep -Seconds 8"), then poll as above.\n` +
      `5. If after the full poll budget Bugbot has neither a check run nor a review on HEAD -> return {sha:${'`'}${head}${'`'}, clean:true, down:true, findings:[]} (treat as down).\n\n` +
      `Scope is the whole PR; you are only reading Bugbot's own output here. For each finding set category: 'code-standard' when it is a pure CODE_RULES/style violation (naming, comments, type hints, magic values, structure) with no behavioral impact; 'bug' otherwise. Return strictly the schema.`,
    { label: 'lens:bugbot', phase: 'Converge', schema: LENS_SCHEMA },
  )
}

/**
 * Code-review lens: a full-diff /code-review-style pass that reports findings
 * without applying any fix.
 * @param {string} head PR HEAD SHA to evaluate
 * @returns {Promise<object>} LENS_SCHEMA result
 */
function runCodeReviewLens(head) {
  return convergeAgent(
    `You are the code-review lens for ${prCoordinates}, HEAD ${head}.\n\n` +
      `Review the FULL origin/main...HEAD diff — every file the PR touches. Do NOT delta-scope to recent commits or to a single file. The workflow already fetched origin/main this round, so do NOT run git fetch; run git diff --name-only origin/main...HEAD to enumerate the changed files, then review the complete diff of each.\n\n` +
      `Apply correctness-focused review: real bugs, broken logic, incorrect error handling, data-loss or security risks, contract mismatches, and reuse/simplification problems. Report only defensible findings with concrete file:line evidence.\n\n` +
      `Do NOT edit, commit, or push — reporting only. Return strictly the schema: clean=true with empty findings when the diff is sound, otherwise one entry per finding (severity P0/P1/P2; category 'code-standard' for pure CODE_RULES/style violations with no behavioral impact, 'bug' otherwise; replyToCommentId=null since these are not yet GitHub threads). Set sha=${'`'}${head}${'`'}, down=false.`,
    { label: 'lens:code-review', phase: 'Converge', schema: LENS_SCHEMA, agentType: 'code-quality-agent' },
  )
}

/**
 * Bug-audit lens: the bugteam-class second-opinion audit over the full diff,
 * applying the shared A–P audit rubric. Reports findings without fixing.
 * @param {string} head PR HEAD SHA to evaluate
 * @returns {Promise<object>} LENS_SCHEMA result
 */
function runAuditLens(head) {
  return convergeAgent(
    `You are the second-opinion bug-audit lens for ${prCoordinates}, HEAD ${head}.\n\n` +
      `Read the audit rubric at ${CONFIG.bugteamRubric} and apply its categories (A through P) against the FULL origin/main...HEAD diff — every file the PR touches, never a delta cut. The workflow already fetched origin/main this round, so do NOT run git fetch; run git diff --name-only origin/main...HEAD first to enumerate scope.\n\n` +
      `This is a clean-room audit: assume nothing from other lenses. Report only findings backed by concrete file:line evidence. Do NOT edit, commit, or push.\n\n` +
      `Return strictly the schema: clean=true with empty findings when the diff passes every category, otherwise one entry per finding (severity P0/P1/P2; category 'code-standard' for pure CODE_RULES/style violations with no behavioral impact, 'bug' otherwise; replyToCommentId=null). Set sha=${'`'}${head}${'`'}, down=false.`,
    { label: 'lens:bug-audit', phase: 'Converge', schema: LENS_SCHEMA, agentType: 'code-quality-agent' },
  )
}

/**
 * Reuse lens: a one-time pre-convergence pass that scans the full diff for
 * places the PR re-implements behavior the codebase already provides, and
 * returns only the reuse improvements that are certain, behaviorally identical,
 * and autonomously implementable. It reports findings without editing; the
 * reuse pass routes the qualifying findings through applyFixes so they are
 * implemented in one commit before the convergence rounds begin.
 * @param {string} head PR HEAD SHA to evaluate
 * @returns {Promise<object>} LENS_SCHEMA result carrying the qualifying reuse findings
 */
function runReuseAuditPass(head) {
  return convergeAgent(
    `You are the REUSE lens for ${prCoordinates}, HEAD ${head}. This pass runs once before convergence to find where the PR re-implements behavior the codebase already provides.\n\n` +
      `Review the FULL origin/main...HEAD diff — every file the PR touches. Do NOT delta-scope to recent commits or a single file. The workflow already fetched origin/main, so do NOT run git fetch; run git diff --name-only origin/main...HEAD to enumerate the changed files, then read the complete diff of each. For every new function, helper, constant, type, or block of logic the PR introduces, search the repository (Serena symbol search, grep, and the project's config/ and shared/ modules) for an existing equivalent that already provides the same behavior.\n\n` +
      `Report a reuse finding ONLY when ALL THREE criteria hold — when any one is in doubt, omit the finding:\n` +
      `  A. CERTAIN: an existing symbol or module unquestionably covers the new code's behavior, and you can cite it at file:line.\n` +
      `  B. BEHAVIORALLY IDENTICAL: replacing the new code with the existing one changes no observable behavior — same inputs, outputs, side effects, and error handling.\n` +
      `  C. AUTONOMOUSLY IMPLEMENTABLE: the replacement is a mechanical edit (import and call the existing symbol, delete the duplicate) that needs no product decision, no API the existing code lacks, and no human judgment.\n\n` +
      `Do NOT edit, commit, or push — report only; a separate fix step applies what you return. Return strictly the schema: clean=true with empty findings when no reuse case clears all three criteria, otherwise one entry per qualifying reuse improvement. For each: file and line of the duplicate in the PR; severity P2; category 'code-standard'; title naming the existing symbol to reuse; detail giving the existing symbol's file:line and the exact mechanical replacement; replyToCommentId=null. Set sha=${'`'}${head}${'`'}, down=false.`,
    { label: 'lens:reuse', phase: 'Reuse', schema: LENS_SCHEMA, agentType: 'code-quality-agent' },
  )
}

/**
 * Render the numbered findings block shared by the fix steps.
 * @param {Array<object>} findings deduped findings to render
 * @returns {string} one numbered line per finding, with any thread-id note
 */
function renderFindingsBlock(findings) {
  return findings
    .map((each, position) => {
      const eachThreadIds = collectFindingThreadIds(each)
      const threadNote = eachThreadIds.length
        ? `\n   (GitHub review comment ids: ${eachThreadIds.join(', ')})`
        : ''
      return `${position + 1}. [${each.severity}] ${each.file}:${each.line} — ${each.title}\n   ${each.detail}${threadNote}`
    })
    .join('\n')
}

const FIX_RECOVERY_MAX_ATTEMPTS = 2

/**
 * Run a commit step and, when it is blocked by a commit-time hook or gate that
 * requires a code change, route back to a fixer: fix the blocking violation,
 * re-verify so a fresh verdict binds the corrected surface, then retry the
 * commit — bounded by FIX_RECOVERY_MAX_ATTEMPTS. The loop breaks early when the
 * fixer makes no edit or the re-verify does not pass, returning the last commit
 * result so the caller's existing no-push handling still applies. A transient
 * failure never enters the loop (commitNeedsCodeRecovery is false), so an auth or
 * network failure keeps the existing blocker path.
 * @param {{runCommit: function, runVerify: function, runRecoverEdit: function}} steps the commit, re-verify, and recover-edit thunks
 * @returns {Promise<object>} the final FIX_SCHEMA result
 */
async function commitWithRecovery({ runCommit, runVerify, runRecoverEdit }) {
  let commitResult = await runCommit()
  let attempt = 0
  while (commitNeedsCodeRecovery(commitResult) && attempt < FIX_RECOVERY_MAX_ATTEMPTS) {
    attempt += 1
    const recoverEdit = await runRecoverEdit(commitResult.blockerDetail, attempt)
    if (recoverEdit?.edited !== true) break
    const verifyTranscript = await runVerify()
    if (!verdictPassed(verifyTranscript)) break
    commitResult = await runCommit()
  }
  return commitResult
}

/**
 * Run the verify step and, when its verdict fails, route back to a fixer: re-fix
 * against the verifier's objection, then re-verify — bounded by
 * FIX_RECOVERY_MAX_ATTEMPTS. The loop breaks early when the fixer makes no edit,
 * returning the last failed verify transcript so the caller's verdict-failed
 * handling still applies; a verify that passes on any attempt returns its passing
 * transcript so the caller proceeds to commit.
 * @param {{runVerify: function, runRecoverEdit: function}} steps the verify and verify-recovery-edit thunks
 * @returns {Promise<string>} the final verify transcript — passing, or the last failed one
 */
async function verifyWithRecovery({ runVerify, runRecoverEdit }) {
  let verifyTranscript = await runVerify()
  let attempt = 0
  while (!verdictPassed(verifyTranscript) && attempt < FIX_RECOVERY_MAX_ATTEMPTS) {
    attempt += 1
    const objection = extractVerifyObjection(verifyTranscript)
    const recoverEdit = await runRecoverEdit(objection, attempt)
    if (recoverEdit?.edited !== true) break
    verifyTranscript = await runVerify()
  }
  return verifyTranscript
}

/**
 * Fix lens: edit (clean-coder, no commit) -> verify (a separate code-verifier
 * emits a verdict fence binding the working tree) -> commit (clean-coder, one
 * commit + push, no edits). The verifier is a distinct agent from the fixer, so
 * the verdict that gates the commit comes from a different agent than the one
 * that edits and pushes — the same editor/verifier separation the repair and
 * conflict paths use, and the separation a workflow code-verifier needs to
 * produce the verdict the verified-commit gate requires, which the SubagentStop
 * minter cannot mint for workflow-spawned agents. When verification fails (or the
 * edit step stalled with no thread to resolve), the commit step is skipped and the
 * unchanged HEAD is returned so the round reads as not-progressed.
 * @param {string} head PR HEAD SHA the findings were raised against
 * @param {Array<object>} findings deduped findings across all lenses
 * @param {string} sourceLabel short description of where the findings came from
 * @returns {Promise<object>} FIX_SCHEMA result
 */
async function applyFixes(head, findings, sourceLabel) {
  const editResult = await runCodeEditorTask('fix-edit', { head, findings, sourceLabel })
  if (editResult?.resolvedWithoutCommit === true && editResult?.edited !== true) {
    return {
      newSha: head,
      pushed: false,
      resolvedWithoutCommit: true,
      summary: editResult?.summary || 'fixes resolved without a code change',
      blockedNeedingEdit: false,
      blockerDetail: '',
    }
  }
  return fixerWithRecovery(head, findings, sourceLabel)
}

/**
 * Blocker message for a CLEAN bugteam audit that did not land. The convergence
 * gate's bugteam-review check can never pass without this review, so a blocked
 * post stops the run with an actionable message rather than re-converging until
 * the iteration cap. Handles a dead post agent (a null result) as not posted.
 * @param {string} head converged PR HEAD SHA
 * @param {object} auditResult CLEAN_AUDIT_SCHEMA result from the post-clean-audit task, or null when the agent died
 * @returns {string} the blocker message naming the post failure and the unblock path
 */
function cleanAuditBlocker(head, auditResult) {
  const reason = auditResult?.reason || 'the post agent returned no result'
  return (
    `clean-audit post blocked: the CLEAN bugteam review could not be posted on HEAD ${head} (${reason}) — ` +
    `the convergence gate's bugteam-review check can never pass without it, so the run stops rather than re-converge to the iteration cap. ` +
    `Allow post_audit_thread.py for this run with a Bash permission rule, or post the CLEAN review by hand, then re-run.`
  )
}

/**
 * Copilot gate: request a Copilot review on HEAD and poll until it lands or the
 * poll cap is hit; return Copilot's findings or a down signal. Copilot is down
 * when it posts an out-of-usage notice (the requester hit their quota) rather
 * than a review, or surfaces no review at all after the poll cap; the gate
 * reports either as down so the run logs a notice and proceeds to mark-ready with
 * the gate bypassed rather than waiting on a review that will not arrive.
 * @param {string} head converged PR HEAD SHA
 * @returns {Promise<object>} COPILOT_SCHEMA result
 */
function runCopilotGate(head) {
  return convergeAgent(
    `You are the Copilot gate for ${prCoordinates}, HEAD ${head}. Do not edit code, commit, or push.\n\n` +
      `Copilot can run out of usage. When the newest Copilot review on HEAD carries an out-of-usage notice — a body stating Copilot was unable to review because the user who requested the review has reached their quota limit, or any equivalent quota / premium-request / usage-limit exhaustion message rather than an actual code review — Copilot is down for this run: return {sha:${'`'}${head}${'`'}, clean:true, down:true, findings:[]} and stop. Do NOT re-request a review, do NOT keep polling, and do NOT treat the notice as a finding.\n\n` +
      `1. Read any existing Copilot review on HEAD first: python "${CONFIG.sharedScripts}/fetch_copilot_reviews.py" --owner ${input.owner} --repo ${input.repo} --pr-number ${input.prNumber}. This lists every Copilot review across all commits newest-first; only count entries whose commit_id starts with ${head}. If the newest such HEAD-scoped Copilot review is the out-of-usage notice above -> return the down result and stop. A notice on any earlier commit is NOT down: ignore it and continue. With no Copilot review on HEAD, skip a duplicate request: python "${CONFIG.sharedScripts}/check_pending_reviews.py" --owner ${input.owner} --repo ${input.repo} --pr-number ${input.prNumber} --user copilot. Exit 0 means a request is already pending; otherwise request one:\n` +
      `   gh api --method POST repos/${input.owner}/${input.repo}/pulls/${input.prNumber}/requested_reviewers -f 'reviewers[]=copilot-pull-request-reviewer[bot]'\n` +
      `2. Poll for Copilot's review on HEAD ${head}: up to ${CONFIG.copilotMaxPolls} attempts, 360 seconds apart (delay each attempt with "sleep 360", or the PowerShell alternative "Start-Sleep -Seconds 360"). Each attempt: python "${CONFIG.sharedScripts}/fetch_copilot_reviews.py" --owner ${input.owner} --repo ${input.repo} --pr-number ${input.prNumber} for the top-level review state, plus gh api "repos/${input.owner}/${input.repo}/pulls/${input.prNumber}/comments" --paginate --slurp for inline comment ids (Copilot's login contains "copilot", case-insensitive). Only count entries whose commit_id starts with ${head}.\n` +
      `   - Out-of-usage notice on HEAD -> return the down result above (clean:true, down:true) and stop.\n` +
      `   - Copilot review present on HEAD whose state is APPROVED, or COMMENTED with no inline findings -> a clean pass: return {sha:${'`'}${head}${'`'}, clean:true, down:false, findings:[]}.\n` +
      `   - Copilot findings on HEAD -> return them (each with its inline comment id in replyToCommentId; category 'code-standard' for pure CODE_RULES/style violations with no behavioral impact, 'bug' otherwise), clean:false, down:false.\n` +
      `   - No review after ${CONFIG.copilotMaxPolls} attempts -> Copilot is down for this run (unreachable, or silently out of quota with no notice): return {sha:${'`'}${head}${'`'}, clean:false, down:true, findings:[]}.\n\n` +
      `Return strictly the schema.`,
    { label: 'copilot-gate', phase: 'Copilot gate', schema: COPILOT_SCHEMA },
  )
}

/**
 * Address the gates a convergence check reported as failing, then hand control
 * back to the converge phase: edit (clean-coder resolves bot threads, applies
 * any fix and rebase in the working tree, no push) -> verify (code-verifier
 * emits a verdict fence binding the working tree) -> commit (clean-coder, one
 * commit + push, no edits). Splitting the edit from the push lets a workflow
 * code-verifier produce the verdict the verified-commit gate requires for the
 * bot-thread fix commit and the post-rebase force-push. When the edit resolved
 * the gates with neither a code change nor a rebase, or the verify step fails,
 * the commit step is skipped and the unchanged HEAD is returned.
 * @param {string} head current PR HEAD SHA
 * @param {Array<string>} failures FAIL lines from the convergence check
 * @returns {Promise<object>} FIX_SCHEMA result
 */
async function repairConvergence(head, failures) {
  const editResult = await runCodeEditorTask('repair-edit', { head, failures })
  const hasPushWork = editResult?.edited === true || editResult?.rebased === true
  if (!hasPushWork) {
    return {
      newSha: head,
      pushed: false,
      resolvedWithoutCommit: true,
      summary: editResult?.summary || 'convergence gates resolved without a code change or rebase',
      blockedNeedingEdit: false,
      blockerDetail: '',
    }
  }
  const verifyTranscript = await verifyWithRecovery({
    runVerify: () => runVerifierTask('repair-verify', { head, failures }),
    runRecoverEdit: (objection, attempt) => runCodeEditorTask('verify-recover', { head, sourceLabel: 'repair', objection, attempt }),
  })
  if (!verdictPassed(verifyTranscript)) {
    return {
      newSha: head,
      pushed: false,
      resolvedWithoutCommit: false,
      summary: `repair verify step did not pass the working-tree repair on HEAD ${head} — not pushing`,
      blockedNeedingEdit: false,
      blockerDetail: '',
    }
  }
  const wasRebased = editResult?.rebased === true
  return commitWithRecovery({
    runCommit: () => runCodeEditorTask('repair-commit', { head, wasRebased }),
    runVerify: () => runVerifierTask('repair-verify', { head, failures }),
    runRecoverEdit: (detail, attempt) => runCodeEditorTask('commit-recover', { head, sourceLabel: 'repair', blockerDetail: detail, attempt }),
  })
}


/**
 * Pre-flight conflict resolution: when the PR branch conflicts with its base,
 * rebase it clean before the bug checks run — check (Explore probes mergeability)
 * -> edit (clean-coder rebases and resolves, no push) -> verify (code-verifier
 * binds a verdict to the rebased tree) -> commit (clean-coder force-with-lease
 * pushes). Returns the post-rebase HEAD so the first converge round runs its
 * lenses on the conflict-free diff. A non-conflicting PR, a rebase the edit step
 * declined, or a failed verdict returns the unchanged HEAD so the run proceeds to
 * the bug checks unchanged. A mid-run conflict (origin/main advancing later) is
 * still caught by the FINALIZE convergence repair, which also rebases.
 * @param {string} head PR HEAD SHA before any rebase
 * @returns {Promise<string>} the HEAD SHA after a successful rebase push, or the unchanged head
 */
async function resolveMergeConflicts(head) {
  const mergeState = await runGitTask('check-merge-conflicts', head)
  if (!isMergeConflicting(mergeState)) return head
  log(`Pre-flight: ${prCoordinates} conflicts with origin/main — rebasing clean before the bug checks`)
  const editResult = await runCodeEditorTask('conflict-edit', { head })
  if (editResult?.rebased !== true) return head
  const failures = ['PR branch had merge conflicts with origin/main; the rebase must leave a clean, conflict-free tree']
  const verifyTranscript = await verifyWithRecovery({
    runVerify: () => runVerifierTask('repair-verify', { head, failures }),
    runRecoverEdit: (objection, attempt) => runCodeEditorTask('verify-recover', { head, sourceLabel: 'conflict-rebase', objection, attempt }),
  })
  if (!verdictPassed(verifyTranscript)) return head
  const commitResult = await commitWithRecovery({
    runCommit: () => runCodeEditorTask('repair-commit', { head, wasRebased: true }),
    runVerify: () => runVerifierTask('repair-verify', { head, failures }),
    runRecoverEdit: (detail, attempt) => runCodeEditorTask('commit-recover', { head, sourceLabel: 'conflict-rebase', blockerDetail: detail, attempt }),
  })
  return commitResult?.newSha || head
}

/**
 * Decide whether a review round surfaced ONLY code-standard violations — pure
 * CODE_RULES/style findings with no behavioral impact. Such a round passes for
 * convergence purposes: the violations are deferred to a follow-up fix issue
 * (plus an environment-hardening PR) rather than blocking this PR.
 * @param {Array<object>} findings deduped findings for the round
 * @returns {boolean} true when every finding is category code-standard
 */
function isStandardsOnlyRound(findings) {
  return findings.length > 0 && findings.every((each) => each.category === 'code-standard')
}

/**
 * Decide whether a standards-only round should file the follow-up fix issue and
 * open the environment-hardening PR. Standards findings are deferred rather than
 * fixed on this PR, so the same code-standard findings re-surface on every
 * converge round and on the Copilot gate; without this guard each re-entry files
 * a fresh duplicate follow-up issue and hardening PR for the one deferred finding
 * class. The follow-up issue is filed once per convergence run — a round whose
 * filing succeeds latches the guard, while a round whose filing failed leaves it
 * clear so a later round retries the filing.
 * @param {boolean} hasAlreadyFiled true when an earlier standards-only round in this run already filed the follow-up issue
 * @returns {boolean} true when this round should attempt the follow-up filing
 */
function shouldOpenStandardsFollowUp(hasAlreadyFiled) {
  return hasAlreadyFiled !== true
}

/**
 * Build the standards-deferral note for the closing report, naming the
 * environment-hardening PR only when one was opened for this run so the note
 * never claims a PR the skip paths did not produce.
 * @param {number} findingsCount count of deferred code-standard findings
 * @param {boolean} wasHardeningPrOpened true when the hardening PR was opened for this run
 * @returns {string} the human-facing deferral note
 */
function standardsDeferralNote(findingsCount, wasHardeningPrOpened) {
  const base = `${findingsCount} code-standard finding(s) deferred to a follow-up fix issue`
  return wasHardeningPrOpened
    ? `${base} plus an environment-hardening PR — verify both land`
    : `${base} — verify it lands (no environment-hardening PR was opened for this run)`
}

/**
 * Parse a GitHub pull-request URL into the owner, repo, and number a recursive
 * converge run needs to address it.
 *
 * A hardening PR the commit step opens returns its URL as
 * `https://github.com/<owner>/<repo>/pull/<number>`; this reads those three
 * coordinates back out so the self-closing orchestrator can converge the
 * deferred PR in turn. A blank or non-matching string yields null, so a commit
 * step that opened no PR contributes no deferred coordinate.
 * @param {string} prUrl the hardening PR's https URL, or an empty string
 * @returns {{owner: string, repo: string, prNumber: number}|null} the parsed coordinates, or null when the URL does not match
 */
function parseDeferredPr(prUrl) {
  if (typeof prUrl !== 'string') return null
  const match = prUrl.match(/github\.com\/([^/]+)\/([^/]+)\/pull\/(\d+)/)
  if (!match) return null
  return { owner: match[1], repo: match[2], prNumber: Number(match[3]) }
}

/**
 * Defer a standards-only round: edit (clean-coder files the follow-up fix issue,
 * stages an environment-hardening hooks/rules change in the config repo's
 * working tree without committing, and resolves the PR's code-standard threads)
 * -> verify (code-verifier binds a verdict to the hardening working tree) ->
 * commit (clean-coder makes one commit, pushes, and opens the DRAFT hardening
 * PR). Splitting the edit from the push lets a workflow code-verifier produce the
 * verdict the verified-commit gate requires for the cross-repo hardening commit.
 * This PR's own branch is never touched. When a hardening PR already opened for
 * this run, the edit staged no hardening, or the verify step fails, the follow-up
 * issue still stands and the commit step is skipped.
 * @param {string} head PR HEAD SHA the findings were raised against
 * @param {Array<object>} findings deduped code-standard-only findings
 * @param {string} sourceLabel short description of where the findings came from
 * @param {boolean} hasHardeningPrAlreadyOpened true when an earlier round already opened the environment-hardening PR for this run, so the verify and commit steps are skipped and no second PR opens while the edit retries the issue filing
 * @returns {Promise<object>} `{ followUpIssueFiled, issueUrl, hardeningPrOpened, deferredPr }` — followUpIssueFiled true when the standards-edit step returned a non-empty issue URL, issueUrl that filed URL (empty string when the filing failed) so a later reuse-path round can reference it when resolving its own threads, hardeningPrOpened true only when the hardening PR was opened on this call, and deferredPr the opened PR's `{owner, repo, prNumber}` (null when none was opened) so the self-closing orchestrator can converge it in turn
 */
async function spawnStandardsFollowUp(head, findings, sourceLabel, hasHardeningPrAlreadyOpened) {
  const editResult = await runCodeEditorTask('standards-edit', { head, findings, sourceLabel })
  const followUpIssueFiled = typeof editResult?.issueUrl === 'string' && editResult.issueUrl.length > 0
  const followUpIssueUrl = followUpIssueFiled ? editResult.issueUrl : ''
  if (hasHardeningPrAlreadyOpened === true) {
    return { followUpIssueFiled, issueUrl: followUpIssueUrl, hardeningPrOpened: false, deferredPr: null }
  }
  if (editResult?.hardeningEdited !== true || !editResult?.hardeningRepoPath) {
    return { followUpIssueFiled, issueUrl: followUpIssueUrl, hardeningPrOpened: false, deferredPr: null }
  }
  const verifyTranscript = await runVerifierTask('hardening-verify', {
    head, sourceLabel, hardeningRepoPath: editResult.hardeningRepoPath, hardeningBranch: editResult.hardeningBranch,
  })
  if (!verdictPassed(verifyTranscript)) {
    return { followUpIssueFiled, issueUrl: followUpIssueUrl, hardeningPrOpened: false, deferredPr: null }
  }
  const commitResult = await runCodeEditorTask('hardening-commit', {
    head, sourceLabel, hardeningRepoPath: editResult.hardeningRepoPath, hardeningBranch: editResult.hardeningBranch, issueUrl: editResult.issueUrl,
  })
  const deferredPr = parseDeferredPr(commitResult?.hardeningPrUrl)
  return { followUpIssueFiled, issueUrl: followUpIssueUrl, hardeningPrOpened: deferredPr !== null, deferredPr }
}

/**
 * Report whether any finding in a batch carries a GitHub review thread that needs
 * an inline reply and resolution.
 * @param {Array<object>} findings the batch of findings
 * @returns {boolean} true when at least one finding carries a review comment id
 */
function findingsCarryThreads(findings) {
  return findings.some((each) => collectFindingThreadIds(each).length > 0)
}

/**
 * On the reuse path — after this run already filed the deferred-fix follow-up
 * issue — reply to and resolve this batch's code-standard review threads against
 * that same issue. The issue filing and hardening PR stay gated behind the
 * run-once flags; only the per-batch thread resolution runs here, so a later
 * standards-only round's bot threads are still marked resolved and the FINALIZE
 * zero-unresolved-bot-threads gate passes. A batch of in-memory audit findings
 * that carries no review thread needs no agent, so the resolve step is skipped.
 * @param {string} head PR HEAD SHA the findings were raised against
 * @param {Array<object>} findings this batch's deduped code-standard-only findings
 * @param {string} sourceLabel short description of where the findings came from
 * @returns {Promise<void>}
 */
async function resolveStandardsThreadsForBatch(head, findings, sourceLabel) {
  if (!findingsCarryThreads(findings)) {
    return
  }
  await runCodeEditorTask('standards-resolve-threads', {
    head, findings, sourceLabel, issueUrl: standardsFollowUpIssueUrl,
  })
}

/**
 * File the deferred follow-up issue and open the environment-hardening PR at most
 * once per convergence run, then reuse them. The two guards latch independently:
 * the follow-up issue latches only when its filing succeeds, and the hardening PR
 * latches the moment one opens and never re-opens. A standards-only round whose
 * issue filing already succeeded — in the converge phase or at the Copilot gate —
 * skips spawnStandardsFollowUp, resolves this batch's own code-standard review
 * threads against the already-filed issue via resolveStandardsThreadsForBatch, and
 * returns the remembered hardening outcome. A round whose issue filing failed
 * re-runs spawnStandardsFollowUp to retry the filing, passing the remembered
 * hardening state so an already-opened hardening PR is never re-opened. The run
 * therefore files one follow-up issue and opens one hardening PR rather than a
 * fresh duplicate per re-entry — while every round still resolves the review
 * threads its own findings carry, even when the filing must retry after the
 * hardening PR has opened.
 * @param {string} head PR HEAD SHA the findings were raised against
 * @param {Array<object>} findings deduped code-standard-only findings
 * @param {string} sourceLabel short description of where the findings came from
 * @returns {Promise<object>} `{ hardeningPrOpened, deferredPr }` — hardeningPrOpened true when a hardening PR was opened for this run, and deferredPr the opened PR's `{owner, repo, prNumber}` when this call opened it (null otherwise) so the self-closing orchestrator can converge it in turn
 */
async function openStandardsFollowUpOnce(head, findings, sourceLabel) {
  if (!shouldOpenStandardsFollowUp(hasStandardsFollowUpFiled)) {
    log(`Standards deferral (${sourceLabel}): reusing the follow-up fix issue already filed for this run rather than filing a duplicate; environment-hardening PR ${wasStandardsHardeningPrOpened ? 'was opened for this run' : 'was not opened for this run'}`)
    await resolveStandardsThreadsForBatch(head, findings, sourceLabel)
    return { hardeningPrOpened: wasStandardsHardeningPrOpened, deferredPr: null }
  }
  const standardsOutcome = await spawnStandardsFollowUp(head, findings, sourceLabel, wasStandardsHardeningPrOpened)
  hasStandardsFollowUpFiled = standardsOutcome?.followUpIssueFiled === true
  if (hasStandardsFollowUpFiled) {
    standardsFollowUpIssueUrl = standardsOutcome.issueUrl
  }
  wasStandardsHardeningPrOpened = wasStandardsHardeningPrOpened || standardsOutcome?.hardeningPrOpened === true
  return { hardeningPrOpened: wasStandardsHardeningPrOpened, deferredPr: standardsOutcome?.deferredPr ?? null }
}

let phase = 'CONVERGE'
let head = null
let rounds = 0
let iterations = 0
let blocker = null
let bugbotDown = input.bugbotDisabled || false
let copilotDown = input.copilotDisabled || false
let copilotNote = null
let standardsNote = null
let hasStandardsFollowUpFiled = false
let wasStandardsHardeningPrOpened = false
let standardsFollowUpIssueUrl = ''
let reuseNote = null
const deferredPrs = []

const preflightHead = await runGitTask('resolve-head')
if (isResolvedHeadUsable(preflightHead?.sha)) {
  await resolveMergeConflicts(preflightHead.sha)
}

log('Reuse pass: scanning the full diff for certain, behaviorally identical, autonomously implementable reuse improvements before convergence')
const reuseHeadResult = await runGitTask('resolve-head')
const reuseHead = reuseHeadResult?.sha
if (isResolvedHeadUsable(reuseHead)) {
  await runGitTask('prefetch-main')
  const reuse = await runReuseAuditPass(reuseHead)
  const reuseFindings = reuse?.findings || []
  if (reuseFindings.length > 0) {
    log(`Reuse pass: ${reuseFindings.length} qualifying reuse improvement(s) — applying before convergence`)
    const reuseFix = await applyFixes(reuseHead, reuseFindings, 'reuse-pass')
    reuseNote = reuseFix?.pushed === true
      ? `${reuseFindings.length} reuse improvement(s) applied before convergence (${reuseFix.newSha?.slice(0, SHA_COMPARISON_PREFIX_LENGTH)})`
      : `${reuseFindings.length} reuse improvement(s) identified before convergence but not landed — the code-review lens re-surfaces any that remain`
  } else {
    log('Reuse pass: no reuse case cleared all three criteria — proceeding to convergence')
  }
} else {
  log('Reuse pass: could not resolve HEAD — proceeding to convergence')
}

while (iterations < CONFIG.maxIterations) {
  iterations += 1
  if (phase === 'CONVERGE') {
    rounds += 1
    const headResult = await runGitTask('resolve-head')
    head = headResult?.sha
    if (!isResolvedHeadUsable(head)) {
      log(`Round ${rounds}: resolve-head agent returned no SHA — retrying without spawning lenses`)
      continue
    }
    await runGitTask('prefetch-main')
    log(`Round ${rounds}: parallel Bugbot + code-review + bug-audit on ${head?.slice(0, 7)}`)
    const lenses = await parallel([
      () => runBugbotLens(head),
      () => runCodeReviewLens(head),
      () => runAuditLens(head),
    ])
    bugbotDown = resolveBugbotDown(lenses[0], input.bugbotDisabled || false)
    const roundOutcome = resolveRoundOutcome(lenses)
    if (roundOutcome.allLensesDead) {
      log(`Round ${rounds}: every lens agent died — retrying without posting a clean artifact`)
      continue
    }
    const findings = roundOutcome.findings
    if (isStandardsOnlyRound(findings)) {
      log(`Round ${rounds}: ${findings.length} code-standard-only finding(s) — deferring to follow-up PRs and treating the round as passed`)
      const standardsOutcome = await openStandardsFollowUpOnce(head, findings, 'converge-round')
      standardsNote = standardsDeferralNote(findings.length, standardsOutcome.hardeningPrOpened)
      if (standardsOutcome?.deferredPr) deferredPrs.push(standardsOutcome.deferredPr)
      const auditResult = await runGeneralUtilityTask('post-clean-audit', { head })
      if (!auditResult?.posted) {
        blocker = cleanAuditBlocker(head, auditResult)
        break
      }
      phase = 'COPILOT'
      continue
    }
    if (findings.length > 0) {
      log(`Round ${rounds}: ${findings.length} finding(s) — applying fixes`)
      const fixResult = await applyFixes(head, findings, 'converge-round')
      const hadThreadBearingFinding = findings.some((each) => collectFindingThreadIds(each).length > 0)
      const fixProgress = detectFixProgress(fixResult, head, hadThreadBearingFinding)
      if (!fixProgress.progressed) {
        blocker = fixResult?.resolvedWithoutCommit === true && !hadThreadBearingFinding
          ? `fix stalled: converge round raised ${findings.length} in-memory finding(s) with no GitHub thread, the fix judged them all stale (resolvedWithoutCommit) and moved no code on HEAD ${head} — re-raising would loop to the iteration cap`
          : `fix lens landed no push for ${findings.length} finding(s) on HEAD ${head}`
        break
      }
      continue
    }
    if (!roundOutcome.roundClean) {
      log(`Round ${rounds}: a lens reported not-clean with no findings on ${head?.slice(0, 7)} — re-converging without a clean artifact`)
      continue
    }
    log(`Round ${rounds}: all lenses clean on ${head?.slice(0, 7)} — posting clean audit artifact`)
    const auditResult = await runGeneralUtilityTask('post-clean-audit', { head })
    if (!auditResult?.posted) {
      blocker = cleanAuditBlocker(head, auditResult)
      break
    }
    phase = 'COPILOT'
    continue
  }

  if (phase === 'COPILOT') {
    if (input.copilotDisabled) {
      copilotDown = true
      copilotNote = 'Copilot was skipped by the quota pre-check (out of premium-request quota, unreachable, or unconfigured) — the Copilot gate was bypassed and the PR was marked ready without a Copilot review'
      log('Copilot gate: the quota pre-check reported Copilot unavailable — skipping the Copilot gate with no agent spawned and proceeding to mark-ready with the gate bypassed.')
      phase = 'FINALIZE'
      continue
    }
    const copilot = await runCopilotGate(head)
    const copilotOutcome = classifyCopilotOutcome(copilot)
    copilotDown = resolveCopilotDown(copilotOutcome)
    copilotNote = null
    if (copilotOutcome.kind === 'retry') {
      log('Copilot gate agent died or returned an unreliable not-clean result with no findings — re-running the gate on the same HEAD')
      continue
    }
    if (copilotOutcome.kind === 'down') {
      log('Copilot gate: Copilot is down or out of quota — no review on HEAD after the poll cap. Logging a notice and proceeding to mark-ready with the Copilot gate bypassed.')
      copilotDown = true
      copilotNote = 'Copilot was down or out of quota — the Copilot gate was bypassed and the PR was marked ready without a Copilot review'
      phase = 'FINALIZE'
      continue
    }
    if (copilotOutcome.kind === 'fix') {
      if (isStandardsOnlyRound(copilotOutcome.findings)) {
        log(`Copilot raised ${copilotOutcome.findings.length} code-standard-only finding(s) — deferring to follow-up PRs and treating the gate as passed`)
        const standardsOutcome = await openStandardsFollowUpOnce(head, copilotOutcome.findings, 'copilot')
        standardsNote = standardsDeferralNote(copilotOutcome.findings.length, standardsOutcome.hardeningPrOpened)
        if (standardsOutcome?.deferredPr) deferredPrs.push(standardsOutcome.deferredPr)
        copilotDown = false
        copilotNote = null
        phase = 'FINALIZE'
        continue
      }
      log(`Copilot raised ${copilotOutcome.findings.length} finding(s) — fixing and re-converging`)
      const fixResult = await applyFixes(head, copilotOutcome.findings, 'copilot')
      const hadThreadBearingFinding = copilotOutcome.findings.some((each) => collectFindingThreadIds(each).length > 0)
      const fixProgress = detectFixProgress(fixResult, head, hadThreadBearingFinding)
      if (!fixProgress.progressed) {
        blocker = fixResult?.resolvedWithoutCommit === true && !hadThreadBearingFinding
          ? `fix stalled: copilot round raised ${copilotOutcome.findings.length} in-memory finding(s) with no GitHub thread, the fix judged them all stale (resolvedWithoutCommit) and moved no code on HEAD ${head} — re-raising would loop to the iteration cap`
          : `copilot fix lens landed no push for ${copilotOutcome.findings.length} finding(s) on HEAD ${head}`
        break
      }
      phase = 'CONVERGE'
      continue
    }
    copilotDown = false
    copilotNote = null
    phase = 'FINALIZE'
    continue
  }

  if (phase === 'FINALIZE') {
    const convergence = await runConvergenceCheck({ bugbotDown, copilotDown })
    const convergenceOutcome = classifyConvergenceOutcome(convergence)
    if (convergenceOutcome.kind === 'retry') {
      log('Convergence check agent died or returned no FAIL lines — re-running the check on the same HEAD')
      continue
    }
    if (convergenceOutcome.kind === 'ready') {
      const readyResult = await runGeneralUtilityTask('mark-ready', { head, copilotDown })
      const readyOutcome = classifyReadyOutcome(readyResult)
      if (readyOutcome.converged) {
        return { converged: true, rounds, finalSha: head, blocker: null, standardsNote, copilotNote, reuseNote, deferredPrs }
      }
      blocker = readyOutcome.blocker
      break
    }
    log(`Convergence check failed: ${convergenceOutcome.failures.join('; ')} — repairing then re-converging`)
    await repairConvergence(head, convergenceOutcome.failures)
    phase = 'CONVERGE'
    continue
  }
}

return {
  converged: false,
  rounds,
  finalSha: head,
  blocker: blocker || `iteration cap reached (${CONFIG.maxIterations})`,
  standardsNote,
  copilotNote,
  reuseNote,
  deferredPrs,
}
