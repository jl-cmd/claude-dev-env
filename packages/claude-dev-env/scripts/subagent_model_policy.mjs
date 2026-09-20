import { existsSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const POLICY_FILE_NAME = 'subagent-model-policy.json';
const POLICY_SCHEMA_VERSION = 1;
const DEFAULT_ROLE = 'worker';
const MODEL_FIELD = 'model';
const EFFORT_FIELDS = ['reasoning_effort', 'effort'];
const ROLE_FIELDS = ['role', 'agent_type', 'agentType'];
const VALIDATED_POLICY_MARKER = Symbol('validatedPolicy');

export class SubagentModelPolicyError extends Error {
    constructor(message) {
        super(message);
        this.name = 'SubagentModelPolicyError';
    }
}

export function defaultSubagentModelPolicyPath() {
    return join(dirname(fileURLToPath(import.meta.url)), '..', 'rules', POLICY_FILE_NAME);
}

export function loadSubagentModelPolicy(policyPath = defaultSubagentModelPolicyPath()) {
    const resolvedPolicyPath = resolve(policyPath);
    if (!existsSync(resolvedPolicyPath)) {
        throw new SubagentModelPolicyError(`policy file is missing: ${resolvedPolicyPath}`);
    }
    let rawPolicy;
    try {
        rawPolicy = JSON.parse(readFileSync(resolvedPolicyPath, 'utf8'));
    } catch (error) {
        const detail = error instanceof SyntaxError ? 'invalid JSON' : error.message;
        throw new SubagentModelPolicyError(`policy file cannot be read: ${detail}`);
    }
    return validateSubagentModelPolicy(rawPolicy);
}

export function validateSubagentModelPolicy(policy) {
    requireObject(policy, 'policy');
    if (policy.schemaVersion !== POLICY_SCHEMA_VERSION) {
        throw new SubagentModelPolicyError('policy schemaVersion must be 1');
    }

    const modelByName = validateModels(policy.models);
    const effortDefinition = validateEfforts(policy.efforts);
    const effortNames = effortDefinition.names;
    const inheritanceAliases = validateStringList(
        policy.inheritanceAliases,
        'inheritanceAliases',
    ).map(normalizeToken);
    if (inheritanceAliases.some(alias => modelByName.aliasOwner.has(alias))) {
        throw new SubagentModelPolicyError('inheritance alias conflicts with a model alias');
    }
    const roleByAlias = validateRoles(policy.roles);
    const trustedAdvisorRoles = validateTrustedAdvisorRoles(policy.roles, roleByAlias);
    const approvedPairs = validateApprovedPairs(policy.approvedPairs, modelByName, effortNames, roleByAlias);
    const approvedPairKeys = new Set(approvedPairs.map(pair => pairKey(pair)));
    const selectorExclusions = validateSelectorExclusions(
        policy.selectorExclusions ?? [],
        modelByName,
        effortNames,
    );
    const advisorDefault = validatePair(
        policy.advisorDefault,
        modelByName,
        effortNames,
        'advisorDefault',
    );
    if (!isPairApproved(advisorDefault, 'advisor', approvedPairs)) {
        throw new SubagentModelPolicyError('advisorDefault must be approved for advisor');
    }

    const replacements = validateReplacements(
        policy.replacements,
        modelByName,
        effortNames,
        approvedPairs,
        'replacements',
    );
    const roleReplacements = validateRoleReplacements(
        policy.roleReplacements,
        modelByName,
        effortNames,
        approvedPairs,
        roleByAlias,
    );
    validateReplacementGraph(replacements, roleReplacements, approvedPairKeys);

    const validatedPolicy = {
        ...policy,
        efforts: {
            ...policy.efforts,
            values: [...effortNames],
            aliases: effortDefinition.aliases,
        },
        modelByName,
        effortNames,
        inheritanceAliases: new Set(inheritanceAliases),
        roleByAlias,
        trustedAdvisorRoles,
        approvedPairs,
        selectorExclusions,
        advisorDefault,
        replacements,
        roleReplacements,
    };
    Object.defineProperty(validatedPolicy, VALIDATED_POLICY_MARKER, { value: true });
    return validatedPolicy;
}

export function resolveSubagentModelRoute(request, options = {}) {
    try {
        const loadedPolicy = options.policy ?? loadSubagentModelPolicy(options.policyPath);
        const policy = isValidatedPolicy(loadedPolicy)
            ? loadedPolicy
            : validateSubagentModelPolicy(loadedPolicy);
        return resolveRouteWithPolicy(request, policy, options);
    } catch (error) {
        if (error instanceof SubagentModelPolicyError) return blockedRoute(error.message);
        throw error;
    }
}

export function routeSubagentToolInput(toolInput, options = {}) {
    if (!isObject(toolInput)) return blockedRoute('subagent tool input must be an object');
    const route = resolveSubagentModelRoute(toolInput, options);
    if (route.status === 'blocked') return { ...route, updatedInput: null };
    if (route.status === 'inherited' || route.status === 'pass') {
        return { ...route, updatedInput: toolInput };
    }
    const updatedInput = { ...toolInput, [MODEL_FIELD]: route.selected.model };
    if (route.selected.effort !== null) {
        const effortField = route.effortField ?? 'reasoning_effort';
        updatedInput[effortField] = route.selected.effort;
        if (effortField !== 'reasoning_effort' && Object.hasOwn(updatedInput, 'reasoning_effort')) {
            delete updatedInput.reasoning_effort;
        }
    }
    return { ...route, updatedInput };
}

export function isSelectorPairExcluded(model, effort, policy) {
    if (effort === null || effort === undefined) return false;
    const modelName = policy.modelByName.aliasOwner.get(normalizeToken(model));
    if (!modelName) return false;
    const normalizedEffort = normalizeToken(effort);
    const effortName = policy.effortNames.has(normalizedEffort)
        ? normalizedEffort
        : policy.efforts.aliases[normalizedEffort];
    return typeof effortName === 'string'
        && policy.selectorExclusions.has(pairKey({ model: modelName, effort: effortName }));
}

function resolveRouteWithPolicy(request, policy, options) {
    if (!isObject(request)) return blockedRoute('subagent tool input must be an object');
    const roleResult = resolveRole(request, policy);
    if (roleResult.status === 'blocked') return roleResult;
    const { role } = roleResult;
    if (role === 'advisor' && !hasTrustedAdvisorSession(policy, options)) {
        return blockedRoute('advisor role is not trusted');
    }

    const effortResult = readEffort(request, policy);
    if (effortResult.status === 'blocked') return effortResult;
    const modelResult = readModel(request, policy);
    if (modelResult.status === 'blocked') return modelResult;
    let { modelName, inherited } = modelResult;
    if (inherited && role === 'advisor') {
        modelName = policy.advisorDefault.model;
        inherited = false;
    }
    if (inherited) {
        if (effortResult.effort !== null) {
            return blockedRoute('parent inheritance cannot set an effort');
        }
        return {
            status: 'inherited',
            role,
            requested: { model: null, effort: null },
            selected: { model: null, effort: null },
            selectedModelName: null,
            effortField: effortResult.field,
            diagnostic: null,
        };
    }

    let effort = effortResult.effort;
    if (effort === null && role === 'advisor') effort = policy.advisorDefault.effort;
    if (effort === null) {
        const modelEfforts = approvedEffortsForModel(modelName, role, policy.approvedPairs);
        if (modelEfforts.length === 1) effort = modelEfforts[0];
    }
    if (effort === null) {
        const modelEfforts = approvedEffortsForModel(modelName, role, policy.approvedPairs);
        if (!options.allowMissingEffort || modelEfforts.length !== 1) {
            return blockedRoute('effort is required for this model');
        }
        effort = modelEfforts[0];
    }

    const requestedPair = { model: modelName, effort };
    const selectedPair = selectReplacement(requestedPair, role, policy);
    if (!selectedPair) {
        return blockedRoute(
            `model and effort pair is not approved: ${modelName}/${effort}`,
        );
    }
    if (!isPairApproved(selectedPair, role, policy.approvedPairs)) {
        return blockedRoute('replacement pair is not approved for this role');
    }
    const availability = validateAvailability(selectedPair, options.availableModelIds, policy);
    if (availability) return blockedRoute(availability);

    const changed = selectedPair.model !== requestedPair.model
        || selectedPair.effort !== requestedPair.effort
        || modelResult.wasAlias
        || effortResult.wasAlias
        || modelResult.wasMissing
        || effortResult.wasMissing;
    const status = changed ? 'remapped' : 'pass';
    return {
        status,
        role,
        requested: {
            model: policy.modelByName[requestedPair.model].id,
            effort: requestedPair.effort,
        },
        selected: {
            model: policy.modelByName[selectedPair.model].id,
            effort: selectedPair.effort,
        },
        selectedModelName: selectedPair.model,
        effortField: effortResult.field,
        diagnostic: null,
    };
}

function validateModels(models) {
    requireObject(models, 'models');
    const modelByName = {};
    const aliasOwner = new Map();
    for (const [rawName, rawModel] of Object.entries(models)) {
        const name = normalizeToken(rawName);
        if (!isIdentifier(name)) throw new SubagentModelPolicyError(`invalid model name: ${rawName}`);
        if (Object.hasOwn(modelByName, name)) {
            throw new SubagentModelPolicyError(`model name is ambiguous: ${name}`);
        }
        requireObject(rawModel, `model ${name}`);
        const id = requireNonEmptyString(rawModel.id, `model ${name} id`);
        const aliases = validateStringList(rawModel.aliases, `model ${name} aliases`);
        const allAliases = [...new Set([name, id, ...aliases].map(normalizeToken))];
        for (const alias of allAliases) {
            const previousOwner = aliasOwner.get(alias);
            if (previousOwner && previousOwner !== name) {
                throw new SubagentModelPolicyError(`model alias is ambiguous: ${alias}`);
            }
            aliasOwner.set(alias, name);
        }
        modelByName[name] = { id, aliases: allAliases, aliasOwner };
    }
    if (Object.keys(modelByName).length === 0) throw new SubagentModelPolicyError('models must not be empty');
    Object.defineProperty(modelByName, 'aliasOwner', { value: aliasOwner, enumerable: false });
    return modelByName;
}

function validateEfforts(efforts) {
    requireObject(efforts, 'efforts');
    const names = validateStringList(efforts.values, 'efforts.values').map(normalizeToken);
    if (new Set(names).size !== names.length || names.some(name => !isIdentifier(name))) {
        throw new SubagentModelPolicyError('effort values must be unique identifiers');
    }
    const aliases = efforts.aliases;
    requireObject(aliases, 'efforts.aliases');
    const canonicalAliases = {};
    for (const [alias, target] of Object.entries(aliases)) {
        const normalizedAlias = normalizeToken(alias);
        const normalizedTarget = normalizeToken(target);
        if (!isIdentifier(normalizedAlias) || !names.includes(normalizedTarget)) {
            throw new SubagentModelPolicyError(`effort alias is invalid: ${alias}`);
        }
        if (Object.hasOwn(canonicalAliases, normalizedAlias)) {
            throw new SubagentModelPolicyError(`effort alias is ambiguous: ${normalizedAlias}`);
        }
        if (names.includes(normalizedAlias)) {
            throw new SubagentModelPolicyError(`effort alias conflicts with value: ${alias}`);
        }
        canonicalAliases[normalizedAlias] = normalizedTarget;
    }
    return { names: new Set(names), aliases: canonicalAliases };
}

function validateRoles(roles) {
    requireObject(roles, 'roles');
    const roleByAlias = new Map();
    const canonicalRoles = ['worker', 'advisor'];
    for (const role of canonicalRoles) {
        const aliases = validateStringList(roles[role], `roles.${role}`).map(normalizeToken);
        const allAliases = [role, ...aliases];
        for (const alias of allAliases) {
            const roleParts = alias.split(':');
            if (roleParts.length > 2 || !roleParts.every(isIdentifier)) {
                throw new SubagentModelPolicyError(`invalid role name: ${alias}`);
            }
            const previousRole = roleByAlias.get(alias);
            if (previousRole && previousRole !== role) {
                throw new SubagentModelPolicyError(`role alias is ambiguous: ${alias}`);
            }
            roleByAlias.set(alias, role);
        }
    }
    const defaultRole = normalizeToken(roles.default);
    if (defaultRole !== DEFAULT_ROLE || !roleByAlias.has(defaultRole)) {
        throw new SubagentModelPolicyError('roles.default must be worker');
    }
    return roleByAlias;
}

function validateTrustedAdvisorRoles(roles, roleByAlias) {
    const configuredRoles = roles.trustedAdvisor ?? roles.advisor.filter(
        role => normalizeToken(role) !== 'advisor',
    );
    const trustedAdvisorRoles = validateStringList(
        configuredRoles,
        'roles.trustedAdvisor',
    ).map(normalizeToken);
    if (new Set(trustedAdvisorRoles).size !== trustedAdvisorRoles.length) {
        throw new SubagentModelPolicyError('roles.trustedAdvisor must be unique');
    }
    if (trustedAdvisorRoles.some(role => roleByAlias.get(role) !== 'advisor')) {
        throw new SubagentModelPolicyError('roles.trustedAdvisor must name advisor roles');
    }
    return new Set(trustedAdvisorRoles);
}

function validateApprovedPairs(rawPairs, modelByName, effortNames, roleByAlias) {
    if (!Array.isArray(rawPairs) || rawPairs.length === 0) {
        throw new SubagentModelPolicyError('approvedPairs must be a non-empty array');
    }
    const pairs = [];
    const pairScopes = new Set();
    for (const rawPair of rawPairs) {
        const pair = validatePair(rawPair, modelByName, effortNames, 'approvedPairs entry');
        const roles = rawPair.roles === undefined || rawPair.roles === null
            ? null
            : validateCanonicalRoles(rawPair.roles, roleByAlias, 'approved pair roles');
        const scopeKey = `${pairKey(pair)}|${roles ? roles.join(',') : '*'}`;
        if (pairScopes.has(scopeKey)) throw new SubagentModelPolicyError(`duplicate pair key: ${scopeKey}`);
        pairScopes.add(scopeKey);
        pairs.push({ ...pair, roles });
    }
    return pairs;
}

function validateSelectorExclusions(rawExclusions, modelByName, effortNames) {
    if (!Array.isArray(rawExclusions)) {
        throw new SubagentModelPolicyError('selectorExclusions must be an array');
    }
    const exclusionKeys = new Set();
    for (const rawExclusion of rawExclusions) {
        const exclusion = validatePair(
            rawExclusion,
            modelByName,
            effortNames,
            'selectorExclusions entry',
        );
        const key = pairKey(exclusion);
        if (exclusionKeys.has(key)) {
            throw new SubagentModelPolicyError(`duplicate selector exclusion: ${key}`);
        }
        exclusionKeys.add(key);
    }
    return exclusionKeys;
}

function validateReplacements(rawReplacements, modelByName, effortNames, approvedPairs, label) {
    if (!Array.isArray(rawReplacements)) throw new SubagentModelPolicyError(`${label} must be an array`);
    const replacements = new Map();
    for (const rawReplacement of rawReplacements) {
        requireObject(rawReplacement, `${label} entry`);
        const requested = validatePair(rawReplacement.requested, modelByName, effortNames, `${label} requested`);
        const selected = validatePair(rawReplacement.selected, modelByName, effortNames, `${label} selected`);
        const key = pairKey(requested);
        if (replacements.has(key)) throw new SubagentModelPolicyError(`ambiguous replacement: ${key}`);
        if (!isPairApproved(selected, null, approvedPairs)) {
            throw new SubagentModelPolicyError(`replacement target is not approved: ${pairKey(selected)}`);
        }
        replacements.set(key, selected);
    }
    return replacements;
}

function validateRoleReplacements(rawReplacements, modelByName, effortNames, approvedPairs, roleByAlias) {
    if (!Array.isArray(rawReplacements)) throw new SubagentModelPolicyError('roleReplacements must be an array');
    const replacements = new Map();
    for (const rawReplacement of rawReplacements) {
        requireObject(rawReplacement, 'roleReplacements entry');
        const role = canonicalRole(rawReplacement.role, roleByAlias, 'role replacement role');
        const requested = validatePair(rawReplacement.requested, modelByName, effortNames, 'role replacement requested');
        const selected = validatePair(rawReplacement.selected, modelByName, effortNames, 'role replacement selected');
        const key = `${role}|${pairKey(requested)}`;
        if (replacements.has(key)) throw new SubagentModelPolicyError(`ambiguous role replacement: ${key}`);
        if (!isPairApproved(selected, role, approvedPairs)) {
            throw new SubagentModelPolicyError(`role replacement target is not approved: ${key}`);
        }
        replacements.set(key, selected);
    }
    return replacements;
}

function validateReplacementGraph(replacements, roleReplacements, approvedPairKeys) {
    const baseKeys = new Set(replacements.keys());
    for (const [key] of roleReplacements) {
        const pair = key.slice(key.indexOf('|') + 1);
        if (baseKeys.has(pair)) throw new SubagentModelPolicyError(`ambiguous role replacement: ${key}`);
    }
    for (const role of ['worker', 'advisor']) {
        const graph = new Map(replacements);
        for (const [key, selected] of roleReplacements) {
            if (key.startsWith(`${role}|`)) graph.set(key.slice(role.length + 1), selected);
        }
        for (const [requestedKey, selected] of graph) {
            const selectedKey = pairKey(selected);
            if (!approvedPairKeys.has(selectedKey)) {
                throw new SubagentModelPolicyError(`replacement target is not approved: ${selectedKey}`);
            }
            const visited = new Set();
            let currentKey = requestedKey;
            while (graph.has(currentKey)) {
                if (visited.has(currentKey)) {
                    throw new SubagentModelPolicyError(`replacement cycle includes: ${currentKey}`);
                }
                visited.add(currentKey);
                currentKey = pairKey(graph.get(currentKey));
            }
            if (visited.size > 1) {
                throw new SubagentModelPolicyError(`replacement destination is not terminal: ${requestedKey}`);
            }
        }
    }
}

function validatePair(rawPair, modelByName, effortNames, label) {
    requireObject(rawPair, label);
    const model = normalizeToken(rawPair.model);
    const effort = normalizeToken(rawPair.effort);
    if (!Object.hasOwn(modelByName, model)) throw new SubagentModelPolicyError(`${label} has unknown model: ${model}`);
    if (!effortNames.has(effort)) throw new SubagentModelPolicyError(`${label} has unknown effort: ${effort}`);
    return { model, effort };
}

function validateCanonicalRoles(rawRoles, roleByAlias, label) {
    if (!Array.isArray(rawRoles) || rawRoles.length === 0) throw new SubagentModelPolicyError(`${label} must be a non-empty array`);
    const roles = rawRoles.map(role => canonicalRole(role, roleByAlias, label));
    if (new Set(roles).size !== roles.length) throw new SubagentModelPolicyError(`${label} must be unique`);
    return roles;
}

function canonicalRole(rawRole, roleByAlias, label) {
    const normalizedRole = normalizeToken(rawRole);
    const role = roleByAlias.get(normalizedRole);
    if (!role) throw new SubagentModelPolicyError(`${label} is unknown: ${normalizedRole}`);
    return role;
}

function resolveRole(request, policy) {
    const suppliedRoles = ROLE_FIELDS
        .filter(field => Object.hasOwn(request, field))
        .map(field => request[field]);
    if (suppliedRoles.length === 0) return { status: 'pass', role: policy.roleByAlias.get(DEFAULT_ROLE) };
    if (suppliedRoles.some(role => typeof role !== 'string' || role.trim() === '')) {
        return blockedRoute('role must be a non-empty string');
    }
    const canonicalRoles = suppliedRoles.map(role => policy.roleByAlias.get(normalizeToken(role)));
    if (canonicalRoles.some(role => !role) || new Set(canonicalRoles).size !== 1) {
        return blockedRoute('role is unknown or ambiguous');
    }
    return { status: 'pass', role: canonicalRoles[0] };
}

function hasTrustedAdvisorSession(policy, options) {
    const metadata = options.trustedSessionMetadata;
    if (!isObject(metadata) || metadata.authorized !== true) return false;
    return typeof metadata.registeredAgentType === 'string'
        && policy.trustedAdvisorRoles.has(normalizeToken(metadata.registeredAgentType));
}

function readModel(request, policy) {
    if (!Object.hasOwn(request, MODEL_FIELD) || request[MODEL_FIELD] === null) {
        return { modelName: null, inherited: true, wasAlias: false, wasMissing: true };
    }
    if (typeof request[MODEL_FIELD] !== 'string' || request[MODEL_FIELD].trim() === '') {
        return blockedRoute('model must be a non-empty string');
    }
    const normalizedModel = normalizeToken(request[MODEL_FIELD]);
    if (policy.inheritanceAliases.has(normalizedModel)) {
        return { modelName: null, inherited: true, wasAlias: true, wasMissing: false };
    }
    const modelName = policy.modelByName.aliasOwner.get(normalizedModel);
    if (!modelName) return blockedRoute(`model is unknown: ${request[MODEL_FIELD]}`);
    return {
        modelName,
        inherited: false,
        wasAlias: request[MODEL_FIELD] !== policy.modelByName[modelName].id,
        wasMissing: false,
    };
}

function readEffort(request, policy) {
    const suppliedFields = EFFORT_FIELDS.filter(field => Object.hasOwn(request, field));
    if (suppliedFields.length > 1) {
        return blockedRoute('effort fields are ambiguous');
    }
    const field = suppliedFields[0] ?? null;
    if (field === null || request[field] === null) {
        return { status: 'pass', effort: null, field, wasAlias: false, wasMissing: true };
    }
    if (typeof request[field] !== 'string' || request[field].trim() === '') {
        return blockedRoute('effort must be a non-empty string');
    }
    const normalizedEffort = normalizeToken(request[field]);
    const canonicalEffort = policy.effortNames.has(normalizedEffort)
        ? normalizedEffort
        : resolveEffortAlias(normalizedEffort, policy);
    if (!canonicalEffort) return blockedRoute(`effort is unknown: ${request[field]}`);
    return {
        status: 'pass',
        effort: canonicalEffort,
        field,
        wasAlias: request[field] !== canonicalEffort,
        wasMissing: false,
    };
}

function resolveEffortAlias(rawEffort, policy) {
    const aliases = policy.efforts.aliases;
    const target = aliases[rawEffort];
    return typeof target === 'string' && policy.effortNames.has(target) ? target : null;
}

function selectReplacement(requestedPair, role, policy) {
    const roleReplacement = policy.roleReplacements.get(`${role}|${pairKey(requestedPair)}`);
    if (roleReplacement) return roleReplacement;
    const replacement = policy.replacements.get(pairKey(requestedPair));
    if (replacement) return replacement;
    return isPairApproved(requestedPair, role, policy.approvedPairs) ? requestedPair : null;
}

function isPairApproved(pair, role, approvedPairs) {
    return approvedPairs.some(approved => pairKey(approved) === pairKey(pair)
        && (approved.roles === null
            || (role === null && approved.roles.includes('worker') && approved.roles.includes('advisor'))
            || (role !== null && approved.roles.includes(role))));
}

function approvedEffortsForModel(modelName, role, approvedPairs) {
    return [...new Set(approvedPairs
        .filter(pair => pair.model === modelName && (pair.roles === null || pair.roles.includes(role)))
        .map(pair => pair.effort))];
}

function validateAvailability(selectedPair, availableModelIds, policy) {
    if (availableModelIds === undefined) return null;
    if (!Array.isArray(availableModelIds) || availableModelIds.some(model => typeof model !== 'string')) {
        return 'available model ids must be an array of strings';
    }
    const availableNames = new Set();
    for (const rawModel of availableModelIds) {
        const modelName = policy.modelByName.aliasOwner.get(normalizeToken(rawModel));
        if (modelName) availableNames.add(modelName);
    }
    return availableNames.has(selectedPair.model)
        ? null
        : `replacement model is unavailable: ${policy.modelByName[selectedPair.model].id}`;
}

function pairKey(pair) {
    return `${pair.model}/${pair.effort}`;
}

function blockedRoute(diagnostic) {
    return {
        status: 'blocked',
        role: null,
        requested: null,
        selected: null,
        selectedModelName: null,
        effortField: null,
        diagnostic,
    };
}

function requireObject(objectCandidate, label) {
    if (!isObject(objectCandidate)) throw new SubagentModelPolicyError(`${label} must be an object`);
}

function validateStringList(stringEntries, label) {
    if (!Array.isArray(stringEntries) || stringEntries.some(entry => typeof entry !== 'string' || entry.trim() === '')) {
        throw new SubagentModelPolicyError(`${label} must be a non-empty string array`);
    }
    return stringEntries;
}

function requireNonEmptyString(stringCandidate, label) {
    if (typeof stringCandidate !== 'string' || stringCandidate.trim() === '') throw new SubagentModelPolicyError(`${label} must be a non-empty string`);
    return stringCandidate;
}

function normalizeToken(token) {
    return typeof token === 'string' ? token.trim().toLowerCase() : '';
}

function isIdentifier(identifier) {
    return /^[a-z][a-z0-9_-]*$/.test(identifier);
}

function isValidatedPolicy(policy) {
    return isObject(policy) && policy[VALIDATED_POLICY_MARKER] === true;
}

function isObject(objectCandidate) {
    return objectCandidate !== null && typeof objectCandidate === 'object' && !Array.isArray(objectCandidate);
}
