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
    { title: 'Converge', detail: 'Bugbot + code-review + bug-audit in parallel each round; one clean-coder applies all fixes; loop until all three are clean on a stable HEAD' },
    { title: 'Copilot gate', detail: 'Request Copilot review and poll up to three times; route findings back into Converge; pass the gate when Copilot is out of usage' },
    { title: 'Finalize', detail: 'Run check_convergence.py; mark draft=false on a full pass' },
  ],
}

const CONFIG = {
  maxIterations: 20,
  copilotMaxPolls: 3,
  sharedScripts: '$HOME/.claude/skills/pr-converge/scripts',
  prLoopScripts: '$HOME/.claude/_shared/pr-loop/scripts',
  bugteamRubric: '$HOME/.claude/skills/bugteam/reference/audit-contract.md',
}

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
    down: { type: 'boolean', description: 'true when Copilot is out of usage (the requester hit their quota) so the gate is bypassed' },
    findings: LENS_SCHEMA.properties.findings,
    blocker: { type: ['string', 'null'], description: 'non-null when Copilot never surfaced a review after the poll cap' },
  },
  required: ['sha', 'clean', 'down', 'findings', 'blocker'],
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
  },
  required: ['newSha', 'pushed', 'resolvedWithoutCommit', 'summary'],
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
 * Decide whether a resolved HEAD SHA is safe to spawn lenses against. A dead
 * resolve-head agent or a malformed result yields a falsy SHA; spawning lenses
 * against it interpolates the literal string 'HEAD undefined' into their prompts
 * and produces a spurious clean verdict on a non-existent commit.
 * @param {string|null|undefined} resolvedHead the SHA from resolveHead()
 * @returns {boolean} true only when the SHA is a non-empty string
 */
function isResolvedHeadUsable(resolvedHead) {
  return typeof resolvedHead === 'string' && resolvedHead.length > 0
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
 * Copilot review. A down result — Copilot out of usage because the requester hit
 * their quota — passes the gate so a usage outage never blocks the run, the same
 * way a down Bugbot lens is bypassed; this is checked before the blocker so a
 * usage outage is a pass, not a no-show. A non-null blocker ends the run;
 * findings route to a fix step. The gate otherwise approves only when it
 * explicitly reports clean:true with no findings — a clean:false result with
 * zero findings is an unreliable or malformed gate response and retries rather
 * than advancing to Finalize, so a PR never goes ready on a HEAD Copilot did not
 * call clean.
 * @param {object|null|undefined} copilot the Copilot gate result, or null on agent failure
 * @returns {{kind: string, blocker?: string, findings?: Array<object>}} the next action
 */
function classifyCopilotOutcome(copilot) {
  if (copilot == null) return { kind: 'retry' }
  if (copilot.down === true) return { kind: 'approved' }
  if (copilot.blocker) return { kind: 'blocker', blocker: copilot.blocker }
  if (copilot.findings.length > 0) return { kind: 'fix', findings: copilot.findings }
  if (copilot.clean === true) return { kind: 'approved' }
  return { kind: 'retry' }
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
const prCoordinates = `owner=${input.owner} repo=${input.repo} PR #${input.prNumber} (https://github.com/${input.owner}/${input.repo}/pull/${input.prNumber})`

/**
 * Resolve the current PR HEAD SHA from GitHub.
 * @returns {Promise<string>} the 40-char HEAD SHA
 */
async function resolveHead() {
  const head = await agent(
    `Print the current HEAD SHA of ${prCoordinates}. Run exactly:\n` +
      `gh api repos/${input.owner}/${input.repo}/pulls/${input.prNumber} --jq .head.sha\n` +
      `Return the full 40-character SHA in the sha field. Do not modify any files.`,
    { label: 'resolve-head', phase: 'Converge', schema: HEAD_SCHEMA, agentType: 'Explore' },
  )
  return head?.sha
}

/**
 * Fetch origin/main once per round before the parallel lenses spawn. The
 * code-review and bug-audit lenses both diff against origin/main; running their
 * own git fetch in parallel contends on the worktree .git lock and fails
 * intermittently, so a single serial fetch here keeps the ref current and the
 * parallel lenses do no git fetch of their own.
 * @returns {Promise<string>} agent transcript (unused)
 */
function prefetchMainForRound() {
  return agent(
    `Refresh the base ref for ${prCoordinates} so the parallel review lenses can diff against an up-to-date origin/main without each running its own fetch. Run exactly:\n` +
      `git fetch origin main\n` +
      `Do not edit, commit, push, rebase, or modify any files — fetch only.`,
    { label: 'prefetch-main', phase: 'Converge', agentType: 'Explore' },
  )
}

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
  return agent(
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
  return agent(
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
  return agent(
    `You are the second-opinion bug-audit lens for ${prCoordinates}, HEAD ${head}.\n\n` +
      `Read the audit rubric at ${CONFIG.bugteamRubric} and apply its categories (A through P) against the FULL origin/main...HEAD diff — every file the PR touches, never a delta cut. The workflow already fetched origin/main this round, so do NOT run git fetch; run git diff --name-only origin/main...HEAD first to enumerate scope.\n\n` +
      `This is a clean-room audit: assume nothing from other lenses. Report only findings backed by concrete file:line evidence. Do NOT edit, commit, or push.\n\n` +
      `Return strictly the schema: clean=true with empty findings when the diff passes every category, otherwise one entry per finding (severity P0/P1/P2; category 'code-standard' for pure CODE_RULES/style violations with no behavioral impact, 'bug' otherwise; replyToCommentId=null). Set sha=${'`'}${head}${'`'}, down=false.`,
    { label: 'lens:bug-audit', phase: 'Converge', schema: LENS_SCHEMA, agentType: 'code-quality-agent' },
  )
}

/**
 * Fix lens: one clean-coder applies every finding in a single TDD commit,
 * pushes, then replies to and resolves any real GitHub review threads.
 * @param {string} head PR HEAD SHA the findings were raised against
 * @param {Array<object>} findings deduped findings across all lenses
 * @param {string} sourceLabel short description of where the findings came from
 * @returns {Promise<object>} FIX_SCHEMA result
 */
function applyFixes(head, findings, sourceLabel) {
  const findingsBlock = findings
    .map((each, position) => {
      const eachThreadIds = collectFindingThreadIds(each)
      const threadNote = eachThreadIds.length
        ? `\n   (GitHub review comment ids: ${eachThreadIds.join(', ')})`
        : ''
      return `${position + 1}. [${each.severity}] ${each.file}:${each.line} — ${each.title}\n   ${each.detail}${threadNote}`
    })
    .join('\n')
  const threadIds = findings
    .flatMap((each) => collectFindingThreadIds(each))
    .filter((each) => typeof each === 'number')
  return agent(
    `You are fixing ${findings.length} finding(s) (${sourceLabel}) on ${prCoordinates}, HEAD ${head}.\n\n` +
      `Findings:\n${findingsBlock}\n\n` +
      `Rules:\n` +
      `- Confirm the working tree is on the PR branch at HEAD ${head} with no unrelated edits before you start.\n` +
      `- Fix every finding test-first (failing test, then minimum code to pass) per CODE_RULES. Verify each concern against current code; a finding whose concern no longer applies needs no code change but still needs its thread resolved.\n` +
      `- Make ONE commit for all fixes, then push to the PR branch.\n` +
      `- For each finding that carries a GitHub review comment id (${threadIds.length ? threadIds.join(', ') : 'none this batch'}): post an inline reply with python "${CONFIG.sharedScripts}/post_fix_reply.py" --owner ${input.owner} --repo ${input.repo} --pr-number ${input.prNumber} --in-reply-to <id> --body "<what changed>". Then resolve the PR review thread by thread node id (PRRT_...): look up the thread id for that comment via GraphQL (match on comment databaseId == <id> in the pull request's reviewThreads), then call the github MCP pull_request_review_write method=resolve_thread with threadId=<PRRT_...> (not the numeric comment id), or run the resolveReviewThread GraphQL mutation with the same threadId.\n` +
      `- Findings with replyToCommentId null are in-memory audit findings: fix them, no reply needed.\n\n` +
      `Return values:\n` +
      `- When you commit and push a fix: newSha=the new HEAD SHA after your push, pushed=true, resolvedWithoutCommit=false.\n` +
      `- When every finding was already addressed so no code change is needed — yet you still resolved each GitHub review thread above: newSha=${head} (the unchanged HEAD), pushed=false, resolvedWithoutCommit=true. Only set this when every thread that carries a comment id is resolved; otherwise the round is treated as stalled.\n` +
      `Always include a one-line summary.`,
    { label: `fix:${sourceLabel}`, phase: 'Converge', schema: FIX_SCHEMA, agentType: 'clean-coder' },
  )
}

/**
 * Post the terminal CLEAN bugteam audit artifact so check_convergence.py sees
 * a clean bugteam review on the converged HEAD.
 * @param {string} head converged PR HEAD SHA
 * @returns {Promise<string>} agent transcript (unused)
 */
function postCleanAudit(head) {
  return agent(
    `Post a CLEAN bugteam audit review on ${prCoordinates} at commit ${head}. All review lenses are clean on this HEAD.\n\n` +
      `Write an empty findings file: create a temp file containing exactly [] (an empty JSON array). Then run:\n` +
      `python "${CONFIG.prLoopScripts}/post_audit_thread.py" --skill bugteam --owner ${input.owner} --repo ${input.repo} --pr-number ${input.prNumber} --commit ${head} --state CLEAN --findings-json <temp-file>\n` +
      `Run the script with --help first if any flag name differs. This posts the APPROVE review body that check_convergence.py reads for the bugteam gate. Do not edit code, commit, or push.`,
    { label: 'post-clean-audit', phase: 'Converge', agentType: 'general-purpose' },
  )
}

/**
 * Copilot gate: request a Copilot review on HEAD and poll until it lands or the
 * poll cap is hit; return Copilot's findings, an out-of-usage down signal, or a
 * blocker. When Copilot is out of usage (the requester hit their quota) it posts
 * an out-of-usage notice rather than a review; the gate reports that as down so
 * the run passes the gate and moves on instead of waiting out the poll cap.
 * @param {string} head converged PR HEAD SHA
 * @returns {Promise<object>} COPILOT_SCHEMA result
 */
function runCopilotGate(head) {
  return agent(
    `You are the Copilot gate for ${prCoordinates}, HEAD ${head}. Do not edit code, commit, or push.\n\n` +
      `Copilot can run out of usage. When the newest Copilot review on HEAD carries an out-of-usage notice — a body stating Copilot was unable to review because the user who requested the review has reached their quota limit, or any equivalent quota / premium-request / usage-limit exhaustion message rather than an actual code review — Copilot is down for this run: return {sha:${'`'}${head}${'`'}, clean:true, down:true, findings:[], blocker:null} and stop. Do NOT re-request a review, do NOT keep polling, and do NOT treat the notice as a finding.\n\n` +
      `1. Read any existing Copilot review on HEAD first: python "${CONFIG.sharedScripts}/fetch_copilot_reviews.py" --owner ${input.owner} --repo ${input.repo} --pr-number ${input.prNumber}. This lists every Copilot review across all commits newest-first; only count entries whose commit_id starts with ${head}. If the newest such HEAD-scoped Copilot review is the out-of-usage notice above -> return the down result and stop. A notice on any earlier commit is NOT down: ignore it and continue. With no Copilot review on HEAD, skip a duplicate request: python "${CONFIG.sharedScripts}/check_pending_reviews.py" --owner ${input.owner} --repo ${input.repo} --pr-number ${input.prNumber} --user copilot. Exit 0 means a request is already pending; otherwise request one:\n` +
      `   gh api --method POST repos/${input.owner}/${input.repo}/pulls/${input.prNumber}/requested_reviewers -f 'reviewers[]=copilot-pull-request-reviewer[bot]'\n` +
      `2. Poll for Copilot's review on HEAD ${head}: up to ${CONFIG.copilotMaxPolls} attempts, 360 seconds apart (delay each attempt with "sleep 360", or the PowerShell alternative "Start-Sleep -Seconds 360"). Each attempt: python "${CONFIG.sharedScripts}/fetch_copilot_reviews.py" --owner ${input.owner} --repo ${input.repo} --pr-number ${input.prNumber} for the top-level review state, plus gh api "repos/${input.owner}/${input.repo}/pulls/${input.prNumber}/comments" --paginate --slurp for inline comment ids (Copilot's login contains "copilot", case-insensitive). Only count entries whose commit_id starts with ${head}.\n` +
      `   - Out-of-usage notice on HEAD -> return the down result above (clean:true, down:true) and stop.\n` +
      `   - Copilot review present and clean/approved on HEAD -> return {sha:${'`'}${head}${'`'}, clean:true, down:false, findings:[], blocker:null}.\n` +
      `   - Copilot findings on HEAD -> return them (each with its inline comment id in replyToCommentId; category 'code-standard' for pure CODE_RULES/style violations with no behavioral impact, 'bug' otherwise), clean:false, down:false, blocker:null.\n` +
      `   - No review after ${CONFIG.copilotMaxPolls} attempts -> return {sha:${'`'}${head}${'`'}, clean:false, down:false, findings:[], blocker:"Copilot did not surface a review on HEAD after ${CONFIG.copilotMaxPolls} polls"}.\n\n` +
      `Return strictly the schema.`,
    { label: 'copilot-gate', phase: 'Copilot gate', schema: COPILOT_SCHEMA },
  )
}

/**
 * Run the authoritative convergence gate.
 * @param {boolean} bugbotDown pass --bugbot-down when Bugbot is opted out or proved unreachable this run
 * @returns {Promise<object>} CONVERGENCE_SCHEMA result
 */
function checkConvergence(bugbotDown) {
  const bugbotDownFlag = bugbotDown ? ' --bugbot-down' : ''
  return agent(
    `Run the convergence gate for ${prCoordinates} and report the result. Do not edit code.\n\n` +
      `Run: python "${CONFIG.sharedScripts}/check_convergence.py" --owner ${input.owner} --repo ${input.repo} --pr-number ${input.prNumber}${bugbotDownFlag}\n\n` +
      `Exit 0 -> every gate passed: return {pass:true, failures:[]}.\n` +
      `Exit 1 -> return {pass:false, failures:[<each printed FAIL line verbatim>]}.\n` +
      `Exit 2 -> retry once; if it still errors, return {pass:false, failures:["check_convergence gh error"]}.`,
    { label: 'check-convergence', phase: 'Finalize', schema: CONVERGENCE_SCHEMA, agentType: 'Explore' },
  )
}

/**
 * Mark the PR ready for review (draft=false) and confirm the transition landed.
 * @param {string} head converged PR HEAD SHA
 * @returns {Promise<object>} READY_SCHEMA result
 */
function markReady(head) {
  return agent(
    `All convergence gates pass for ${prCoordinates} on HEAD ${head}. Mark the PR ready, then confirm it left draft state. Do not edit code.\n\n` +
      `1. Run: gh pr ready ${input.prNumber} --repo ${input.owner}/${input.repo}\n` +
      `2. Re-query the draft state: gh api repos/${input.owner}/${input.repo}/pulls/${input.prNumber} --jq .draft\n` +
      `Return {ready:true} only when step 2 prints false (the PR is no longer a draft). If step 1 errors or step 2 still prints true, return {ready:false}.`,
    { label: 'mark-ready', phase: 'Finalize', schema: READY_SCHEMA, agentType: 'general-purpose' },
  )
}

/**
 * Address the gates a convergence check reported as failing, then hand control
 * back to the converge phase. Resolves lingering bot threads and rebases when
 * the PR is not mergeable.
 * @param {string} head current PR HEAD SHA
 * @param {Array<string>} failures FAIL lines from the convergence check
 * @returns {Promise<object>} FIX_SCHEMA result
 */
function repairConvergence(head, failures) {
  const failureBlock = failures.length
    ? failures.map((each, position) => `${position + 1}. ${each}`).join('\n')
    : 'none reported'
  return agent(
    `The convergence check for ${prCoordinates} failed these gates on HEAD ${head}:\n${failureBlock}\n\n` +
      `Address only the failing gates:\n` +
      `- Unresolved bot review threads: fetch the threads where isResolved is false (gh api graphql, or the github MCP pull_request_read get_review_comments), then keep only the bot-authored ones — a thread whose root comment author login contains "cursor", "claude", or "copilot" (case-insensitive substring). Explicitly skip every human reviewer thread; the convergence gate counts only unresolved bot threads, so touching a human thread is out of scope. For each bot thread, verify the concern against current code; if it still applies, fix it test-first; either way post an inline reply and resolve the thread.\n` +
      `- PR not mergeable: rebase onto origin/main and force-push (git fetch origin main; git rebase origin/main; resolve conflicts; git push --force-with-lease).\n` +
      `- A dirty bot review or a still-pending requested reviewer: leave it; the next round re-runs that reviewer.\n` +
      `Make at most one commit for any code fix. Return the HEAD SHA after any push in newSha (the unchanged ${head} when nothing was pushed), pushed true/false, resolvedWithoutCommit=false (this gate already accepts an unchanged HEAD), and a one-line summary.`,
    { label: 'repair-convergence', phase: 'Finalize', schema: FIX_SCHEMA, agentType: 'clean-coder' },
  )
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
 * Defer a standards-only round: one agent files a GitHub issue listing every
 * code-standard finding, opens a draft PR hardening the Claude environment
 * (hooks/rules) so those violation classes are blocked before code is written,
 * and replies to / resolves any GitHub threads the findings carry, noting the
 * deferral. This PR's branch is never touched.
 * @param {string} head PR HEAD SHA the findings were raised against
 * @param {Array<object>} findings deduped code-standard-only findings
 * @param {string} sourceLabel short description of where the findings came from
 * @returns {Promise<string>} agent transcript (unused)
 */
function spawnStandardsFollowUp(head, findings, sourceLabel) {
  const findingsBlock = findings
    .map((each, position) => {
      const eachThreadIds = collectFindingThreadIds(each)
      const threadNote = eachThreadIds.length
        ? `\n   (GitHub review comment ids: ${eachThreadIds.join(', ')})`
        : ''
      return `${position + 1}. [${each.severity}] ${each.file}:${each.line} — ${each.title}\n   ${each.detail}${threadNote}`
    })
    .join('\n')
  return agent(
    `A review round on ${prCoordinates}, HEAD ${head}, surfaced ONLY code-standard violations (CODE_RULES/style, no behavioral impact). The convergence run treats the round as passed and defers these to follow-up work, which you now create. Do NOT commit or push to the PR's own branch.\n\n` +
      `Findings:\n${findingsBlock}\n\n` +
      `1. Follow-up fix issue: file a GitHub issue on ${input.owner}/${input.repo} (gh issue create --body-file with a temp file) titled "Deferred code-standard fixes from PR #${input.prNumber}". The body references the PR and lists each finding with its file:line, severity, and detail. The issue carries the fix work; do not open a fix PR.\n` +
      `2. Environment-hardening PR: in the Claude environment config repo (the repo owning ~/.claude hooks and rules — JonEcho/llm-settings for hooks, jl-cmd/claude-code-config for rules/skills; pick whichever owns the needed surface), create a branch and open a DRAFT PR that hardens hooks/rules so each violation class found here is blocked at Write/Edit time, before code is written or reviewed. Reference the issue from step 1 in the PR body.\n` +
      `3. For each finding that carries a GitHub review comment id: post an inline reply via python "${CONFIG.sharedScripts}/post_fix_reply.py" --owner ${input.owner} --repo ${input.repo} --pr-number ${input.prNumber} --in-reply-to <id> --body "Code-standard-only finding — deferred to follow-up issue <url>." Then resolve the thread by its PRRT_ node id (GraphQL lookup on comment databaseId, then resolveReviewThread or the github MCP pull_request_review_write method=resolve_thread).\n\n` +
      `Return a one-line summary naming the follow-up issue URL and the hardening PR URL.`,
    { label: `standards-followup:${sourceLabel}`, phase: 'Converge', agentType: 'clean-coder' },
  )
}

let phase = 'CONVERGE'
let head = null
let rounds = 0
let iterations = 0
let blocker = null
let bugbotDown = input.bugbotDisabled || false
let standardsNote = null

while (iterations < CONFIG.maxIterations) {
  iterations += 1
  if (phase === 'CONVERGE') {
    rounds += 1
    head = await resolveHead()
    if (!isResolvedHeadUsable(head)) {
      log(`Round ${rounds}: resolve-head agent returned no SHA — retrying without spawning lenses`)
      continue
    }
    await prefetchMainForRound()
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
      await spawnStandardsFollowUp(head, findings, 'converge-round')
      standardsNote = `${findings.length} code-standard finding(s) deferred to a follow-up fix issue plus an environment-hardening PR — verify both land`
      await postCleanAudit(head)
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
    await postCleanAudit(head)
    phase = 'COPILOT'
    continue
  }

  if (phase === 'COPILOT') {
    const copilot = await runCopilotGate(head)
    const copilotOutcome = classifyCopilotOutcome(copilot)
    if (copilotOutcome.kind === 'retry') {
      log('Copilot gate agent died or returned an unreliable not-clean result with no findings — re-running the gate on the same HEAD')
      continue
    }
    if (copilotOutcome.kind === 'blocker') {
      blocker = copilotOutcome.blocker
      break
    }
    if (copilotOutcome.kind === 'fix') {
      if (isStandardsOnlyRound(copilotOutcome.findings)) {
        log(`Copilot raised ${copilotOutcome.findings.length} code-standard-only finding(s) — deferring to follow-up PRs and treating the gate as passed`)
        await spawnStandardsFollowUp(head, copilotOutcome.findings, 'copilot')
        standardsNote = `${copilotOutcome.findings.length} code-standard finding(s) deferred to a follow-up fix issue plus an environment-hardening PR — verify both land`
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
    phase = 'FINALIZE'
    continue
  }

  if (phase === 'FINALIZE') {
    const convergence = await checkConvergence(bugbotDown)
    const convergenceOutcome = classifyConvergenceOutcome(convergence)
    if (convergenceOutcome.kind === 'retry') {
      log('Convergence check agent died or returned no FAIL lines — re-running the check on the same HEAD')
      continue
    }
    if (convergenceOutcome.kind === 'ready') {
      const readyResult = await markReady(head)
      const readyOutcome = classifyReadyOutcome(readyResult)
      if (readyOutcome.converged) {
        return { converged: true, rounds, finalSha: head, blocker: null, standardsNote }
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
}
