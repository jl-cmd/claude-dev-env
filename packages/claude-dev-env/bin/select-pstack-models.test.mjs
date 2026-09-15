import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { defaultSubagentModelPolicyPath } from '../scripts/subagent_model_policy.mjs';
import {
    allPstackRoleRequirements,
    selectPstackDelegation,
} from '../scripts/select_pstack_models.mjs';

const ALL_PSTACK_ROLES = [
    'feature, refactoring',
    'bug-fix',
    'perf-issue',
    'hillclimb',
    'judgment and prose',
    'hardest tasks',
    'how explorer',
    'how explainer',
    'how critics',
    'why investigators',
    'why synthesizer',
    'reflect tooling',
    'reflect judgment, divergent, synthesizer',
    'arena runners',
    'arena cross-judge pool',
    'swarm workers',
    'architect runners',
    'interrogate reviewers',
];

function writeHostPreferences(preferencesDirectory, host, modelsByRole, defaultEffort) {
    mkdirSync(preferencesDirectory, { recursive: true });
    const preferences = { host, modelsByRole };
    if (defaultEffort !== undefined) preferences.defaultEffort = defaultEffort;
    writeFileSync(
        join(preferencesDirectory, 'pstack-model-preferences.' + host + '.json'),
        JSON.stringify(preferences),
    );
}

function writePolicyWithModels(preferencesDirectory, modelEntries) {
    const policy = JSON.parse(readFileSync(defaultSubagentModelPolicyPath(), 'utf8'));
    for (const [name, id] of Object.entries(modelEntries)) {
        policy.models[name] = { id, aliases: [] };
        policy.approvedPairs.push({ model: name, effort: 'medium' });
    }
    const policyPath = join(preferencesDirectory, 'subagent-model-policy.json');
    writeFileSync(policyPath, JSON.stringify(policy));
    return policyPath;
}

function selectWithPreferences(preferencesDirectory, overrides) {
    return selectPstackDelegation({
        host: 'codex',
        inventoryHost: 'codex',
        role: 'feature, refactoring',
        delegationIndex: 0,
        availableModelIds: ['gpt-5.6-sol'],
        confirmedSuitableModelIds: [],
        parentFallback: {
            isAllowed: false,
            hasMaterialCapabilityLoss: false,
        },
        requestedEffort: 'medium',
        preferencesDirectory,
        ...overrides,
    });
}

test('portable policy represents every pstack role without model ids', () => {
    assert.deepEqual(Object.keys(allPstackRoleRequirements), ALL_PSTACK_ROLES);
    const serializedRequirements = JSON.stringify(allPstackRoleRequirements);
    assert.doesNotMatch(serializedRequirements, /gpt-|claude-|grok-/i);
});

test('Codex preferences skip an excluded pair in a panel', () => {
    const preferencesDirectory = mkdtempSync(join(tmpdir(), 'pstack-codex-'));
    try {
        writeHostPreferences(preferencesDirectory, 'codex', {
            'how critics': ['gpt-5.6-terra', 'gpt-5.6-sol', 'gpt-6-astra'],
        });
        const selection = selectWithPreferences(preferencesDirectory, {
            role: 'how critics',
            delegationIndex: 1,
            availableModelIds: [
                'gpt-5.6-sol',
                'gpt-6-astra',
                'gpt-5.6-terra',
                'gpt-5.6-luna',
            ],
        });
        assert.equal(selection.canDelegate, true);
        assert.equal(selection.selectedHost, 'codex');
        assert.equal(selection.selectionSource, 'host-preference');
        assert.deepEqual(selection.panel.selectedModelIds, [
            'gpt-5.6-luna',
            'gpt-6-astra',
            'gpt-5.6-luna',
        ]);
        assert.equal(selection.panel.isCrossModelDiverse, false);
        assert.deepEqual(selection.nativeSpawnArguments, {
            model: 'gpt-6-astra',
            reasoning_effort: 'medium',
        });
        assert.equal(selection.omitNativeModelArgument, false);
        assert.equal(selection.availabilityValidated, true);
    } finally {
        rmSync(preferencesDirectory, { recursive: true, force: true });
    }
});

test('selector exclusions remove Sol Medium before its Luna remap enters a panel', () => {
    const preferencesDirectory = mkdtempSync(join(tmpdir(), 'pstack-sol-exclusion-'));
    try {
        writeHostPreferences(preferencesDirectory, 'codex', {
            'how critics': [
                { model: ' Sol ', effort: 'Medium' },
                { model: 'gpt-5.6-sol', effort: 'medium' },
                { model: 'gpt-5.6-luna', effort: 'high' },
                { model: 'gpt-6-astra', effort: 'medium' },
            ],
        });
        const selection = selectWithPreferences(preferencesDirectory, {
            role: 'how critics',
            panel: { agentCount: 2, requiresDistinctModels: true },
            availableModelIds: ['gpt-5.6-sol', 'gpt-5.6-luna', 'gpt-6-astra'],
            confirmedSuitableModelIds: ['gpt-5.6-sol'],
        });
        assert.equal(selection.canDelegate, true);
        assert.deepEqual(selection.panel.selectedModelPairs, [
            { model: 'gpt-5.6-luna', effort: 'high' },
            { model: 'gpt-6-astra', effort: 'medium' },
        ]);
        assert.deepEqual(selection.nativeSpawnArguments, {
            model: 'gpt-5.6-luna',
            reasoning_effort: 'high',
        });
        assert.deepEqual(selection.routingDiagnostics, []);
    } finally {
        rmSync(preferencesDirectory, { recursive: true, force: true });
    }
});

test('a foreign host reads only its own saved preferences', () => {
    const preferencesDirectory = mkdtempSync(join(tmpdir(), 'pstack-host-'));
    try {
        writeHostPreferences(preferencesDirectory, 'codex', {
            'feature, refactoring': ['gpt-5.6-sol'],
        });
        writeHostPreferences(preferencesDirectory, 'claude', {
            'feature, refactoring': ['confirmed-claude-model'],
        });
        const selection = selectWithPreferences(preferencesDirectory, {
            host: 'claude',
            inventoryHost: 'claude',
            availableModelIds: ['confirmed-claude-model', 'gpt-5.6-sol'],
        });
        assert.equal(selection.selectedHost, 'claude');
        assert.deepEqual(selection.nativeSpawnArguments, {
            model: 'confirmed-claude-model',
        });
    } finally {
        rmSync(preferencesDirectory, { recursive: true, force: true });
    }
});

test('an unavailable preferred model stops before a confirmed host alternative', () => {
    const preferencesDirectory = mkdtempSync(join(tmpdir(), 'pstack-alternative-'));
    try {
        writeHostPreferences(preferencesDirectory, 'codex', {
            'feature, refactoring': ['gpt-5.6-terra'],
        });
        const policyPath = writePolicyWithModels(preferencesDirectory, {
            current: 'confirmed-current-model',
        });
        const selection = selectWithPreferences(preferencesDirectory, {
            availableModelIds: ['confirmed-current-model'],
            confirmedSuitableModelIds: ['confirmed-current-model'],
            policyPath,
        });
        assert.equal(selection.canDelegate, false);
        assert.match(selection.failure, /model-routing-failed: replacement model is unavailable/);
        assert.deepEqual(selection.nativeSpawnArguments, {});
    } finally {
        rmSync(preferencesDirectory, { recursive: true, force: true });
    }
});

test('the arena cross-judge pool selects one model other than the parent', () => {
    const preferencesDirectory = mkdtempSync(join(tmpdir(), 'pstack-judge-'));
    try {
        writeHostPreferences(preferencesDirectory, 'codex', {
            'arena cross-judge pool': ['gpt-5.6-sol', 'gpt-6-astra'],
        });
        const selection = selectWithPreferences(preferencesDirectory, {
            role: 'arena cross-judge pool',
            parentModelId: 'gpt-5.6-sol',
            availableModelIds: ['gpt-5.6-sol', 'gpt-6-astra'],
        });
        assert.equal(selection.panel.agentCount, 1);
        assert.deepEqual(selection.nativeSpawnArguments, {
            model: 'gpt-6-astra',
            reasoning_effort: 'medium',
        });
    } finally {
        rmSync(preferencesDirectory, { recursive: true, force: true });
    }
});
test('the arena cross-judge prefers a real alternative over parent inheritance', () => {
    const preferencesDirectory = mkdtempSync(join(tmpdir(), 'pstack-judge-parent-'));
    try {
        writeHostPreferences(preferencesDirectory, 'codex', {
            'arena cross-judge pool': ['auto', 'confirmed-other-model'],
        });
        const policyPath = writePolicyWithModels(preferencesDirectory, {
            other: 'confirmed-other-model',
        });
        const selection = selectWithPreferences(preferencesDirectory, {
            role: 'arena cross-judge pool',
            parentModelId: 'current-parent-model',
            availableModelIds: ['confirmed-other-model'],
            parentFallback: {
                isAllowed: true,
                hasMaterialCapabilityLoss: false,
            },
            policyPath,
        });
        assert.deepEqual(selection.nativeSpawnArguments, {
            model: 'confirmed-other-model',
            reasoning_effort: 'medium',
        });
        assert.equal(selection.omitNativeModelArgument, false);
    } finally {
        rmSync(preferencesDirectory, { recursive: true, force: true });
    }
});

test('a same-model swarm reports its actual panel composition', () => {
    const preferencesDirectory = mkdtempSync(join(tmpdir(), 'pstack-swarm-'));
    try {
        writeHostPreferences(preferencesDirectory, 'codex', {
            'swarm workers': ['gpt-5.6-luna'],
        });
        const selection = selectWithPreferences(preferencesDirectory, {
            role: 'swarm workers',
            delegationIndex: 2,
            panel: {
                agentCount: 4,
                requiresDistinctModels: false,
            },
            availableModelIds: ['gpt-5.6-luna'],
        });
        assert.equal(selection.canDelegate, true);
        assert.equal(selection.panel.agentCount, 4);
        assert.deepEqual(selection.panel.selectedModelIds, [
            'gpt-5.6-luna',
            'gpt-5.6-luna',
            'gpt-5.6-luna',
            'gpt-5.6-luna',
        ]);
        assert.equal(selection.panel.isCrossModelDiverse, false);
        assert.deepEqual(selection.nativeSpawnArguments, {
            model: 'gpt-5.6-luna',
            reasoning_effort: 'high',
        });
    } finally {
        rmSync(preferencesDirectory, { recursive: true, force: true });
    }
});

test('a diversity-required panel fails without enough distinct models', () => {
    const preferencesDirectory = mkdtempSync(join(tmpdir(), 'pstack-diversity-'));
    try {
        writeHostPreferences(preferencesDirectory, 'codex', {
            'interrogate reviewers': ['gpt-5.6-terra', 'auto', 'gpt-5.6-sol'],
        });
        const selection = selectWithPreferences(preferencesDirectory, {
            role: 'interrogate reviewers',
            availableModelIds: ['gpt-5.6-terra', 'gpt-5.6-sol'],
        });
        assert.equal(selection.canDelegate, false);
        assert.equal(selection.requiresUserChoice, true);
        assert.match(selection.failure, /model-routing-failed:/);
        assert.equal(selection.panel.isCrossModelDiverse, false);
        assert.deepEqual(selection.nativeSpawnArguments, {});
    } finally {
        rmSync(preferencesDirectory, { recursive: true, force: true });
    }
});

test('parent inheritance omits the native model argument', () => {
    const preferencesDirectory = mkdtempSync(join(tmpdir(), 'pstack-parent-'));
    try {
        writeHostPreferences(preferencesDirectory, 'codex', {
            'feature, refactoring': ['inherit-parent'],
        });
        const selection = selectWithPreferences(preferencesDirectory, {
            availableModelIds: [],
            parentFallback: {
                isAllowed: true,
                hasMaterialCapabilityLoss: false,
            },
        });
        assert.equal(selection.canDelegate, true);
        assert.equal(selection.selectionSource, 'parent-inheritance');
        assert.deepEqual(selection.nativeSpawnArguments, {});
        assert.equal(selection.omitNativeModelArgument, true);
    } finally {
        rmSync(preferencesDirectory, { recursive: true, force: true });
    }
});

test('parent inheritance rejects an explicit preference effort', () => {
    const preferencesDirectory = mkdtempSync(join(tmpdir(), 'pstack-parent-effort-'));
    try {
        writeHostPreferences(preferencesDirectory, 'codex', {
            'feature, refactoring': [{ model: 'auto', effort: 'medium' }],
        });
        const selection = selectWithPreferences(preferencesDirectory, {
            availableModelIds: [],
            parentFallback: {
                isAllowed: true,
                hasMaterialCapabilityLoss: false,
            },
        });
        assert.equal(selection.canDelegate, false);
        assert.equal(selection.failure, 'model-routing-failed: parent inheritance cannot set an effort');
        assert.deepEqual(selection.panel.selectedModelIds, []);
        assert.deepEqual(selection.nativeSpawnArguments, {});
    } finally {
        rmSync(preferencesDirectory, { recursive: true, force: true });
    }
});

test('selector rejects policy-defined inheritance aliases in model inventories', () => {
    const preferencesDirectory = mkdtempSync(join(tmpdir(), 'pstack-inventory-alias-'));
    try {
        assert.throws(
            () => selectWithPreferences(preferencesDirectory, {
                availableModelIds: ['auto'],
                confirmedSuitableModelIds: ['auto'],
                parentFallback: {
                    isAllowed: true,
                    hasMaterialCapabilityLoss: false,
                },
            }),
            /confirmed suitable model ids must contain native model ids/,
        );
        const policy = JSON.parse(readFileSync(defaultSubagentModelPolicyPath(), 'utf8'));
        policy.inheritanceAliases = ['custom-parent'];
        const policyPath = join(preferencesDirectory, 'subagent-model-policy.json');
        writeFileSync(policyPath, JSON.stringify(policy));
        assert.throws(
            () => selectWithPreferences(preferencesDirectory, {
                availableModelIds: ['custom-parent'],
                confirmedSuitableModelIds: [],
                parentFallback: {
                    isAllowed: true,
                    hasMaterialCapabilityLoss: false,
                },
                policyPath,
            }),
            /available model ids must contain native model ids/,
        );
    } finally {
        rmSync(preferencesDirectory, { recursive: true, force: true });
    }
});

test('material capability loss requires a user choice before inheritance', () => {
    const preferencesDirectory = mkdtempSync(join(tmpdir(), 'pstack-parent-loss-'));
    try {
        writeHostPreferences(preferencesDirectory, 'codex', {
            'hardest tasks': ['inherit-parent'],
        });
        const selection = selectWithPreferences(preferencesDirectory, {
            role: 'hardest tasks',
            availableModelIds: [],
            parentFallback: {
                isAllowed: true,
                hasMaterialCapabilityLoss: true,
            },
        });
        assert.equal(selection.canDelegate, false);
        assert.equal(selection.requiresUserChoice, true);
        assert.equal(selection.failure, 'parent-capability-loss');
        assert.deepEqual(selection.nativeSpawnArguments, {});
    } finally {
        rmSync(preferencesDirectory, { recursive: true, force: true });
    }
});

test('inventory and confirmed alternatives must belong to the selected host', () => {
    const preferencesDirectory = mkdtempSync(join(tmpdir(), 'pstack-inventory-'));
    try {
        assert.throws(
            () => selectWithPreferences(preferencesDirectory, {
                host: 'codex',
                inventoryHost: 'claude',
            }),
            /inventory host must match selected host/,
        );
        assert.throws(
            () => selectWithPreferences(preferencesDirectory, {
                availableModelIds: ['confirmed-current-model'],
                confirmedSuitableModelIds: ['missing-model'],
            }),
            /confirmed suitable models must be available/,
        );
    } finally {
        rmSync(preferencesDirectory, { recursive: true, force: true });
    }
});

test('an empty model set materializes allowed parent inheritance', () => {
    const preferencesDirectory = mkdtempSync(join(tmpdir(), 'pstack-empty-parent-'));
    try {
        const selection = selectWithPreferences(preferencesDirectory, {
            availableModelIds: [],
            parentFallback: {
                isAllowed: true,
                hasMaterialCapabilityLoss: false,
            },
        });
        assert.equal(selection.canDelegate, true);
        assert.equal(selection.selectionSource, 'parent-inheritance');
        assert.deepEqual(selection.panel.selectedModelIds, [null]);
        assert.equal(selection.omitNativeModelArgument, true);
        assert.deepEqual(selection.nativeSpawnArguments, {});
    } finally {
        rmSync(preferencesDirectory, { recursive: true, force: true });
    }
});

test('delegation index and fallback flags require exact boundary types', () => {
    const preferencesDirectory = mkdtempSync(join(tmpdir(), 'pstack-boundary-'));
    try {
        for (const invalidIndex of [undefined, Number.NaN, 0.5, -1]) {
            assert.throws(
                () => selectWithPreferences(preferencesDirectory, {
                    delegationIndex: invalidIndex,
                }),
                /delegation index must be a non-negative integer/,
            );
        }
        for (const invalidRole of ['toString', ['feature, refactoring']]) {
            assert.throws(
                () => selectWithPreferences(preferencesDirectory, {
                    role: invalidRole,
                }),
                /role must name a portable pstack role/,
            );
        }
        assert.throws(
            () => selectWithPreferences(preferencesDirectory, {
                parentFallback: {
                    isAllowed: 'yes',
                    hasMaterialCapabilityLoss: false,
                },
            }),
            /parent fallback flags must be booleans/,
        );
        assert.throws(
            () => selectWithPreferences(preferencesDirectory, {
                parentFallback: {
                    isAllowed: true,
                },
            }),
            /parent fallback flags must be booleans/,
        );
    } finally {
        rmSync(preferencesDirectory, { recursive: true, force: true });
    }
});

test('an optional-diversity review panel reports repeated models', () => {
    const preferencesDirectory = mkdtempSync(join(tmpdir(), 'pstack-review-panel-'));
    try {
        writeHostPreferences(preferencesDirectory, 'codex', {
            'how critics': ['gpt-5.6-luna'],
        });
        const selection = selectWithPreferences(preferencesDirectory, {
            role: 'how critics',
            delegationIndex: 2,
            panel: {
                agentCount: 3,
                requiresDistinctModels: false,
            },
            availableModelIds: ['gpt-5.6-luna'],
        });
        assert.equal(selection.canDelegate, true);
        assert.deepEqual(selection.panel.selectedModelIds, [
            'gpt-5.6-luna',
            'gpt-5.6-luna',
            'gpt-5.6-luna',
        ]);
        assert.equal(selection.panel.isCrossModelDiverse, false);
    } finally {
        rmSync(preferencesDirectory, { recursive: true, force: true });
    }
});

test('a model-only preference still goes through policy validation', () => {
    const preferencesDirectory = mkdtempSync(join(tmpdir(), 'pstack-routing-model-only-'));
    try {
        writeHostPreferences(preferencesDirectory, 'codex', {
            'feature, refactoring': ['unknown-model'],
        });
        const selection = selectWithPreferences(preferencesDirectory, {
            availableModelIds: ['unknown-model'],
        });
        assert.equal(selection.canDelegate, false);
        assert.match(selection.failure, /model-routing-failed: model is unknown/);
        assert.deepEqual(selection.nativeSpawnArguments, {});
    } finally {
        rmSync(preferencesDirectory, { recursive: true, force: true });
    }
});

test('a model-only Terra preference uses the host effort before routing', () => {
    const preferencesDirectory = mkdtempSync(join(tmpdir(), 'pstack-routing-terra-default-'));
    try {
        writeHostPreferences(preferencesDirectory, 'codex', {
            'feature, refactoring': ['Terra'],
        });
        const selection = selectWithPreferences(preferencesDirectory, {
            requestedEffort: 'medium',
            availableModelIds: ['gpt-5.6-terra', 'gpt-5.6-luna'],
        });
        assert.equal(selection.canDelegate, true);
        assert.deepEqual(selection.nativeSpawnArguments, {
            model: 'gpt-5.6-luna',
            reasoning_effort: 'xhigh',
        });
    } finally {
        rmSync(preferencesDirectory, { recursive: true, force: true });
    }
});

test('a profile default effort supplies a missing model-only effort', () => {
    const preferencesDirectory = mkdtempSync(join(tmpdir(), 'pstack-routing-profile-default-'));
    try {
        writeHostPreferences(preferencesDirectory, 'codex', {
            'feature, refactoring': ['Terra'],
        }, 'medium');
        const selection = selectWithPreferences(preferencesDirectory, {
            requestedEffort: undefined,
            availableModelIds: ['gpt-5.6-terra', 'gpt-5.6-luna'],
        });
        assert.deepEqual(selection.nativeSpawnArguments, {
            model: 'gpt-5.6-luna',
            reasoning_effort: 'xhigh',
        });
    } finally {
        rmSync(preferencesDirectory, { recursive: true, force: true });
    }
});

test('a model-only worker Astra preference uses the host effort before routing', () => {
    const preferencesDirectory = mkdtempSync(join(tmpdir(), 'pstack-routing-astra-default-'));
    try {
        writeHostPreferences(preferencesDirectory, 'codex', {
            'feature, refactoring': ['Astra'],
        });
        const selection = selectWithPreferences(preferencesDirectory, {
            requestedEffort: 'high',
            availableModelIds: ['gpt-6-astra'],
        });
        assert.equal(selection.canDelegate, true);
        assert.deepEqual(selection.nativeSpawnArguments, {
            model: 'gpt-6-astra',
            reasoning_effort: 'low',
        });
    } finally {
        rmSync(preferencesDirectory, { recursive: true, force: true });
    }
});

test('a model-only preference holds when the host supplies no usable effort', () => {
    const preferencesDirectory = mkdtempSync(join(tmpdir(), 'pstack-routing-missing-effort-'));
    try {
        writeHostPreferences(preferencesDirectory, 'codex', {
            'feature, refactoring': ['Terra'],
        });
        const selection = selectWithPreferences(preferencesDirectory, {
            requestedEffort: undefined,
            availableModelIds: ['gpt-5.6-terra'],
        });
        assert.equal(selection.canDelegate, false);
        assert.match(selection.failure, /effort is required for this model/);
    } finally {
        rmSync(preferencesDirectory, { recursive: true, force: true });
    }
});

test('a model-only Sol preference holds when no Sol effort remains approved', () => {
    const preferencesDirectory = mkdtempSync(join(tmpdir(), 'pstack-routing-sol-missing-effort-'));
    try {
        writeHostPreferences(preferencesDirectory, 'codex', {
            'feature, refactoring': ['Sol'],
        });
        const selection = selectWithPreferences(preferencesDirectory, {
            requestedEffort: undefined,
            availableModelIds: ['gpt-5.6-sol', 'gpt-5.6-luna'],
        });
        assert.equal(selection.canDelegate, false);
        assert.match(selection.failure, /effort is required for this model/);
    } finally {
        rmSync(preferencesDirectory, { recursive: true, force: true });
    }
});

test('non-Codex inheritance keeps its ordered parent fallback', () => {
    const preferencesDirectory = mkdtempSync(join(tmpdir(), 'pstack-routing-parent-'));
    try {
        writeHostPreferences(preferencesDirectory, 'claude', {
            'feature, refactoring': ['auto', 'opus'],
        });
        const selection = selectPstackDelegation({
            host: 'claude',
            inventoryHost: 'claude',
            role: 'feature, refactoring',
            delegationIndex: 0,
            availableModelIds: ['opus'],
            confirmedSuitableModelIds: [],
            parentFallback: {
                isAllowed: true,
                hasMaterialCapabilityLoss: false,
            },
            preferencesDirectory,
        });
        assert.equal(selection.canDelegate, true);
        assert.equal(selection.omitNativeModelArgument, true);
        assert.equal(selection.selectionSource, 'parent-inheritance');
        assert.deepEqual(selection.panel.selectedModelIds, [null]);
    } finally {
        rmSync(preferencesDirectory, { recursive: true, force: true });
    }
});

test('selector routes preference pairs before panel dedupe', () => {
    const preferencesDirectory = mkdtempSync(join(tmpdir(), 'pstack-routing-'));
    try {
        writeHostPreferences(preferencesDirectory, 'codex', {
            'feature, refactoring': [
                { model: 'gpt-5.6-terra', effort: 'medium' },
                { model: 'gpt-5.6-luna', effort: 'medium' },
            ],
        });
        const selection = selectWithPreferences(preferencesDirectory, {
            panel: { agentCount: 2, requiresDistinctModels: false },
            availableModelIds: ['gpt-5.6-terra', 'gpt-5.6-luna'],
        });
        assert.equal(selection.canDelegate, true);
        assert.deepEqual(selection.panel.selectedModelIds, [
            'gpt-5.6-luna',
            'gpt-5.6-luna',
        ]);
        assert.deepEqual(selection.panel.selectedModelPairs, [
            { model: 'gpt-5.6-luna', effort: 'xhigh' },
            { model: 'gpt-5.6-luna', effort: 'xhigh' },
        ]);
        assert.equal(selection.panel.isCrossModelDiverse, false);
        assert.deepEqual(selection.nativeSpawnArguments, {
            model: 'gpt-5.6-luna',
            reasoning_effort: 'xhigh',
        });
    } finally {
        rmSync(preferencesDirectory, { recursive: true, force: true });
    }
});

test('panel diversity uses selected models after routing', () => {
    const preferencesDirectory = mkdtempSync(join(tmpdir(), 'pstack-routing-panel-'));
    try {
        writeHostPreferences(preferencesDirectory, 'codex', {
            'arena runners': [
                { model: 'gpt-5.6-terra', effort: 'medium' },
                { model: 'gpt-5.6-sol', effort: 'medium' },
                { model: 'gpt-6-astra', effort: 'medium' },
            ],
        });
        const selection = selectWithPreferences(preferencesDirectory, {
            role: 'arena runners',
            availableModelIds: [
                'gpt-5.6-terra',
                'gpt-5.6-sol',
                'gpt-6-astra',
                'gpt-5.6-luna',
            ],
        });
        assert.equal(selection.canDelegate, false);
        assert.equal(selection.failure, 'distinct-models-unavailable');
        assert.deepEqual(selection.panel.selectedModelIds, [
            'gpt-5.6-luna',
            'gpt-6-astra',
        ]);
        assert.equal(selection.panel.isCrossModelDiverse, false);
        assert.deepEqual(selection.routingDiagnostics, []);
    } finally {
        rmSync(preferencesDirectory, { recursive: true, force: true });
    }
});

test('selector keeps other Sol remaps as contenders', () => {
    const preferencesDirectory = mkdtempSync(join(tmpdir(), 'pstack-sol-remap-'));
    try {
        writeHostPreferences(preferencesDirectory, 'codex', {
            'feature, refactoring': [{ model: 'gpt-5.6-sol', effort: 'high' }],
        });
        const selection = selectWithPreferences(preferencesDirectory, {
            availableModelIds: ['gpt-5.6-sol', 'gpt-6-astra'],
        });
        assert.equal(selection.canDelegate, true);
        assert.deepEqual(selection.panel.selectedModelIds, ['gpt-6-astra']);
        assert.deepEqual(selection.panel.selectedModelPairs, [
            { model: 'gpt-6-astra', effort: 'low' },
        ]);
        assert.deepEqual(selection.routingDiagnostics, []);
    } finally {
        rmSync(preferencesDirectory, { recursive: true, force: true });
    }
});

test('unavailable routed models hold selection', () => {
    const preferencesDirectory = mkdtempSync(join(tmpdir(), 'pstack-routing-unavailable-'));
    try {
        writeHostPreferences(preferencesDirectory, 'codex', {
            'feature, refactoring': [{ model: 'gpt-5.6-terra', effort: 'medium' }],
        });
        const selection = selectWithPreferences(preferencesDirectory, {
            availableModelIds: ['gpt-5.6-terra'],
        });
        assert.equal(selection.canDelegate, false);
        assert.equal(selection.requiresUserChoice, true);
        assert.match(selection.failure, /model-routing-failed: replacement model is unavailable/);
        assert.deepEqual(selection.nativeSpawnArguments, {});
    } finally {
        rmSync(preferencesDirectory, { recursive: true, force: true });
    }
});

test('malformed routing policy holds selection with a diagnostic', () => {
    const preferencesDirectory = mkdtempSync(join(tmpdir(), 'pstack-routing-policy-'));
    try {
        writeHostPreferences(preferencesDirectory, 'codex', {
            'feature, refactoring': [{ model: 'gpt-5.6-terra', effort: 'medium' }],
        });
        const policyPath = join(preferencesDirectory, 'subagent-model-policy.json');
        writeFileSync(policyPath, '{"schemaVersion":1}\n');
        const selection = selectWithPreferences(preferencesDirectory, { policyPath });
        assert.equal(selection.canDelegate, false);
        assert.match(selection.failure, /model-routing-failed: models must be an object/);
        assert.deepEqual(selection.nativeSpawnArguments, {});
    } finally {
        rmSync(preferencesDirectory, { recursive: true, force: true });
    }
});

test('an explicit missing policy path holds selection', () => {
    const preferencesDirectory = mkdtempSync(join(tmpdir(), 'pstack-missing-policy-'));
    try {
        writeHostPreferences(preferencesDirectory, 'codex', {
            'feature, refactoring': [{ model: 'Terra', effort: 'medium' }],
        });
        const selection = selectWithPreferences(preferencesDirectory, {
            policyPath: join(preferencesDirectory, 'missing-policy.json'),
        });
        assert.equal(selection.canDelegate, false);
        assert.match(selection.failure, /policy file is missing/);
    } finally {
        rmSync(preferencesDirectory, { recursive: true, force: true });
    }
});
