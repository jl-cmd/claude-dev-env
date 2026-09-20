import { readFileSync } from 'node:fs';

import { resolveSubagentModelRoute } from './subagent_model_policy.mjs';

function blockedRoute(diagnostic) {
    return { status: 'blocked', diagnostic };
}

function isObject(objectCandidate) {
    return objectCandidate !== null && typeof objectCandidate === 'object' && !Array.isArray(objectCandidate);
}

function validatePolicyPath(input) {
    if (!Object.hasOwn(input, 'policyPath')) return null;
    if (typeof input.policyPath !== 'string' || input.policyPath.trim() === '') {
        return 'advisor route policyPath must be a non-empty string';
    }
    return null;
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
        const routingInputIssue = validatePolicyPath(input);
        routingDecision = routingInputIssue
            ? blockedRoute(routingInputIssue)
            : resolveSubagentModelRoute({
                agent_type: 'advisor',
                ...(input.model !== undefined && input.model !== null ? { model: input.model } : {}),
                ...(input.reasoning_effort !== undefined ? { reasoning_effort: input.reasoning_effort } : {}),
            }, {
                policyPath: input.policyPath,
                trustedSessionMetadata: {
                    authorized: true,
                    registeredAgentType: 'advisor',
                },
            });
    }
    process.stdout.write(JSON.stringify(routingDecision));
    if (routingDecision.status === 'blocked') process.exitCode = 1;
}
