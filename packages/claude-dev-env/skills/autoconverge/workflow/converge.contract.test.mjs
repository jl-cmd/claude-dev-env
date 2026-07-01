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
const skillSource = readFileSync(
  join(workflowDirectory, '..', 'SKILL.md'),
  'utf8',
);

function lensPromptBody(builderName) {
  let builderStart = convergeSource.indexOf(`function ${builderName}(`);
  if (builderStart === -1) {
    builderStart = convergeSource.indexOf(`const ${builderName} =`);
    assert.notEqual(builderStart, -1, `expected ${builderName} to exist as a function or const`);
  }
  const nextBuilderMatch = /\n(?:async )?function /.exec(convergeSource.slice(builderStart + 1));
  const builderEnd =
    nextBuilderMatch === null ? convergeSource.length : builderStart + 1 + nextBuilderMatch.index;
  return convergeSource.slice(builderStart, builderEnd);
}

function functionSource(functionName) {
  const functionStart = convergeSource.indexOf(`function ${functionName}(`);
  assert.notEqual(functionStart, -1, `expected ${functionName} to exist`);
  const nextMatch = /\n(?:async )?function /.exec(convergeSource.slice(functionStart + 1));
  const functionEnd =
    nextMatch === null ? convergeSource.length : functionStart + 1 + nextMatch.index;
  return convergeSource.slice(functionStart, functionEnd);
}

test('code-review lens prompt no longer instructs a per-lens git fetch', () => {
  assert.doesNotMatch(lensPromptBody('runCodeReviewLens'), /git fetch origin main/);
});

test('bug-audit lens prompt no longer instructs a per-lens git fetch', () => {
  assert.doesNotMatch(lensPromptBody('runAuditLens'), /git fetch origin main/);
});

test('a single round-level prefetch step fetches origin/main before the parallel lenses', () => {
  assert.ok(convergeSource.includes("runGitTask('prefetch-main')"));
  const prefetchCallIndex = convergeSource.indexOf("runGitTask('prefetch-main')");
  const parallelLensIndex = convergeSource.indexOf('const lenses = await parallel(');
  assert.notEqual(prefetchCallIndex, -1, 'expected prefetch to be invoked');
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
  const repairPrompt = functionSource('runCodeEditorTask');
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
  const repairPrompt = functionSource('runCodeEditorTask');
  assert.doesNotMatch(
    repairPrompt,
    /fetch every thread where isResolved is false/,
    'the unfiltered instruction could resolve human reviewer threads',
  );
});

test('the bugbot lens waits through the Monitor tool, not a foreground sleep', () => {
  const bugbotPrompt = lensPromptBody('runBugbotLens');
  assert.match(bugbotPrompt, /Monitor tool/, 'expected the bugbot poll to wait via the Monitor tool');
  assert.doesNotMatch(
    bugbotPrompt,
    /sleep 60|sleep 8|Start-Sleep/,
    'expected no foreground sleep in the bugbot poll delays',
  );
});

test('the copilot gate waits through the Monitor tool, not a foreground sleep', () => {
  const copilotPrompt = lensPromptBody('runCopilotGate');
  assert.match(copilotPrompt, /Monitor tool/, 'expected the copilot poll to wait via the Monitor tool');
  assert.doesNotMatch(copilotPrompt, /sleep 360|Start-Sleep/, 'expected no foreground sleep in the copilot poll delay');
});

test('gotchas doc describes the reviewer wait as a Monitor poll, not a foreground sleep', () => {
  assert.match(gotchasSource, /Monitor tool/, 'expected the gotcha to name the Monitor-based reviewer wait');
  assert.doesNotMatch(
    gotchasSource,
    /shell-agnostic/i,
    'the reviewer wait is a Monitor poll, not a shell-agnostic sleep loop',
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
  const headResolveCallIndex = convergeSource.indexOf("runGitTask('resolve-head')", convergeBranchStart);
  assert.notEqual(headResolveCallIndex, -1, 'expected CONVERGE to re-resolve HEAD via runGitTask');
});

test('fix edit prompt resolves threads by PRRT thread node id looked up from the comment databaseId', () => {
  const editPrompt = functionSource('runCodeEditorTask');
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
    functionSource('runCodeEditorTask'),
    /then resolve that thread \(use the github MCP pull_request_review_write/,
    'resolve_thread and resolveReviewThread require a PRRT_... thread node id, not the comment id',
  );
});

test('the fix flow runs the edit task then fixerWithRecovery after the edit step', () => {
  const applyFixesBody = lensPromptBody('applyFixes');
  assert.match(applyFixesBody, /runCodeEditorTask\('fix-edit'/, "expected applyFixes to call runCodeEditorTask('fix-edit')");
  assert.match(applyFixesBody, /fixerWithRecovery\(/, 'expected applyFixes to call fixerWithRecovery');
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
  for (const verifyFunctionName of ['runVerifierTask']) {
    const verifyBody = lensPromptBody(verifyFunctionName);
    assert.match(
      verifyBody,
      /buildVerdictFenceSteps\(/,
      `expected ${verifyFunctionName} to call buildVerdictFenceSteps (cwd-immune branch binding)`,
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

test('runFixerTask never verifies — verification belongs to the separate verifier', () => {
  const fixerBody = lensPromptBody('runFixerTask');
  assert.doesNotMatch(fixerBody, /buildVerdictFenceSteps\(/, 'expected the fixer to not emit a verdict fence — the separate verifier does');
  assert.doesNotMatch(fixerBody, /agentType:\s*'code-verifier'/, 'expected the fixer to be clean-coder only');
  assert.match(fixerBody, /agentType:\s*'clean-coder'/, 'expected the fixer to use clean-coder for its commit and recovery edits');
});

test('runVerifierTask uses --manifest-hash-for-branch with the hardening branch and forbids edits', () => {
  const verifyBody = lensPromptBody('runVerifierTask');
  assert.match(
    verifyBody,
    /--manifest-hash-for-branch/,
    'expected the verifier to bind by hardening branch (cwd-immune)',
  );
  assert.match(
    verifyBody,
    /do no edits|make no edits|not edit|no file edits/i,
    'expected the verifier to be told to make no edits',
  );
});

test('runVerifierTask passes PR coordinates to buildVerdictFenceSteps for the fix-verify and repair-verify tasks', () => {
  const verifyBody = lensPromptBody('runVerifierTask');
  assert.match(verifyBody, /task === 'fix-verify'/, 'expected runVerifierTask to carry the fix-path verify task');
  assert.match(
    verifyBody,
    /buildVerdictFenceSteps\(input\.owner, input\.repo, input\.prNumber\)/,
    'expected runVerifierTask to pass PR coordinates to buildVerdictFenceSteps',
  );
});

test('the commit path in runFixerTask forbids further edits and uses clean-coder', () => {
  const fixerBody = lensPromptBody('runFixerTask');
  assert.match(
    fixerBody,
    /no (?:further |additional )?(?:file )?edits|do not edit|make no edits/i,
    'expected the commit path to forbid further edits',
  );
  assert.match(
    fixerBody,
    /agentType:\s*'clean-coder'/,
    'expected the commit path to use clean-coder',
  );
});

test('the repair flow uses the direct-spawn task helpers for edit, verify, and commit', () => {
  const repairBody = lensPromptBody('repairConvergence');
  assert.match(repairBody, /runCodeEditorTask\(/, 'expected repairConvergence to call runCodeEditorTask');
  assert.match(repairBody, /runVerifierTask\(/, 'expected repairConvergence to call runVerifierTask');
  assert.match(repairBody, /verdictPassed\(/, 'expected the verify verdict to gate the repair commit step');
});

test('the standards-deferral flow uses the direct-spawn task helpers for edit, verify, and commit', () => {
  const standardsBody = lensPromptBody('spawnStandardsFollowUp');
  assert.match(standardsBody, /runCodeEditorTask\(/, 'expected spawnStandardsFollowUp to call runCodeEditorTask');
  assert.match(standardsBody, /runVerifierTask\(/, 'expected spawnStandardsFollowUp to call runVerifierTask');
  assert.match(standardsBody, /verdictPassed\(/, 'expected the verify verdict to gate the hardening commit step');
});

test('repair-commit and hardening-commit paths use clean-coder and forbid edits', () => {
  const codeEditorBody = lensPromptBody('runCodeEditorTask');
  assert.match(
    codeEditorBody,
    /no (?:further |additional )?(?:file )?edits|do not edit|make no edits/i,
    'expected the commit paths to forbid further edits',
  );
  assert.match(
    codeEditorBody,
    /agentType:\s*'clean-coder'/,
    'expected the commit paths to use clean-coder',
  );
});

test('the code-editor standards-edit path stages hardening without committing and uses clean-coder', () => {
  const editBody = lensPromptBody('runCodeEditorTask');
  assert.match(
    editBody,
    /do not commit and do not push|NO commit and NO push|Do NOT commit/i,
    'expected the standards edit path to leave the hardening change uncommitted',
  );
  assert.match(
    editBody,
    /agentType:\s*'clean-coder'/,
    'expected the edit paths to use clean-coder',
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

test('a reuse-audit lens builder exists', () => {
  assert.match(convergeSource, /function runReuseAuditPass\(/);
});

test('the reuse pass runs once before the convergence loop', () => {
  const reuseCallIndex = convergeSource.indexOf('await runReuseAuditPass(');
  const loopIndex = convergeSource.indexOf('while (iterations < CONFIG.maxIterations)');
  assert.notEqual(reuseCallIndex, -1, 'expected the reuse pass to be invoked');
  assert.notEqual(loopIndex, -1, 'expected the convergence loop to exist');
  assert.ok(
    reuseCallIndex < loopIndex,
    'expected the reuse pass to run before the convergence loop starts',
  );
});

test('the reuse lens prompt enumerates all three qualifying criteria and an omit rule', () => {
  const reusePrompt = lensPromptBody('runReuseAuditPass');
  assert.match(reusePrompt, /CERTAIN/);
  assert.match(reusePrompt, /BEHAVIORALLY IDENTICAL/);
  assert.match(reusePrompt, /AUTONOMOUSLY IMPLEMENTABLE/);
  assert.match(
    reusePrompt,
    /when any one is in doubt, omit the finding/i,
    'expected the reuse lens to drop any finding that fails a criterion',
  );
});

test('the reuse lens reviews the full diff and does not edit', () => {
  const reusePrompt = lensPromptBody('runReuseAuditPass');
  assert.match(reusePrompt, /origin\/main\.\.\.HEAD/);
  assert.match(
    reusePrompt,
    /Do NOT edit, commit, or push/,
    'expected the reuse lens to report findings without editing',
  );
});

test('the reuse pass applies its findings through applyFixes, not the standards-deferral path', () => {
  const reuseCallIndex = convergeSource.indexOf('await runReuseAuditPass(');
  const loopIndex = convergeSource.indexOf('while (iterations < CONFIG.maxIterations)');
  const reuseBlock = convergeSource.slice(reuseCallIndex, loopIndex);
  assert.match(
    reuseBlock,
    /applyFixes\(reuseHead, reuseFindings, 'reuse-pass'\)/,
    'expected the reuse pass to apply its findings via applyFixes',
  );
  assert.doesNotMatch(
    reuseBlock,
    /spawnStandardsFollowUp/,
    'expected the reuse pass to apply improvements, not defer them',
  );
});

test('the reuse lens runs under the Reuse phase', () => {
  const reusePrompt = lensPromptBody('runReuseAuditPass');
  assert.match(reusePrompt, /phase: 'Reuse'/);
});

test('the pre-commit gate step is a shared constant that dry-runs the CODE_RULES commit gate', () => {
  assert.match(convergeSource, /const PRE_COMMIT_GATE_STEP =/);
  const stepStart = convergeSource.indexOf('const PRE_COMMIT_GATE_STEP =');
  const stepEnd = convergeSource.indexOf('\n\n', stepStart);
  const stepBody = convergeSource.slice(stepStart, stepEnd);
  assert.match(stepBody, /code_rules_gate\.py/);
  assert.match(stepBody, /--staged/);
  assert.match(
    stepBody,
    /do NOT commit/i,
    'expected the gate step to forbid committing — it is a dry committability check',
  );
});

const editStepTaskDispatchers = ['runCodeEditorTask', 'runFixerTask'];

for (const helperName of editStepTaskDispatchers) {
  test(`${helperName} appends the pre-commit gate step to its edit prompts`, () => {
    assert.match(
      functionSource(helperName),
      /\+\s*PRE_COMMIT_GATE_STEP/,
      `expected ${helperName} to append PRE_COMMIT_GATE_STEP to its edit-task prompts`,
    );
  });
}

const editStepTasks = [
  ['runCodeEditorTask', 'fix-edit'],
  ['runCodeEditorTask', 'repair-edit'],
  ['runCodeEditorTask', 'standards-edit'],
  ['runCodeEditorTask', 'commit-recover'],
];

for (const [helperName, taskName] of editStepTasks) {
  test(`${helperName} routes the ${taskName} task to a pre-commit-gated edit prompt`, () => {
    assert.match(
      functionSource(helperName),
      new RegExp(`task === '${taskName}'`),
      `expected ${helperName} to handle the ${taskName} task`,
    );
  });
}

function preambleText() {
  const preambleStart = convergeSource.indexOf('const HEADLESS_SAFETY_PREAMBLE =');
  assert.notEqual(preambleStart, -1, 'expected HEADLESS_SAFETY_PREAMBLE to exist');
  const preambleEnd = convergeSource.indexOf('\n\nlet ', preambleStart);
  return convergeSource.slice(preambleStart, preambleEnd === -1 ? undefined : preambleEnd);
}

test('preamble prescribes authoring a Python helper for variable-built or multi-step sandboxes', () => {
  assert.match(
    preambleText(),
    /python\s+<file>\.py|python\s+<.*>\.py|author.*python.*helper|python.*helper.*sandbox|sandbox.*python.*helper/i,
    'expected the preamble to prescribe running a Python helper file for multi-step sandbox teardown',
  );
});

test('preamble does not claim the standalone or both rm auto-allow paths fail closed on any $', () => {
  const text = preambleText().replace(/\$\(\.\.\.\)/g, 'SUBSHELL').replace(/\s+/g, ' ');
  const overstatesStandalone =
    /\b(?:both|standalone|neither)\b[^.]*fail closed[^.]*any \$/i.test(text) ||
    /\b(?:both|standalone|neither)\b[^.]*any \$[^.]*fail closed/i.test(text);
  assert.equal(
    overstatesStandalone,
    false,
    'only the compound path fails closed on any $ in the target; the standalone path accepts a $-bearing target whose literal path already sits under an ephemeral root',
  );
});

test('preamble does not claim $CLAUDE_JOB_DIR/tmp is blocked', () => {
  assert.doesNotMatch(
    preambleText(),
    /CLAUDE_JOB_DIR\/tmp is NOT auto-allowed/i,
    'under an ephemeral cwd the hook auto-allows rm targeting $CLAUDE_JOB_DIR/tmp',
  );
});

test('preamble scopes its rm-shape claim to the narrowest auto-allow path, not the full set', () => {
  assert.doesNotMatch(
    preambleText(),
    /auto-allows rm only when ALL of these hold/i,
    'the hook has three rm auto-allow paths, so the preamble must not assert one narrow shape is the complete set',
  );
});

test('SKILL.md does not claim the standalone or both rm auto-allow paths fail closed on any $', () => {
  const text = skillSource.replace(/`/g, '').replace(/\$\(\.\.\.\)/g, 'SUBSHELL').replace(/\s+/g, ' ');
  const overstatesStandalone =
    /\b(?:both|standalone|neither)\b[^.]*fail closed[^.]*any \$/i.test(text) ||
    /\b(?:both|standalone|neither)\b[^.]*any \$[^.]*fail closed/i.test(text);
  assert.equal(
    overstatesStandalone,
    false,
    'only the compound path fails closed on any $ in the target; the standalone path accepts a $-bearing target whose literal path already sits under an ephemeral root',
  );
});

test('SKILL.md does not claim it enforces the exact rm shape the hook auto-allows', () => {
  assert.doesNotMatch(
    skillSource,
    /exact rm shape the hook auto-allows/i,
    'the hook has multiple rm auto-allow paths, so SKILL.md must not assert one narrow shape is the exact set',
  );
});

test('preamble does not attribute the known-temp-var resolution to the standalone or compound paths', () => {
  assert.doesNotMatch(
    preambleText().replace(/\s+/g, ' '),
    /Across these paths[\s\S]*?CLAUDE_JOB_DIR/i,
    'the temp-var resolution lives only in the broad cwd-scoped path; the standalone and compound paths do not resolve known temp variables',
  );
});

test('preamble attributes the known-temp-var resolution to a third cwd-scoped auto-allow path', () => {
  const text = preambleText().replace(/\s+/g, ' ');
  const tempVarSentenceMatch =
    /[^.]*\bTMPDIR\b[^.]*CLAUDE_JOB_DIR[^.]*\./i.exec(text);
  assert.notEqual(
    tempVarSentenceMatch,
    null,
    'expected a sentence describing the TEMP/TMP/TMPDIR/CLAUDE_JOB_DIR resolution',
  );
  assert.match(
    tempVarSentenceMatch[0],
    /declares? an ephemeral cwd|declared ephemeral cwd|ephemeral-cwd path|third (?:auto-allow )?path|cwd-scoped path/i,
    'expected the temp-var resolution to be tied to the cwd-scoped path that declares an ephemeral working directory, not the standalone or compound paths',
  );
});

test('SKILL.md does not attribute the known-temp-var resolution to the standalone or compound paths', () => {
  assert.doesNotMatch(
    skillSource.replace(/\s+/g, ' '),
    /Across those paths[\s\S]*?CLAUDE_JOB_DIR/i,
    'the temp-var resolution lives only in the broad cwd-scoped path; the standalone and compound paths do not resolve known temp variables',
  );
});

test('SKILL.md attributes the known-temp-var resolution to the cwd-scoped auto-allow path', () => {
  const tempVarSentenceMatch =
    /[^.]*\bTMPDIR\b[^.]*CLAUDE_JOB_DIR[^.]*\./i.exec(skillSource.replace(/\s+/g, ' '));
  assert.notEqual(
    tempVarSentenceMatch,
    null,
    'expected a sentence describing the TEMP/TMP/TMPDIR/CLAUDE_JOB_DIR resolution',
  );
  assert.match(
    tempVarSentenceMatch[0],
    /declares? an ephemeral cwd|declared ephemeral cwd|ephemeral-cwd path|third (?:auto-allow )?path|cwd-scoped path/i,
    'expected the temp-var resolution to be tied to the cwd-scoped path that declares an ephemeral working directory, not the standalone or compound paths',
  );
});

test('convergeAgent prepends HEADLESS_SAFETY_PREAMBLE and the worktree directive to every prompt', () => {
  const convergeAgentBody = lensPromptBody('convergeAgent');
  assert.match(
    convergeAgentBody,
    /HEADLESS_SAFETY_PREAMBLE.*worktreeDirective/,
    'expected convergeAgent to prepend both preamble and worktree directive',
  );
});

const taskDispatchers = [
  { name: 'runGitTask', isAsync: false },
  { name: 'runFixerTask', isAsync: false },
  { name: 'fixerWithRecovery', isAsync: true },
  { name: 'runCodeEditorTask', isAsync: false },
  { name: 'runVerifierTask', isAsync: false },
  { name: 'runGeneralUtilityTask', isAsync: false },
  { name: 'runConvergenceCheck', isAsync: false },
];

for (const { name, isAsync } of taskDispatchers) {
  const prefix = isAsync ? 'async ' : '';
  test(`function ${prefix}${name} exists in converge.mjs`, () => {
    const needle = isAsync ? `async function ${name}(` : `function ${name}(`;
    assert.ok(convergeSource.includes(needle), `expected ${name} to exist`);
  });
}

test('runGeneralUtilityTask only handles the two tasks it is called with', () => {
  const generalBody = functionSource('runGeneralUtilityTask');
  assert.doesNotMatch(
    generalBody,
    /task === 'bugbot-lens'/,
    'the live Bugbot lens is runBugbotLens; the dead bugbot-lens branch must be removed',
  );
  assert.doesNotMatch(
    generalBody,
    /Copilot can run out of usage/,
    'the live Copilot gate is runCopilotGate; the dead copilot-gate branch must be removed',
  );
  assert.doesNotMatch(
    generalBody,
    /convergence summary/,
    'the convergence-summary producer was removed; the dead branch must not return',
  );
});

const orphanedHelperNames = [
  'applyFixesEdit',
  'recoverCommitBlockEdit',
  'recoverVerifyFailEdit',
  'checkConvergence',
  'markReady',
  'repairConvergenceEdit',
  'verifyRepairChanges',
  'commitRepairFixes',
  'resolveConflictsEdit',
  'standardsFollowUpEdit',
  'verifyHardeningChanges',
  'commitHardeningPr',
  'postCleanAudit',
  'spawnConvergenceSummary',
];

for (const orphanName of orphanedHelperNames) {
  test(`${orphanName} is removed — its behavior lives in a direct-spawn task dispatcher`, () => {
    assert.ok(
      !convergeSource.includes(`function ${orphanName}(`),
      `expected the orphaned ${orphanName} definition to be deleted (CODE_RULES 9.8)`,
    );
  });
}

test('the whole priming spawn-agent family is removed — every dispatcher spawns fresh', () => {
  assert.doesNotMatch(
    convergeSource,
    /function\s+spawn\w+Agent\s*\(/,
    'expected no spawn<Role>Agent priming function to survive — each task dispatcher spawns a fresh agent',
  );
});

test('parseLastVerdictFence returns non-null for a verdict fence with valid JSON', () => {
  const parseModule = new Function(
    `${functionSource('parseLastVerdictFence')}\n` +
    'return { parseLastVerdictFence };',
  )();
  const result = parseModule.parseLastVerdictFence('```verdict\n{"all_pass":true,"findings":[],"manifest_sha256":"abc"}\n```');
  assert.notEqual(result, null);
  assert.equal(result.all_pass, true);
});

test('parseLastVerdictFence returns null for non-string input', () => {
  const parseModule = new Function(
    `${functionSource('parseLastVerdictFence')}\n` +
    'return { parseLastVerdictFence };',
  )();
  assert.equal(parseModule.parseLastVerdictFence(null), null);
  assert.equal(parseModule.parseLastVerdictFence(undefined), null);
});

test('parseLastVerdictFence returns null when no verdict fence is present', () => {
  const parseModule = new Function(
    `${functionSource('parseLastVerdictFence')}\n` +
    'return { parseLastVerdictFence };',
  )();
  assert.equal(parseModule.parseLastVerdictFence('plain text with no fence'), null);
});

test('parseLastVerdictFence returns null for malformed JSON in the fence', () => {
  const parseModule = new Function(
    `${functionSource('parseLastVerdictFence')}\n` +
    'return { parseLastVerdictFence };',
  )();
  assert.equal(parseModule.parseLastVerdictFence('```verdict\nnot json\n```'), null);
});

test('verdictPassed calls parseLastVerdictFence', () => {
  const verdictBody = lensPromptBody('verdictPassed');
  assert.match(verdictBody, /parseLastVerdictFence\(/, 'expected verdictPassed to call the shared parser');
});

test('extractVerifyObjection calls parseLastVerdictFence', () => {
  const objectionBody = lensPromptBody('extractVerifyObjection');
  assert.match(objectionBody, /parseLastVerdictFence\(/, 'expected extractVerifyObjection to call the shared parser');
});

test('the headless preamble routes waits through the Monitor tool and forbids ending a turn to await work', () => {
  const preambleStart = convergeSource.indexOf('const HEADLESS_SAFETY_PREAMBLE =');
  assert.notEqual(preambleStart, -1, 'expected a HEADLESS_SAFETY_PREAMBLE definition');
  const preambleEnd = convergeSource.indexOf('\n\nlet activeRepoPath', preambleStart);
  assert.notEqual(preambleEnd, -1, 'expected the preamble to end before activeRepoPath');
  const preamble = convergeSource.slice(preambleStart, preambleEnd);
  assert.match(preamble, /foreground sleep is blocked/i, 'expected the preamble to state foreground sleep is blocked');
  assert.match(preamble, /Monitor tool/, 'expected the preamble to route waits through the Monitor tool');
  assert.match(preamble, /StructuredOutput/, 'expected the preamble to require a schema agent to always call StructuredOutput');
  assert.match(preamble, /never end your turn to wait/i, 'expected the preamble to forbid ending a turn to await background work');
});

test('no agent prompt instructs a foreground sleep as the poll delay', () => {
  assert.doesNotMatch(
    convergeSource,
    /delay each (?:attempt|iteration|retry) with "sleep/,
    'expected no poll directive to instruct a foreground sleep as the between-attempt delay',
  );
  assert.doesNotMatch(
    convergeSource,
    /Start-Sleep -Seconds/,
    'expected no agent prompt to instruct a foreground PowerShell Start-Sleep',
  );
});
