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
  const nextFunctionMatch = /\n(?:async )?function /.exec(convergeSource.slice(functionStart + 1));
  const functionEnd =
    nextFunctionMatch === null ? convergeSource.length : functionStart + 1 + nextFunctionMatch.index;
  return convergeSource.slice(functionStart, functionEnd);
}

const helperModule = new Function(
  `${functionBody('isMergeConflicting')}\nreturn { isMergeConflicting };`,
)();
const { isMergeConflicting } = helperModule;

test('isMergeConflicting treats a dead check agent (null/undefined) as not conflicting', () => {
  assert.equal(isMergeConflicting(null), false);
  assert.equal(isMergeConflicting(undefined), false);
});

test('isMergeConflicting reports a conflict only when the check returned conflicting:true', () => {
  assert.equal(isMergeConflicting({ conflicting: true }), true);
  assert.equal(isMergeConflicting({ conflicting: false }), false);
});

test('the git agent handles merge-conflict checks with shell-agnostic polling', () => {
  const gitBody = functionBody('runGitTask');
  assert.match(gitBody, /mergeable/, 'expected the git agent to read the PR mergeable field');
  assert.match(
    gitBody,
    /do not edit, commit, push, or rebase|read only/i,
    'expected the git agent merge check to be read-only',
  );
  assert.match(gitBody, /MERGE_CONFLICT_SCHEMA/, 'expected the git agent to return MERGE_CONFLICT_SCHEMA');
  assert.match(gitBody, /sleep 5|Start-Sleep/, 'expected a shell-agnostic poll delay');
});

test('runCodeEditorTask conflict-edit path rebases onto origin/main and makes no push', () => {
  const body = functionBody('runCodeEditorTask');
  assert.match(body, /git rebase origin\/main/, 'expected the edit path to rebase onto origin/main');
  assert.match(
    body,
    /do not push|no push|not push/i,
    'expected the edit path to leave the push to the commit step',
  );
});

test('resolveMergeConflicts runs check -> edit -> verify -> commit and gates the push on the verdict', () => {
  const body = functionBody('resolveMergeConflicts');
  const checkIndex = body.indexOf("runGitTask('check-merge-conflicts'");
  const editIndex = body.indexOf("runCodeEditorTask('conflict-edit'");
  const verifyIndex = body.indexOf('runVerifierTask(');
  const commitIndex = body.indexOf('commitWithRecovery(');
  assert.notEqual(checkIndex, -1, 'expected the conflict check to run');
  assert.notEqual(editIndex, -1, 'expected the edit step to run');
  assert.notEqual(verifyIndex, -1, 'expected the verify step to run');
  assert.notEqual(commitIndex, -1, 'expected the commit step to run');
  assert.ok(
    checkIndex < editIndex && editIndex < verifyIndex && verifyIndex < commitIndex,
    'expected the order check -> edit -> verify -> commit',
  );
  assert.match(body, /verdictPassed\(/, 'expected the verifier verdict to gate the force-push');
});

test('resolveMergeConflicts rebases only when the check reports a conflict', () => {
  const body = functionBody('resolveMergeConflicts');
  assert.match(body, /isMergeConflicting\(/, 'expected the orchestrator to branch on the conflict decision');
  assert.match(
    body,
    /if \(!isMergeConflicting\([^)]*\)\) return head/,
    'expected a clean PR to return the unchanged HEAD without rebasing',
  );
});

test('the merge-conflict pre-flight runs once before the round loop, ahead of the parallel bug-check lenses', () => {
  const preflightCall = convergeSource.indexOf('await resolveMergeConflicts(');
  const whileLoop = convergeSource.indexOf('while (iterations < CONFIG.maxIterations)');
  const firstLens = convergeSource.indexOf('const lenses = await parallel(');
  assert.notEqual(preflightCall, -1, 'expected the pre-flight resolveMergeConflicts call site');
  assert.ok(preflightCall < whileLoop, 'expected the pre-flight to run before the round loop');
  assert.ok(preflightCall < firstLens, 'expected the pre-flight to run before the first bug-check lenses');
});
