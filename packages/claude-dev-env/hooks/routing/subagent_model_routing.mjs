import { readFileSync, realpathSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { routeSubagentToolInput } from '../../scripts/subagent_model_policy.mjs';

const targetToolName = 'multi_agent_v1__spawn_agent';
const hookEventName = 'PreToolUse';
const defaultBlockingDiagnostic = 'subagent model routing blocked';

export function buildSubagentModelRoutingResponse(hookPayload, routingOptions = {}) {
    if (!isObject(hookPayload)) return buildBlockedResponse('hook input must be an object');
    if (!isTargetSubagentTool(hookPayload)) return {};

    const routeOptions = buildRouteOptions(hookPayload, routingOptions);
    const routingDecision = routeToolInput(hookPayload.tool_input, routeOptions);
    if (routingDecision.status === 'blocked') {
        return buildBlockedResponse(routingDecision.diagnostic);
    }
    if (routingDecision.status !== 'remapped') return {};

    return buildAllowResponse(routingDecision.updatedInput);
}

export function main(serializedInput = readFileSync(0, 'utf8')) {
    let hookPayload;
    try {
        hookPayload = JSON.parse(serializedInput);
    } catch {
        hookPayload = null;
    }

    const hookResponse = hookPayload === null
        ? buildBlockedResponse('hook input is not valid JSON')
        : buildSubagentModelRoutingResponse(hookPayload);
    process.stdout.write(JSON.stringify(hookResponse));
}

function buildRouteOptions(hookPayload, routingOptions) {
    const routeOptions = { ...routingOptions };
    const availableModelIds = routeOptions.availableModelIds
        ?? hookPayload.availableModelIds
        ?? hookPayload.available_model_ids;
    if (availableModelIds !== undefined) routeOptions.availableModelIds = availableModelIds;
    return routeOptions;
}

function routeToolInput(toolInput, routeOptions) {
    return routeSubagentToolInput(toolInput, routeOptions);
}

function isTargetSubagentTool(hookPayload) {
    return hookPayload.tool_name === targetToolName;
}

function buildAllowResponse(updatedInput) {
    return {
        hookSpecificOutput: {
            hookEventName,
            permissionDecision: 'allow',
            updatedInput,
        },
    };
}

function buildBlockedResponse(diagnostic) {
    return {
        hookSpecificOutput: {
            hookEventName,
            permissionDecision: 'deny',
            permissionDecisionReason: diagnostic || defaultBlockingDiagnostic,
        },
    };
}

function isObject(candidate) {
    return candidate !== null && typeof candidate === 'object' && !Array.isArray(candidate);
}

if (process.argv[1] && realpathSync(process.argv[1]) === realpathSync(fileURLToPath(import.meta.url))) {
    main();
}
