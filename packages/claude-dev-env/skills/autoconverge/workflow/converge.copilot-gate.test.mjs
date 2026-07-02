import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const workflowDirectory = dirname(fileURLToPath(import.meta.url));
const convergeSource = readFileSync(join(workflowDirectory, 'converge.mjs'), 'utf8');

function functionBody(functionName) {
  const functionStart = convergeSource.indexOf(`function ${functionName}(`);
  assert.notEqual(functionStart, -1, `expected ${functionName} to exist`);
  const nextFunctionStart = convergeSource.indexOf('\nfunction ', functionStart + 1);
  const functionEnd = nextFunctionStart === -1 ? convergeSource.length : nextFunctionStart;
  return convergeSource.slice(functionStart, functionEnd);
}

const productionModule = new Function(
  `${functionBody('classifyCopilotOutcome')}\n` +
    `${functionBody('resolveCopilotDown')}\n` +
    'return { classifyCopilotOutcome, resolveCopilotDown };',
)();
const { classifyCopilotOutcome, resolveCopilotDown } = productionModule;

function copilotResult(overrides) {
  return {
    sha: 'abcdef0',
    clean: false,
    down: false,
    findings: [],
    ...overrides,
  };
}

test('an out-of-usage Copilot result (down) routes to the down kind', () => {
  const outcome = classifyCopilotOutcome(copilotResult({ clean: true, down: true }));
  assert.equal(outcome.kind, 'down');
});

test('a down Copilot result routes to down even when clean is false', () => {
  const outcome = classifyCopilotOutcome(copilotResult({ clean: false, down: true }));
  assert.equal(outcome.kind, 'down');
});

test('a dead Copilot gate agent retries rather than passing', () => {
  assert.equal(classifyCopilotOutcome(null).kind, 'retry');
});

test('a reachable Copilot gate with no findings and no clean verdict retries', () => {
  const outcome = classifyCopilotOutcome(copilotResult({ clean: false, down: false }));
  assert.equal(outcome.kind, 'retry');
});

test('Copilot findings route to a fix when Copilot is reachable and not down', () => {
  const outcome = classifyCopilotOutcome(
    copilotResult({
      findings: [
        {
          file: 'a.py',
          line: 1,
          severity: 'P1',
          category: 'bug',
          title: 't',
          detail: 'd',
          replyToCommentId: null,
        },
      ],
    }),
  );
  assert.equal(outcome.kind, 'fix');
});

test('COPILOT_SCHEMA carries a required down field', () => {
  const schemaStart = convergeSource.indexOf('const COPILOT_SCHEMA =');
  const schemaEnd = convergeSource.indexOf('const HEAD_SCHEMA =');
  assert.notEqual(schemaStart, -1, 'expected COPILOT_SCHEMA to exist');
  const schemaSource = convergeSource.slice(schemaStart, schemaEnd);
  assert.match(schemaSource, /down:\s*\{\s*type:\s*'boolean'/);
  assert.match(schemaSource, /required:\s*\[[^\]]*'down'[^\]]*\]/);
  assert.doesNotMatch(
    schemaSource,
    /blocker:/,
    'the Copilot gate no longer surfaces a blocker; a down result carries the outage',
  );
});

test('the Copilot gate prompt detects an out-of-usage notice and returns a down result', () => {
  const copilotPrompt = functionBody('runCopilotGate');
  assert.match(
    copilotPrompt,
    /quota|out of usage|out-of-usage/i,
    'expected the gate to name the out-of-usage / quota signal',
  );
  assert.match(
    copilotPrompt,
    /down:\s*true/,
    'expected the gate to return down:true on an out-of-usage notice',
  );
});

test('the step-1 out-of-usage down-detection requires the notice commit_id to start with HEAD', () => {
  const copilotPrompt = functionBody('runCopilotGate');
  const stepOneStart = copilotPrompt.indexOf('`1.');
  assert.notEqual(stepOneStart, -1, 'expected a step-1 instruction in the gate prompt');
  const stepTwoStart = copilotPrompt.indexOf('`2.', stepOneStart);
  assert.notEqual(stepTwoStart, -1, 'expected a step-2 instruction in the gate prompt');
  const stepOneText = copilotPrompt.slice(stepOneStart, stepTwoStart);
  assert.match(
    stepOneText,
    /commit_id starts with \$\{head\}/,
    'expected step 1 to scope the out-of-usage notice to reviews whose commit_id starts with HEAD, matching step 2 and the convergence gate',
  );
});

test('a Copilot no-show after the poll cap returns a down result rather than a blocker', () => {
  const copilotPrompt = functionBody('runCopilotGate');
  const noReviewStart = copilotPrompt.indexOf('No review after');
  assert.notEqual(noReviewStart, -1, 'expected a no-show branch in the gate prompt');
  const noReviewBranch = copilotPrompt.slice(noReviewStart, noReviewStart + 200);
  assert.match(
    noReviewBranch,
    /down:\s*true/,
    'expected a Copilot no-show after the poll cap to return down:true',
  );
  assert.doesNotMatch(
    noReviewBranch,
    /blocker:/,
    'expected the no-show branch to carry a down result, not a blocker',
  );
});

test('the Copilot gate accepts a COMMENTED review with no inline findings as a clean pass', () => {
  const copilotPrompt = functionBody('runCopilotGate');
  assert.match(
    copilotPrompt,
    /COMMENTED with no inline findings/,
    'expected the clean-pass branch to accept a COMMENTED review with no inline findings, matching the canonical ALL_COPILOT_CLEAN_REVIEW_STATES rule where a Copilot COMMENTED review is a clean state',
  );
});

test('the Copilot gate polls long enough to catch a normal-latency Copilot review', () => {
  const budgetMatch = convergeSource.match(/copilotMaxPolls:\s*(\d+)/);
  assert.notEqual(budgetMatch, null, 'expected copilotMaxPolls in CONFIG');
  assert.ok(
    Number(budgetMatch[1]) >= 6,
    `expected copilotMaxPolls >= 6 (>= ~36 min at 360s per attempt) so a normal-latency Copilot review lands before the no-show fallback triggers, got ${budgetMatch[1]}`,
  );
});

test('runConvergenceCheck wires the --copilot-down flag from the copilotDown context', () => {
  const checkConvergenceBody = functionBody('runConvergenceCheck');
  assert.match(
    checkConvergenceBody,
    /context\.copilotDown \? ' --copilot-down' : ''/,
    'expected runConvergenceCheck to append --copilot-down when copilotDown is set',
  );
  assert.match(
    checkConvergenceBody,
    /\$\{copilotDownFlag\}/,
    'expected the --copilot-down flag to be interpolated into the script invocation',
  );
});

test('the COPILOT phase routes a down outcome to FINALIZE with the gate bypassed', () => {
  const copilotPhaseStart = convergeSource.indexOf("if (phase === 'COPILOT') {");
  assert.notEqual(copilotPhaseStart, -1, 'expected a COPILOT phase block');
  const downBranchStart = convergeSource.indexOf("copilotOutcome.kind === 'down'", copilotPhaseStart);
  assert.notEqual(downBranchStart, -1, 'expected the COPILOT phase to handle a down outcome');
  const downBranch = convergeSource.slice(downBranchStart, downBranchStart + 400);
  assert.match(downBranch, /copilotDown = true/);
  assert.match(downBranch, /copilotNote =/);
  assert.match(downBranch, /phase = 'FINALIZE'/);
});

test('resolveCopilotDown reports down only for a down outcome', () => {
  assert.equal(resolveCopilotDown({ kind: 'down' }), true);
});

test('resolveCopilotDown clears the bypass for an approved outcome', () => {
  assert.equal(resolveCopilotDown({ kind: 'approved' }), false);
});

test('resolveCopilotDown clears the bypass for a fix outcome carrying findings', () => {
  assert.equal(
    resolveCopilotDown({
      kind: 'fix',
      findings: [
        {
          file: 'a.py',
          line: 1,
          severity: 'P1',
          category: 'bug',
          title: 't',
          detail: 'd',
          replyToCommentId: null,
        },
      ],
    }),
    false,
  );
});

test('resolveCopilotDown clears the bypass for a retry outcome', () => {
  assert.equal(resolveCopilotDown({ kind: 'retry' }), false);
});

test('the standards-only Copilot sub-path resets copilotDown before FINALIZE', () => {
  const standardsBranchStart = convergeSource.indexOf(
    'isStandardsOnlyRound(copilotOutcome.findings)',
  );
  assert.notEqual(
    standardsBranchStart,
    -1,
    'expected the COPILOT phase to handle a standards-only Copilot fix outcome',
  );
  const standardsBranch = convergeSource.slice(standardsBranchStart, standardsBranchStart + 800);
  const resetIndex = standardsBranch.indexOf('copilotDown = false');
  const finalizeIndex = standardsBranch.indexOf("phase = 'FINALIZE'");
  assert.notEqual(
    resetIndex,
    -1,
    'expected the standards-only sub-path to reset copilotDown so a recovered Copilot is not bypassed',
  );
  assert.notEqual(finalizeIndex, -1, 'expected the standards-only sub-path to reach FINALIZE');
  assert.ok(
    resetIndex < finalizeIndex,
    'expected copilotDown to be cleared before the transition to FINALIZE',
  );
  assert.match(
    standardsBranch.slice(0, finalizeIndex),
    /copilotNote = null/,
    'expected the standards-only sub-path to clear the stale copilotNote alongside copilotDown',
  );
});

test('the COPILOT phase recomputes copilotDown from each gate outcome via resolveCopilotDown', () => {
  const copilotPhaseStart = convergeSource.indexOf("if (phase === 'COPILOT') {");
  assert.notEqual(copilotPhaseStart, -1, 'expected a COPILOT phase block');
  const finalizePhaseStart = convergeSource.indexOf(
    "if (phase === 'FINALIZE') {",
    copilotPhaseStart,
  );
  assert.notEqual(finalizePhaseStart, -1, 'expected a FINALIZE phase block after COPILOT');
  const copilotPhase = convergeSource.slice(copilotPhaseStart, finalizePhaseStart);
  assert.match(
    copilotPhase,
    /copilotDown = resolveCopilotDown\(copilotOutcome\)/,
    'expected the COPILOT phase to recompute copilotDown from the current outcome so a recovered Copilot is never bypassed',
  );
});

test('markReady receives copilotDown so it can opt the unflagged hook out of the Copilot gate', () => {
  const finalizeStart = convergeSource.indexOf("if (phase === 'FINALIZE') {");
  assert.notEqual(finalizeStart, -1, 'expected a FINALIZE phase block');
  const markReadyCall = convergeSource.indexOf("'mark-ready'", finalizeStart);
  assert.notEqual(markReadyCall, -1, 'expected the FINALIZE phase to route mark-ready through the general-utility agent');
  const callSlice = convergeSource.slice(markReadyCall - 20, markReadyCall + 60);
  assert.match(
    callSlice,
    /copilotDown/,
    'expected mark-ready context to include copilotDown so the agent can opt the unflagged hook out of the Copilot gate',
  );
});

test('the mark-ready task in runGeneralUtilityTask opts the unflagged convergence hook out of Copilot when copilotDown', () => {
  const markReadyBody = functionBody('runGeneralUtilityTask');
  assert.match(
    markReadyBody,
    /context\.copilotDown/,
    'expected the mark-ready task to branch on copilotDown',
  );
  assert.match(
    markReadyBody,
    /CLAUDE_REVIEWS_DISABLED/,
    'expected the mark-ready prompt to set CLAUDE_REVIEWS_DISABLED so the unflagged hook re-derives the Copilot bypass',
  );
  assert.match(
    markReadyBody,
    /copilot/,
    'expected the mark-ready opt-out to name the copilot token',
  );
});

test('the COPILOT phase short-circuits on input.copilotDisabled before spawning the gate agent', () => {
  const copilotPhaseStart = convergeSource.indexOf("if (phase === 'COPILOT') {");
  assert.notEqual(copilotPhaseStart, -1, 'expected a COPILOT phase block');
  const gateCallIndex = convergeSource.indexOf('await runCopilotGate(head)', copilotPhaseStart);
  assert.notEqual(gateCallIndex, -1, 'expected the COPILOT phase to call runCopilotGate when Copilot is enabled');
  const beforeGate = convergeSource.slice(copilotPhaseStart, gateCallIndex);
  assert.match(
    beforeGate,
    /if \(input\.copilotDisabled\)/,
    'expected the quota pre-check bypass to guard the COPILOT phase before any gate agent spawns',
  );
  assert.match(beforeGate, /copilotDown = true/, 'expected the bypass to mark copilotDown');
  assert.match(beforeGate, /copilotNote =/, 'expected the bypass to set a copilotNote');
  assert.match(beforeGate, /phase = 'FINALIZE'/, 'expected the bypass to advance to FINALIZE');
  assert.match(beforeGate, /continue/, 'expected the bypass to continue without spawning the gate agent');
});

test('copilotDown initializes from input.copilotDisabled so the pre-check decision carries into the loop', () => {
  assert.match(
    convergeSource,
    /let copilotDown = input\.copilotDisabled \|\| false/,
    'expected copilotDown to seed from the copilotDisabled run input',
  );
});

test('a copilotDisabled run reaches FINALIZE with --copilot-down', () => {
  const copilotPhaseStart = convergeSource.indexOf("if (phase === 'COPILOT') {");
  const bypassStart = convergeSource.indexOf('if (input.copilotDisabled)', copilotPhaseStart);
  assert.notEqual(bypassStart, -1, 'expected an input.copilotDisabled bypass in the COPILOT phase');
  const bypassBlock = convergeSource.slice(bypassStart, bypassStart + 800);
  assert.match(bypassBlock, /copilotDown = true/, 'expected the bypass to set copilotDown');
  assert.match(bypassBlock, /phase = 'FINALIZE'/, 'expected the bypass to advance to FINALIZE');
  const convergenceCheckBody = functionBody('runConvergenceCheck');
  assert.match(
    convergenceCheckBody,
    /context\.copilotDown \? ' --copilot-down' : ''/,
    'expected the convergence check to pass --copilot-down when the bypassed copilotDown reaches FINALIZE',
  );
});

function loadStandardsFollowUpDecision() {
  return new Function(
    `${functionBody('shouldOpenStandardsFollowUp')}\n` +
      'return shouldOpenStandardsFollowUp;',
  )();
}

test('the deferred follow-up create runs exactly once across a three-round standards run', () => {
  const shouldOpenStandardsFollowUp = loadStandardsFollowUpDecision();
  let alreadyOpened = false;
  let createCount = 0;
  for (let round = 0; round < 3; round += 1) {
    if (shouldOpenStandardsFollowUp(alreadyOpened)) {
      createCount += 1;
      alreadyOpened = true;
    }
  }
  assert.equal(
    createCount,
    1,
    'expected the deferred follow-up issue and hardening PR to be created exactly once across a multi-round run',
  );
});

test('shouldOpenStandardsFollowUp opens on the first standards-only round and skips afterward', () => {
  const shouldOpenStandardsFollowUp = loadStandardsFollowUpDecision();
  assert.equal(shouldOpenStandardsFollowUp(false), true);
  assert.equal(shouldOpenStandardsFollowUp(true), false);
});

test('the run seeds the standards follow-up flags to false so the first standards-only round opens the follow-up', () => {
  assert.match(
    convergeSource,
    /let hasStandardsFollowUpFiled = false/,
    'expected a run-scoped hasStandardsFollowUpFiled flag seeded false',
  );
  assert.match(
    convergeSource,
    /let wasStandardsHardeningPrOpened = false/,
    'expected a run-scoped wasStandardsHardeningPrOpened flag seeded false',
  );
});

test('openStandardsFollowUpOnce gates spawnStandardsFollowUp behind the run-once flag and remembers the outcome', () => {
  const onceBody = extractCallableSource('openStandardsFollowUpOnce');
  assert.match(
    onceBody,
    /shouldOpenStandardsFollowUp\(hasStandardsFollowUpFiled\)/,
    'expected the helper to consult the run-once decision on the current flag',
  );
  assert.match(
    onceBody,
    /await spawnStandardsFollowUp\(head, findings, sourceLabel, wasStandardsHardeningPrOpened\)/,
    'expected the helper to pass the remembered hardening state into the spawn so an already-opened PR is never re-opened',
  );
  assert.match(
    onceBody,
    /hasStandardsFollowUpFiled = standardsOutcome\?\.followUpIssueFiled === true/,
    'expected the helper to latch the flag only when the follow-up issue was actually filed so a transient failure retries on a later round',
  );
  assert.match(
    onceBody,
    /wasStandardsHardeningPrOpened = wasStandardsHardeningPrOpened \|\| standardsOutcome\?\.hardeningPrOpened === true/,
    'expected the hardening guard to latch the moment a hardening PR opens and stay latched across rounds so a later issue-filing retry never re-opens it',
  );
  assert.match(
    onceBody,
    /hardeningPrOpened: wasStandardsHardeningPrOpened/,
    'expected the helper to return the cached hardening outcome as hardeningPrOpened',
  );
});

test('both standards-deferral call sites route the create through openStandardsFollowUpOnce', () => {
  const onceCalls = convergeSource.match(/await openStandardsFollowUpOnce\(/g) || [];
  assert.equal(
    onceCalls.length,
    2,
    'expected the converge-round and copilot standards call sites to both defer to openStandardsFollowUpOnce',
  );
  const directCreates = convergeSource.match(/await spawnStandardsFollowUp\(/g) || [];
  assert.equal(
    directCreates.length,
    1,
    'expected spawnStandardsFollowUp to be invoked once from openStandardsFollowUpOnce, never directly at a call site',
  );
});

function extractCallableSource(functionName) {
  const asyncStart = convergeSource.indexOf(`async function ${functionName}(`);
  const plainStart = convergeSource.indexOf(`function ${functionName}(`);
  const declarationStart = asyncStart !== -1 ? asyncStart : plainStart;
  assert.notEqual(declarationStart, -1, `expected ${functionName} to exist`);
  const bodyStart = convergeSource.indexOf('{', declarationStart);
  let depth = 0;
  let index = bodyStart;
  for (; index < convergeSource.length; index += 1) {
    const character = convergeSource[index];
    if (character === '{') {
      depth += 1;
    } else if (character === '}') {
      depth -= 1;
      if (depth === 0) {
        index += 1;
        break;
      }
    }
  }
  return convergeSource.slice(declarationStart, index);
}

const parseableHardeningCommitResult = { hardeningPrUrl: 'https://github.com/owner/repo/pull/7', summary: 'opened' };

function loadStandardsFollowUpRuntime(recordedCalls, standardsEditResult, hardeningCommitResult = parseableHardeningCommitResult) {
  const runtimeSource =
    'let hasStandardsFollowUpFiled = false;\n' +
    'let wasStandardsHardeningPrOpened = false;\n' +
    "let standardsFollowUpIssueUrl = '';\n" +
    'async function runCodeEditorTask(taskName, context) {\n' +
    '  recordedCalls.push({ task: taskName, context });\n' +
    "  if (taskName === 'standards-edit') return standardsEditResult;\n" +
    "  if (taskName === 'hardening-commit') return hardeningCommitResult;\n" +
    '  return {};\n' +
    '}\n' +
    'async function runVerifierTask() {\n' +
    '  return { passed: true };\n' +
    '}\n' +
    'function verdictPassed() {\n' +
    '  return true;\n' +
    '}\n' +
    'function log() {}\n' +
    `${extractCallableSource('collectFindingThreadIds')}\n` +
    `${extractCallableSource('findingsCarryThreads')}\n` +
    `${extractCallableSource('shouldOpenStandardsFollowUp')}\n` +
    `${extractCallableSource('parseDeferredPr')}\n` +
    `${extractCallableSource('spawnStandardsFollowUp')}\n` +
    `${extractCallableSource('resolveStandardsThreadsForBatch')}\n` +
    `${extractCallableSource('openStandardsFollowUpOnce')}\n` +
    'return {\n' +
    '  openStandardsFollowUpOnce,\n' +
    '  guards: () => ({ hasStandardsFollowUpFiled, wasStandardsHardeningPrOpened, standardsFollowUpIssueUrl }),\n' +
    '};';
  return new Function('recordedCalls', 'standardsEditResult', 'hardeningCommitResult', runtimeSource)(
    recordedCalls,
    standardsEditResult,
    hardeningCommitResult,
  );
}

function loadParseDeferredPr() {
  return new Function(`${extractCallableSource('parseDeferredPr')}\nreturn parseDeferredPr;`)();
}

test('parseDeferredPr parses a full canonical hardening PR URL into its coordinates', () => {
  const parseDeferredPr = loadParseDeferredPr();
  assert.deepEqual(
    parseDeferredPr('https://github.com/jl-cmd/claude-code-config/pull/824'),
    { owner: 'jl-cmd', repo: 'claude-code-config', prNumber: 824 },
  );
});

test('parseDeferredPr accepts a trailing slash, query string, or fragment on the PR URL', () => {
  const parseDeferredPr = loadParseDeferredPr();
  assert.equal(parseDeferredPr('https://github.com/owner/repo/pull/7/').prNumber, 7);
  assert.equal(parseDeferredPr('https://github.com/owner/repo/pull/7?w=1').prNumber, 7);
  assert.equal(parseDeferredPr('https://github.com/owner/repo/pull/7#issuecomment-42').prNumber, 7);
});

test('parseDeferredPr rejects a PR URL embedded in surrounding log text so it never parses the wrong number', () => {
  const parseDeferredPr = loadParseDeferredPr();
  assert.equal(
    parseDeferredPr('opened https://github.com/owner/repo/pull/7 then https://github.com/owner/repo/pull/9'),
    null,
  );
});

test('parseDeferredPr rejects a deep-linked pull path so a non-canonical URL parses no coordinate', () => {
  const parseDeferredPr = loadParseDeferredPr();
  assert.equal(parseDeferredPr('https://github.com/owner/repo/pull/7/files'), null);
});

test('a second standards-only round never re-opens a hardening PR after the first round opened one but failed to file the issue', async () => {
  const recordedCalls = [];
  const issueFailedHardeningStaged = {
    issueUrl: '',
    hardeningEdited: true,
    hardeningRepoPath: '/tmp/hardening',
    hardeningBranch: 'harden-standards',
  };
  const runtime = loadStandardsFollowUpRuntime(recordedCalls, issueFailedHardeningStaged);

  const firstRoundHardeningPr = await runtime.openStandardsFollowUpOnce('sha1', [{ file: 'a.py', line: 1 }], 'converge-round');
  const secondRoundHardeningPr = await runtime.openStandardsFollowUpOnce('sha1', [{ file: 'a.py', line: 1 }], 'copilot');

  const hardeningCommitCalls = recordedCalls.filter((call) => call.task === 'hardening-commit').length;
  assert.equal(
    hardeningCommitCalls,
    1,
    'expected the hardening PR to be committed exactly once even when the follow-up issue filing must retry on the second round',
  );
  assert.equal(firstRoundHardeningPr.hardeningPrOpened, true, 'expected the first round to open the hardening PR');
  assert.equal(secondRoundHardeningPr.hardeningPrOpened, true, 'expected the second round to report the hardening PR as opened for this run');
  assert.equal(
    runtime.guards().wasStandardsHardeningPrOpened,
    true,
    'expected the hardening guard to stay latched across rounds',
  );
  assert.equal(
    runtime.guards().hasStandardsFollowUpFiled,
    false,
    'expected the issue guard to stay clear so the filing keeps retrying',
  );
});

test('a hardening-commit that opens a PR but returns an unparseable URL still latches the run-once guard', async () => {
  const recordedCalls = [];
  const issueFailedHardeningStaged = {
    issueUrl: '',
    hardeningEdited: true,
    hardeningRepoPath: '/tmp/hardening',
    hardeningBranch: 'harden-standards',
  };
  const unparseableUrlHardeningCommitResult = { hardeningPrUrl: 'draft-hardening-pr-opened', summary: 'opened' };
  const runtime = loadStandardsFollowUpRuntime(recordedCalls, issueFailedHardeningStaged, unparseableUrlHardeningCommitResult);

  const firstRoundHardeningPr = await runtime.openStandardsFollowUpOnce('sha1', [{ file: 'a.py', line: 1 }], 'converge-round');
  const secondRoundHardeningPr = await runtime.openStandardsFollowUpOnce('sha1', [{ file: 'a.py', line: 1 }], 'copilot');

  const hardeningCommitCalls = recordedCalls.filter((call) => call.task === 'hardening-commit').length;
  assert.equal(
    hardeningCommitCalls,
    1,
    'expected the non-empty-URL commit to latch the guard so a second round opens no duplicate hardening PR',
  );
  assert.equal(firstRoundHardeningPr.hardeningPrOpened, true, 'expected a non-empty (though unparseable) URL to report the hardening PR as opened');
  assert.equal(firstRoundHardeningPr.deferredPr, null, 'expected the unparseable URL to contribute no deferred coordinate');
  assert.equal(secondRoundHardeningPr.hardeningPrOpened, true, 'expected the second round to report the hardening PR as opened for this run');
  assert.equal(
    runtime.guards().wasStandardsHardeningPrOpened,
    true,
    'expected the hardening guard to latch even though the returned URL never parsed',
  );
});

test('a hardening-commit that opens no PR (empty hardeningPrUrl) leaves the run-once guard clear so a later round retries the open', async () => {
  const recordedCalls = [];
  const issueFailedHardeningStaged = {
    issueUrl: '',
    hardeningEdited: true,
    hardeningRepoPath: '/tmp/hardening',
    hardeningBranch: 'harden-standards',
  };
  const noPrHardeningCommitResult = { hardeningPrUrl: '', summary: 'no PR opened' };
  const runtime = loadStandardsFollowUpRuntime(recordedCalls, issueFailedHardeningStaged, noPrHardeningCommitResult);

  const firstRoundHardeningPr = await runtime.openStandardsFollowUpOnce('sha1', [{ file: 'a.py', line: 1 }], 'converge-round');
  const secondRoundHardeningPr = await runtime.openStandardsFollowUpOnce('sha1', [{ file: 'a.py', line: 1 }], 'copilot');

  const hardeningCommitCalls = recordedCalls.filter((call) => call.task === 'hardening-commit').length;
  assert.equal(
    hardeningCommitCalls,
    2,
    'expected the empty-URL commit (no PR opened) to leave the guard clear so a later round retries the open',
  );
  assert.equal(firstRoundHardeningPr.hardeningPrOpened, false, 'expected an empty URL to report no hardening PR opened');
  assert.equal(secondRoundHardeningPr.hardeningPrOpened, false, 'expected the retry round to still report no hardening PR opened');
  assert.equal(
    runtime.guards().wasStandardsHardeningPrOpened,
    false,
    'expected the hardening guard to stay clear when no PR opened so the open keeps retrying',
  );
});

test('a later standards-only round resolves its own review threads after the follow-up issue was already filed', async () => {
  const recordedCalls = [];
  const issueFiledNoHardening = {
    issueUrl: 'https://github.com/jl-cmd/claude-code-config/issues/900',
    hardeningEdited: false,
    hardeningRepoPath: '',
    hardeningBranch: '',
  };
  const runtime = loadStandardsFollowUpRuntime(recordedCalls, issueFiledNoHardening);

  await runtime.openStandardsFollowUpOnce('sha1', [{ file: 'a.py', line: 1, replyToCommentId: null }], 'converge-round');
  await runtime.openStandardsFollowUpOnce('sha1', [{ file: 'b.py', line: 2, replyToCommentId: 42 }], 'copilot');

  const standardsEditCalls = recordedCalls.filter((call) => call.task === 'standards-edit');
  assert.equal(standardsEditCalls.length, 1, 'expected the follow-up issue to be filed exactly once across the run');

  const resolveCalls = recordedCalls.filter((call) => call.task === 'standards-resolve-threads');
  assert.equal(resolveCalls.length, 1, 'expected the reuse-path round to resolve its own batch review threads');
  assert.deepEqual(
    resolveCalls[0].context.findings,
    [{ file: 'b.py', line: 2, replyToCommentId: 42 }],
    'expected the resolve step to receive the reuse-path batch findings so their threads get replied-to and resolved',
  );
  assert.equal(
    resolveCalls[0].context.issueUrl,
    'https://github.com/jl-cmd/claude-code-config/issues/900',
    'expected the resolve step to reference the already-filed follow-up issue in its inline reply',
  );
});

test('a reuse-path standards round carrying no review threads spawns no thread-resolution agent', async () => {
  const recordedCalls = [];
  const issueFiledNoHardening = {
    issueUrl: 'https://github.com/jl-cmd/claude-code-config/issues/901',
    hardeningEdited: false,
    hardeningRepoPath: '',
    hardeningBranch: '',
  };
  const runtime = loadStandardsFollowUpRuntime(recordedCalls, issueFiledNoHardening);

  await runtime.openStandardsFollowUpOnce('sha1', [{ file: 'a.py', line: 1, replyToCommentId: null }], 'converge-round');
  await runtime.openStandardsFollowUpOnce('sha1', [{ file: 'b.py', line: 2, replyToCommentId: null }], 'copilot');

  const resolveCalls = recordedCalls.filter((call) => call.task === 'standards-resolve-threads');
  assert.equal(
    resolveCalls.length,
    0,
    'expected no thread-resolution agent when the reuse-path batch of in-memory findings carries no review threads',
  );
});

