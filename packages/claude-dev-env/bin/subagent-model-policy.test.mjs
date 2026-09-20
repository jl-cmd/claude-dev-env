import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import { cpSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
    defaultSubagentModelPolicyPath,
    loadSubagentModelPolicy,
    resolveSubagentModelRoute,
    routeSubagentToolInput,
    SubagentModelPolicyError,
    validateSubagentModelPolicy,
} from '../scripts/subagent_model_policy.mjs';

const PACKAGE_ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const POLICY_SOURCE = defaultSubagentModelPolicyPath();

function route(request, options = {}) {
    return resolveSubagentModelRoute(request, options);
}

function advisorRoute(request, options = {}) {
    return route(request, {
        trustedSessionMetadata: {
            authorized: true,
            registeredAgentType: 'team-advisor',
        },
        ...options,
    });
}

const replacements = [
    [['Luna', 'low'], ['gpt-5.6-luna', 'high']],
    [['Luna', 'medium'], ['gpt-5.6-luna', 'high']],
    [['Sol', 'low'], ['gpt-5.6-luna', 'xhigh']],
    [['Sol', 'medium'], ['gpt-5.6-luna', 'max']],
    [['Terra', 'low'], ['gpt-5.6-luna', 'xhigh']],
    [['Terra', 'medium'], ['gpt-5.6-luna', 'xhigh']],
    [['Terra', 'high'], ['gpt-5.6-luna', 'xhigh']],
    [['Terra', 'xhigh'], ['gpt-5.6-luna', 'max']],
    [['Sol', 'high'], ['gpt-6-astra', 'low']],
    [['Sol', 'xhigh'], ['gpt-6-astra', 'low']],
    [['Sol', 'max'], ['gpt-6-astra', 'low']],
    [['Terra', 'max'], ['gpt-6-astra', 'low']],
];

test('the shipped policy parses and names native model ids', () => {
    const policy = loadSubagentModelPolicy();
    assert.equal(policy.modelByName.astra.id, 'gpt-6-astra');
    assert.equal(policy.modelByName.sol.id, 'gpt-5.6-sol');
    assert.equal(policy.modelByName.terra.id, 'gpt-5.6-terra');
    assert.equal(policy.modelByName.luna.id, 'gpt-5.6-luna');
    assert.deepEqual(policy.advisorDefault, { model: 'astra', effort: 'medium' });
});

test('poteto plugin aliases use worker routing without advisor privileges', () => {
    for (const agent_type of ['poteto-agent', 'pstack:poteto-agent']) {
        const result = route({ agent_type, model: 'Astra', reasoning_effort: 'high' });
        assert.deepEqual(result.selected, { model: 'gpt-6-astra', effort: 'low' });
    }
});

test('every approved pair returns its literal native pair', () => {
    const expected = [
        [['Luna', 'high'], ['gpt-5.6-luna', 'high']],
        [['Luna', 'xhigh'], ['gpt-5.6-luna', 'xhigh']],
        [['Luna', 'max'], ['gpt-5.6-luna', 'max']],
        [['Astra', 'low'], ['gpt-6-astra', 'low']],
        [['Astra', 'medium'], ['gpt-6-astra', 'medium']],
    ];
    for (const [[model, effort], [expectedModel, expectedEffort]] of expected) {
        const result = route({ model, reasoning_effort: effort });
        assert.ok(['pass', 'remapped'].includes(result.status));
        assert.deepEqual(result.selected, { model: expectedModel, effort: expectedEffort });
        const nativeRoute = route({ model: expectedModel, reasoning_effort: expectedEffort });
        assert.equal(nativeRoute.status, 'pass');
        assert.deepEqual(nativeRoute.selected, { model: expectedModel, effort: expectedEffort });
    }
    const advisor = advisorRoute({
        model: 'Astra',
        reasoning_effort: 'high',
        agent_type: 'team-advisor',
    });
    assert.equal(advisor.status, 'remapped');
    assert.deepEqual(advisor.selected, { model: 'gpt-6-astra', effort: 'high' });
});

test('selector exclusions keep Sol Medium out while direct routing remaps', () => {
    const policy = loadSubagentModelPolicy();
    assert.equal(policy.selectorExclusions.has('sol/medium'), true);
    const result = route({ model: 'Sol', reasoning_effort: 'medium' });
    assert.equal(result.status, 'remapped');
    assert.deepEqual(result.selected, { model: 'gpt-5.6-luna', effort: 'max' });

    const rawPolicy = JSON.parse(readFileSync(POLICY_SOURCE, 'utf8'));
    rawPolicy.selectorExclusions = [{ model: 'missing', effort: 'medium' }];
    assert.throws(
        () => validateSubagentModelPolicy(rawPolicy),
        /selectorExclusions entry has unknown model/,
    );
});

test('every automatic replacement returns its literal destination', () => {
    for (const [[model, effort], [expectedModel, expectedEffort]] of replacements) {
        const result = route({ model, reasoning_effort: effort });
        assert.equal(result.status, 'remapped');
        assert.deepEqual(result.selected, { model: expectedModel, effort: expectedEffort });
    }
});

test('advisor and worker Astra restrictions use role-specific replacements', () => {
    assert.deepEqual(
        advisorRoute({ model: 'Astra', reasoning_effort: 'xhigh', agent_type: 'team-advisor' }).selected,
        { model: 'gpt-6-astra', effort: 'medium' },
    );
    assert.deepEqual(
        route({ model: 'Astra', reasoning_effort: 'max', agent_type: 'worker' }).selected,
        { model: 'gpt-6-astra', effort: 'low' },
    );
    assert.deepEqual(
        advisorRoute({ model: 'Astra', reasoning_effort: 'high', agent_type: 'team-advisor' }).selected,
        { model: 'gpt-6-astra', effort: 'high' },
    );
});

test('registered advisor roles satisfy advisory authorization', () => {
    const result = advisorRoute({
        model: 'Astra',
        reasoning_effort: 'high',
        agent_type: 'team-advisor',
    });

    assert.deepEqual(result.selected, { model: 'gpt-6-astra', effort: 'high' });
});

test('a policy from the first stack revision remains routable', () => {
    const legacyPolicy = JSON.parse(readFileSync(POLICY_SOURCE, 'utf8'));
    delete legacyPolicy.roles.trustedAdvisor;
    const result = advisorRoute(
        {
            model: 'Astra',
            reasoning_effort: 'high',
            agent_type: 'team-advisor',
        },
        { policy: legacyPolicy },
    );
    assert.deepEqual(result.selected, { model: 'gpt-6-astra', effort: 'high' });
});

test('an advisor role claim cannot grant advisory authorization', () => {
    const result = route({
        model: 'Astra',
        reasoning_effort: 'high',
        agent_type: 'team-advisor',
    });
    assert.equal(result.status, 'blocked');
    assert.equal(result.diagnostic, 'advisor role is not trusted');
});

test('Astra Light resolves to Astra Low', () => {
    const result = route({ model: 'Astra', reasoning_effort: 'Light' });
    assert.deepEqual(result.selected, { model: 'gpt-6-astra', effort: 'low' });
});

test('missing advisor settings use the policy default', () => {
    const result = advisorRoute({ agent_type: 'team-advisor' });
    assert.deepEqual(result.selected, { model: 'gpt-6-astra', effort: 'medium' });
});

test('the advisor bridge blocks malformed input', () => {
    const bridgePath = join(PACKAGE_ROOT, 'scripts', 'resolve_advisor_model_route.mjs');
    assert.throws(
        () => execFileSync(process.execPath, [bridgePath], { encoding: 'utf8', input: '{' }),
        error => {
            assert.equal(error.status, 1);
            assert.deepEqual(JSON.parse(error.stdout), {
                status: 'blocked',
                diagnostic: 'advisor route input is not valid JSON',
            });
            return true;
        },
    );
});

test('the advisor bridge routes Sol Medium to Luna Max', () => {
    const bridgePath = join(PACKAGE_ROOT, 'scripts', 'resolve_advisor_model_route.mjs');
    const bridgeExecution = spawnSync(
        process.execPath,
        [bridgePath],
        {
            encoding: 'utf8',
            input: JSON.stringify({ model: 'Sol', reasoning_effort: 'medium' }),
        },
    );
    assert.equal(bridgeExecution.status, 0);
    assert.equal(bridgeExecution.stderr, '');
    const advisorDecision = JSON.parse(bridgeExecution.stdout);
    assert.equal(advisorDecision.status, 'remapped');
    assert.equal(advisorDecision.role, 'advisor');
    assert.equal(advisorDecision.diagnostic, null);
    assert.deepEqual(advisorDecision.selected, { model: 'gpt-5.6-luna', effort: 'max' });
});

test('missing worker settings preserve parent inheritance', () => {
    const input = { message: 'keep', agent_type: 'worker' };
    const result = routeSubagentToolInput(input);
    assert.equal(result.status, 'inherited');
    assert.strictEqual(result.updatedInput, input);
});

test('Sol without an effort stays blocked after its only approved pair is removed', () => {
    const result = route(
        { model: 'Sol' },
        { allowMissingEffort: true },
    );
    assert.equal(result.status, 'blocked');
    assert.equal(result.diagnostic, 'effort is required for this model');
});

test('unknown input holds with a short diagnostic', () => {
    assert.match(route({ model: 'Unknown', reasoning_effort: 'medium' }).diagnostic, /model is unknown/);
    assert.match(route({ model: 'Terra', reasoning_effort: 'future' }).diagnostic, /effort is unknown/);
    assert.match(route({ model: 'Sol', reasoning_effort: 'medium', agent_type: 'unregistered' }).diagnostic, /role is unknown/);
});

test('dual effort fields hold instead of leaving one stale', () => {
    const result = route({ model: 'Luna', reasoning_effort: 'low', effort: 'low' });
    assert.equal(result.status, 'blocked');
    assert.match(result.diagnostic, /effort fields are ambiguous/);
});

test('native values with case or whitespace differences are canonicalized', () => {
    const result = routeSubagentToolInput({
        model: ' gpt-5.6-sol ',
        reasoning_effort: 'Medium',
        message: 'keep',
    });
    assert.equal(result.status, 'remapped');
    assert.deepEqual(result.updatedInput, {
        model: 'gpt-5.6-luna',
        reasoning_effort: 'max',
        message: 'keep',
    });
});

test('unavailable replacements hold the spawn', () => {
    const result = route(
        { model: 'Sol', reasoning_effort: 'medium' },
        { availableModelIds: ['gpt-5.6-sol'] },
    );
    assert.equal(result.status, 'blocked');
    assert.match(result.diagnostic, /replacement model is unavailable/);
});

test('the tool route copies every non-routing field', () => {
    const input = {
        assignment: 'preserve',
        message: 'do the work',
        child_permissions: { shell: 'ask' },
        output_contract: ['summary'],
        model: 'Terra',
        reasoning_effort: 'Medium',
    };
    const result = routeSubagentToolInput(input);
    assert.deepEqual(result.updatedInput, {
        assignment: 'preserve',
        message: 'do the work',
        child_permissions: { shell: 'ask' },
        output_contract: ['summary'],
        model: 'gpt-5.6-luna',
        reasoning_effort: 'xhigh',
    });
    assert.deepEqual(input, {
        assignment: 'preserve',
        message: 'do the work',
        child_permissions: { shell: 'ask' },
        output_contract: ['summary'],
        model: 'Terra',
        reasoning_effort: 'Medium',
    });
});

test('a second route pass is idempotent', () => {
    const first = routeSubagentToolInput(
        { model: 'Sol', reasoning_effort: 'medium', message: 'keep' },
        {},
    );
    const second = routeSubagentToolInput(first.updatedInput);
    assert.equal(first.status, 'remapped');
    assert.equal(second.status, 'pass');
    assert.deepEqual(second.updatedInput, first.updatedInput);
});

test('a temporary policy copy changes the next route without source edits', () => {
    const temporaryRoot = mkdtempSync(join(tmpdir(), 'subagent-policy-'));
    try {
        const temporaryPolicy = join(temporaryRoot, 'policy.json');
        const sourceText = readFileSync(POLICY_SOURCE, 'utf8');
        const policy = JSON.parse(sourceText);
        writeFileSync(temporaryPolicy, sourceText);
        assert.deepEqual(route(
            { model: 'Sol', reasoning_effort: 'medium' },
            { policyPath: temporaryPolicy },
        ).selected, { model: 'gpt-5.6-luna', effort: 'max' });
        policy.replacements = policy.replacements.map(replacement => (
            replacement.requested.model === 'sol' && replacement.requested.effort === 'medium'
                ? { ...replacement, selected: { model: 'luna', effort: 'xhigh' } }
                : replacement
        ));
        writeFileSync(temporaryPolicy, JSON.stringify(policy));
        const updatedRoute = route(
            { model: 'Sol', reasoning_effort: 'medium' },
            { policyPath: temporaryPolicy },
        );
        assert.deepEqual(updatedRoute.selected, { model: 'gpt-5.6-luna', effort: 'xhigh' });
        assert.equal(readFileSync(POLICY_SOURCE, 'utf8'), sourceText);
    } finally {
        rmSync(temporaryRoot, { recursive: true, force: true });
    }
});

test('malformed policy data fails validation', () => {
    assert.throws(
        () => validateSubagentModelPolicy({ schemaVersion: 1 }),
        error => error instanceof SubagentModelPolicyError && /models must be an object/.test(error.message),
    );
    const policy = JSON.parse(readFileSync(POLICY_SOURCE, 'utf8'));
    assert.throws(
        () => validateSubagentModelPolicy({
            ...policy,
            replacements: [
                {
                    requested: { model: 'terra', effort: 'medium' },
                    selected: { model: 'terra', effort: 'medium' },
                },
            ],
        }),
        /replacement target is not approved/,
    );
    const blocked = resolveSubagentModelRoute(
        { model: 'Terra', reasoning_effort: 'medium' },
        { policy: { schemaVersion: 1 } },
    );
    assert.equal(blocked.status, 'blocked');
    assert.match(blocked.diagnostic, /models must be an object/);
});

test('a copied policy cannot forge the validated-policy marker', () => {
    const policy = JSON.parse(readFileSync(POLICY_SOURCE, 'utf8'));
    const validatedPolicy = validateSubagentModelPolicy(policy);
    const copiedPolicy = { ...validatedPolicy, models: {} };
    const result = resolveSubagentModelRoute(
        { model: 'Terra', reasoning_effort: 'medium' },
        { policy: copiedPolicy },
    );
    assert.equal(result.status, 'blocked');
    assert.match(result.diagnostic, /models must not be empty/);
});

test('normalized effort aliases resolve from the validated policy', () => {
    const policy = JSON.parse(readFileSync(POLICY_SOURCE, 'utf8'));
    policy.efforts.aliases = { Light: 'LOW' };
    const validatedPolicy = validateSubagentModelPolicy(policy);
    const result = resolveSubagentModelRoute(
        { model: 'Astra', reasoning_effort: 'Light' },
        { policy: validatedPolicy },
    );
    assert.deepEqual(result.selected, { model: 'gpt-6-astra', effort: 'low' });
});

test('inheritance aliases cannot shadow model aliases', () => {
    const policy = JSON.parse(readFileSync(POLICY_SOURCE, 'utf8'));
    policy.inheritanceAliases = ['astra'];
    assert.throws(
        () => validateSubagentModelPolicy(policy),
        /inheritance alias conflicts with a model alias/,
    );
});

test('model names cannot collide after normalization', () => {
    const policy = JSON.parse(readFileSync(POLICY_SOURCE, 'utf8'));
    policy.models.Astra = { id: 'gpt-6-astra-copy', aliases: [] };
    assert.throws(
        () => validateSubagentModelPolicy(policy),
        /model name is ambiguous: astra/,
    );
});

test('combined role routes must end at an approved terminal pair', () => {
    const policy = JSON.parse(readFileSync(POLICY_SOURCE, 'utf8'));
    const solMediumReplacement = policy.replacements.find(replacement => (
        replacement.requested.model === 'sol'
        && replacement.requested.effort === 'medium'
    ));
    solMediumReplacement.selected = { model: 'astra', effort: 'low' };
    policy.roleReplacements.push({
        role: 'worker',
        requested: { model: 'astra', effort: 'low' },
        selected: { model: 'luna', effort: 'high' },
    });
    assert.throws(
        () => validateSubagentModelPolicy(policy),
        /replacement destination is not terminal/,
    );
});

test('replacement cycles fail policy validation', () => {
    const policy = JSON.parse(readFileSync(POLICY_SOURCE, 'utf8'));
    policy.replacements.push(
        {
            requested: { model: 'luna', effort: 'high' },
            selected: { model: 'luna', effort: 'xhigh' },
        },
        {
            requested: { model: 'luna', effort: 'xhigh' },
            selected: { model: 'luna', effort: 'high' },
        },
    );
    assert.throws(
        () => validateSubagentModelPolicy(policy),
        /replacement cycle includes/,
    );
});

test('base replacement targets must be approved for every role', () => {
    const policy = JSON.parse(readFileSync(POLICY_SOURCE, 'utf8'));
    policy.replacements = policy.replacements.map(replacement => (
        replacement.requested.model === 'terra' && replacement.requested.effort === 'medium'
            ? { ...replacement, selected: { model: 'astra', effort: 'high' } }
            : replacement
    ));
    assert.throws(
        () => validateSubagentModelPolicy(policy),
        /replacement target is not approved: astra\/high/,
    );
});

test('policy aliases stay in the policy file', () => {
    const source = readFileSync(join(PACKAGE_ROOT, 'scripts', 'subagent_model_policy.mjs'), 'utf8');
    assert.doesNotMatch(source, /gpt-5\.6-(?:luna|sol|terra)|gpt-6-astra/);
});
