import { readFileSync } from 'node:fs';

import { resolveSubagentModelRoute } from './subagent_model_policy.mjs';

function blockedRoute(diagnostic) {
    return { status: 'blocked', diagnostic };
}

function isObject(value) {
    return value !== null && typeof value === 'object' && !Array.isArray(value);
}

let input;
try {
    input = JSON.parse(readFileSync(0, 'utf8'));
} catch {
    const routingDecision = blockedRoute('advisor route input is not valid JSON');
    process.stdout.write(JSON.stringify(routingDecision));
    process.exitCode = 1;
}

if (input !== undefined) {
    let routingDecision;
    if (!isObject(input)) {
        routingDecision = blockedRoute('advisor route input must be an object');
    } else {
        routingDecision = resolveSubagentModelRoute({
            agent_type: 'session-advisor',
            ...(input.model !== undefined && input.model !== null ? { model: input.model } : {}),
            ...(input.reasoning_effort !== undefined ? { reasoning_effort: input.reasoning_effort } : {}),
        }, {
            policyPath: input.policyPath,
            trustedSessionMetadata: {
                authorized: true,
                registeredAgentType: 'session-advisor',
            },
        });
    }
    process.stdout.write(JSON.stringify(routingDecision));
    if (routingDecision.status === 'blocked') process.exitCode = 1;
}
