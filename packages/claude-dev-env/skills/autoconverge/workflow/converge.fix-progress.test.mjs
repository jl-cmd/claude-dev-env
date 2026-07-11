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

function constantLine(constantName) {
  const constantSource = readFileSync(join(workflowDirectory, 'converge.mjs'), 'utf8');
  const matchedLine = constantSource
    .split('\n')
    .find((eachLine) => eachLine.trimStart().startsWith(`const ${constantName} =`));
  assert.ok(matchedLine, `expected ${constantName} to be declared`);
  return matchedLine;
}

const productionModule = new Function(
  `${constantLine('SHA_COMPARISON_PREFIX_LENGTH')}\n` +
    `${functionBody('normalizeShaForComparison')}\n` +
    `${functionBody('collectFindingThreadIds')}\n` +
    `${functionBody('detectFixProgress')}\n` +
    'return { detectFixProgress, collectFindingThreadIds };',
)();

const { detectFixProgress, collectFindingThreadIds } = productionModule;

const PRIOR_HEAD = 'abcdef0123456789abcdef0123456789abcdef01';
const MOVED_HEAD = 'fedcba9876543210fedcba9876543210fedcba98';

function nullThreadFinding() {
  return { file: 'converge.mjs', line: 278, severity: 'P2', title: 'stale', detail: 'x', replyToCommentId: null };
}

function threadBearingFinding() {
  return { file: 'converge.mjs', line: 278, severity: 'P2', title: 'stale', detail: 'x', replyToCommentId: 4242 };
}

test('a resolvedWithoutCommit round whose findings carry no thread id does not count as progress', () => {
  const allNullThreadFindings = [nullThreadFinding(), nullThreadFinding()];
  const hadThreadBearingFinding = allNullThreadFindings.some(
    (eachFinding) => collectFindingThreadIds(eachFinding).length > 0,
  );
  const fixProgress = detectFixProgress(
    { newSha: PRIOR_HEAD, pushed: false, resolvedWithoutCommit: true, summary: 'judged stale' },
    PRIOR_HEAD,
    hadThreadBearingFinding,
  );
  assert.equal(fixProgress.progressed, false);
});

test('a resolvedWithoutCommit round with at least one thread-bearing finding still counts as progress', () => {
  const mixedFindings = [nullThreadFinding(), threadBearingFinding()];
  const hadThreadBearingFinding = mixedFindings.some(
    (eachFinding) => collectFindingThreadIds(eachFinding).length > 0,
  );
  const fixProgress = detectFixProgress(
    { newSha: PRIOR_HEAD, pushed: false, resolvedWithoutCommit: true, summary: 'resolved threads' },
    PRIOR_HEAD,
    hadThreadBearingFinding,
  );
  assert.equal(fixProgress.progressed, true);
  assert.equal(fixProgress.newSha, PRIOR_HEAD);
});

test('a pushed fix that moved HEAD still progresses regardless of thread-bearing findings', () => {
  const fixProgress = detectFixProgress(
    { newSha: MOVED_HEAD, pushed: true, resolvedWithoutCommit: false, summary: 'committed' },
    PRIOR_HEAD,
    false,
  );
  assert.equal(fixProgress.progressed, true);
  assert.equal(fixProgress.newSha, MOVED_HEAD);
});

test('a dead fix agent never progresses', () => {
  const fixProgress = detectFixProgress(null, PRIOR_HEAD, true);
  assert.equal(fixProgress.progressed, false);
  assert.equal(fixProgress.newSha, PRIOR_HEAD);
});

test('the converge call site sets a fix-stalled blocker when an all-null-thread resolvedWithoutCommit round cannot progress', () => {
  const convergeBranch = convergeSource.slice(
    convergeSource.indexOf("const fixResult = await applyFixes(head, findings, 'converge-round')"),
    convergeSource.indexOf("if (!roundOutcome.roundClean)"),
  );
  assert.match(convergeBranch, /collectFindingThreadIds/);
  assert.match(convergeBranch, /fix stalled/i);
});

test('the copilot call site sets a fix-stalled blocker when an all-null-thread resolvedWithoutCommit round cannot progress', () => {
  const copilotBranch = convergeSource.slice(
    convergeSource.indexOf("const fixResult = await applyFixes(head, copilotOutcome.findings, 'copilot')"),
    convergeSource.indexOf("phase = 'CONVERGE'\n      continue\n    }\n    phase = 'FINALIZE'"),
  );
  assert.match(copilotBranch, /collectFindingThreadIds/);
  assert.match(copilotBranch, /fix stalled/i);
});
