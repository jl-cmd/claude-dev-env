import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const workflowDirectory = dirname(fileURLToPath(import.meta.url));
const convergeSource = readFileSync(join(workflowDirectory, 'converge.mjs'), 'utf8');
const skillSource = readFileSync(join(workflowDirectory, '..', 'SKILL.md'), 'utf8');
const stopConditionsSource = readFileSync(
  join(workflowDirectory, '..', 'reference', 'stop-conditions.md'),
  'utf8',
);

function functionBody(functionName) {
  const functionStart = convergeSource.indexOf(`function ${functionName}(`);
  assert.notEqual(functionStart, -1, `expected ${functionName} to exist`);
  const nextFunctionStart = convergeSource.indexOf('\nfunction ', functionStart + 1);
  const functionEnd = nextFunctionStart === -1 ? convergeSource.length : nextFunctionStart;
  return convergeSource.slice(functionStart, functionEnd);
}

const productionModule = new Function(
  `${functionBody('classifyCodexGateOutcome')}\n` +
    'return { classifyCodexGateOutcome };',
)();
const { classifyCodexGateOutcome } = productionModule;

function codexResult(overrides) {
  return {
    sha: 'abcdef0',
    clean: false,
    down: false,
    skipped: false,
    skipReason: '',
    findings: [],
    ...overrides,
  };
}

function codexFinding(overrides) {
  return {
    file: 'a.py',
    line: 1,
    severity: 'P1',
    category: 'bug',
    title: 't',
    detail: 'd',
    replyToCommentId: null,
    ...overrides,
  };
}

test('a required clean Codex result routes to clean so the run stamps codex-clean HEAD', () => {
  const outcome = classifyCodexGateOutcome(codexResult({ clean: true }));
  assert.equal(outcome.kind, 'clean');
});

test('an opt-out token skip routes to skip-token', () => {
  const outcome = classifyCodexGateOutcome(
    codexResult({ clean: true, down: true, skipped: true, skipReason: 'token' }),
  );
  assert.equal(outcome.kind, 'skip-token');
});

test('a usage-threshold skip routes to skip-usage', () => {
  const outcome = classifyCodexGateOutcome(
    codexResult({ clean: true, down: false, skipped: true, skipReason: 'usage' }),
  );
  assert.equal(outcome.kind, 'skip-usage');
});

test('a codex_down result routes to down', () => {
  const outcome = classifyCodexGateOutcome(codexResult({ clean: false, down: true }));
  assert.equal(outcome.kind, 'down');
});

test('Codex findings route to a fix when the review completed with findings', () => {
  const outcome = classifyCodexGateOutcome(
    codexResult({
      findings: [codexFinding()],
    }),
  );
  assert.equal(outcome.kind, 'fix');
  assert.equal(outcome.findings.length, 1);
});

test('a dead Codex gate agent retries rather than passing', () => {
  assert.equal(classifyCodexGateOutcome(null).kind, 'retry');
});

test('a reachable Codex gate with no findings and no clean verdict retries', () => {
  const outcome = classifyCodexGateOutcome(codexResult({ clean: false, down: false }));
  assert.equal(outcome.kind, 'retry');
});

test('skipped with an unknown skipReason retries rather than silently advancing', () => {
  const outcome = classifyCodexGateOutcome(
    codexResult({ skipped: true, skipReason: 'mystery' }),
  );
  assert.equal(outcome.kind, 'retry');
});

test('CODEX_SCHEMA requires skipped and skipReason drawn from the skip-reason constant', () => {
  const schemaStart = convergeSource.indexOf('const CODEX_SCHEMA =');
  const schemaEnd = convergeSource.indexOf('const COPILOT_VERIFY_VERDICTS =');
  assert.notEqual(schemaStart, -1, 'expected CODEX_SCHEMA to exist');
  const schemaSource = convergeSource.slice(schemaStart, schemaEnd);
  assert.match(schemaSource, /skipped:\s*\{\s*type:\s*'boolean'/);
  assert.match(schemaSource, /enum:\s*CODEX_SKIP_REASONS/);
  assert.match(schemaSource, /required:\s*\[[^\]]*'skipped'[^\]]*\]/);
  assert.match(schemaSource, /required:\s*\[[^\]]*'skipReason'[^\]]*\]/);
});

test('the Codex gate prompt honors reviews_disabled.py with only --reviewer codex', () => {
  const codexPrompt = functionBody('runCodexGate');
  const reviewsDisabledIndex = codexPrompt.indexOf('reviews_disabled.py');
  assert.notEqual(reviewsDisabledIndex, -1, 'expected reviews_disabled.py invocation');
  const invocationLineEnd = codexPrompt.indexOf('\\n', reviewsDisabledIndex);
  const invocationLine = codexPrompt.slice(reviewsDisabledIndex, invocationLineEnd);
  assert.match(invocationLine, /--reviewer codex/);
  assert.doesNotMatch(invocationLine, /--owner|--repo/);
});

test('the Codex gate prompt decides required vs skip only through is_codex_review_required', () => {
  const codexPrompt = functionBody('runCodexGate');
  assert.match(codexPrompt, /codex_usage_probe\.py/, 'expected the usage probe CLI');
  assert.match(
    codexPrompt,
    /is_codex_review_required/,
    'expected the shared probe helper rather than an inline percent threshold',
  );
  assert.doesNotMatch(
    codexPrompt,
    /WEEKLY_USAGE_GATE_THRESHOLD_PERCENT|\b10\s*%|\bpercent_left\s*[><=]/,
    'expected no duplicate threshold literal or inline comparison in the gate prompt',
  );
});

test('the Codex gate prompt treats a non-zero usage-probe exit as codex_down not usage skip', () => {
  const codexPrompt = functionBody('runCodexGate');
  assert.match(
    codexPrompt,
    /Non-zero exit means the Codex CLI or probe is broken/,
    'expected an explicit non-zero probe exit branch',
  );
  assert.match(
    codexPrompt,
    /Never map a failed probe to skipReason:'usage'/,
    'expected failed probe to be barred from the usage-skip path',
  );
  assert.match(
    codexPrompt,
    /clean:false, down:true, skipped:false, skipReason:''/,
    'expected failed probe to return the codex_down schema shape',
  );
});

test('the Codex gate prompt sys.path insert uses CONFIG.codexScripts not a literal $HOME token', () => {
  const codexPrompt = functionBody('runCodexGate');
  assert.match(
    codexPrompt,
    /sys\.path\.insert\(0, r'\$\{CONFIG\.codexScripts\}'\)/,
    'expected sys.path.insert to interpolate CONFIG.codexScripts (home-expanded at CONFIG build)',
  );
  assert.doesNotMatch(
    codexPrompt,
    /sys\.path\.insert\(0, r'\$HOME/,
    'expected no unexpanded $HOME inside the Python raw-string path',
  );
});

test('the Codex gate prompt runs the review wrapper against the PR base branch', () => {
  const codexPrompt = functionBody('runCodexGate');
  assert.match(codexPrompt, /run_codex_review/, 'expected the codex-review wrapper');
  assert.match(codexPrompt, /base_branch/, 'expected the wrapper to receive the PR base');
  assert.match(codexPrompt, /\.base\.ref/, 'expected the agent to resolve the PR base ref');
  assert.match(codexPrompt, /parse_codex_findings/, 'expected findings to come from the shared parser');
});

test('the CODEX phase stamps codexCleanAt on clean and clears it on skip/down', () => {
  const codexPhaseStart = convergeSource.indexOf("if (phase === 'CODEX') {");
  const finalizePhaseStart = convergeSource.indexOf("if (phase === 'FINALIZE') {", codexPhaseStart);
  assert.notEqual(codexPhaseStart, -1, 'expected a CODEX phase block');
  assert.notEqual(finalizePhaseStart, -1, 'expected FINALIZE after CODEX');
  const codexPhase = convergeSource.slice(codexPhaseStart, finalizePhaseStart);
  assert.match(codexPhase, /await runCodexGate\(head\)/);
  assert.match(codexPhase, /classifyCodexGateOutcome\(codex\)/);
  assert.match(codexPhase, /codexCleanAt = head/, 'expected a clean pass to stamp the HEAD');
  assert.match(codexPhase, /skip-token[\s\S]*codexDown = true[\s\S]*codexCleanAt = null/);
  assert.match(codexPhase, /skip-usage[\s\S]*codexDown = false[\s\S]*codexCleanAt = null/);
  assert.match(codexPhase, /kind === 'down'[\s\S]*codexDown = true[\s\S]*codexCleanAt = null/);
});

test('the CODEX phase routes findings through applyFixes and re-enters CONVERGE', () => {
  const codexPhaseStart = convergeSource.indexOf("if (phase === 'CODEX') {");
  const finalizePhaseStart = convergeSource.indexOf("if (phase === 'FINALIZE') {", codexPhaseStart);
  const codexPhase = convergeSource.slice(codexPhaseStart, finalizePhaseStart);
  assert.match(codexPhase, /applyFixes\(head, codexOutcome\.findings, 'codex'\)/);
  assert.match(codexPhase, /phase = 'CONVERGE'/);
  assert.match(codexPhase, /head = null/);
});

test('the COPILOT phase advances to CODEX rather than FINALIZE on a clean or bypass path', () => {
  const copilotPhaseStart = convergeSource.indexOf("if (phase === 'COPILOT') {");
  const codexPhaseStart = convergeSource.indexOf("if (phase === 'CODEX') {", copilotPhaseStart);
  assert.notEqual(copilotPhaseStart, -1, 'expected a COPILOT phase block');
  assert.notEqual(codexPhaseStart, -1, 'expected a CODEX phase after COPILOT');
  const copilotPhase = convergeSource.slice(copilotPhaseStart, codexPhaseStart);
  assert.match(copilotPhase, /phase = 'CODEX'/);
  assert.doesNotMatch(copilotPhase, /phase = 'FINALIZE'/);
});

test('the merged FINALIZE check receives codexDown and codexCleanAt and passes matching flags', () => {
  const finalizeStart = convergeSource.indexOf("if (phase === 'FINALIZE') {");
  assert.notEqual(finalizeStart, -1, 'expected a FINALIZE phase block');
  const checkCall = convergeSource.indexOf('runConvergenceCheck(', finalizeStart);
  assert.notEqual(checkCall, -1, 'expected the FINALIZE phase to call runConvergenceCheck');
  const checkLine = convergeSource.slice(checkCall, convergeSource.indexOf('\n', checkCall));
  assert.match(checkLine, /codexDown/);
  assert.match(checkLine, /codexCleanAt/);
  const checkBody = functionBody('runConvergenceCheck');
  assert.match(checkBody, /context\.codexDown \? ' --codex-down' : ''/);
  assert.match(checkBody, /context\.codexCleanAt \? ` --codex-clean-at \$\{context\.codexCleanAt\}` : ''/);
  assert.match(checkBody, /if \(context\.codexDown\) reviewerOptOutTokens\.push\('codex'\)/);
});

test('runConvergenceCheck tells the finalize agent to persist codex_clean_at for the flagless mark-ready re-check', () => {
  const checkBody = functionBody('runConvergenceCheck');
  assert.match(
    checkBody,
    /codexCleanAtNote/,
    'expected a dedicated note when the Codex gate stamped clean on HEAD',
  );
  assert.match(
    checkBody,
    /pr-converge-state\.json/,
    'expected the note to name the job-dir state file the mark-ready blocker re-reads',
  );
  assert.match(
    checkBody,
    /codex_clean_at/,
    'expected the note to write the codex_clean_at key the flagless re-check resolves',
  );
  assert.match(
    checkBody,
    /CLAUDE_JOB_DIR/,
    'expected the note to locate the state file under CLAUDE_JOB_DIR',
  );
  assert.match(
    checkBody,
    /needsCodexCleanExportFallback/,
    'expected a single-export fallback path when CLAUDE_JOB_DIR is unset',
  );
  assert.match(
    checkBody,
    /Emit exactly one export/,
    'expected the opt-out instruction to forbid a second overwriting export',
  );
  assert.doesNotMatch(
    checkBody,
    /export CLAUDE_REVIEWS_DISABLED="codex"/,
    'expected no second solo codex export that would overwrite other tokens',
  );
});

test('CONFIG expands home for the codex-review scripts directory', () => {
  assert.match(
    convergeSource,
    /const homeDirectory = \([\s\S]*?homeDirectoryPayload\.homeDirectory/,
    'expected home to be sourced from the workflow args payload (the sandbox exposes no process)',
  );
  assert.match(
    convergeSource,
    /codexScripts:\s*`\$\{homeDirectory\}\/\.claude\/skills\/codex-review\/scripts`/,
    'expected codexScripts to expand homeDirectory rather than embed $HOME',
  );
  assert.doesNotMatch(
    convergeSource,
    /codexScripts:\s*'\$HOME\//,
    'expected no literal $HOME token in codexScripts (Python raw strings do not expand it)',
  );
});

test('no process global is read unguarded (the workflow sandbox exposes no process)', () => {
  const unguardedProcessLines = convergeSource
    .split('\n')
    .filter((sourceLine) => sourceLine.includes('process.') && !sourceLine.includes('typeof process'));
  assert.deepEqual(
    unguardedProcessLines,
    [],
    'every process.* read must sit on a line guarded by typeof process; the Bun workflow sandbox has no process global',
  );
});

test('the home directory is sourced from the workflow args payload', () => {
  assert.match(
    convergeSource,
    /const homeDirectoryPayload = normalizeRunInput\(args\)/,
    'expected homeDirectory to read args (the only channel into the process-less sandbox), parsed via normalizeRunInput',
  );
});

test('meta lists the Codex gate phase between Copilot and Finalize', () => {
  const copilotPhaseIndex = convergeSource.indexOf("title: 'Copilot gate'");
  const codexPhaseIndex = convergeSource.indexOf("title: 'Codex gate'");
  const finalizePhaseIndex = convergeSource.indexOf("title: 'Finalize'");
  assert.notEqual(codexPhaseIndex, -1, 'expected a Codex gate phase in meta');
  assert.ok(copilotPhaseIndex < codexPhaseIndex && codexPhaseIndex < finalizePhaseIndex);
});

test('SKILL.md names Codex among the terminal confirmation gates', () => {
  assert.match(skillSource, /Codex/i);
});

test('stop-conditions.md documents the Codex gate skip paths as non-blockers', () => {
  assert.match(stopConditionsSource, /Codex/i);
  assert.match(stopConditionsSource, /codex/i);
});
