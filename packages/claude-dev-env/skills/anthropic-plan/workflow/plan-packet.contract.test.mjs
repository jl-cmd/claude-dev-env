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

test('repair schema carries the recovery signal', () => {
  const repairSchemaBody = functionBody('repairSchema');
  assert.match(repairSchemaBody, /recovered/);
  assert.match(repairSchemaBody, /recoveryNote/);
});

test('workflow folds repair-path recovery into the top-level recovered signal', () => {
  const runBody = functionBody('runPlanPacketWorkflow');
  const repairCallMatch = /const\s+(\w+)\s*=\s*await repairPacket\(/.exec(runBody);
  assert.notEqual(repairCallMatch, null, 'expected the repair result to be captured');
  const repairResultName = repairCallMatch[1];
  const recordRecoveryMatch = new RegExp(`recordRecovery\\(${repairResultName}\\)`).exec(runBody);
  assert.notEqual(recordRecoveryMatch, null, 'expected the repair result to feed the recovery signal');
});

test('workflow error path returns the recovery keys', () => {
  const runBody = functionBody('runPlanPacketWorkflow');
  const catchIndex = runBody.indexOf('catch (');
  assert.notEqual(catchIndex, -1, 'expected a catch block');
  const catchBody = runBody.slice(catchIndex);
  assert.match(catchBody, /\brecovered\b/);
  assert.match(catchBody, /\brecoveryNote\b/);
});

test('workflow declares a reuse audit phase', () => {
  assert.match(workflowSource, /Reuse audit/);
  assert.match(workflowSource, /title:\s*'Reuse audit'/);
});

test('reuse audit runner uses a structured schema and the reuse audit phase', () => {
  const reuseAuditBody = functionBody('runReuseAudit');
  assert.match(reuseAuditBody, /schema:\s*reuseAuditSchema\(\)/);
  assert.match(reuseAuditBody, /phase:\s*'Reuse audit'/);
});

test('reuse audit schema gates on allJustified', () => {
  const reuseAuditSchemaBody = functionBody('reuseAuditSchema');
  assert.match(reuseAuditSchemaBody, /allJustified/);
  assert.match(reuseAuditSchemaBody, /findings/);
  assert.match(reuseAuditSchemaBody, /summary/);
});

test('reuse audit prompt searches shared_utils for existing equivalents', () => {
  const reuseAuditPromptBody = functionBody('reuseAuditPrompt');
  assert.match(reuseAuditPromptBody, /shared_utils/);
  assert.match(reuseAuditPromptBody, /reuse-audit\.md/);
  assert.match(reuseAuditPromptBody, /unjustified-reproduction/);
});

test('workflow runs the reuse audit after writing the packet', () => {
  const runBody = functionBody('runPlanPacketWorkflow');
  const writeIndex = runBody.indexOf('await writePacket');
  const reuseAuditIndex = runBody.indexOf('runReuseAudit');
  assert.ok(writeIndex !== -1 && reuseAuditIndex !== -1);
  assert.ok(writeIndex < reuseAuditIndex);
});

test('reuse audit prompt self-heals a blocked write by staging and copying into place', () => {
  const reuseAuditPromptBody = functionBody('reuseAuditPrompt');
  assert.match(reuseAuditPromptBody, /stag/i);
  assert.match(reuseAuditPromptBody, /copy/i);
  assert.match(reuseAuditPromptBody, /recover/i);
});

test('reuse audit schema carries the recovery signal', () => {
  const reuseAuditSchemaBody = functionBody('reuseAuditSchema');
  assert.match(reuseAuditSchemaBody, /recovered/);
  assert.match(reuseAuditSchemaBody, /recoveryNote/);
});

test('workflow folds reuse-audit recovery into the top-level recovered signal', () => {
  const runBody = functionBody('runPlanPacketWorkflow');
  assert.match(runBody, /recordRecovery\(reuseAudit\)/);
});

test('workflow folds the reuse audit gate into the clean validation check', () => {
  const runBody = functionBody('runPlanPacketWorkflow');
  assert.match(runBody, /reuseAudit\.allJustified/);
  assert.match(runBody, /reuseAuditFindings/);
});

test('workflow declares a visualize phase', () => {
  assert.match(workflowSource, /title:\s*'Visualize'/);
});

test('workflow runs the visualize phase after validation', () => {
  const runBody = functionBody('runPlanPacketWorkflow');
  const visualHtmlIndex = runBody.indexOf('runVisualHtml(packetPath)');
  const validationLoopIndex = runBody.indexOf('while (!hasCleanValidation(');
  assert.ok(visualHtmlIndex !== -1 && validationLoopIndex !== -1);
  assert.ok(visualHtmlIndex > validationLoopIndex);
});

test('visual html schema carries the html path', () => {
  const visualHtmlSchemaBody = functionBody('visualHtmlSchema');
  assert.match(visualHtmlSchemaBody, /htmlPath/);
});

test('visual html prompt names the template and the output file', () => {
  const visualHtmlPromptBody = functionBody('visualHtmlPrompt');
  assert.match(visualHtmlPromptBody, /visual-plan\.template\.html/);
  assert.match(visualHtmlPromptBody, /visual-plan\.html/);
});

test('visual html prompt self-heals a blocked write by staging and copying into place', () => {
  const visualHtmlPromptBody = functionBody('visualHtmlPrompt');
  assert.match(visualHtmlPromptBody, /stag/i);
  assert.match(visualHtmlPromptBody, /copy/i);
  assert.match(visualHtmlPromptBody, /recover/i);
});

test('visual html schema carries the recovery signal', () => {
  const visualHtmlSchemaBody = functionBody('visualHtmlSchema');
  assert.match(visualHtmlSchemaBody, /recovered/);
  assert.match(visualHtmlSchemaBody, /recoveryNote/);
});

test('workflow folds visual-html recovery into the top-level recovered signal', () => {
  const runBody = functionBody('runPlanPacketWorkflow');
  assert.match(runBody, /recordRecovery\(visualHtml\)/);
});

test('workflow returns the visual html path', () => {
  const runBody = functionBody('runPlanPacketWorkflow');
  assert.match(runBody, /visualHtmlPath/);
});
