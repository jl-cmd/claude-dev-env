import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const workflowDirectory = dirname(fileURLToPath(import.meta.url));
const convergeSource = readFileSync(join(workflowDirectory, 'converge.mjs'), 'utf8');

function sliceBetween(startNeedle, endNeedle) {
  const sliceStart = convergeSource.indexOf(startNeedle);
  assert.notEqual(sliceStart, -1, `expected ${startNeedle} to exist`);
  const sliceEnd = convergeSource.indexOf(endNeedle, sliceStart + startNeedle.length);
  assert.notEqual(sliceEnd, -1, `expected ${endNeedle} to exist after ${startNeedle}`);
  return convergeSource.slice(sliceStart, sliceEnd);
}

const productionModule = new Function(
  `${sliceBetween('const worktreeDirective =', '\nconst convergeAgent =')}\n` +
    'return { worktreeDirective };',
)();
const { worktreeDirective } = productionModule;

test('a single-PR run (no repoPath) produces an empty worktree directive', () => {
  assert.equal(worktreeDirective(null), '');
});

test('a path-scoped run pins every agent to the PR worktree by absolute path', () => {
  const directive = worktreeDirective('/worktrees/pr-398');
  assert.match(directive, /\/worktrees\/pr-398/);
  assert.match(directive, /cd /);
  assert.match(directive, /git, gh, diff, edit, commit, push, and test/);
});

test('a path-scoped run defers to a step that names a different repository directory', () => {
  assert.match(worktreeDirective('/worktrees/pr-398'), /different repository directory/i);
});

test('convergeAgent prepends the worktree directive for the active repo path', () => {
  const agentDefinition = sliceBetween('const convergeAgent =', '\nconst PRE_COMMIT_GATE_STEP');
  assert.match(agentDefinition, /worktreeDirective\(activeRepoPath\)/);
  assert.match(agentDefinition, /HEADLESS_SAFETY_PREAMBLE/);
});

test('the run binds activeRepoPath from input.repoPath after the input is parsed', () => {
  assert.match(convergeSource, /activeRepoPath = typeof input\.repoPath === 'string'/);
});
