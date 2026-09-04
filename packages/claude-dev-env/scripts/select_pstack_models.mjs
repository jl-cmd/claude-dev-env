import { existsSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const inheritanceAliases = new Set(['inherit-parent', 'auto']);
const hostNamePattern = /^[a-z0-9][a-z0-9_-]*$/;
const defaultSingleDelegationPanel = Object.freeze({
    agentCount: 1,
    requiresDistinctModels: false,
});

export const allPstackRoleRequirements = Object.freeze({
    'feature, refactoring': 'reliable code execution',
    'bug-fix': 'careful diagnosis and code execution',
    'perf-issue': 'systems reasoning and performance analysis',
    'hillclimb': 'strong iterative judgment',
    'judgment and prose': 'strong judgment and clear prose',
    'hardest tasks': 'highest available reasoning capability',
    'how explorer': 'fast codebase exploration',
    'how explainer': 'clear technical synthesis',
    'how critics': 'independent technical criticism',
    'why investigators': 'fast evidence gathering',
    'why synthesizer': 'strong evidence synthesis',
    'reflect tooling': 'reliable tool and workflow analysis',
    'reflect judgment, divergent, synthesizer': 'strong judgment and divergent analysis',
    'arena runners': 'independent solution development',
    'arena cross-judge pool': 'independent comparative judgment',
    'swarm workers': 'fast bounded task execution',
    'architect runners': 'independent architecture design',
    'interrogate reviewers': 'independent adversarial review',
});

export const defaultPanelByPstackRole = Object.freeze({
    'how critics': Object.freeze({ agentCount: 3, requiresDistinctModels: false }),
    'arena runners': Object.freeze({ agentCount: 3, requiresDistinctModels: true }),
    'swarm workers': defaultSingleDelegationPanel,
    'architect runners': Object.freeze({ agentCount: 2, requiresDistinctModels: true }),
    'interrogate reviewers': Object.freeze({ agentCount: 3, requiresDistinctModels: true }),
});

export function selectPstackDelegation(input) {
    validateSelectionInput(input);
    const panel = resolvePanel(input);
    validateDelegationIndex(input.delegationIndex, panel.agentCount);
    const modelsByRole = readHostPreferences(input);
    const allCandidates = collectCandidates(input, modelsByRole[input.role] ?? []);
    const allSelectedCandidates = selectPanelCandidates(allCandidates, panel);
    return buildSelection(input, panel, allSelectedCandidates);
}

function validateSelectionInput(input) {
    if (!input || typeof input !== 'object' || Array.isArray(input)) {
        throw new Error('selection input must be an object');
    }
    validateHost(input.host, input.inventoryHost);
    validateDelegationIndex(input.delegationIndex);
    requireStringArray(input.availableModelIds, 'available model ids');
    requireStringArray(input.confirmedSuitableModelIds, 'confirmed suitable model ids');
    validateRealModelIds(input.availableModelIds, 'available model ids');
    validateParentFallback(input.parentFallback);
    validateConfirmedModels(input);
    if (typeof input.role !== 'string' || !Object.hasOwn(allPstackRoleRequirements, input.role)) {
        throw new Error('role must name a portable pstack role');
    }
}

function validateHost(host, inventoryHost) {
    if (typeof host !== 'string' || !hostNamePattern.test(host)) {
        throw new Error('host must be a lowercase host identifier');
    }
    if (inventoryHost !== host) {
        throw new Error('inventory host must match selected host');
    }
}

function validateDelegationIndex(delegationIndex, agentCount) {
    if (!Number.isInteger(delegationIndex) || delegationIndex < 0) {
        throw new Error('delegation index must be a non-negative integer');
    }
    if (agentCount !== undefined && delegationIndex >= agentCount) {
        throw new Error('delegation index must identify an agent in the panel');
    }
}

function requireStringArray(allEntries, label) {
    if (!Array.isArray(allEntries) || allEntries.some(
        eachEntry => typeof eachEntry !== 'string' || eachEntry === '',
    )) {
        throw new Error(label + ' must be an array of non-empty strings');
    }
}

function validateRealModelIds(allModelIds, label) {
    if (allModelIds.some(eachModelId => inheritanceAliases.has(eachModelId))) {
        throw new Error(label + ' cannot contain inheritance aliases');
    }
}

function validateParentFallback(parentFallback) {
    const hasBooleanFlags = parentFallback
        && typeof parentFallback === 'object'
        && typeof parentFallback.isAllowed === 'boolean'
        && typeof parentFallback.hasMaterialCapabilityLoss === 'boolean';
    if (!hasBooleanFlags) {
        throw new Error('parent fallback flags must be booleans');
    }
}

function validateConfirmedModels(input) {
    validateRealModelIds(input.confirmedSuitableModelIds, 'confirmed suitable model ids');
    const allAvailableModelIds = new Set(input.availableModelIds);
    if (input.confirmedSuitableModelIds.some(
        eachModelId => !allAvailableModelIds.has(eachModelId),
    )) {
        throw new Error('confirmed suitable models must be available');
    }
}

function resolvePanel(input) {
    const panel = input.panel
        ?? defaultPanelByPstackRole[input.role]
        ?? defaultSingleDelegationPanel;
    const hasValidShape = panel
        && typeof panel === 'object'
        && Number.isInteger(panel.agentCount)
        && panel.agentCount > 0
        && typeof panel.requiresDistinctModels === 'boolean';
    if (!hasValidShape) {
        throw new Error('panel requires a positive agent count and a diversity boolean');
    }
    return {
        agentCount: panel.agentCount,
        requiresDistinctModels: panel.requiresDistinctModels,
    };
}

function readHostPreferences(input) {
    const preferencesDirectory = input.preferencesDirectory
        ?? resolve(dirname(fileURLToPath(import.meta.url)), '..', 'rules');
    const preferencesPath = join(
        preferencesDirectory,
        'pstack-model-preferences.' + input.host + '.json',
    );
    if (!existsSync(preferencesPath)) {
        return {};
    }
    const preferences = JSON.parse(readFileSync(preferencesPath, 'utf8'));
    if (preferences.host !== input.host) {
        throw new Error('preference host must match selected host');
    }
    return preferences.modelsByRole ?? {};
}

function collectCandidates(input, allPreferredModelIds) {
    requireStringArray(allPreferredModelIds, 'role preferences');
    const allAvailableModelIds = new Set(input.availableModelIds);
    const allPreferredCandidates = allPreferredModelIds
        .map(eachModelId => preferenceCandidate(eachModelId, allAvailableModelIds, input))
        .filter(Boolean);
    const allAlternativeCandidates = input.confirmedSuitableModelIds.map(
        eachModelId => modelCandidate(eachModelId, 'confirmed-host-alternative'),
    );
    const allCandidates = deduplicateCandidates([
        ...allPreferredCandidates,
        ...allAlternativeCandidates,
    ]);
    const allCandidatesWithFallback = allCandidates.length === 0
        && input.parentFallback.isAllowed
        ? [parentCandidate()]
        : allCandidates;
    return orderCrossJudgeCandidates(input, allCandidatesWithFallback);
}

function preferenceCandidate(modelId, allAvailableModelIds, input) {
    if (inheritanceAliases.has(modelId)) {
        return input.parentFallback.isAllowed ? parentCandidate() : null;
    }
    return allAvailableModelIds.has(modelId)
        ? modelCandidate(modelId, 'host-preference')
        : null;
}

function modelCandidate(modelId, source) {
    return { kind: 'model', modelId, source };
}

function parentCandidate() {
    return { kind: 'parent', modelId: null, source: 'parent-inheritance' };
}

function deduplicateCandidates(allCandidates) {
    const seenCandidateKeys = new Set();
    return allCandidates.filter(eachCandidate => {
        const candidateKey = eachCandidate.kind + ':' + (eachCandidate.modelId ?? '');
        if (seenCandidateKeys.has(candidateKey)) {
            return false;
        }
        seenCandidateKeys.add(candidateKey);
        return true;
    });
}

function orderCrossJudgeCandidates(input, allCandidates) {
    if (input.role !== 'arena cross-judge pool' || !input.parentModelId) {
        return allCandidates;
    }
    const allOtherCandidates = allCandidates.filter(
        eachCandidate => eachCandidate.kind === 'model'
            && eachCandidate.modelId !== input.parentModelId,
    );
    const allParentCandidates = allCandidates.filter(
        eachCandidate => eachCandidate.kind === 'parent'
            || eachCandidate.modelId === input.parentModelId,
    );
    return [...allOtherCandidates, ...allParentCandidates];
}

function selectPanelCandidates(allCandidates, panel) {
    if (panel.requiresDistinctModels) {
        return allCandidates
            .filter(eachCandidate => eachCandidate.kind === 'model')
            .slice(0, panel.agentCount);
    }
    if (allCandidates.length === 0) {
        return [];
    }
    return Array.from(
        { length: panel.agentCount },
        (_, index) => allCandidates[index % allCandidates.length],
    );
}

function buildSelection(input, requestedPanel, allSelectedCandidates) {
    const panel = reportPanel(requestedPanel, allSelectedCandidates);
    const failure = selectionFailure(input, panel, allSelectedCandidates);
    const selectedCandidate = allSelectedCandidates[input.delegationIndex];
    return {
        selectedHost: input.host,
        role: input.role,
        requiredCapability: allPstackRoleRequirements[input.role],
        availabilityValidated: true,
        canDelegate: failure === null,
        requiresUserChoice: failure !== null,
        failure,
        selectionSource: selectedCandidate?.source ?? null,
        panel,
        nativeSpawnArguments: nativeSpawnArguments(selectedCandidate, failure),
        omitNativeModelArgument: selectedCandidate?.kind === 'parent',
    };
}

function reportPanel(requestedPanel, allSelectedCandidates) {
    const allSelectedModelIds = allSelectedCandidates.map(
        eachCandidate => eachCandidate.modelId,
    );
    const distinctRealModelCount = new Set(allSelectedModelIds.filter(Boolean)).size;
    return {
        agentCount: requestedPanel.agentCount,
        requiresDistinctModels: requestedPanel.requiresDistinctModels,
        selectedModelIds: allSelectedModelIds,
        selectionSources: allSelectedCandidates.map(eachCandidate => eachCandidate.source),
        isCrossModelDiverse: requestedPanel.agentCount > 1
            && distinctRealModelCount === requestedPanel.agentCount,
    };
}

function selectionFailure(input, panel, allSelectedCandidates) {
    if (panel.requiresDistinctModels && !panel.isCrossModelDiverse) {
        return 'distinct-models-unavailable';
    }
    if (allSelectedCandidates.length < panel.agentCount) {
        return 'no-supported-model';
    }
    if (allSelectedCandidates.some(eachCandidate => eachCandidate.kind === 'parent')
        && input.parentFallback.hasMaterialCapabilityLoss) {
        return 'parent-capability-loss';
    }
    return null;
}

function nativeSpawnArguments(selectedCandidate, failure) {
    if (failure || !selectedCandidate || selectedCandidate.kind === 'parent') {
        return {};
    }
    return { model: selectedCandidate.modelId };
}

async function readSelectionInput() {
    let inputText = '';
    for await (const eachChunk of process.stdin) {
        inputText += eachChunk;
    }
    return JSON.parse(inputText);
}

function isEntryPoint() {
    return process.argv[1]
        && resolve(process.argv[1]) === fileURLToPath(import.meta.url);
}

if (isEntryPoint()) {
    const selectionInput = await readSelectionInput();
    console.log(JSON.stringify(selectPstackDelegation(selectionInput)));
}
