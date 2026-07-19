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

const productionModule = new Function(
  `const SHA_COMPARISON_PREFIX_LENGTH = 7;\n` +
    `${functionBody('normalizeShaForComparison')}\n` +
    `${functionBody('isP2OnlyFindings')}\n` +
    `${functionBody('nextPhaseAfterP2OnlyFix')}\n` +
    `${functionBody('routeAfterP2OnlyFix')}\n` +
    'return { isP2OnlyFindings, nextPhaseAfterP2OnlyFix, routeAfterP2OnlyFix };',
)();

const { isP2OnlyFindings, nextPhaseAfterP2OnlyFix, routeAfterP2OnlyFix } = productionModule;

function finding(overrides) {
  return {
    file: 'a.py',
    line: 1,
    severity: 'P2',
    category: 'bug',
    title: 't',
    detail: 'd',
    replyToCommentId: null,
    ...overrides,
  };
}

function phaseBranch(phaseMarker) {
  const phaseStart = convergeSource.indexOf(phaseMarker);
  assert.notEqual(phaseStart, -1, `expected ${phaseMarker} to exist`);
  const nextPhaseStart = convergeSource.indexOf('\n  if (phase === ', phaseStart + 1);
  const phaseEnd = nextPhaseStart === -1 ? convergeSource.length : nextPhaseStart;
  return convergeSource.slice(phaseStart, phaseEnd);
}

test('isP2OnlyFindings is false for an empty findings list', () => {
  assert.equal(isP2OnlyFindings([]), false);
});

test('isP2OnlyFindings is true when every finding is severity P2', () => {
  assert.equal(isP2OnlyFindings([finding(), finding({ file: 'b.py', line: 2 })]), true);
});

test('isP2OnlyFindings is false when a P1 is mixed in with P2 findings', () => {
  assert.equal(isP2OnlyFindings([finding(), finding({ severity: 'P1' })]), false);
});

test('isP2OnlyFindings is false when every finding is severity P1', () => {
  assert.equal(isP2OnlyFindings([finding({ severity: 'P1' })]), false);
});

test('isP2OnlyFindings is false when a finding is missing severity', () => {
  assert.equal(isP2OnlyFindings([{ file: 'a.py', line: 1, category: 'bug' }]), false);
});

test('nextPhaseAfterP2OnlyFix advances CONVERGE to BUGBOT', () => {
  assert.equal(nextPhaseAfterP2OnlyFix('CONVERGE'), 'BUGBOT');
});

test('nextPhaseAfterP2OnlyFix advances BUGBOT to COPILOT', () => {
  assert.equal(nextPhaseAfterP2OnlyFix('BUGBOT'), 'COPILOT');
});

test('nextPhaseAfterP2OnlyFix advances COPILOT to CODEX', () => {
  assert.equal(nextPhaseAfterP2OnlyFix('COPILOT'), 'CODEX');
});

test('nextPhaseAfterP2OnlyFix advances CODEX to FINALIZE', () => {
  assert.equal(nextPhaseAfterP2OnlyFix('CODEX'), 'FINALIZE');
});

test('routeAfterP2OnlyFix re-converges when the fix moved HEAD', () => {
  const route = routeAfterP2OnlyFix('aaa111', { newSha: 'bbb222' }, 'COPILOT');
  assert.equal(route.didMoveHead, true);
  assert.equal(route.fixedHead, 'bbb222');
  assert.equal(route.nextPhase, 'CONVERGE');
});

test('routeAfterP2OnlyFix advances when HEAD is unchanged', () => {
  const route = routeAfterP2OnlyFix('aaa111', { newSha: 'aaa111' }, 'COPILOT');
  assert.equal(route.didMoveHead, false);
  assert.equal(route.fixedHead, 'aaa111');
  assert.equal(route.nextPhase, 'COPILOT');
});

test('nextPhaseAfterP2OnlyFix uses an in-function lookup map', () => {
  const body = functionBody('nextPhaseAfterP2OnlyFix');
  assert.match(body, /nextPhaseByCurrent/);
  assert.match(body, /CONVERGE:\s*'BUGBOT'/);
  assert.match(body, /BUGBOT:\s*'COPILOT'/);
  assert.match(body, /COPILOT:\s*'CODEX'/);
});

test('applyP2OnlyFix runs applyFixes then detectFixProgress in order', () => {
  const body = functionBody('applyP2OnlyFix');
  const applyIndex = body.indexOf('applyFixes(head, findings, sourceLabel)');
  const detectIndex = body.indexOf('detectFixProgress(fixResult, head, hadThreadBearingFinding)');
  assert.notEqual(applyIndex, -1, 'expected applyFixes in applyP2OnlyFix');
  assert.notEqual(detectIndex, -1, 'expected detectFixProgress in applyP2OnlyFix');
  assert.ok(applyIndex < detectIndex, 'applyFixes must precede detectFixProgress');
  assert.match(body, /collectFindingThreadIds/);
});

test('CONVERGE places the P2-only branch between standards-only and generic fix', () => {
  const convergeBranch = phaseBranch("if (phase === 'CONVERGE')");
  const standardsIndex = convergeBranch.indexOf('isStandardsOnlyRound(findings)');
  const p2OnlyIndex = convergeBranch.indexOf('isP2OnlyFindings(findings)');
  const genericFixIndex = convergeBranch.indexOf("finding(s) — applying fixes");
  assert.notEqual(standardsIndex, -1, 'expected the standards-only branch');
  assert.notEqual(p2OnlyIndex, -1, 'expected the P2-only branch');
  assert.notEqual(genericFixIndex, -1, 'expected the generic fix branch');
  assert.ok(standardsIndex < p2OnlyIndex, 'standards-only must precede P2-only');
  assert.ok(p2OnlyIndex < genericFixIndex, 'P2-only must precede generic fix');
});

test('CONVERGE P2-only branch fixes once and routes via routeAfterP2OnlyFix', () => {
  const convergeBranch = phaseBranch("if (phase === 'CONVERGE')");
  const p2Start = convergeBranch.indexOf('isP2OnlyFindings(findings)');
  const genericFixStart = convergeBranch.indexOf("finding(s) — applying fixes");
  const p2Branch = convergeBranch.slice(p2Start, genericFixStart);
  assert.match(p2Branch, /P2-only/);
  assert.match(p2Branch, /applyP2OnlyFix\(head, findings, 'converge-round'/);
  assert.match(p2Branch, /routeAfterP2OnlyFix\(head, p2Fix, advancePhase\)/);
  assert.match(p2Branch, /nextPhaseAfterP2OnlyFix\('CONVERGE'\)/);
  assert.match(p2Branch, /head = p2Route\.fixedHead/);
  assert.match(p2Branch, /phase = p2Route\.nextPhase/);
  assert.doesNotMatch(p2Branch, /head = null/);
});

test('BUGBOT P2-only branch routes through routeAfterP2OnlyFix', () => {
  const bugbotBranch = phaseBranch("if (phase === 'BUGBOT')");
  const standardsIndex = bugbotBranch.indexOf('isStandardsOnlyRound(bugbotOutcome.findings)');
  const p2OnlyIndex = bugbotBranch.indexOf('isP2OnlyFindings(bugbotOutcome.findings)');
  const genericFixIndex = bugbotBranch.indexOf('fixing and re-converging');
  assert.ok(standardsIndex < p2OnlyIndex, 'standards-only must precede P2-only on BUGBOT');
  assert.ok(p2OnlyIndex < genericFixIndex, 'P2-only must precede generic re-converge on BUGBOT');
  const p2Branch = bugbotBranch.slice(p2OnlyIndex, genericFixIndex);
  assert.match(p2Branch, /P2-only/);
  assert.match(p2Branch, /nextPhaseAfterP2OnlyFix\('BUGBOT'\)/);
  assert.match(p2Branch, /applyP2OnlyFix\(head, bugbotOutcome\.findings, 'bugbot'/);
  assert.match(p2Branch, /routeAfterP2OnlyFix\(head, p2Fix, advancePhase\)/);
  assert.match(p2Branch, /phase = p2Route\.nextPhase/);
});

test('COPILOT P2-only branch routes through routeAfterP2OnlyFix', () => {
  const copilotBranch = phaseBranch("if (phase === 'COPILOT')");
  const standardsIndex = copilotBranch.indexOf('isStandardsOnlyRound(roundFindings)');
  const p2OnlyIndex = copilotBranch.indexOf('isP2OnlyFindings(roundFindings)');
  const genericFixIndex = copilotBranch.indexOf('fixing and re-converging');
  assert.ok(standardsIndex < p2OnlyIndex, 'standards-only must precede P2-only on COPILOT');
  assert.ok(p2OnlyIndex < genericFixIndex, 'P2-only must precede generic re-converge on COPILOT');
  const p2Branch = copilotBranch.slice(p2OnlyIndex, genericFixIndex);
  assert.match(p2Branch, /P2-only/);
  assert.match(p2Branch, /nextPhaseAfterP2OnlyFix\('COPILOT'\)/);
  assert.match(p2Branch, /applyP2OnlyFix\(head, roundFindings, 'copilot'/);
  assert.match(p2Branch, /routeAfterP2OnlyFix\(head, p2Fix, advancePhase\)/);
  assert.match(p2Branch, /phase = p2Route\.nextPhase/);
});

test('CODEX P2-only branch routes through routeAfterP2OnlyFix and stamps codexCleanAt only when HEAD is stable', () => {
  const codexBranch = phaseBranch("if (phase === 'CODEX')");
  const standardsIndex = codexBranch.indexOf('isStandardsOnlyRound(codexOutcome.findings)');
  const p2OnlyIndex = codexBranch.indexOf('isP2OnlyFindings(codexOutcome.findings)');
  const genericFixIndex = codexBranch.indexOf('fixing and re-converging');
  assert.ok(standardsIndex < p2OnlyIndex, 'standards-only must precede P2-only on CODEX');
  assert.ok(p2OnlyIndex < genericFixIndex, 'P2-only must precede generic re-converge on CODEX');
  const p2Branch = codexBranch.slice(p2OnlyIndex, genericFixIndex);
  assert.match(p2Branch, /P2-only/);
  assert.match(p2Branch, /nextPhaseAfterP2OnlyFix\('CODEX'\)/);
  assert.match(p2Branch, /applyP2OnlyFix\(head, codexOutcome\.findings, 'codex'/);
  assert.match(p2Branch, /routeAfterP2OnlyFix\(head, p2Fix, advancePhase\)/);
  assert.match(p2Branch, /codexCleanAt = head/);
  assert.match(p2Branch, /didMoveHead/);
});

test('generic fix branches still re-converge for mixed or P0/P1 findings', () => {
  const bugbotBranch = phaseBranch("if (phase === 'BUGBOT')");
  const genericStart = bugbotBranch.indexOf('fixing and re-converging');
  const genericBranch = bugbotBranch.slice(genericStart);
  assert.match(genericBranch, /phase = 'CONVERGE'/);
  assert.match(genericBranch, /head = null/);

  const copilotBranch = phaseBranch("if (phase === 'COPILOT')");
  const copilotGenericStart = copilotBranch.indexOf('fixing and re-converging');
  const copilotGeneric = copilotBranch.slice(copilotGenericStart);
  assert.match(copilotGeneric, /phase = 'CONVERGE'/);
  assert.match(copilotGeneric, /head = null/);
});
