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

function constantLine(constantName) {
  const matchedLine = convergeSource
    .split('\n')
    .find((eachLine) => eachLine.trimStart().startsWith(`const ${constantName} =`));
  assert.ok(matchedLine, `expected ${constantName} to be declared`);
  return matchedLine;
}

function schemaSource(schemaName, nextDeclaration) {
  const schemaStart = convergeSource.indexOf(`const ${schemaName} = {`);
  assert.notEqual(schemaStart, -1, `expected ${schemaName} to exist`);
  const schemaEnd = convergeSource.indexOf(`const ${nextDeclaration}`, schemaStart);
  assert.notEqual(schemaEnd, -1, `expected ${nextDeclaration} to follow ${schemaName}`);
  return convergeSource.slice(schemaStart, schemaEnd);
}

const pureModule = new Function(
  `${functionSource('commitNeedsCodeRecovery')}\n` + 'return { commitNeedsCodeRecovery };',
)();

const { commitNeedsCodeRecovery } = pureModule;

test('a dead commit agent (null result) does not need code recovery', () => {
  assert.equal(commitNeedsCodeRecovery(null), false);
});

test('a pushed commit does not need code recovery even with the flag and detail set', () => {
  assert.equal(
    commitNeedsCodeRecovery({ pushed: true, blockedNeedingEdit: true, blockerDetail: 'CODE_RULES' }),
    false,
  );
});

test('a transient failure (flag false, empty detail) does not need code recovery', () => {
  assert.equal(
    commitNeedsCodeRecovery({ pushed: false, blockedNeedingEdit: false, blockerDetail: '' }),
    false,
  );
});

test('a code-edit block (flag true, concrete detail) needs code recovery', () => {
  assert.equal(
    commitNeedsCodeRecovery({
      pushed: false,
      blockedNeedingEdit: true,
      blockerDetail: 'BLOCKED [code-rules]: collection param needs all_ prefix',
    }),
    true,
  );
});

test('a flagged block with an empty detail does not need code recovery', () => {
  assert.equal(
    commitNeedsCodeRecovery({ pushed: false, blockedNeedingEdit: true, blockerDetail: '' }),
    false,
  );
});

test('a detail without the flag does not need code recovery', () => {
  assert.equal(
    commitNeedsCodeRecovery({ pushed: false, blockedNeedingEdit: false, blockerDetail: 'some text' }),
    false,
  );
});

test('FIX_SCHEMA declares blockedNeedingEdit and blockerDetail as properties', () => {
  const fixSchema = schemaSource('FIX_SCHEMA', 'EDIT_SCHEMA');
  assert.match(fixSchema, /blockedNeedingEdit:\s*\{[\s\S]*?type:\s*'boolean'/);
  assert.match(fixSchema, /blockerDetail:\s*\{[\s\S]*?type:\s*'string'/);
});

test('FIX_SCHEMA requires blockedNeedingEdit and blockerDetail', () => {
  const fixSchema = schemaSource('FIX_SCHEMA', 'EDIT_SCHEMA');
  const requiredMatch = /required:\s*\[([^\]]*)\]/.exec(fixSchema);
  assert.ok(requiredMatch, 'expected FIX_SCHEMA to carry a required array');
  assert.match(requiredMatch[1], /blockedNeedingEdit/);
  assert.match(requiredMatch[1], /blockerDetail/);
});

test('FIX_RECOVERY_MAX_ATTEMPTS is declared and bounds the recovery loop at 2', () => {
  assert.match(constantLine('FIX_RECOVERY_MAX_ATTEMPTS'), /=\s*2\s*$/);
});

test('the commit path in runCodeEditorTask separates an edit-requiring block from a transient failure', () => {
  const commitBody = functionSource('runCodeEditorTask');
  assert.match(commitBody, /blockedNeedingEdit/, 'expected the edit-block flag to be set in the prompt');
  assert.match(commitBody, /blockerDetail/, 'expected the verbatim blocker detail to be requested');
  assert.match(
    commitBody,
    /code_rules_gate|CODE_RULES/,
    'expected the commit prompt to name the CODE_RULES commit gate as an edit-requiring block',
  );
  assert.match(
    commitBody,
    /transient/i,
    'expected the commit prompt to name the transient (non-code) failure case',
  );
});

test('the commit-recover task in runCodeEditorTask is a clean-coder edit step bound to the blocker detail and leaves changes uncommitted', () => {
  const recoverBody = functionSource('runCodeEditorTask');
  assert.match(recoverBody, /agentType:\s*'clean-coder'/, 'expected the fixer to use clean-coder');
  assert.match(recoverBody, /schema:\s*EDIT_SCHEMA/, 'expected the fixer to reuse EDIT_SCHEMA');
  assert.match(recoverBody, /task === 'commit-recover'/, 'expected the commit-recover task branch');
  assert.match(recoverBody, /context\.blockerDetail/, 'expected the fixer prompt to consume the blocker detail');
  assert.match(
    recoverBody,
    /only the (?:violation|finding|block)/i,
    'expected the fixer to be scoped to only the blocking violation',
  );
  assert.match(
    recoverBody,
    /do not commit and do not push|NO commit and NO push|Do NOT commit|leave .*uncommitted|uncommitted/i,
    'expected the fixer to leave its fix uncommitted for the re-verify and retry commit',
  );
});

test('commitWithRecovery bounds the loop, re-verifies, and retries the commit on a code block', () => {
  const recoveryBody = functionSource('commitWithRecovery');
  assert.match(recoveryBody, /commitNeedsCodeRecovery\(/, 'expected the loop guard to call commitNeedsCodeRecovery');
  assert.match(
    recoveryBody,
    /attempt\s*<\s*FIX_RECOVERY_MAX_ATTEMPTS/,
    'expected the loop to be bounded by FIX_RECOVERY_MAX_ATTEMPTS',
  );
  assert.match(recoveryBody, /runRecoverEdit\(/, 'expected the loop to spawn the recover-edit fixer');
  assert.match(recoveryBody, /runVerify\(/, 'expected the loop to re-verify after the fixer edit');
  assert.match(recoveryBody, /verdictPassed\(/, 'expected a fresh verdict to gate the retry commit');
  assert.match(recoveryBody, /runCommit\(/, 'expected the loop to retry the commit');
  const editGuardIndex = recoveryBody.search(/edited\s*!==\s*true/);
  const verifyGateIndex = recoveryBody.search(/verdictPassed\(/);
  assert.notEqual(editGuardIndex, -1, 'expected an early break when the fixer made no edit');
  assert.ok(
    editGuardIndex < verifyGateIndex,
    'expected the no-edit break to precede the re-verify gate',
  );
  const recoverEditIndex = recoveryBody.search(/runRecoverEdit\(/);
  const reverifyIndex = recoveryBody.search(/runVerify\(/);
  const retryCommitIndex = recoveryBody.lastIndexOf('runCommit(');
  assert.ok(
    recoverEditIndex < reverifyIndex && reverifyIndex < retryCommitIndex,
    'expected order recover-edit -> re-verify -> retry commit, so a verify/commit swap fails',
  );
});

test('applyFixes routes through the fix-edit task and fixerWithRecovery', () => {
  const applyFixesBody = functionSource('applyFixes');
  assert.match(applyFixesBody, /runCodeEditorTask\('fix-edit'/, "expected applyFixes to call runCodeEditorTask('fix-edit')");
  assert.match(applyFixesBody, /fixerWithRecovery\(/, 'expected applyFixes to call fixerWithRecovery');
});

test('applyFixes delegates to fixerWithRecovery, which grades fixes with a separate verifier from the fixer', () => {
  const applyFixesBody = functionSource('applyFixes');
  assert.match(
    applyFixesBody,
    /fixerWithRecovery\(head, findings, sourceLabel\)/,
    'expected applyFixes to delegate the verify and commit flow to fixerWithRecovery',
  );
  const recoveryBody = functionSource('fixerWithRecovery');
  assert.match(
    recoveryBody,
    /runVerifierTask\('fix-verify'/,
    'expected fixerWithRecovery to grade the fixes with the code-verifier task so the verdict is independent of the fixer',
  );
  assert.match(
    recoveryBody,
    /runFixerTask\('commit'/,
    'expected fixerWithRecovery to commit through the clean-coder fixer task',
  );
});

test('fixerWithRecovery runs verify via runVerifierTask and edits/commits via runFixerTask', () => {
  const recoveryBody = functionSource('fixerWithRecovery');
  assert.match(
    recoveryBody,
    /runVerifierTask\('fix-verify'/,
    'expected fixerWithRecovery to run the verify step through the separate verifier task',
  );
  assert.match(
    recoveryBody,
    /runFixerTask\('commit'/,
    'expected fixerWithRecovery to run the commit step through the fixer task',
  );
  assert.doesNotMatch(
    recoveryBody,
    /runFixerTask\('(?:verify-commit|fix-verify)'/,
    'expected the verify step never to route through the fixer task — the verifier grades a different agent than the one that edits',
  );
});

test('the fix-path verify routes through a different helper and agentType than the fix-path edits, mirroring the repair path', () => {
  const recoveryBody = functionSource('fixerWithRecovery');
  const verifyHelperMatch = /(\w+)\('fix-verify'/.exec(recoveryBody);
  const editHelperMatch = /(\w+)\('commit'/.exec(recoveryBody);
  assert.ok(verifyHelperMatch, 'expected a verify call naming its task helper');
  assert.ok(editHelperMatch, 'expected an edit/commit call naming its task helper');
  assert.equal(verifyHelperMatch[1], 'runVerifierTask', 'expected verify to route through runVerifierTask (code-verifier)');
  assert.equal(editHelperMatch[1], 'runFixerTask', 'expected commit to route through runFixerTask (clean-coder)');
  assert.notEqual(
    verifyHelperMatch[1],
    editHelperMatch[1],
    'expected the verify step to route through a different helper than the edit/commit step',
  );
});

test('the verifier carries a fix-verify task so the fix path verdict comes from the verifier', () => {
  const verifierBody = functionSource('runVerifierTask');
  assert.match(verifierBody, /task === 'fix-verify'/, 'expected runVerifierTask to handle the fix-verify task');
  assert.match(verifierBody, /buildVerdictFenceSteps\(/, 'expected the fix-verify task to emit a verdict fence');
  assert.match(verifierBody, /agentType:\s*'code-verifier'/, 'expected the fix-verify task to run as code-verifier');
});

test('runFixerTask no longer verifies its own edits — no code-verifier verify-commit task remains', () => {
  const fixerBody = functionSource('runFixerTask');
  assert.doesNotMatch(
    fixerBody,
    /task === 'verify-commit'/,
    'expected the fixer to no longer carry the verify-commit task that graded its own edits',
  );
  assert.doesNotMatch(
    fixerBody,
    /agentType:\s*'code-verifier'/,
    'expected the fixer to be clean-coder only — a separate verifier grades the working tree',
  );
});

test('repairConvergence routes its commit through commitWithRecovery wired to the repair-path steps', () => {
  const repairBody = functionSource('repairConvergence');
  assert.match(repairBody, /commitWithRecovery\(/, 'expected repairConvergence to call commitWithRecovery');
  assert.match(repairBody, /runCodeEditorTask\(/, 'expected repairConvergence to use runCodeEditorTask');
  assert.match(repairBody, /runVerifierTask\(/, 'expected repairConvergence to use runVerifierTask');
});

test('the round-loop fix-stalled blockers survive the recovery wiring', () => {
  assert.match(convergeSource, /fix lens landed no push for/);
  assert.match(convergeSource, /copilot fix lens landed no push for/);
});

const verifyObjectionModule = new Function(
  `${functionSource('parseLastVerdictFence')}\n` +
    `${constantLine('VERIFY_OBJECTION_FALLBACK')}\n` +
    `${functionSource('renderVerifyObjectionLine')}\n` +
    `${functionSource('extractVerifyObjection')}\n` +
    'return { extractVerifyObjection, VERIFY_OBJECTION_FALLBACK };',
)();

const { extractVerifyObjection, VERIFY_OBJECTION_FALLBACK } = verifyObjectionModule;

test('extractVerifyObjection falls back for a non-string transcript', () => {
  assert.equal(extractVerifyObjection(null), VERIFY_OBJECTION_FALLBACK);
});

test('extractVerifyObjection falls back when no verdict fence is present', () => {
  assert.equal(
    extractVerifyObjection('the verifier wrote prose with no verdict fence'),
    VERIFY_OBJECTION_FALLBACK,
  );
});

test('extractVerifyObjection falls back when the verdict fence carries no findings', () => {
  const transcript = '```verdict\n{"all_pass": false, "findings": []}\n```';
  assert.equal(extractVerifyObjection(transcript), VERIFY_OBJECTION_FALLBACK);
});

test('extractVerifyObjection renders each verdict finding as check then detail', () => {
  const transcript =
    '```verdict\n{"all_pass": false, "findings": [{"check": "Finding 1", "detail": "still over-blocks"}, {"check": "Finding 2", "detail": "boundary unchecked"}]}\n```';
  const objection = extractVerifyObjection(transcript);
  assert.match(objection, /1\. Finding 1 — still over-blocks/);
  assert.match(objection, /2\. Finding 2 — boundary unchecked/);
});

test('extractVerifyObjection reads the LAST verdict fence', () => {
  const transcript =
    '```verdict\n{"all_pass": false, "findings": [{"check": "stale", "detail": "old"}]}\n```\nretry\n```verdict\n{"all_pass": false, "findings": [{"check": "fresh", "detail": "new"}]}\n```';
  const objection = extractVerifyObjection(transcript);
  assert.match(objection, /fresh — new/);
  assert.doesNotMatch(objection, /stale/);
});

test('extractVerifyObjection renders bare string findings as their text', () => {
  const transcript =
    '```verdict\n{"all_pass": false, "findings": ["boundary still over-blocks", "missing test for empty input"]}\n```';
  const objection = extractVerifyObjection(transcript);
  assert.match(objection, /1\. boundary still over-blocks/);
  assert.match(objection, /2\. missing test for empty input/);
  assert.doesNotMatch(objection, /unnamed check/);
});

test('extractVerifyObjection renders alternate-keyed objects (title, message, description, issue)', () => {
  const transcript =
    '```verdict\n{"all_pass": false, "findings": [{"title": "over-blocks", "detail": "boundary unchecked"}, {"message": "regex too broad"}, {"description": "no fallback path"}, {"issue": "stale fixture"}]}\n```';
  const objection = extractVerifyObjection(transcript);
  assert.match(objection, /over-blocks — boundary unchecked/);
  assert.match(objection, /regex too broad/);
  assert.match(objection, /no fallback path/);
  assert.match(objection, /stale fixture/);
  assert.doesNotMatch(objection, /unnamed check/);
  assert.doesNotMatch(objection, /no detail/);
});

test('extractVerifyObjection renders mixed string and object findings', () => {
  const transcript =
    '```verdict\n{"all_pass": false, "findings": ["plain concern", {"check": "named", "detail": "explained"}]}\n```';
  const objection = extractVerifyObjection(transcript);
  assert.match(objection, /1\. plain concern/);
  assert.match(objection, /2\. named — explained/);
});

test('extractVerifyObjection stringifies an object whose keys it does not recognize', () => {
  const transcript = '```verdict\n{"all_pass": false, "findings": [{"severity": "P1", "line": 42}]}\n```';
  const objection = extractVerifyObjection(transcript);
  assert.match(objection, /severity/);
  assert.match(objection, /42/);
  assert.doesNotMatch(objection, /unnamed check/);
});

test('extractVerifyObjection falls back when no finding yields usable text', () => {
  const transcript = '```verdict\n{"all_pass": false, "findings": [null, {}, ""]}\n```';
  assert.equal(extractVerifyObjection(transcript), VERIFY_OBJECTION_FALLBACK);
});

test('the verify-recover task in runCodeEditorTask is a clean-coder edit step bound to the verifier objection and leaves changes uncommitted', () => {
  const recoverBody = functionSource('runCodeEditorTask');
  assert.match(recoverBody, /agentType:\s*'clean-coder'/, 'expected the fixer to use clean-coder');
  assert.match(recoverBody, /schema:\s*EDIT_SCHEMA/, 'expected the fixer to reuse EDIT_SCHEMA');
  assert.match(recoverBody, /VERIFY-RECOVERY fixer/, 'expected the verify-recovery prompt body');
  assert.match(recoverBody, /context\.objection/, 'expected the fixer prompt to consume the verifier objection');
  assert.match(
    recoverBody,
    /do not commit and do not push|Do NOT commit|leave .*uncommitted|uncommitted/i,
    'expected the fixer to leave its fix uncommitted for the re-verify and retry commit',
  );
});

test('verifyWithRecovery bounds the loop, re-fixes on a failed verdict, and re-verifies', () => {
  const recoveryBody = functionSource('verifyWithRecovery');
  assert.match(recoveryBody, /verdictPassed\(/, 'expected the loop guard to call verdictPassed');
  assert.match(
    recoveryBody,
    /attempt\s*<\s*FIX_RECOVERY_MAX_ATTEMPTS/,
    'expected the loop to be bounded by FIX_RECOVERY_MAX_ATTEMPTS',
  );
  assert.match(recoveryBody, /runRecoverEdit\(/, 'expected the loop to spawn the verify-recovery fixer');
  assert.match(recoveryBody, /runVerify\(/, 'expected the loop to re-verify after the fixer edit');
  assert.match(
    recoveryBody,
    /extractVerifyObjection\(/,
    'expected the loop to feed the fixer the verifier objection',
  );
  const editGuardIndex = recoveryBody.search(/edited\s*!==\s*true/);
  assert.notEqual(editGuardIndex, -1, 'expected an early break when the fixer made no edit');
  const recoverEditIndex = recoveryBody.search(/runRecoverEdit\(/);
  const reverifyIndex = recoveryBody.lastIndexOf('runVerify(');
  assert.ok(recoverEditIndex < reverifyIndex, 'expected order recover-edit -> re-verify, so a swap fails');
});

test('applyFixes routes through fixerWithRecovery which handles verify and commit', () => {
  const applyFixesBody = functionSource('applyFixes');
  assert.match(applyFixesBody, /fixerWithRecovery\(/, 'expected applyFixes to call fixerWithRecovery');
  assert.match(applyFixesBody, /runCodeEditorTask\('fix-edit'/, "expected applyFixes to call runCodeEditorTask('fix-edit')");
});

test('repairConvergence routes its verify through verifyWithRecovery wired to the task helpers', () => {
  const repairBody = functionSource('repairConvergence');
  assert.match(repairBody, /verifyWithRecovery\(/, 'expected repairConvergence to call verifyWithRecovery');
  assert.match(repairBody, /runVerifierTask\(/, 'expected repairConvergence to use runVerifierTask for verify');
  assert.match(repairBody, /runCodeEditorTask\(/, 'expected repairConvergence to use runCodeEditorTask for recover');
});
