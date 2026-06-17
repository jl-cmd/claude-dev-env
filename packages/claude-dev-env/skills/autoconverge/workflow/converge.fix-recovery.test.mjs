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
  assert.match(constantLine('FIX_RECOVERY_MAX_ATTEMPTS'), /=\s*2/);
});

for (const commitFunctionName of ['commitVerifiedFixes', 'commitRepairFixes']) {
  test(`${commitFunctionName} prompt separates an edit-requiring block from a transient failure`, () => {
    const commitBody = functionSource(commitFunctionName);
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
}

test('recoverCommitBlockEdit is a clean-coder edit step bound to the blocker detail and leaves changes uncommitted', () => {
  const recoverBody = functionSource('recoverCommitBlockEdit');
  assert.match(recoverBody, /agentType:\s*'clean-coder'/, 'expected the fixer to use clean-coder');
  assert.match(recoverBody, /schema:\s*EDIT_SCHEMA/, 'expected the fixer to reuse EDIT_SCHEMA');
  assert.match(recoverBody, /label:\s*`fix-recover:/, 'expected the fix-recover label');
  assert.match(recoverBody, /blockerDetail/, 'expected the fixer prompt to consume the blocker detail');
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
});

test('applyFixes routes its commit through commitWithRecovery wired to the fix-path steps', () => {
  const applyFixesBody = functionSource('applyFixes');
  assert.match(applyFixesBody, /commitWithRecovery\(/, 'expected applyFixes to call commitWithRecovery');
  assert.match(applyFixesBody, /runCommit:\s*\(\)\s*=>\s*commitVerifiedFixes\(/);
  assert.match(applyFixesBody, /runVerify:\s*\(\)\s*=>\s*verifyFixesInWorkingTree\(/);
  assert.match(applyFixesBody, /runRecoverEdit:[\s\S]*?recoverCommitBlockEdit\(/);
});

test('repairConvergence routes its commit through commitWithRecovery wired to the repair-path steps', () => {
  const repairBody = functionSource('repairConvergence');
  assert.match(repairBody, /commitWithRecovery\(/, 'expected repairConvergence to call commitWithRecovery');
  assert.match(repairBody, /runCommit:\s*\(\)\s*=>\s*commitRepairFixes\(/);
  assert.match(repairBody, /runVerify:\s*\(\)\s*=>\s*verifyRepairChanges\(/);
  assert.match(repairBody, /runRecoverEdit:[\s\S]*?recoverCommitBlockEdit\(/);
});

test('the round-loop fix-stalled blockers survive the recovery wiring', () => {
  assert.match(convergeSource, /fix lens landed no push for/);
  assert.match(convergeSource, /copilot fix lens landed no push for/);
});
