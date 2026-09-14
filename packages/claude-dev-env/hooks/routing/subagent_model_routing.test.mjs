import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

import { buildSubagentModelRoutingResponse } from './subagent_model_routing.mjs';

const targetToolName = 'multi_agent_v1__spawn_agent';

function buildHookPayload(toolInput, metadata = {}) {
    return { tool_name: targetToolName, tool_input: toolInput, ...metadata };
}

test('remaps Terra Medium to Luna Xhigh', () => {
    const hookResponse = buildSubagentModelRoutingResponse(buildHookPayload({
        model: 'Terra',
        reasoning_effort: 'Medium',
    }));

    assert.equal(hookResponse.hookSpecificOutput.updatedInput.model, 'gpt-5.6-luna');
    assert.equal(
        hookResponse.hookSpecificOutput.updatedInput.reasoning_effort,
        'xhigh',
    );
});

test('emits only the allow response shape after a remap', () => {
    const hookResponse = buildSubagentModelRoutingResponse(buildHookPayload({
        model: 'Terra',
        reasoning_effort: 'medium',
    }));

    assert.deepEqual(Object.keys(hookResponse), ['hookSpecificOutput']);
    assert.deepEqual(Object.keys(hookResponse.hookSpecificOutput), [
        'hookEventName',
        'permissionDecision',
        'updatedInput',
    ]);
    assert.deepEqual(hookResponse.hookSpecificOutput, {
        hookEventName: 'PreToolUse',
        permissionDecision: 'allow',
        updatedInput: {
            model: 'gpt-5.6-luna',
            reasoning_effort: 'xhigh',
        },
    });
});

test('preserves every non-routing tool field', () => {
    const toolInput = {
        assignment: 'preserve',
        message: 'do the work',
        child_permissions: { shell: 'ask' },
        output_contract: ['summary'],
        model: 'Terra',
        reasoning_effort: 'medium',
    };

    const hookResponse = buildSubagentModelRoutingResponse(buildHookPayload(toolInput));

    assert.deepEqual(hookResponse.hookSpecificOutput.updatedInput, {
        assignment: 'preserve',
        message: 'do the work',
        child_permissions: { shell: 'ask' },
        output_contract: ['summary'],
        model: 'gpt-5.6-luna',
        reasoning_effort: 'xhigh',
    });
    assert.deepEqual(toolInput, {
        assignment: 'preserve',
        message: 'do the work',
        child_permissions: { shell: 'ask' },
        output_contract: ['summary'],
        model: 'Terra',
        reasoning_effort: 'medium',
    });
});

test('passes unrelated tool calls through', () => {
    const hookResponse = buildSubagentModelRoutingResponse({
        tool_name: 'Task',
        tool_input: { model: 'Terra', reasoning_effort: 'medium' },
    });

    assert.deepEqual(hookResponse, {});
});

test('blocks malformed policy, unknown input, unavailable replacement, and untrusted advisor roles', () => {
    const malformedPolicyResponse = buildSubagentModelRoutingResponse(
        buildHookPayload({ model: 'Terra', reasoning_effort: 'medium' }),
        { policy: {} },
    );
    const unknownInputResponse = buildSubagentModelRoutingResponse(
        buildHookPayload({ model: 'Unknown', reasoning_effort: 'medium' }),
    );
    const unavailableReplacementResponse = buildSubagentModelRoutingResponse(
        buildHookPayload({ model: 'Terra', reasoning_effort: 'medium' }),
        { availableModelIds: ['gpt-5.6-terra'] },
    );
    const untrustedAdvisorResponse = buildSubagentModelRoutingResponse(
        buildHookPayload({
            agent_type: 'advisor',
            model: 'Astra',
            reasoning_effort: 'medium',
        }),
    );

    const allBlockedResponses = [
        [malformedPolicyResponse, /policy/],
        [unknownInputResponse, /model is unknown/],
        [unavailableReplacementResponse, /replacement model is unavailable/],
        [untrustedAdvisorResponse, /advisor role is not trusted/],
    ];
    for (const [eachBlockedResponse, eachExpectedDiagnostic] of allBlockedResponses) {
        assert.equal(eachBlockedResponse.hookSpecificOutput.permissionDecision, 'deny');
        assert.equal(eachBlockedResponse.hookSpecificOutput.hookEventName, 'PreToolUse');
        assert.equal(typeof eachBlockedResponse.hookSpecificOutput.permissionDecisionReason, 'string');
        assert.match(
            eachBlockedResponse.hookSpecificOutput.permissionDecisionReason,
            eachExpectedDiagnostic,
        );
    }
});

test('allows a registered session advisor with trusted session metadata', () => {
    const hookResponse = buildSubagentModelRoutingResponse(
        buildHookPayload({
            agent_type: 'session-advisor',
            model: 'Astra',
            reasoning_effort: 'high',
        }),
        {
            trustedSessionMetadata: {
                authorized: true,
                registeredAgentType: 'session-advisor',
            },
        },
    );

    assert.deepEqual(hookResponse.hookSpecificOutput.updatedInput, {
        agent_type: 'session-advisor',
        model: 'gpt-6-astra',
        reasoning_effort: 'high',
    });
});

test('a session advisor name without trusted session metadata is blocked', () => {
    const hookResponse = buildSubagentModelRoutingResponse(buildHookPayload({
        agent_type: 'session-advisor',
        model: 'Astra',
        reasoning_effort: 'high',
    }));
    assert.equal(hookResponse.hookSpecificOutput.permissionDecision, 'deny');
    assert.equal(
        hookResponse.hookSpecificOutput.permissionDecisionReason,
        'advisor role is not trusted',
    );
});

test('payload advisor metadata cannot grant advisory authorization', () => {
    const hookResponse = buildSubagentModelRoutingResponse(buildHookPayload(
        {
            agent_type: 'advisor',
            model: 'Astra',
            reasoning_effort: 'high',
        },
        {
            trustedSessionMetadata: {
                authorized: true,
                registeredAgentType: 'advisor',
            },
        },
    ));
    assert.equal(hookResponse.hookSpecificOutput.permissionDecision, 'deny');
    assert.equal(
        hookResponse.hookSpecificOutput.permissionDecisionReason,
        'advisor role is not trusted',
    );
});

test('the installed command blocks an advisor without host metadata', () => {
    const output = execFileSync(
        process.execPath,
        [fileURLToPath(new URL('./subagent_model_routing.mjs', import.meta.url))],
        {
            encoding: 'utf8',
            input: JSON.stringify(buildHookPayload({
                agent_type: 'session-advisor',
                model: 'Astra',
                reasoning_effort: 'high',
            })),
        },
    );
    const hookResponse = JSON.parse(output);
    assert.equal(hookResponse.hookSpecificOutput.permissionDecision, 'deny');
    assert.equal(
        hookResponse.hookSpecificOutput.permissionDecisionReason,
        'advisor role is not trusted',
    );
});

test('keeps a second routing pass unchanged', () => {
    const firstResponse = buildSubagentModelRoutingResponse(buildHookPayload({
        model: 'Terra',
        reasoning_effort: 'medium',
        message: 'keep',
    }));
    const secondResponse = buildSubagentModelRoutingResponse(buildHookPayload(
        firstResponse.hookSpecificOutput.updatedInput,
    ));

    assert.deepEqual(secondResponse, {});
    assert.deepEqual(firstResponse.hookSpecificOutput.updatedInput, {
        model: 'gpt-5.6-luna',
        reasoning_effort: 'xhigh',
        message: 'keep',
    });
});
