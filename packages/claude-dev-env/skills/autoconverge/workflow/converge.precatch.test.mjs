import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const workflowDirectory = dirname(fileURLToPath(import.meta.url));
const convergeSource = readFileSync(join(workflowDirectory, 'converge.mjs'), 'utf8');

function functionSource(functionName) {
  const functionStart = convergeSource.indexOf(`function ${functionName}(`);
  assert.notEqual(functionStart, -1, `expected ${functionName} to exist`);
  const nextMatch = /\n(?:async )?function /.exec(convergeSource.slice(functionStart + 1));
  const functionEnd =
    nextMatch === null ? convergeSource.length : functionStart + 1 + nextMatch.index;
  return convergeSource.slice(functionStart, functionEnd);
}

function sliceBetween(startNeedle, endNeedle) {
  const sliceStart = convergeSource.indexOf(startNeedle);
  assert.notEqual(sliceStart, -1, `expected ${startNeedle} to exist`);
  const sliceEnd = convergeSource.indexOf(endNeedle, sliceStart + startNeedle.length);
  assert.notEqual(sliceEnd, -1, `expected ${endNeedle} to exist after ${startNeedle}`);
  return convergeSource.slice(sliceStart, sliceEnd);
}

test('runStaticSweep exists and runs after the preflight-git no-SHA guard and before the parallel lenses', () => {
  assert.match(convergeSource, /function runStaticSweep\(/, 'expected the static-sweep lens builder to exist');
  const sweepCallIndex = convergeSource.indexOf('await runStaticSweep(');
  assert.notEqual(sweepCallIndex, -1, 'expected the CONVERGE round to invoke runStaticSweep');
  const noShaGuardIndex = convergeSource.indexOf('preflight-git agent returned no SHA');
  const parallelIndex = convergeSource.indexOf('const lenses = await parallel(');
  assert.ok(
    noShaGuardIndex !== -1 && noShaGuardIndex < sweepCallIndex,
    'expected the static sweep to run after the no-SHA guard',
  );
  assert.ok(
    sweepCallIndex < parallelIndex,
    'expected the static sweep to run before the opus reading lenses so they review sweep-clean code',
  );
});

test('the static-sweep prompt names the deterministic gates and never invokes the gh CLI', () => {
  const body = functionSource('runStaticSweep');
  assert.match(body, /code_rules_gate\.py/, 'expected the CODE_RULES gate to be named');
  assert.match(body, /--base/, 'expected the gate to run against the origin/main base');
  assert.match(body, /\bruff\b/, 'expected ruff to be named');
  assert.match(body, /\bmypy\b/, 'expected mypy to be named');
  assert.match(body, /\bpytest\b/, 'expected stem-matched pytest to be named');
  assert.doesNotMatch(body, /\bgh\b/, 'expected the sweep to use only local commands so it runs in a cloud session');
});

test('the static-sweep runs on the sonnetMedium tier via convergeReadOnlyAgent with the Explore agent type', () => {
  const body = functionSource('runStaticSweep');
  assert.match(body, /convergeReadOnlyAgent\(/, 'expected the sweep to spawn through the read-only preamble');
  assert.match(body, /renderLensDiffContext\(preflightResult\)/, 'expected the sweep to inject the preflight changed-file context');
  assert.match(body, /label: 'lens:static-sweep'/);
  assert.match(body, /agentType: 'Explore'/);
  assert.match(body, /\.\.\.TIERS\.sonnetMedium/, 'expected the deterministic sweep to run on the cheaper sonnet tier');
});

test('a static-sweep finding routes through applyFixes with the static-sweep label and nulls head before continue', () => {
  const sweepBranch = sliceBetween('await runStaticSweep(', "const lenses = await parallel(");
  assert.match(sweepBranch, /applyFixes\(head, sweep\.findings, 'static-sweep'\)/, 'expected sweep findings to route through applyFixes');
  assert.match(sweepBranch, /detectFixProgress\(sweepFix, head, false\)/, 'expected the sweep fix to check fix progress with no thread-bearing finding');
  const headNullIndex = sweepBranch.indexOf('head = null');
  const continueIndex = sweepBranch.indexOf('continue');
  assert.notEqual(headNullIndex, -1, 'expected the sweep-findings branch to null head so the next round reviews the fixed code');
  assert.ok(headNullIndex < continueIndex, 'expected head to be invalidated before the sweep branch continues');
});

test('runAuditLens carries the adversarial second pass and points at the pre-catch rubric', () => {
  const body = functionSource('runAuditLens');
  assert.match(body, /missed at least 3 P1/, 'expected the mandatory adversarial second pass');
  assert.match(body, /CONFIG\.precatchRubric/, 'expected the audit lens to point at the pre-catch rubric for the doc-parity/test/PR-description lanes');
  assert.doesNotMatch(body, /nothing new is an acceptable/i, 'expected a bare "nothing new" to be rejected');
});

test('runSelfReviewLens exists on opusMedium via convergeReadOnlyAgent and covers the three semantic lanes', () => {
  const body = functionSource('runSelfReviewLens');
  assert.match(body, /convergeReadOnlyAgent\(/, 'expected the self-review lens to spawn through the read-only preamble');
  assert.match(body, /renderLensDiffContext\(preflightResult\)/, 'expected the self-review lens to inject the preflight changed-file context');
  assert.match(body, /CONFIG\.precatchRubric/, 'expected the self-review lens to read the pre-catch rubric');
  assert.match(body, /pr-consistency-audit/, 'expected the self-review lens to reuse the pr-consistency-audit method');
  assert.match(body, /category-o-docstring-vs-impl-drift/, 'expected the self-review lens to cite the category-o drift rubric');
  assert.match(body, /parity/i, 'expected the doc-vs-code parity lane');
  assert.match(body, /Test-assertion completeness/i, 'expected the test-assertion completeness lane');
  assert.match(body, /PR-description-vs-diff/i, 'expected the PR-description parity lane');
  assert.match(body, /label: 'lens:self-review'/);
  assert.match(body, /\.\.\.TIERS\.opusMedium/, 'expected the semantic lens to stay on opus');
});

test('the round parallel array holds exactly the three internal lenses and no Bugbot slot', () => {
  const parallelArray = sliceBetween('const lenses = await parallel([', '])');
  assert.match(parallelArray, /runCodeReviewLens\(head, reviewerAvailability\)/);
  assert.match(parallelArray, /runAuditLens\(head, reviewerAvailability\)/);
  assert.match(parallelArray, /runSelfReviewLens\(head, reviewerAvailability\)/);
  assert.doesNotMatch(parallelArray, /runBugbotLens/, 'expected Bugbot to leave the per-round parallel and become a terminal gate');
  assert.doesNotMatch(parallelArray, /isBugbotDownPreSpawn/, 'expected the pre-spawn Bugbot-down decision to be gone from the round');
  assert.doesNotMatch(convergeSource, /const isBugbotDownPreSpawn/, 'expected no pre-spawn Bugbot-down decision anywhere in the round');
});

test('both the CONVERGE clean branch and the standards-only branch route to the terminal BUGBOT phase', () => {
  const convergeBranch = sliceBetween("if (phase === 'CONVERGE') {", "if (phase === 'BUGBOT') {");
  const toBugbot = convergeBranch.match(/phase = 'BUGBOT'/g) || [];
  assert.equal(toBugbot.length, 2, 'expected the standards-only and all-clean branches to both set phase = BUGBOT');
  assert.doesNotMatch(convergeBranch, /phase = 'COPILOT'/, 'expected the CONVERGE block to route to BUGBOT, not straight to COPILOT');
});

test('the terminal BUGBOT phase skips runBugbotLens when the reviewer-availability gate reports Bugbot down', () => {
  const bugbotPhase = sliceBetween("if (phase === 'BUGBOT') {", "if (phase === 'COPILOT') {");
  const availabilityGateIndex = bugbotPhase.indexOf('resolveReviewerDown(reviewerAvailability?.bugbot, input.bugbotDisabled || false)');
  const gateCallIndex = bugbotPhase.indexOf('await runBugbotLens(head, reviewerAvailability)');
  assert.notEqual(availabilityGateIndex, -1, 'expected the terminal gate to consult resolveReviewerDown before spawning the Bugbot lens');
  assert.notEqual(gateCallIndex, -1, 'expected the terminal gate to call runBugbotLens when Bugbot is enabled');
  assert.ok(availabilityGateIndex < gateCallIndex, 'expected the availability gate to short-circuit before any Bugbot agent spawns');
  const beforeGate = bugbotPhase.slice(availabilityGateIndex, gateCallIndex);
  assert.match(beforeGate, /bugbotDown = true/, 'expected the availability-down path to mark bugbotDown');
  assert.match(beforeGate, /phase = 'COPILOT'/, 'expected the availability-down path to advance to the Copilot gate with no agent');
});

test('the terminal BUGBOT phase classifies via the shared reviewer-gate classifier and routes each outcome', () => {
  const bugbotPhase = sliceBetween("if (phase === 'BUGBOT') {", "if (phase === 'COPILOT') {");
  assert.match(bugbotPhase, /classifyReviewerGateOutcome\(bugbot\)/, 'expected the terminal gate to reuse the shared reviewer-gate classifier');
  assert.match(bugbotPhase, /applyFixes\(head, bugbotOutcome\.findings, 'bugbot'\)/, 'expected a Bugbot fix outcome to route through applyFixes');
  assert.match(bugbotPhase, /head = null\n\s*phase = 'CONVERGE'/, 'expected a Bugbot fix to invalidate head and re-enter CONVERGE');
  assert.match(bugbotPhase, /phase = 'COPILOT'/, 'expected a clean or down Bugbot verdict to advance to the Copilot gate');
});

test('convergeReadOnlyAgent exists and the read-only preamble omits the rm-shape paragraph the edit preamble keeps', () => {
  assert.match(convergeSource, /const convergeReadOnlyAgent = \(prompt, options\) =>/, 'expected the read-only agent spawner to exist');
  const preambleRegion = convergeSource.slice(
    convergeSource.indexOf('const HEADLESS_EDIT_PREAMBLE ='),
    convergeSource.indexOf('\nlet activeRepoPath'),
  );
  const preambleModule = new Function(
    `${preambleRegion}\nreturn { HEADLESS_EDIT_PREAMBLE, HEADLESS_READONLY_PREAMBLE };`,
  )();
  assert.match(preambleModule.HEADLESS_EDIT_PREAMBLE, /rm shape rules/, 'expected the edit preamble to retain the rm-shape rules');
  assert.doesNotMatch(preambleModule.HEADLESS_READONLY_PREAMBLE, /rm shape rules/, 'expected the read-only preamble to drop the rm-shape paragraph');
  assert.ok(
    preambleModule.HEADLESS_READONLY_PREAMBLE.length < preambleModule.HEADLESS_EDIT_PREAMBLE.length,
    'expected the read-only preamble to be shorter than the edit preamble',
  );
});

test('COMMIT_RECOVERY_MAX_ATTEMPTS is one and bounds the commitWithRecovery loop', () => {
  assert.match(convergeSource, /const COMMIT_RECOVERY_MAX_ATTEMPTS = 1/, 'expected a dedicated commit-recovery cap of one');
  assert.match(convergeSource, /const FIX_RECOVERY_MAX_ATTEMPTS = 2/, 'expected the wider verify-recovery cap to stay at two');
  const commitBody = functionSource('commitWithRecovery');
  assert.match(commitBody, /attempt < COMMIT_RECOVERY_MAX_ATTEMPTS/, 'expected commitWithRecovery to bound its loop by the dedicated cap');
});
