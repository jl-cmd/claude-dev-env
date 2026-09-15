import assert from 'node:assert/strict';
import test from 'node:test';
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import {
    configureContinuityHosts,
    continuityHookConfiguration,
    mergeContinuityHooks,
    removeContinuityHooks,
} from './install-session-continuity.mjs';

function installRootFixture() {
    const root = mkdtempSync(join(tmpdir(), 'continuity-roots-'));
    const skillsInstallDirectory = join(root, 'agents', 'skills');
    const companionDirectory = join(skillsInstallDirectory, 'session-continuity');
    mkdirSync(companionDirectory, { recursive: true });
    writeFileSync(join(companionDirectory, 'continuity.mjs'), 'export default null;\n');
    writeFileSync(join(companionDirectory, 'SKILL.md'), '# companion\n');
    const managedRoot = join(root, 'claude');
    const codexRulesInstallDirectory = join(root, 'codex', 'rules');
    const cursorInstallDirectory = join(root, 'cursor');
    for (const directory of [managedRoot, codexRulesInstallDirectory, cursorInstallDirectory]) {
        mkdirSync(directory, { recursive: true });
    }
    return { managedRoot, skillsInstallDirectory, codexRulesInstallDirectory, cursorInstallDirectory };
}

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

test('Cursor setup keeps other hooks, sets the file version, and stays idempotent', () => {
    const existing = { hooks: { beforeShellExecution: [{ command: 'existing' }] } };
    const script = '/home/jon/.agents/skills/session-continuity/continuity.mjs';
    const first = mergeContinuityHooks(existing, 'cursor', script);
    assert.equal(first.version, 1);
    assert.equal(first.hooks.beforeShellExecution[0].command, 'existing');
    assert.deepEqual(mergeContinuityHooks(first, 'cursor', script), first);
    assert.equal(existing.hooks.beforeShellExecution.length, 1);
    assert.throws(() => mergeContinuityHooks(first, 'cursor', '/other/session-continuity/continuity.mjs'), /Another continuity installation/);
});

test('Cursor setup registers only documented context-carrying events', () => {
    const configuration = continuityHookConfiguration('cursor', '/home/jon/.agents/skills/session-continuity/continuity.mjs');
    assert.deepEqual(Object.keys(configuration), ['sessionStart', 'beforeSubmitPrompt', 'preCompact', 'postToolUse']);
    for (const entries of Object.values(configuration)) {
        assert.equal(entries.length, 1);
        assert.equal(entries[0].command, 'node "/home/jon/.agents/skills/session-continuity/continuity.mjs" hook cursor');
    }
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

test('configureContinuityHosts writes each host config, reads it back, and repeats without a change', () => {
    const roots = installRootFixture();
    const settingsPath = join(roots.managedRoot, 'settings.json');
    writeFileSync(settingsPath, JSON.stringify({ permissions: { deny: ['secret'] } }, null, 2) + '\n');
    const first = configureContinuityHosts(roots, ['claude', 'codex', 'cursor']);
    assert.deepEqual(first.map(result => result.changed), [true, true, true]);
    const written = JSON.parse(readFileSync(settingsPath, 'utf8'));
    assert.deepEqual(written.permissions.deny, ['secret']);
    const command = written.hooks.SessionStart[0].hooks[0].command;
    assert.equal(command.endsWith('session-continuity/continuity.mjs" hook claude'), true);
    const second = configureContinuityHosts(roots, ['claude', 'codex', 'cursor']);
    assert.deepEqual(second.map(result => result.changed), [false, false, false]);
});

test('removeContinuityHooks takes out only the companion registrations', () => {
    const roots = installRootFixture();
    configureContinuityHosts(roots, ['claude']);
    const settingsPath = join(roots.managedRoot, 'settings.json');
    const settings = JSON.parse(readFileSync(settingsPath, 'utf8'));
    settings.hooks.SessionStart.unshift({ hooks: [{ type: 'command', command: 'python other_hook.py' }] });
    const removedCount = removeContinuityHooks(settings);
    assert.equal(removedCount, 3);
    assert.deepEqual(Object.keys(settings.hooks), ['SessionStart']);
    assert.equal(settings.hooks.SessionStart.length, 1);
    assert.equal(settings.hooks.SessionStart[0].hooks[0].command, 'python other_hook.py');
});
