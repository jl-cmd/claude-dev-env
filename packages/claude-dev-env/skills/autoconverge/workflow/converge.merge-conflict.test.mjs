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

test('checkMergeConflicts is a read-only mergeability probe that polls until GitHub computes it', () => {
  const body = functionBody('checkMergeConflicts');
  assert.match(body, /mergeable/, 'expected the probe to read the PR mergeable field');
  assert.match(
    body,
    /do not edit, commit, push, or rebase|read only/i,
    'expected the probe to be read-only',
  );
  assert.match(body, /agentType:\s*'Explore'/, 'expected the probe to use the read-only Explore agent');
  assert.match(body, /schema:\s*MERGE_CONFLICT_SCHEMA/, 'expected the probe to return MERGE_CONFLICT_SCHEMA');
  assert.match(body, /null/, 'expected the probe to handle GitHub returning mergeable:null while it computes');
  assert.match(body, /sleep 5|Start-Sleep/, 'expected a shell-agnostic poll delay');
});

test('resolveConflictsEdit rebases onto origin/main and makes no push', () => {
  const body = functionBody('resolveConflictsEdit');
  assert.match(body, /git rebase origin\/main/, 'expected the edit step to rebase onto origin/main');
  assert.match(
    body,
    /do not push|no push|not push/i,
    'expected the edit step to leave the push to the commit step',
  );
  assert.match(body, /agentType:\s*'clean-coder'/, 'expected the edit step to use clean-coder');
});

test('resolveMergeConflicts runs check -> edit -> verify -> commit and gates the push on the verdict', () => {
  const body = functionBody('resolveMergeConflicts');
  const checkIndex = body.indexOf('checkMergeConflicts(');
  const editIndex = body.indexOf('resolveConflictsEdit(');
  const verifyIndex = body.indexOf('verifyRepairChanges(');
  const commitIndex = body.indexOf('commitRepairFixes(');
  assert.notEqual(checkIndex, -1, 'expected the conflict check to run');
  assert.notEqual(editIndex, -1, 'expected the rebase edit step to run');
  assert.notEqual(verifyIndex, -1, 'expected the verify step to run');
  assert.notEqual(commitIndex, -1, 'expected the commit step to run');
  assert.ok(
    checkIndex < editIndex && editIndex < verifyIndex && verifyIndex < commitIndex,
    'expected the order check -> edit -> verify -> commit',
  );
  assert.match(body, /verdictPassed\(/, 'expected the verifier verdict to gate the force-push');
  assert.match(
    body,
    /commitRepairFixes\(head,\s*true\)/,
    'expected the commit to force-with-lease (wasRebased=true) after a rebase',
  );
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
