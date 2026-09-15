import { existsSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
    defaultSubagentModelPolicyPath,
    isSelectorPairExcluded,
    loadSubagentModelPolicy,
    resolveSubagentModelRoute,
} from './subagent_model_policy.mjs';

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
    const hostPreferences = readHostPreferences(input);
    const routingInput = (input.requestedEffort === undefined || input.requestedEffort === null)
        && hostPreferences.defaultEffort !== undefined
        ? { ...input, requestedEffort: hostPreferences.defaultEffort }
        : input;
    const selectionPolicy = loadSelectionPolicy(input);
    if (selectionPolicy.policy) validateModelIdInventories(input, selectionPolicy.policy);
    const { allCandidates, routingFailures } = collectCandidates(
        routingInput,
        hostPreferences.modelsByRole[routingInput.role] ?? [],
        selectionPolicy,
    );
    const allSelectedCandidates = selectPanelCandidates(allCandidates, panel);
    return buildSelection(routingInput, panel, allSelectedCandidates, routingFailures);
}

function validateSelectionInput(input) {
    if (!input || typeof input !== 'object' || Array.isArray(input)) {
        throw new Error('selection input must be an object');
    }
    validateHost(input.host, input.inventoryHost);
    validateDelegationIndex(input.delegationIndex);
    requireStringArray(input.availableModelIds, 'available model ids');
    requireStringArray(input.confirmedSuitableModelIds, 'confirmed suitable model ids');
    if (input.requestedEffort !== undefined && input.requestedEffort !== null
        && (typeof input.requestedEffort !== 'string' || input.requestedEffort.trim() === '')) {
        throw new Error('requested effort must be a non-empty string');
    }
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
    const allAvailableModelIds = new Set(input.availableModelIds);
    if (input.confirmedSuitableModelIds.some(
        eachModelId => !allAvailableModelIds.has(eachModelId),
    )) {
        throw new Error('confirmed suitable models must be available');
    }
}

function validateModelIdInventories(input, policy) {
    const inventories = [
        ['confirmed suitable model ids', input.confirmedSuitableModelIds],
        ['available model ids', input.availableModelIds],
    ];
    for (const [label, modelIds] of inventories) {
        if (modelIds.some(eachModelId => policy.inheritanceAliases.has(eachModelId.trim().toLowerCase()))) {
            throw new Error(label + ' must contain native model ids');
        }
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
        return { modelsByRole: {}, defaultEffort: undefined };
    }
    const preferences = JSON.parse(readFileSync(preferencesPath, 'utf8'));
    if (preferences.host !== input.host) {
        throw new Error('preference host must match selected host');
    }
    return {
        modelsByRole: preferences.modelsByRole ?? {},
        defaultEffort: preferences.defaultEffort,
    };
}

function loadSelectionPolicy(input) {
    try {
        return { policy: loadSubagentModelPolicy(resolvePolicyPath(input)), error: null };
    } catch (error) {
        return {
            policy: null,
            error: error instanceof Error ? error.message : String(error),
        };
    }
}

function collectCandidates(input, allPreferredModelEntries, selectionPolicy) {
    validatePreferenceEntries(allPreferredModelEntries, 'role preferences');
    if (!selectionPolicy.policy) {
        return { allCandidates: [], routingFailures: [selectionPolicy.error] };
    }
    const routingFailures = [];
    const allPreferredCandidates = allPreferredModelEntries
        .map(eachEntry => preferenceCandidate(
            eachEntry,
            input,
            'host-preference',
            routingFailures,
            selectionPolicy.policy,
        ))
        .filter(Boolean);
    const allAlternativeCandidates = input.confirmedSuitableModelIds
        .map(eachModelId => preferenceCandidate(
            eachModelId,
            input,
            'confirmed-host-alternative',
            routingFailures,
            selectionPolicy.policy,
        ))
        .filter(Boolean);
    const allCandidates = deduplicateCandidates([
        ...allPreferredCandidates,
        ...allAlternativeCandidates,
    ]);
    const allCandidatesWithFallback = allCandidates.length === 0 && routingFailures.length === 0
        && input.parentFallback.isAllowed
        ? [parentCandidate()]
        : allCandidates;
    return {
        allCandidates: orderCrossJudgeCandidates(input, allCandidatesWithFallback),
        routingFailures,
    };
}

function preferenceCandidate(
    preferenceEntry,
    input,
    source,
    routingFailures,
    policy,
) {
    const resolvedEntry = resolvePreferenceEntry(preferenceEntry, input, policy);
    if (resolvedEntry.error) {
        routingFailures.push(resolvedEntry.error);
        return null;
    }
    const { modelId, effort } = resolvedEntry;
    if (isSelectorPairExcluded(modelId, effort, policy)) return null;
    if (policy.inheritanceAliases.has(modelId.trim().toLowerCase())) {
        if (effort !== null) {
            routingFailures.push('parent inheritance cannot set an effort');
            return null;
        }
        return input.parentFallback.isAllowed ? parentCandidate() : null;
    }
    if (input.host !== 'codex') {
        return input.availableModelIds.includes(modelId)
            ? modelCandidate(modelId, source)
            : null;
    }
    const routeRequest = { model: modelId, agent_type: input.routingRole ?? 'worker' };
    if (effort !== null) routeRequest.reasoning_effort = effort;
    const route = resolveSubagentModelRoute(
        routeRequest,
        {
            policyPath: resolvePolicyPath(input),
            policy,
            availableModelIds: input.availableModelIds,
            allowMissingEffort: effort === null,
            trustedSessionMetadata: input.trustedSessionMetadata,
        },
    );
    if (route.status === 'blocked') {
        routingFailures.push(route.diagnostic);
        return null;
    }
    if (isSelectorPairExcluded(route.selected.model, route.selected.effort, policy)) return null;
    if (route.status === 'inherited') return input.parentFallback.isAllowed ? parentCandidate() : null;
    return modelCandidate(route.selected.model, source, route);
}

function modelCandidate(modelId, source, route = null) {
    return {
        kind: 'model',
        modelId,
        source,
        requestedPair: route?.requested ?? null,
        selectedPair: route?.selected ?? null,
        effort: route?.selected?.effort ?? null,
    };
}

function parentCandidate() {
    return {
        kind: 'parent',
        modelId: null,
        source: 'parent-inheritance',
        requestedPair: null,
        selectedPair: null,
        effort: null,
    };
}

function resolvePreferenceEntry(preferenceEntry, input, policy = null) {
    const preferenceModel = typeof preferenceEntry === 'string'
        ? preferenceEntry
        : preferenceEntry?.modelId ?? preferenceEntry?.model;
    const isInheritanceAlias = typeof preferenceModel === 'string'
        && policy?.inheritanceAliases.has(preferenceModel.trim().toLowerCase());
    const fallbackEffort = isInheritanceAlias ? null : input.requestedEffort ?? null;
    if (typeof preferenceEntry === 'string' && preferenceEntry !== '') {
        return { modelId: preferenceEntry, effort: fallbackEffort, error: null };
    }
    if (!preferenceEntry || typeof preferenceEntry !== 'object' || Array.isArray(preferenceEntry)) {
        return { modelId: null, effort: null, error: 'role preferences must contain model ids or pair objects' };
    }
    const modelId = preferenceEntry.modelId ?? preferenceEntry.model;
    const effortFields = ['reasoning_effort', 'effort'].filter(
        field => Object.hasOwn(preferenceEntry, field),
    );
    if (effortFields.length > 1) {
        return { modelId: null, effort: null, error: 'role preference effort fields are ambiguous' };
    }
    const effort = preferenceEntry[effortFields[0]] ?? fallbackEffort;
    if (typeof modelId !== 'string' || modelId === '') {
        return { modelId: null, effort: null, error: 'role preference model must be a non-empty string' };
    }
    return { modelId, effort, error: null };
}

function validatePreferenceEntries(allEntries, label) {
    if (!Array.isArray(allEntries)) throw new Error(label + ' must be an array');
    allEntries.forEach(eachEntry => {
        const resolvedEntry = resolvePreferenceEntry(eachEntry, {});
        if (resolvedEntry.error) throw new Error(resolvedEntry.error);
    });
}

function resolvePolicyPath(input) {
    if (typeof input.policyPath === 'string' && input.policyPath.trim() !== '') {
        return input.policyPath;
    }
    const allPolicyPaths = [
        input.preferencesDirectory
            ? join(input.preferencesDirectory, 'subagent-model-policy.json')
            : null,
        defaultSubagentModelPolicyPath(),
    ].filter(Boolean);
    return allPolicyPaths.find(eachPath => existsSync(eachPath)) ?? allPolicyPaths[0];
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

function buildSelection(input, requestedPanel, allSelectedCandidates, routingFailures) {
    const panel = reportPanel(requestedPanel, allSelectedCandidates);
    const failure = selectionFailure(input, panel, allSelectedCandidates, routingFailures);
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
        routingDiagnostics: routingFailures,
        nativeSpawnArguments: nativeSpawnArguments(selectedCandidate, failure),
        omitNativeModelArgument: selectedCandidate?.kind === 'parent',
    };
}

function reportPanel(requestedPanel, allSelectedCandidates) {
    const allSelectedModelIds = allSelectedCandidates.map(
        eachCandidate => eachCandidate.modelId,
    );
    const distinctModelCount = new Set(allSelectedModelIds.filter(Boolean)).size;
    return {
        agentCount: requestedPanel.agentCount,
        requiresDistinctModels: requestedPanel.requiresDistinctModels,
        selectedModelIds: allSelectedModelIds,
        requestedModelPairs: allSelectedCandidates.map(eachCandidate => eachCandidate.requestedPair),
        selectedModelPairs: allSelectedCandidates.map(eachCandidate => eachCandidate.selectedPair),
        selectionSources: allSelectedCandidates.map(eachCandidate => eachCandidate.source),
        isCrossModelDiverse: requestedPanel.agentCount > 1
            && distinctModelCount === requestedPanel.agentCount,
    };
}

function selectionFailure(input, panel, allSelectedCandidates, routingFailures) {
    if (routingFailures.length > 0) {
        return 'model-routing-failed: ' + routingFailures[0];
    }
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
    const spawnArguments = { model: selectedCandidate.modelId };
    if (selectedCandidate.effort !== null) {
        spawnArguments.reasoning_effort = selectedCandidate.effort;
    }
    return spawnArguments;
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
