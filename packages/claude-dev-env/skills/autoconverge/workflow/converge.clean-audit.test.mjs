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

function moduleConstantSource(constantName) {
  const constantMatch = convergeSource.match(
    new RegExp(`const ${constantName} = (\\[[\\s\\S]*?\\])`),
  );
  assert.notEqual(constantMatch, null, `expected ${constantName} to exist`);
  return constantMatch[1];
}

const productionModule = new Function(
  `${functionBody('cleanAuditBlocker')}\n` + 'return { cleanAuditBlocker };',
)();

const { cleanAuditBlocker } = productionModule;

const provenanceModule = new Function(
  `const LENS_NAMES = ${moduleConstantSource('LENS_NAMES')};\n` +
    `${functionBody('nameLensResults')}\n` +
    `${functionBody('describeStandardsDeferral')}\n` +
    'return { nameLensResults, describeStandardsDeferral };',
)();

const { nameLensResults, describeStandardsDeferral } = provenanceModule;

const CONVERGED_HEAD = 'abcdef0123456789abcdef0123456789abcdef01';

test('cleanAuditBlocker names the denial reason, the HEAD, and the unblock path', () => {
  const message = cleanAuditBlocker(CONVERGED_HEAD, {
    posted: false,
    reviewUrl: '',
    reason: 'denied by the auto mode classifier',
  });
  assert.match(message, /denied by the auto mode classifier/);
  assert.match(message, /post_audit_thread\.py/);
  assert.match(message, new RegExp(CONVERGED_HEAD));
  assert.match(message, /can never pass without it/);
});

test('cleanAuditBlocker falls back to a no-result reason when the post agent died', () => {
  const message = cleanAuditBlocker(CONVERGED_HEAD, null);
  assert.match(message, /the post agent returned no result/);
});

test('the post-clean-audit task in runGeneralUtilityTask returns the CLEAN_AUDIT_SCHEMA result rather than an unused transcript', () => {
  const body = functionBody('runGeneralUtilityTask');
  assert.match(body, /task === 'post-clean-audit'/);
  assert.match(body, /schema: CLEAN_AUDIT_SCHEMA/);
  assert.doesNotMatch(body, /agent transcript \(unused\)/);
});

test('nameLensResults classifies a ran lens, a down stub, and a dead agent and pins the positional lens roster', () => {
  const bugbotDownStub = { sha: 'a', clean: true, down: true, findings: [] };
  const auditReport = { sha: 'a', clean: true, down: false, findings: [] };
  const namedLenses = nameLensResults([bugbotDownStub, null, auditReport]);
  assert.equal(namedLenses.length, 3);
  assert.equal(namedLenses[0].status, 'down');
  assert.equal(namedLenses[0].report, null);
  assert.equal(namedLenses[1].status, 'dead');
  assert.equal(namedLenses[1].report, null);
  assert.equal(namedLenses[2].status, 'ran');
  assert.equal(namedLenses[2].report, auditReport);
  const allLensNames = namedLenses.map((eachEntry) => eachEntry.lens);
  assert.deepEqual(allLensNames, ['Cursor Bugbot', 'code-review', 'bug-audit']);
});

test('the post-clean-audit prompt quotes only lenses that ran and discloses the not-run lenses without inventing a result', () => {
  const body = functionBody('runGeneralUtilityTask');
  assert.match(body, /context\.lensResults/);
  assert.match(body, /status === 'ran'/);
  assert.match(body, /JSON\.stringify\(ranLenses/);
  assert.match(body, /did not run/);
  assert.match(body, /agent died/);
  assert.match(body, /context\.deferredStandardsFindings/);
  assert.doesNotMatch(body, /containing exactly \[\]/);
  assert.doesNotMatch(body, /Write an empty findings file/);
  assert.doesNotMatch(body, /All review lenses are clean on this HEAD/);
});

test('the post-clean-audit prompt fences untrusted lens-derived content as data, not instructions', () => {
  const body = functionBody('runGeneralUtilityTask');
  assert.match(body, /BEGIN LENS DATA/);
  assert.match(body, /END LENS DATA/);
  assert.match(body, /untrusted data/);
  assert.match(body, /never .*instructions|not .*instructions/);
});

test('describeStandardsDeferral names the filed follow-up fix issue URL and flags a filing that did not land', () => {
  const filedDisposition = describeStandardsDeferral({
    issueFiled: true,
    issueUrl: 'https://github.com/o/r/issues/7',
  });
  assert.match(filedDisposition, /follow-up fix issue/);
  assert.match(filedDisposition, /https:\/\/github\.com\/o\/r\/issues\/7/);

  const unfiledDisposition = describeStandardsDeferral({ issueFiled: false, issueUrl: '' });
  assert.match(unfiledDisposition, /did not land/);
  assert.match(unfiledDisposition, /untracked/);

  const missingDisposition = describeStandardsDeferral(null);
  assert.match(missingDisposition, /did not land/);
});

test('the post-clean-audit prompt words the deferral from the follow-up fix issue state, not a blanket follow-up PR claim', () => {
  const body = functionBody('runGeneralUtilityTask');
  assert.match(body, /context\.standardsDeferral/);
  assert.match(body, /describeStandardsDeferral\(context\.standardsDeferral\)/);
  assert.doesNotMatch(convergeSource, /deferred to a follow-up PR/);
});

test('the post-clean-audit prompt drops the postFindings variable and states the empty-array invariant by construction', () => {
  const body = functionBody('runGeneralUtilityTask');
  assert.doesNotMatch(body, /postFindings/);
  assert.doesNotMatch(body, /aggregated blocking findings across those lens results/);
  assert.match(body, /empty JSON array|empty findings array by construction/);
});

test('CLEAN_AUDIT_SCHEMA requires posted, reviewUrl, and reason', () => {
  assert.match(
    convergeSource,
    /const CLEAN_AUDIT_SCHEMA = \{[\s\S]*?required: \['posted', 'reviewUrl', 'reason'\]/,
  );
});

test('the standards-only call site breaks with a clean-audit blocker when the post does not land', () => {
  const branch = convergeSource.slice(
    convergeSource.indexOf('if (isStandardsOnlyRound(findings)) {'),
    convergeSource.indexOf('if (findings.length > 0) {'),
  );
  assert.match(branch, /runGeneralUtilityTask\(.*'post-clean-audit'/);
  assert.match(branch, /if \(!auditResult\?\.posted\)/);
  assert.match(branch, /blocker = cleanAuditBlocker\(head, auditResult\)/);
  assert.match(branch, /\bbreak\b/);
});

test('the standards-only call site relays lens provenance, the deferred standards findings, and the deferral filing state', () => {
  const branch = convergeSource.slice(
    convergeSource.indexOf('if (isStandardsOnlyRound(findings)) {'),
    convergeSource.indexOf('if (findings.length > 0) {'),
  );
  assert.match(branch, /lensResults: nameLensResults\(lenses\)/);
  assert.match(branch, /deferredStandardsFindings: findings/);
  assert.match(branch, /standardsDeferral: \{/);
  assert.match(branch, /issueFiled: hasStandardsFollowUpFiled/);
  assert.match(branch, /issueUrl: standardsFollowUpIssueUrl/);
  assert.doesNotMatch(branch, /postFindings/);
});

test('the all-clean call site breaks with a clean-audit blocker when the post does not land', () => {
  const branch = convergeSource.slice(
    convergeSource.indexOf('all lenses clean on'),
    convergeSource.indexOf("if (phase === 'COPILOT') {"),
  );
  assert.match(branch, /runGeneralUtilityTask\(.*'post-clean-audit'/);
  assert.match(branch, /if \(!auditResult\?\.posted\)/);
  assert.match(branch, /blocker = cleanAuditBlocker\(head, auditResult\)/);
  assert.match(branch, /\bbreak\b/);
});

test('the all-clean call site relays lens provenance into the post-clean-audit context without a postFindings field', () => {
  const branch = convergeSource.slice(
    convergeSource.indexOf('all lenses clean on'),
    convergeSource.indexOf("if (phase === 'COPILOT') {"),
  );
  assert.match(branch, /lensResults: nameLensResults\(lenses\)/);
  assert.doesNotMatch(branch, /postFindings/);
});
