import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
    FOLDED_HOOK_RELATIVE_PATHS,
    RETIRED_HOOK_REGISTRATION_RELATIVE_PATHS,
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
const allRetiredPolicyRegistrations = [
    'blocking/plain_language_blocker.py',
    'lifecycle/config_change_guard.py',
    'blocking/docstring_rule_gate_count_blocker.py',
    'blocking/write_existing_file_blocker.py',
    'blocking/sensitive_file_protector.py',
    'blocking/pii_prevention_blocker.py',
    'blocking/duplicate_rmtree_helper_blocker.py',
    'blocking/claude_md_orphan_file_blocker.py',
    'blocking/package_inventory_stale_blocker.py',
    'blocking/env_var_table_code_drift_blocker.py',
    'blocking/pytest_testpaths_orphan_blocker.py',
    'blocking/destructive_command_blocker.py',
    'blocking/shell_substitution_blocker.py',
    'blocking/piped_pytest_blocker.py',
    'blocking/cursor_cli_python_misfire_blocker.py',
    'blocking/unscoped_search_blocker.py',
    'blocking/nas_ssh_binary_enforcer.py',
    'blocking/block_main_commit.py',
    'blocking/session_edit_stage_gate.py',
    'blocking/bash_pre_tool_use_dispatcher.py',
    'blocking/stop_dispatcher.py',
    'blocking/bot_mention_comment_blocker.py',
    'blocking/fable_spawn_gate.py',
    'blocking/luna_fast_mode_gate.py',
    'blocking/orchestrator_refresh_reschedule_gate.py',
    'blocking/ask_user_question_shape_blocker.py',
    'blocking/send_user_file_open_locally_blocker.py',
    'blocking/question_to_user_enforcer.py',
    'blocking/session_handoff_blocker.py',
];
const sourceHooks = JSON.parse(readFileSync(new URL('../hooks/hooks.json', import.meta.url), 'utf8'));
const installedRoot = '/fixture-home/.claude';
const foreignCommand = 'python /unmanaged/keep_this_hook.py';
const foreignSessionCommand = 'node /unmanaged/session.js';

function legacySettings() {
    return {
        permissions: {
            allow: ['Read'],
            deny: ['Bash(git push --force)'],
            ask: ['Bash(git push)'],
        },
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
                    ...allRetiredPolicyRegistrations.map(relativePath => ({
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

test('every retired policy registration has an installer-owned prune path', () => {
    for (const relativePath of allRetiredPolicyRegistrations) {
        assert.ok(RETIRED_HOOK_REGISTRATION_RELATIVE_PATHS.has(relativePath), relativePath);
    }
});

test('upgrade prunes legacy direct file checks while retaining foreign hooks', () => {
    const settings = legacySettings();
    mergeHooksIntoSettings(settings, sourceHooks, installedRoot, 'python3');
    const commands = allCommands(settings);
    for (const relativePath of [...allRetiredWriteHooks, ...allRetiredPolicyRegistrations]) {
        assert.ok(!commands.some(command => command.includes(relativePath)), relativePath);
    }
    assert.ok(commands.includes(foreignCommand));
    assert.ok(commands.includes(foreignSessionCommand));
    assert.deepEqual(settings.permissions, {
        allow: ['Read'],
        deny: ['Bash(git push --force)'],
        ask: ['Bash(git push)'],
    });
    assert.ok(commands.every(command => !command.includes('/blocking/stop_dispatcher.py')));
    assert.ok(commands.some(command => command.includes('/blocking/pre_tool_use_dispatcher.py')));
    assert.ok(commands.every(command => !command.includes('/blocking/bash_pre_tool_use_dispatcher.py')));
});

test('reinstall does not restore retired direct checks or duplicate foreign hooks', () => {
    const settings = legacySettings();
    mergeHooksIntoSettings(settings, sourceHooks, installedRoot, 'python3');
    const firstInstall = structuredClone(settings);
    mergeHooksIntoSettings(settings, sourceHooks, installedRoot, 'python3');
    assert.deepEqual(settings, firstInstall);
    assert.equal(allCommands(settings).filter(command => command === foreignCommand).length, 1);
});
