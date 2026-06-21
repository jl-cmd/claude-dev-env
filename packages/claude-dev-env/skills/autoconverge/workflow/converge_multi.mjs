/**
 * Autoconverge multi-PR fan-out workflow driver.
 *
 * SINGLE-FILE CONTRACT — keep this file self-contained. The Workflow runtime
 * wraps this body in a function (so top-level await and return work) and rejects
 * static import statements, and `export const meta` must be the first statement.
 * This driver fans out one converge.mjs child run per PR with parallel(); the
 * converge.mjs child uses only agent()/parallel() (never workflow()), so the
 * one-level workflow() nesting limit holds.
 */

export const meta = {
  name: 'autoconverge-multi',
  description: 'Drive several draft PRs to convergence in one run: fan out one autoconverge converge.mjs child per PR in parallel, each pinned to its own checked-out worktree via repoPath, then report every PR\'s outcome together.',
  whenToUse: 'Launched by the /autoconverge skill when the user names more than one PR to converge at once; the single-PR path launches workflow/converge.mjs directly.',
  phases: [
    { title: 'Converge all', detail: 'One converge.mjs child run per PR, all in parallel; each child is pinned to its own PR worktree through repoPath' },
  ],
}

/**
 * Normalize the workflow args global into a parsed object.
 *
 * The Workflow runtime may deliver args as a JSON-encoded string or as an
 * object; a string is parsed and an object passes through unchanged. A non-JSON
 * or empty string yields null so a malformed payload becomes a structured
 * blocker rather than aborting the run.
 * @param {string|object} rawArgs the workflow args global (JSON string or object)
 * @returns {object|null} the parsed args, or null when a string payload fails to parse
 */
function normalizeMultiInput(rawArgs) {
  if (typeof rawArgs !== 'string') return rawArgs
  try {
    return JSON.parse(rawArgs)
  } catch {
    return null
  }
}

/**
 * Decide whether one PR entry carries every coordinate a child run needs.
 *
 * A child converge run needs the PR's owner, repo, and number to address its
 * GitHub calls, and the absolute worktree path the PR is checked out in to pin
 * its agents there.
 * @param {object} prEntry one element of the args.prs array
 * @returns {boolean} true when owner, repo, prNumber, and a non-empty string repoPath are all present
 */
function isUsablePrEntry(prEntry) {
  return (
    prEntry != null &&
    Boolean(prEntry.owner) &&
    Boolean(prEntry.repo) &&
    Boolean(prEntry.prNumber) &&
    typeof prEntry.repoPath === 'string' &&
    Boolean(prEntry.repoPath)
  )
}

/**
 * Validate the normalized multi-PR input into usable coordinates or a blocker.
 *
 * A fan-out run needs the absolute converge.mjs script path and a non-empty list
 * of PR entries that each carry owner, repo, prNumber, and the absolute worktree
 * path the PR is checked out in. A payload that fails to parse, a non-string
 * convergeScriptPath, a missing or empty prs list, or any entry missing a
 * coordinate yields a blocker the top-level run reports as
 * {converged:false, blocker} rather than throwing on a missing field.
 * @param {string|object} rawArgs the workflow args global (JSON string or object)
 * @returns {{input: object|null, blocker: string|null}} usable coordinates or a blocker
 */
function classifyMultiInput(rawArgs) {
  const candidate = normalizeMultiInput(rawArgs)
  if (candidate == null) {
    return {
      input: null,
      blocker: 'invalid run coordinates: the workflow args did not parse into an object',
    }
  }
  if (typeof candidate.convergeScriptPath !== 'string' || !candidate.convergeScriptPath) {
    return {
      input: null,
      blocker:
        'invalid run coordinates: convergeScriptPath (absolute path to converge.mjs) is required',
    }
  }
  if (!Array.isArray(candidate.prs) || candidate.prs.length === 0) {
    return {
      input: null,
      blocker: 'invalid run coordinates: prs must be a non-empty array of PR entries',
    }
  }
  const unusableEntryCount = candidate.prs.filter(
    (eachEntry) => !isUsablePrEntry(eachEntry),
  ).length
  if (unusableEntryCount > 0) {
    return {
      input: null,
      blocker: `invalid run coordinates: ${unusableEntryCount} PR entry/entries missing owner, repo, prNumber, or repoPath`,
    }
  }
  return { input: candidate, blocker: null }
}

const multiInput = classifyMultiInput(args)
if (multiInput.blocker) {
  return { converged: false, prCount: 0, convergedCount: 0, results: [], blocker: multiInput.blocker }
}
const input = multiInput.input

phase('Converge all')
log(`autoconverge multi-PR: driving ${input.prs.length} PR(s) to ready in parallel`)

const childResults = await parallel(
  input.prs.map((eachPr) => async () => {
    const childOutcome = await workflow(
      { scriptPath: input.convergeScriptPath },
      {
        owner: eachPr.owner,
        repo: eachPr.repo,
        prNumber: eachPr.prNumber,
        repoPath: eachPr.repoPath,
        bugbotDisabled: Boolean(eachPr.bugbotDisabled),
      },
    )
    return {
      owner: eachPr.owner,
      repo: eachPr.repo,
      prNumber: eachPr.prNumber,
      converged: Boolean(childOutcome && childOutcome.converged),
      rounds: childOutcome && childOutcome.rounds !== undefined ? childOutcome.rounds : null,
      finalSha: childOutcome && childOutcome.finalSha !== undefined ? childOutcome.finalSha : null,
      blocker: childOutcome && childOutcome.blocker !== undefined ? childOutcome.blocker : null,
    }
  }),
)

const results = childResults.map((eachResult, eachIndex) =>
  eachResult === null
    ? {
        owner: input.prs[eachIndex].owner,
        repo: input.prs[eachIndex].repo,
        prNumber: input.prs[eachIndex].prNumber,
        converged: false,
        rounds: null,
        finalSha: null,
        blocker: 'child run threw or was skipped before returning an outcome',
      }
    : eachResult,
)

const convergedCount = results.filter((eachResult) => eachResult.converged).length
log(`autoconverge multi-PR done: ${convergedCount}/${results.length} PR(s) converged`)

return {
  converged: convergedCount === results.length,
  prCount: results.length,
  convergedCount,
  results,
  blocker: null,
}
