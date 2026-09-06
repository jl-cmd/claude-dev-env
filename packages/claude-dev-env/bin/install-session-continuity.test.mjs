import assert from 'node:assert/strict';
import test from 'node:test';
import { continuityHookConfiguration, mergeContinuityHooks } from './install-session-continuity.mjs';

test('setup preserves other hooks and settings, is idempotent, and rejects competing profiles', () => {
    const existing = { permissions: { deny: ['secret'] }, hooks: { SessionStart: [{ hooks: [{ type: 'command', command: 'existing-hook' }] }] } };
    const script = '/home/jon/.agents/skills/session-continuity/continuity.mjs';
    const first = mergeContinuityHooks(existing, 'claude', script);
    assert.deepEqual(mergeContinuityHooks(first, 'claude', script), first);
    assert.deepEqual(first.permissions, existing.permissions);
    assert.equal(first.hooks.SessionStart[0].hooks[0].command, 'existing-hook');
    assert.equal(existing.hooks.SessionStart.length, 1);
    assert.throws(() => mergeContinuityHooks(first, 'claude', '/other/session-continuity/continuity.mjs'), /Another continuity installation/);
    assert.throws(() => continuityHookConfiguration('claude', '/path/with$expansion/continuity.mjs'), /expansion/);
});

test('Cursor setup refuses an unsupported automatic activation claim without changing config', () => {
    const existing = { version: 1, hooks: { beforeSubmitPrompt: [{ command: 'existing' }] } };
    const before = JSON.stringify(existing);
    assert.throws(() => mergeContinuityHooks(existing, 'cursor', '/skill/continuity.mjs'), /beforeSubmitPrompt has no agent-context output/);
    assert.equal(JSON.stringify(existing), before);
});

for (const host of ['claude', 'codex']) {
    test(`${host}: setup registers only documented context-loading events`, () => {
        const configuration = continuityHookConfiguration(host, '/home/jon/.agents/skills/session-continuity/continuity.mjs');
        const expected = host === 'claude'
            ? ['UserPromptSubmit', 'UserPromptExpansion', 'SessionStart']
            : ['UserPromptSubmit', 'SessionStart'];
        assert.deepEqual(Object.keys(configuration), expected);
        for (const groups of Object.values(configuration)) {
            assert.equal(groups.length, 1);
            assert.equal(groups[0].hooks[0].type, 'command');
            assert.equal(groups[0].hooks[0].command, `node "/home/jon/.agents/skills/session-continuity/continuity.mjs" hook ${host}`);
        }
        assert.equal(new RegExp(configuration.SessionStart[0].matcher).test('compact'), true);
        if (host === 'claude') {
            assert.equal(new RegExp(configuration.UserPromptExpansion[0].matcher).test('pstack:poteto-mode'), true);
            assert.equal(new RegExp(configuration.UserPromptExpansion[0].matcher).test('explain-poteto-mode'), false);
        }
    });
}
