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
    const route = blockedRoute('advisor route input is not valid JSON');
    process.stdout.write(JSON.stringify(route));
    process.exitCode = 1;
}

if (input !== undefined) {
    const route = !isObject(input)
        ? blockedRoute('advisor route input must be an object')
        : resolveSubagentModelRoute({
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
    process.stdout.write(JSON.stringify(route));
    if (route.status === 'blocked') process.exitCode = 1;
}
