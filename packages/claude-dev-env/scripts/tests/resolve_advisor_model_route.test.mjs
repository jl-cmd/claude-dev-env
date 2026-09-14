import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const scriptPath = fileURLToPath(new URL('../resolve_advisor_model_route.mjs', import.meta.url));

function runBridge(input) {
    return spawnSync(process.execPath, [scriptPath], {
        input,
        encoding: 'utf8',
    });
}

test('advisor bridge selects the policy default', () => {
    const result = runBridge(JSON.stringify({ reasoning_effort: 'xhigh' }));
    assert.equal(result.status, 0);
    assert.deepEqual(JSON.parse(result.stdout).selected, {
        model: 'gpt-6-astra',
        effort: 'medium',
    });
});

test('advisor bridge blocks malformed JSON', () => {
    const result = runBridge('{');
    assert.equal(result.status, 1);
    assert.deepEqual(JSON.parse(result.stdout), {
        status: 'blocked',
        diagnostic: 'advisor route input is not valid JSON',
    });
});
