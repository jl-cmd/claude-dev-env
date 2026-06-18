import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const workflowDirectory = dirname(fileURLToPath(import.meta.url));
const workflowPath = join(workflowDirectory, 'plan-packet.mjs');
const workflowSource = existsSync(workflowPath) ? readFileSync(workflowPath, 'utf8') : '';

function functionBody(functionName) {
  const functionStart = workflowSource.indexOf(`function ${functionName}(`);
  assert.notEqual(functionStart, -1, `expected ${functionName} to exist`);
  const nextFunctionMatch = /\n(?:async )?function /.exec(workflowSource.slice(functionStart + 1));
  const functionEnd =
    nextFunctionMatch === null ? workflowSource.length : functionStart + 1 + nextFunctionMatch.index;
  return workflowSource.slice(functionStart, functionEnd);
}

test('workflow file exists and starts with meta export', () => {
  assert.ok(existsSync(workflowPath), 'expected workflow/plan-packet.mjs to exist');
  assert.match(workflowSource.trimStart(), /^export const meta = /);
  assert.doesNotMatch(workflowSource, /^import\s/m);
});

test('workflow declares packet creation, validation, and approval phases', () => {
  assert.match(workflowSource, /name:\s*'plan-packet'/);
  assert.match(workflowSource, /Discover/);
  assert.match(workflowSource, /Write packet/);
  assert.match(workflowSource, /Validate/);
  assert.match(workflowSource, /Approval/);
});

test('workflow requires the docs plans packet root', () => {
  const pathBuilder = functionBody('buildPacketPath');
  assert.match(pathBuilder, /docs/);
  assert.match(pathBuilder, /plans/);
  assert.doesNotMatch(pathBuilder, /\.claude\/plans/);
});

test('workflow writes the packet before spawning the validator', () => {
  const runBody = functionBody('runPlanPacketWorkflow');
  const writeIndex = runBody.indexOf('writePacket');
  const deterministicIndex = runBody.indexOf('runDeterministicValidation');
  const semanticIndex = runBody.indexOf('runSemanticValidator');
  assert.ok(writeIndex !== -1 && deterministicIndex !== -1 && semanticIndex !== -1);
  assert.ok(writeIndex < deterministicIndex);
  assert.ok(deterministicIndex < semanticIndex);
});

test('workflow repairs semantic findings and caps repair loops at three', () => {
  const runBody = functionBody('runPlanPacketWorkflow');
  assert.match(runBody, /maxRepairLoops:\s*3/);
  assert.match(runBody, /repairPacket/);
  assert.match(runBody, /semanticValidation\.allPassed/);
});

test('semantic validator uses a dedicated validator agent with structured schema', () => {
  const validatorBody = functionBody('runSemanticValidator');
  assert.match(validatorBody, /agentType:\s*'plan-packet-validator'/);
  assert.match(validatorBody, /schema:\s*validationSchema\(\)/);
  assert.match(validatorBody, /source-backed/);
  assert.match(validatorBody, /blind build agent/);
});

test('writer self-heals a blocked write by staging and copying into place', () => {
  const writerPrompt = functionBody('writePacketPrompt');
  assert.match(writerPrompt, /stage/i);
  assert.match(writerPrompt, /copy/i);
  assert.match(writerPrompt, /recover/i);
  assert.doesNotMatch(writerPrompt, /stop immediately/i);
});

test('packet write schema carries the recovery signal', () => {
  const writeSchema = functionBody('packetWriteSchema');
  assert.match(writeSchema, /recovered/);
});

test('workflow proceeds to validation without failing closed on a blocked write', () => {
  const runBody = functionBody('runPlanPacketWorkflow');
  const writeIndex = runBody.indexOf('await writePacket');
  const deterministicIndex = runBody.indexOf('runDeterministicValidation');
  assert.ok(writeIndex !== -1 && deterministicIndex !== -1);
  assert.ok(writeIndex < deterministicIndex);
  const betweenWriteAndValidation = runBody.slice(writeIndex, deterministicIndex);
  assert.doesNotMatch(betweenWriteAndValidation, /return/);
  assert.match(runBody, /recovered/);
});

test('workflow stops before implementation work', () => {
  const runBody = functionBody('runPlanPacketWorkflow');
  assert.match(runBody, /implementationStarted:\s*false/);
  assert.doesNotMatch(runBody, /clean-coder/);
  assert.doesNotMatch(runBody, /git commit/);
});

test('workflow fails closed when a phase errors', () => {
  const runBody = functionBody('runPlanPacketWorkflow');
  assert.match(runBody, /try\s*{/);
  assert.match(runBody, /catch\s*\(/);
  assert.match(runBody, /validationPassed:\s*false/);
  assert.match(runBody, /approvalRequired:\s*true/);
});
