import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const workflowDirectory = dirname(fileURLToPath(import.meta.url));
const multiSource = readFileSync(join(workflowDirectory, 'converge_multi.mjs'), 'utf8');

function sourceSliceBetween(startNeedle, endNeedle) {
  const sliceStart = multiSource.indexOf(startNeedle);
  assert.notEqual(sliceStart, -1, `expected ${startNeedle} to exist`);
  const sliceEnd = multiSource.indexOf(endNeedle, sliceStart + startNeedle.length);
  assert.notEqual(sliceEnd, -1, `expected ${endNeedle} to exist after ${startNeedle}`);
  return multiSource.slice(sliceStart, sliceEnd);
}

const productionModule = new Function(
  `${sourceSliceBetween('function normalizeMultiInput(', '\nconst multiInput =')}\n` +
    'return { normalizeMultiInput, isUsablePrEntry, classifyMultiInput };',
)();
const { normalizeMultiInput, classifyMultiInput } = productionModule;

const SCRIPT_PATH = '/abs/skills/autoconverge/workflow/converge.mjs';

function validEntry(prNumber) {
  return {
    owner: 'JonEcho',
    repo: 'python-automation',
    prNumber,
    repoPath: `/worktrees/pr-${prNumber}`,
  };
}

function validArgs() {
  return { convergeScriptPath: SCRIPT_PATH, prs: [validEntry(398), validEntry(402)] };
}

test('an object payload passes through unchanged', () => {
  const parsed = validArgs();
  assert.deepEqual(normalizeMultiInput(parsed), parsed);
});

test('a JSON-encoded string payload is parsed into coordinates', () => {
  assert.deepEqual(normalizeMultiInput(JSON.stringify(validArgs())), validArgs());
});

test('a non-JSON string returns null rather than throwing', () => {
  assert.equal(normalizeMultiInput('not json at all'), null);
});

test('valid coordinates classify with no blocker and keep every PR entry', () => {
  const classified = classifyMultiInput(validArgs());
  assert.equal(classified.blocker, null);
  assert.equal(classified.input.prs.length, 2);
});

test('a missing convergeScriptPath is blocked', () => {
  const classified = classifyMultiInput({ prs: [validEntry(398)] });
  assert.equal(classified.input, null);
  assert.match(classified.blocker, /convergeScriptPath/);
});

test('an empty prs array is blocked', () => {
  const classified = classifyMultiInput({ convergeScriptPath: SCRIPT_PATH, prs: [] });
  assert.equal(classified.input, null);
  assert.match(classified.blocker, /non-empty array/);
});

test('a missing prs list is blocked', () => {
  const classified = classifyMultiInput({ convergeScriptPath: SCRIPT_PATH });
  assert.equal(classified.input, null);
  assert.match(classified.blocker, /non-empty array/);
});

test('a non-array prs value is blocked', () => {
  const classified = classifyMultiInput({ convergeScriptPath: SCRIPT_PATH, prs: 'nope' });
  assert.equal(classified.input, null);
  assert.match(classified.blocker, /non-empty array/);
});

test('an entry missing prNumber is blocked', () => {
  const badEntry = { owner: 'JonEcho', repo: 'python-automation', repoPath: '/w/x' };
  const classified = classifyMultiInput({ convergeScriptPath: SCRIPT_PATH, prs: [badEntry] });
  assert.equal(classified.input, null);
  assert.match(classified.blocker, /missing/);
});

test('an entry missing repoPath is blocked', () => {
  const badEntry = { owner: 'JonEcho', repo: 'python-automation', prNumber: 398 };
  const classified = classifyMultiInput({ convergeScriptPath: SCRIPT_PATH, prs: [badEntry] });
  assert.equal(classified.input, null);
  assert.match(classified.blocker, /missing/);
});

test('a null payload is blocked', () => {
  const classified = classifyMultiInput('not json at all');
  assert.equal(classified.input, null);
  assert.match(classified.blocker, /did not parse/);
});
