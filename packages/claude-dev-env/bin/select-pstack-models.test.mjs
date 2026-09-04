import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
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

function writeHostPreferences(preferencesDirectory, host, modelsByRole) {
    mkdirSync(preferencesDirectory, { recursive: true });
    writeFileSync(
        join(preferencesDirectory, 'pstack-model-preferences.' + host + '.json'),
        JSON.stringify({ host, modelsByRole }),
    );
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
        preferencesDirectory,
        ...overrides,
    });
}

test('portable policy represents every pstack role without model ids', () => {
    assert.deepEqual(Object.keys(allPstackRoleRequirements), ALL_PSTACK_ROLES);
    const serializedRequirements = JSON.stringify(allPstackRoleRequirements);
    assert.doesNotMatch(serializedRequirements, /gpt-|claude-|grok-/i);
});

test('Codex preferences select every available model in a diverse panel', () => {
    const preferencesDirectory = mkdtempSync(join(tmpdir(), 'pstack-codex-'));
    try {
        writeHostPreferences(preferencesDirectory, 'codex', {
            'how critics': ['gpt-5.6-terra', 'gpt-5.6-sol', 'gpt-6-astra'],
        });
        const selection = selectWithPreferences(preferencesDirectory, {
            role: 'how critics',
            delegationIndex: 1,
            availableModelIds: ['gpt-5.6-sol', 'gpt-6-astra', 'gpt-5.6-terra'],
        });
        assert.equal(selection.canDelegate, true);
        assert.equal(selection.selectedHost, 'codex');
        assert.equal(selection.selectionSource, 'host-preference');
        assert.deepEqual(selection.panel.selectedModelIds, [
            'gpt-5.6-terra',
            'gpt-5.6-sol',
            'gpt-6-astra',
        ]);
        assert.equal(selection.panel.isCrossModelDiverse, true);
        assert.deepEqual(selection.nativeSpawnArguments, { model: 'gpt-5.6-sol' });
        assert.equal(selection.omitNativeModelArgument, false);
        assert.equal(selection.availabilityValidated, true);
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

test('an unavailable preferred model uses a confirmed host alternative', () => {
    const preferencesDirectory = mkdtempSync(join(tmpdir(), 'pstack-alternative-'));
    try {
        writeHostPreferences(preferencesDirectory, 'codex', {
            'feature, refactoring': ['gpt-5.6-sol'],
        });
        const selection = selectWithPreferences(preferencesDirectory, {
            availableModelIds: ['confirmed-current-model'],
            confirmedSuitableModelIds: ['confirmed-current-model'],
        });
        assert.equal(selection.canDelegate, true);
        assert.equal(selection.selectionSource, 'confirmed-host-alternative');
        assert.deepEqual(selection.nativeSpawnArguments, {
            model: 'confirmed-current-model',
        });
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
        assert.deepEqual(selection.nativeSpawnArguments, { model: 'gpt-6-astra' });
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
        const selection = selectWithPreferences(preferencesDirectory, {
            role: 'arena cross-judge pool',
            parentModelId: 'current-parent-model',
            availableModelIds: ['confirmed-other-model'],
            parentFallback: {
                isAllowed: true,
                hasMaterialCapabilityLoss: false,
            },
        });
        assert.deepEqual(selection.nativeSpawnArguments, {
            model: 'confirmed-other-model',
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
        assert.deepEqual(selection.nativeSpawnArguments, { model: 'gpt-5.6-luna' });
    } finally {
        rmSync(preferencesDirectory, { recursive: true, force: true });
    }
});

test('a diversity-required panel fails without enough distinct real models', () => {
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
        assert.equal(selection.failure, 'distinct-models-unavailable');
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
            'how critics': ['gpt-5.6-sol'],
        });
        const selection = selectWithPreferences(preferencesDirectory, {
            role: 'how critics',
            delegationIndex: 2,
            panel: {
                agentCount: 3,
                requiresDistinctModels: false,
            },
            availableModelIds: ['gpt-5.6-sol'],
        });
        assert.equal(selection.canDelegate, true);
        assert.deepEqual(selection.panel.selectedModelIds, [
            'gpt-5.6-sol',
            'gpt-5.6-sol',
            'gpt-5.6-sol',
        ]);
        assert.equal(selection.panel.isCrossModelDiverse, false);
    } finally {
        rmSync(preferencesDirectory, { recursive: true, force: true });
    }
});