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
  const nextBuilderMatch = /\n(?:async )?function /.exec(convergeSource.slice(builderStart + 1));
  const builderEnd =
    nextBuilderMatch === null ? convergeSource.length : builderStart + 1 + nextBuilderMatch.index;
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

test('repair-convergence edit step filters unresolved threads to bot authors and skips human threads', () => {
  const repairPrompt = lensPromptBody('repairConvergenceEdit');
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

test('repair-convergence edit step no longer instructs resolving every unresolved thread without an author filter', () => {
  const repairPrompt = lensPromptBody('repairConvergenceEdit');
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

test('fix edit prompt resolves threads by PRRT thread node id looked up from the comment databaseId', () => {
  const editPrompt = lensPromptBody('applyFixesEdit');
  assert.match(editPrompt, /PRRT/, 'expected the thread node id form (PRRT_...) to be named');
  assert.match(
    editPrompt,
    /databaseId/,
    'expected the GraphQL lookup matching comment databaseId to be named',
  );
  assert.match(
    editPrompt,
    /not the numeric comment id/,
    'expected an explicit guard against passing the numeric comment id to resolve_thread',
  );
});

test('fix edit prompt does not pass the numeric comment id straight to resolve_thread', () => {
  assert.doesNotMatch(
    lensPromptBody('applyFixesEdit'),
    /then resolve that thread \(use the github MCP pull_request_review_write/,
    'resolve_thread and resolveReviewThread require a PRRT_... thread node id, not the comment id',
  );
});

test('the fix flow spawns a code-verifier step between the edit step and the commit step', () => {
  const applyFixesBody = lensPromptBody('applyFixes');
  const editIndex = applyFixesBody.indexOf('applyFixesEdit(');
  const verifyIndex = applyFixesBody.indexOf('verifyFixesInWorkingTree(');
  const commitIndex = applyFixesBody.indexOf('commitVerifiedFixes(');
  assert.notEqual(editIndex, -1, 'expected applyFixes to call the edit step');
  assert.notEqual(verifyIndex, -1, 'expected applyFixes to call the verify step');
  assert.notEqual(commitIndex, -1, 'expected applyFixes to call the commit step');
  assert.ok(
    editIndex < verifyIndex && verifyIndex < commitIndex,
    'expected the order edit -> verify -> commit so the verifier verdict binds the fixed working tree',
  );
});

test('the shared verdict-fence builder names the binding-hash command and the verdict fence', () => {
  const fenceBuilder = lensPromptBody('buildVerdictFenceSteps');
  assert.match(
    fenceBuilder,
    /--manifest-hash-for-branch/,
    'expected the binding-hash command to use --manifest-hash-for-branch (cwd-immune)',
  );
  assert.doesNotMatch(
    fenceBuilder,
    /--manifest-hash(?!-for-branch)/,
    'expected the old --manifest-hash <REPO> form to be removed in favour of --manifest-hash-for-branch',
  );
  assert.match(
    fenceBuilder,
    /verification_verdict_store\.py/,
    'expected the verdict-store script that computes the binding hash to be named',
  );
  assert.match(fenceBuilder, /```verdict/, 'expected the verdict fence to be specified');
  assert.match(fenceBuilder, /manifest_sha256/, 'expected the verdict fence to carry manifest_sha256');
  assert.match(
    fenceBuilder,
    /gh pr view/,
    'expected buildVerdictFenceSteps to resolve the head branch via gh pr view (cwd-immune)',
  );
  assert.match(
    fenceBuilder,
    /headRefName/,
    'expected buildVerdictFenceSteps to extract the headRefName from gh pr view output',
  );
});

test('the verdict-fence binding does not self-resolve a cwd via git rev-parse for the manifest hash', () => {
  const fenceBuilder = lensPromptBody('buildVerdictFenceSteps');
  assert.doesNotMatch(
    fenceBuilder,
    /git rev-parse --show-toplevel/,
    'expected the binding hash to be cwd-immune (no git rev-parse in the binding step)',
  );
});

test('every verify step calls buildVerdictFenceSteps, uses code-verifier, and forbids edits', () => {
  for (const verifyFunctionName of [
    'verifyFixesInWorkingTree',
    'verifyRepairChanges',
  ]) {
    const verifyBody = lensPromptBody(verifyFunctionName);
    assert.match(
      verifyBody,
      /buildVerdictFenceSteps\(/,
      `expected ${verifyFunctionName} to call buildVerdictFenceSteps (cwd-immune branch binding)`,
    );
    assert.doesNotMatch(
      verifyBody,
      /VERDICT_FENCE_STEPS(?!\s*\))/,
      `expected ${verifyFunctionName} not to reference the removed VERDICT_FENCE_STEPS constant`,
    );
    assert.match(
      verifyBody,
      /agentType:\s*'code-verifier'/,
      `expected ${verifyFunctionName} to spawn the code-verifier agent type`,
    );
    assert.doesNotMatch(
      verifyBody,
      /schema:/,
      `expected ${verifyFunctionName} to pass no schema so its verdict fence stays as assistant text`,
    );
    assert.match(
      verifyBody,
      /do no edits|make no edits|not edit|no file edits/i,
      `expected ${verifyFunctionName} to be told to make no edits`,
    );
  }
});

test('verifyHardeningChanges uses --manifest-hash-for-branch with the hardening branch, uses code-verifier, and forbids edits', () => {
  const verifyBody = lensPromptBody('verifyHardeningChanges');
  assert.match(
    verifyBody,
    /--manifest-hash-for-branch/,
    'expected verifyHardeningChanges to bind by hardening branch (cwd-immune)',
  );
  assert.doesNotMatch(
    verifyBody,
    /--manifest-hash(?!-for-branch)/,
    'expected verifyHardeningChanges not to use the old --manifest-hash <REPO> form',
  );
  assert.match(
    verifyBody,
    /agentType:\s*'code-verifier'/,
    'expected verifyHardeningChanges to spawn the code-verifier agent type',
  );
  assert.doesNotMatch(
    verifyBody,
    /schema:/,
    'expected verifyHardeningChanges to pass no schema so its verdict fence stays as assistant text',
  );
  assert.match(
    verifyBody,
    /do no edits|make no edits|not edit|no file edits/i,
    'expected verifyHardeningChanges to be told to make no edits',
  );
});

test('verifyFixesInWorkingTree and verifyRepairChanges pass input.owner, input.repo, input.prNumber to buildVerdictFenceSteps', () => {
  for (const verifyFunctionName of ['verifyFixesInWorkingTree', 'verifyRepairChanges']) {
    const verifyBody = lensPromptBody(verifyFunctionName);
    assert.match(
      verifyBody,
      /buildVerdictFenceSteps\(input\.owner,\s*input\.repo,\s*input\.prNumber\)/,
      `expected ${verifyFunctionName} to pass PR coordinates to buildVerdictFenceSteps`,
    );
  }
});

test('the commit step is instructed to make no further file edits', () => {
  const commitBody = lensPromptBody('commitVerifiedFixes');
  assert.match(
    commitBody,
    /no (?:further |additional )?(?:file )?edits|do not edit|make no edits/i,
    'expected the commit step to forbid further edits so the verified surface stays bound',
  );
  assert.match(
    commitBody,
    /agentType:\s*'clean-coder'/,
    'expected the commit step to use clean-coder',
  );
});

test('the repair flow spawns a code-verifier step between the edit step and the commit step', () => {
  const repairBody = lensPromptBody('repairConvergence');
  const editIndex = repairBody.indexOf('repairConvergenceEdit(');
  const verifyIndex = repairBody.indexOf('verifyRepairChanges(');
  const commitIndex = repairBody.indexOf('commitRepairFixes(');
  assert.notEqual(editIndex, -1, 'expected repairConvergence to call the edit step');
  assert.notEqual(verifyIndex, -1, 'expected repairConvergence to call the verify step');
  assert.notEqual(commitIndex, -1, 'expected repairConvergence to call the commit step');
  assert.ok(
    editIndex < verifyIndex && verifyIndex < commitIndex,
    'expected edit -> verify -> commit so the verifier verdict binds the repaired working tree',
  );
  assert.match(
    repairBody,
    /verdictPassed\(/,
    'expected the verify verdict to gate the repair commit step',
  );
});

test('the standards-deferral flow spawns a code-verifier step between the edit step and the commit step', () => {
  const standardsBody = lensPromptBody('spawnStandardsFollowUp');
  const editIndex = standardsBody.indexOf('standardsFollowUpEdit(');
  const verifyIndex = standardsBody.indexOf('verifyHardeningChanges(');
  const commitIndex = standardsBody.indexOf('commitHardeningPr(');
  assert.notEqual(editIndex, -1, 'expected spawnStandardsFollowUp to call the edit step');
  assert.notEqual(verifyIndex, -1, 'expected spawnStandardsFollowUp to call the verify step');
  assert.notEqual(commitIndex, -1, 'expected spawnStandardsFollowUp to call the commit step');
  assert.ok(
    editIndex < verifyIndex && verifyIndex < commitIndex,
    'expected edit -> verify -> commit so the verifier verdict binds the hardening working tree',
  );
  assert.match(
    standardsBody,
    /verdictPassed\(/,
    'expected the verify verdict to gate the hardening commit step',
  );
});

test('the repair and hardening commit steps forbid further edits and use clean-coder', () => {
  for (const commitFunctionName of ['commitRepairFixes', 'commitHardeningPr']) {
    const commitBody = lensPromptBody(commitFunctionName);
    assert.match(
      commitBody,
      /no (?:further |additional )?(?:file )?edits|do not edit|make no edits/i,
      `expected ${commitFunctionName} to forbid further edits so the verified surface stays bound`,
    );
    assert.match(
      commitBody,
      /agentType:\s*'clean-coder'/,
      `expected ${commitFunctionName} to use clean-coder`,
    );
  }
});

test('the standards-deferral edit step stages the hardening change without committing', () => {
  const editBody = lensPromptBody('standardsFollowUpEdit');
  assert.match(
    editBody,
    /do not commit and do not push|NO commit and NO push|Do NOT commit/i,
    'expected the standards edit step to leave the hardening change uncommitted',
  );
  assert.match(
    editBody,
    /agentType:\s*'clean-coder'/,
    'expected the standards edit step to use clean-coder',
  );
});

test('spawnStandardsFollowUp reports whether a hardening PR opened on every path', () => {
  const body = lensPromptBody('spawnStandardsFollowUp');
  const falseReturns = body.match(/hardeningPrOpened:\s*false/g) || [];
  assert.ok(
    falseReturns.length >= 2,
    'expected both skip paths (no hardening staged, verify failed) to return hardeningPrOpened:false',
  );
  assert.match(
    body,
    /hardeningPrOpened:\s*true/,
    'expected the commit path to return hardeningPrOpened:true',
  );
});

test('the standards-deferral note names the hardening PR only when one opened', () => {
  const noteBody = lensPromptBody('standardsDeferralNote');
  assert.match(
    noteBody,
    /environment-hardening PR/,
    'expected the opened-PR branch to name the hardening PR',
  );
  assert.match(
    noteBody,
    /no environment-hardening PR/i,
    'expected the skip branch to state no hardening PR was opened',
  );
});

test('both standards-deferral call sites build standardsNote from the spawnStandardsFollowUp outcome', () => {
  const callSiteUses = convergeSource.match(/standardsNote = standardsDeferralNote\(/g) || [];
  assert.equal(
    callSiteUses.length,
    2,
    'expected both standards-deferral call sites to build standardsNote via standardsDeferralNote(...)',
  );
  assert.doesNotMatch(
    convergeSource,
    /standardsNote = `\$\{[^}]+\} code-standard finding\(s\) deferred to a follow-up fix issue plus an environment-hardening PR/,
    'expected no unconditional hardening-PR claim in standardsNote',
  );
});
