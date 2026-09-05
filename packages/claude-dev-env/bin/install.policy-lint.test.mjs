import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
    FOLDED_HOOK_RELATIVE_PATHS,
    mergeHooksIntoSettings,
} from './install.mjs';

const allRetiredWriteHooks = [
    'blocking/code_rules_enforcer.py',
    'blocking/tdd_enforcer.py',
    'blocking/windows_rmtree_blocker.py',
    'blocking/state_description_blocker.py',
    'blocking/subprocess_budget_completeness.py',
    'blocking/hook_prose_detector_consistency.py',
    'blocking/workflow_substitution_slot_blocker.py',
];
const sourceHooks = JSON.parse(readFileSync(new URL('../hooks/hooks.json', import.meta.url), 'utf8'));
const installedRoot = '/fixture-home/.claude';
const foreignCommand = 'python /unmanaged/keep_this_hook.py';
const foreignSessionCommand = 'node /unmanaged/session.js';

function legacySettings() {
    return {
        permissions: { allow: ['Read'] },
        hooks: {
            PreToolUse: [{
                matcher: 'Write|Edit|MultiEdit|apply_patch',
                hooks: [
                    { type: 'command', command: foreignCommand, timeout: 17 },
                    ...allRetiredWriteHooks.map(relativePath => ({
                        type: 'command',
                        command: `python ${installedRoot}/hooks/${relativePath}`,
                        timeout: 10,
                    })),
                ],
            }],
            SessionStart: [{
                matcher: '',
                hooks: [{ type: 'command', command: foreignSessionCommand, timeout: 9 }],
            }],
        },
    };
}

function allCommands(settings) {
    return Object.values(settings.hooks).flatMap(groups =>
        groups.flatMap(group => group.hooks.map(hook => hook.command)));
}

test('every retired write registration already has an installer-owned prune path', () => {
    for (const relativePath of allRetiredWriteHooks) {
        assert.ok(FOLDED_HOOK_RELATIVE_PATHS.has(relativePath), relativePath);
    }
});

test('upgrade prunes legacy direct file checks while retaining foreign hooks', () => {
    const settings = legacySettings();
    mergeHooksIntoSettings(settings, sourceHooks, installedRoot, 'python3');
    const commands = allCommands(settings);
    for (const relativePath of allRetiredWriteHooks) {
        assert.ok(!commands.some(command => command.includes(relativePath)), relativePath);
    }
    assert.ok(commands.includes(foreignCommand));
    assert.ok(commands.includes(foreignSessionCommand));
    assert.deepEqual(settings.permissions, { allow: ['Read'] });
    assert.ok(commands.some(command => command.includes('/blocking/pre_tool_use_dispatcher.py')));
    assert.ok(commands.some(command => command.includes('/blocking/bash_pre_tool_use_dispatcher.py')));
});

test('reinstall does not restore retired direct checks or duplicate foreign hooks', () => {
    const settings = legacySettings();
    mergeHooksIntoSettings(settings, sourceHooks, installedRoot, 'python3');
    const firstInstall = structuredClone(settings);
    mergeHooksIntoSettings(settings, sourceHooks, installedRoot, 'python3');
    assert.deepEqual(settings, firstInstall);
    assert.equal(allCommands(settings).filter(command => command === foreignCommand).length, 1);
});
