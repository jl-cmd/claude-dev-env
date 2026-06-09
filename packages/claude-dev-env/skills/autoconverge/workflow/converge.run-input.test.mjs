import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const workflowDirectory = dirname(fileURLToPath(import.meta.url));
const convergeSource = readFileSync(join(workflowDirectory, 'converge.mjs'), 'utf8');

function sourceSliceBetween(startNeedle, endNeedle) {
  const sliceStart = convergeSource.indexOf(startNeedle);
  assert.notEqual(sliceStart, -1, `expected ${startNeedle} to exist`);
  const sliceEnd = convergeSource.indexOf(endNeedle, sliceStart + startNeedle.length);
  assert.notEqual(sliceEnd, -1, `expected ${endNeedle} to exist after ${startNeedle}`);
  return convergeSource.slice(sliceStart, sliceEnd);
}

const productionModule = new Function(
  `${sourceSliceBetween('function normalizeRunInput(', '\nconst runInput =')}\n` +
    'return { normalizeRunInput, classifyRunInput };',
)();

const { normalizeRunInput, classifyRunInput } = productionModule;

const VALID_COORDINATES = { owner: 'jl-cmd', repo: 'claude-code-config', prNumber: 543 };

test('an object payload passes through unchanged', () => {
  assert.deepEqual(normalizeRunInput(VALID_COORDINATES), VALID_COORDINATES);
});

test('a JSON-encoded string payload is parsed into coordinates', () => {
  assert.deepEqual(normalizeRunInput(JSON.stringify(VALID_COORDINATES)), VALID_COORDINATES);
});

test('a non-JSON string returns null rather than throwing', () => {
  assert.equal(normalizeRunInput('not json at all'), null);
});

test('an empty string returns null rather than throwing', () => {
  assert.equal(normalizeRunInput(''), null);
});

test('classifyRunInput accepts coordinates carrying owner, repo, and prNumber', () => {
  const classified = classifyRunInput(VALID_COORDINATES);
  assert.deepEqual(classified.input, VALID_COORDINATES);
  assert.equal(classified.blocker, null);
});

test('classifyRunInput blocks a failed parse with a structured blocker and no input', () => {
  const classified = classifyRunInput('not json at all');
  assert.equal(classified.input, null);
  assert.match(classified.blocker, /coordinates/i);
});

test('classifyRunInput blocks a null payload with a structured blocker', () => {
  const classified = classifyRunInput(null);
  assert.equal(classified.input, null);
  assert.match(classified.blocker, /coordinates/i);
});

test('classifyRunInput blocks a payload missing owner', () => {
  const classified = classifyRunInput({ repo: 'claude-code-config', prNumber: 543 });
  assert.equal(classified.input, null);
  assert.match(classified.blocker, /coordinates/i);
});

test('classifyRunInput blocks a payload missing prNumber', () => {
  const classified = classifyRunInput({ owner: 'jl-cmd', repo: 'claude-code-config' });
  assert.equal(classified.input, null);
  assert.match(classified.blocker, /coordinates/i);
});

test('the top-level run guards an unusable input into a structured blocker before reading input.owner', () => {
  const guardBlock = convergeSource.slice(
    convergeSource.indexOf('const runInput = classifyRunInput('),
    convergeSource.indexOf('const prCoordinates ='),
  );
  assert.match(guardBlock, /runInput\.blocker/);
  assert.match(guardBlock, /converged: false/);
  assert.match(guardBlock, /return/);
});
