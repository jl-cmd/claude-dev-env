import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const workflowDirectory = dirname(fileURLToPath(import.meta.url));
const convergeSource = readFileSync(join(workflowDirectory, 'converge.mjs'), 'utf8');
const gotchasSource = readFileSync(
  join(workflowDirectory, '..', 'reference', 'gotchas.md'),
  'utf8',
);

function lensPromptBody(builderName) {
  const builderStart = convergeSource.indexOf(`function ${builderName}(`);
  assert.notEqual(builderStart, -1, `expected ${builderName} to exist`);
  const nextBuilderStart = convergeSource.indexOf('\nfunction ', builderStart + 1);
  const builderEnd = nextBuilderStart === -1 ? convergeSource.length : nextBuilderStart;
  return convergeSource.slice(builderStart, builderEnd);
}

test('code-review lens prompt no longer instructs a per-lens git fetch', () => {
  assert.doesNotMatch(lensPromptBody('runCodeReviewLens'), /git fetch origin main/);
});

test('bug-audit lens prompt no longer instructs a per-lens git fetch', () => {
  assert.doesNotMatch(lensPromptBody('runAuditLens'), /git fetch origin main/);
});

test('a single round-level prefetch step fetches origin/main before the parallel lenses', () => {
  assert.match(convergeSource, /function prefetchMainForRound\(/);
  const prefetchCallIndex = convergeSource.indexOf('await prefetchMainForRound(');
  const parallelLensIndex = convergeSource.indexOf('const lenses = await parallel(');
  assert.notEqual(prefetchCallIndex, -1, 'expected prefetchMainForRound to be invoked');
  assert.notEqual(parallelLensIndex, -1, 'expected the parallel lens block to exist');
  assert.ok(
    prefetchCallIndex < parallelLensIndex,
    'expected the round prefetch to run before the parallel lenses spawn',
  );
});

test('bugbot lens preamble does not blanket-instruct passing --owner/--repo to every script', () => {
  const bugbotPrompt = lensPromptBody('runBugbotLens');
  assert.doesNotMatch(
    bugbotPrompt,
    /use the existing scripts; pass --owner/,
    'the blanket clause breaks reviews_disabled.py, which accepts only --reviewer',
  );
});

test('bugbot lens invokes reviews_disabled.py with only --reviewer', () => {
  const bugbotPrompt = lensPromptBody('runBugbotLens');
  const reviewsDisabledIndex = bugbotPrompt.indexOf('reviews_disabled.py');
  assert.notEqual(reviewsDisabledIndex, -1, 'expected reviews_disabled.py invocation');
  const invocationLineEnd = bugbotPrompt.indexOf('\\n', reviewsDisabledIndex);
  const invocationLine = bugbotPrompt.slice(reviewsDisabledIndex, invocationLineEnd);
  assert.match(invocationLine, /--reviewer bugbot/);
  assert.doesNotMatch(
    invocationLine,
    /--owner|--repo/,
    'reviews_disabled.py argparse rejects --owner/--repo with SystemExit(2)',
  );
});

test('gotchas doc states parallel lenses must avoid concurrent git operations', () => {
  assert.doesNotMatch(gotchasSource, /cannot race on git state/);
  assert.match(gotchasSource, /fetch.*once.*before/i);
});

test('repair-convergence filters unresolved threads to bot authors and skips human threads', () => {
  const repairPrompt = lensPromptBody('repairConvergence');
  assert.match(
    repairPrompt,
    /cursor.*claude.*copilot|copilot.*cursor.*claude|claude.*cursor.*copilot/is,
    'expected the bot-author allowlist (Cursor/Claude/Copilot) to be named',
  );
  assert.match(
    repairPrompt,
    /skip.*human|human.*skip/is,
    'expected an explicit instruction to skip human reviewer threads',
  );
});

test('repair-convergence no longer instructs resolving every unresolved thread without an author filter', () => {
  const repairPrompt = lensPromptBody('repairConvergence');
  assert.doesNotMatch(
    repairPrompt,
    /fetch every thread where isResolved is false/,
    'the unfiltered instruction could resolve human reviewer threads',
  );
});

test('bugbot lens delay instructions are shell-agnostic with PowerShell as an alternative', () => {
  const bugbotPrompt = lensPromptBody('runBugbotLens');
  assert.match(bugbotPrompt, /sleep 60/, 'expected a shell-agnostic 60-second poll delay');
  assert.match(bugbotPrompt, /sleep 8/, 'expected a concrete 8-second delay command');
  assert.match(
    bugbotPrompt,
    /Start-Sleep[\s\S]*alternative|alternative[\s\S]*Start-Sleep/i,
    'expected PowerShell to be named only as an allowed alternative',
  );
  assert.doesNotMatch(
    bugbotPrompt,
    /wait 8 seconds(?!,)/,
    'the vague "wait 8 seconds" phrasing must carry a concrete command',
  );
});

test('copilot gate delay instruction is shell-agnostic with PowerShell as an alternative', () => {
  const copilotPrompt = lensPromptBody('runCopilotGate');
  assert.match(copilotPrompt, /sleep 360/, 'expected a shell-agnostic 360-second poll delay');
  assert.match(
    copilotPrompt,
    /Start-Sleep[\s\S]*alternative|alternative[\s\S]*Start-Sleep/i,
    'expected PowerShell to be named only as an allowed alternative',
  );
});

test('gotchas doc describes the reviewer wait as shell-agnostic', () => {
  assert.match(
    gotchasSource,
    /\bsleep\b/i,
    'expected the wait guidance to name a shell-agnostic sleep',
  );
  assert.doesNotMatch(
    gotchasSource,
    /a single PowerShell\s*`?Start-Sleep`?\s*loop/i,
    'PowerShell Start-Sleep must be an alternative, not the sole mechanism',
  );
});

function finalizeRepairBranch() {
  const repairCallIndex = convergeSource.indexOf('await repairConvergence(');
  assert.notEqual(repairCallIndex, -1, 'expected the FINALIZE repair call to exist');
  const transitionIndex = convergeSource.indexOf("phase = 'CONVERGE'", repairCallIndex);
  assert.notEqual(transitionIndex, -1, 'expected a CONVERGE transition after the repair call');
  const continueIndex = convergeSource.indexOf('continue', transitionIndex);
  assert.notEqual(continueIndex, -1, 'expected a continue statement to close the FINALIZE repair branch');
  const branchEnd = continueIndex + 'continue'.length;
  return convergeSource.slice(repairCallIndex, branchEnd);
}

test('the FINALIZE repair branch does not re-assign head from the repair before re-converging', () => {
  assert.doesNotMatch(
    finalizeRepairBranch(),
    /head\s*=\s*repair/,
    'the next CONVERGE pass re-resolves HEAD from GitHub, so assigning the repair SHA here is dead',
  );
});

function fixBranchAfter(branchLabel) {
  const labelIndex = convergeSource.indexOf(branchLabel);
  assert.notEqual(labelIndex, -1, `expected the ${branchLabel} marker to exist`);
  const applyFixesIndex = convergeSource.indexOf('await applyFixes(', labelIndex);
  assert.notEqual(applyFixesIndex, -1, `expected an applyFixes call after ${branchLabel}`);
  const continueIndex = convergeSource.indexOf('continue', applyFixesIndex);
  assert.notEqual(continueIndex, -1, `expected a continue statement to close the ${branchLabel} branch`);
  const branchEnd = continueIndex + 'continue'.length;
  return convergeSource.slice(applyFixesIndex, branchEnd);
}

test('the CONVERGE fix branch does not re-assign head from the fix before re-converging', () => {
  assert.doesNotMatch(
    fixBranchAfter('${findings.length} finding(s) — applying fixes'),
    /head\s*=\s*fixProgress/,
    'the next CONVERGE pass re-resolves HEAD from GitHub, so assigning the fix SHA here is dead',
  );
});

test('the COPILOT fix branch does not re-assign head from the fix before re-converging', () => {
  assert.doesNotMatch(
    fixBranchAfter('${copilotOutcome.findings.length} finding(s) — fixing and re-converging'),
    /head\s*=\s*fixProgress/,
    'the CONVERGE pass it transitions to re-resolves HEAD from GitHub, so assigning the fix SHA here is dead',
  );
});

test('the CONVERGE branch re-resolves HEAD from GitHub on every entry', () => {
  const convergeBranchStart = convergeSource.indexOf("if (phase === 'CONVERGE')");
  assert.notEqual(convergeBranchStart, -1, 'expected the CONVERGE branch to exist');
  const resolveHeadIndex = convergeSource.indexOf('head = await resolveHead()', convergeBranchStart);
  assert.notEqual(resolveHeadIndex, -1, 'expected CONVERGE to re-resolve HEAD via resolveHead()');
});

test('fix prompt resolves threads by PRRT thread node id looked up from the comment databaseId', () => {
  const fixPrompt = lensPromptBody('applyFixes');
  assert.match(fixPrompt, /PRRT/, 'expected the thread node id form (PRRT_...) to be named');
  assert.match(
    fixPrompt,
    /databaseId/,
    'expected the GraphQL lookup matching comment databaseId to be named',
  );
  assert.match(
    fixPrompt,
    /not the numeric comment id/,
    'expected an explicit guard against passing the numeric comment id to resolve_thread',
  );
});

test('fix prompt does not pass the numeric comment id straight to resolve_thread', () => {
  assert.doesNotMatch(
    lensPromptBody('applyFixes'),
    /then resolve that thread \(use the github MCP pull_request_review_write/,
    'resolve_thread and resolveReviewThread require a PRRT_... thread node id, not the comment id',
  );
});

function convergenceSummarySchemaBody() {
  const schemaStart = convergeSource.indexOf('const CONVERGENCE_SUMMARY_SCHEMA = {');
  assert.notEqual(schemaStart, -1, 'expected CONVERGENCE_SUMMARY_SCHEMA to be defined');
  const nextSchemaStart = convergeSource.indexOf('\nconst CONVERGENCE_SCHEMA = {', schemaStart);
  assert.notEqual(nextSchemaStart, -1, 'expected CONVERGENCE_SCHEMA to follow the summary schema');
  return convergeSource.slice(schemaStart, nextSchemaStart);
}

test('CONVERGENCE_SUMMARY_SCHEMA requires verdictLine and issueClasses', () => {
  const schemaBody = convergenceSummarySchemaBody();
  assert.match(schemaBody, /verdictLine: \{ type: 'string'/);
  assert.match(schemaBody, /issueClasses: \{\s*type: 'array'/);
  assert.match(
    schemaBody,
    /required: \['verdictLine', 'issueClasses'\]/,
    'expected verdictLine and issueClasses to be the required top-level fields',
  );
});

test('CONVERGENCE_SUMMARY_SCHEMA issueClasses items carry every required field', () => {
  const schemaBody = convergenceSummarySchemaBody();
  for (const eachField of ['plainName', 'count', 'severity', 'category', 'status', 'whatItWas']) {
    assert.match(
      schemaBody,
      new RegExp(`${eachField}: \\{ type: '(string|integer)'`),
      `expected the issueClasses item to define ${eachField}`,
    );
  }
  assert.match(
    schemaBody,
    /required: \['plainName', 'count', 'severity', 'category', 'status', 'whatItWas'\]/,
    'expected all six issueClasses item fields to be required',
  );
  assert.match(schemaBody, /enum: \['P0', 'P1', 'P2'\]/, 'expected the severity enum');
  assert.match(schemaBody, /enum: \['bug', 'code-standard'\]/, 'expected the category enum');
  assert.match(schemaBody, /enum: \['fixed', 'deferred'\]/, 'expected the status enum');
});

test('the Copilot standards-only branch pushes its findings into the accumulator before deferring', () => {
  const branchMarkerIndex = convergeSource.indexOf(
    '${copilotOutcome.findings.length} code-standard-only finding(s) — deferring to follow-up PRs and treating the gate as passed',
  );
  assert.notEqual(branchMarkerIndex, -1, 'expected the Copilot standards-only branch marker to exist');
  const accumulatorPushIndex = convergeSource.indexOf(
    'allRoundFindings.push(...copilotOutcome.findings)',
    branchMarkerIndex,
  );
  assert.notEqual(
    accumulatorPushIndex,
    -1,
    'expected the Copilot standards-only branch to push its findings into allRoundFindings so the summary counts deferred standards findings',
  );
  const deferralCallIndex = convergeSource.indexOf("await spawnStandardsFollowUp(", branchMarkerIndex);
  assert.notEqual(deferralCallIndex, -1, 'expected the Copilot standards-only deferral call to exist');
  assert.ok(
    accumulatorPushIndex < deferralCallIndex,
    'expected the findings push to precede the deferral, matching the converge-round standards-only branch ordering',
  );
});

test('converge.mjs records the convergence summary before the converged return', () => {
  const summaryCallIndex = convergeSource.indexOf('await spawnConvergenceSummary(');
  assert.notEqual(summaryCallIndex, -1, 'expected spawnConvergenceSummary to be invoked');
  const convergedReturnIndex = convergeSource.indexOf(
    'return { converged: true, rounds, finalSha: head',
    summaryCallIndex,
  );
  assert.notEqual(convergedReturnIndex, -1, 'expected the converged return after the summary call');
  assert.ok(
    summaryCallIndex < convergedReturnIndex,
    'expected the summary to be recorded before the converged return',
  );
});
