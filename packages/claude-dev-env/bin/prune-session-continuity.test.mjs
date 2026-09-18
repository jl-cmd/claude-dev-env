import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { join } from 'node:path';
import {
    continuityHostConfigurationPaths,
    isContinuityHookCommand,
    removeContinuityHooks,
} from './prune-session-continuity.mjs';

const ROOTS = {
    managedRoot: join('/managed', '.claude'),
    codexRulesInstallDirectory: join('/managed', '.codex', 'rules'),
    cursorInstallDirectory: join('/managed', '.cursor'),
};

const COMPANION_COMMAND = 'node "/managed/.agents/skills/session-continuity/continuity.mjs" hook claude';

test('a companion command is recognized and another hook command is not', () => {
    assert.equal(isContinuityHookCommand(COMPANION_COMMAND), true);
    assert.equal(isContinuityHookCommand('node "/managed/.agents/hooks/routing/other.mjs"'), false);
    assert.equal(isContinuityHookCommand(undefined), false);
});

test('each host names the configuration file that holds its registrations', () => {
    assert.deepEqual(continuityHostConfigurationPaths(ROOTS), {
        claude: join('/managed', '.claude', 'settings.json'),
        codex: join('/managed', '.codex', 'hooks.json'),
        cursor: join('/managed', '.cursor', 'hooks.json'),
    });
});

test('a grouped registration is removed and the sibling hook stays', () => {
    const configuration = {
        hooks: {
            SessionStart: [{
                matcher: 'startup',
                hooks: [
                    { type: 'command', command: COMPANION_COMMAND },
                    { type: 'command', command: 'node "/managed/.agents/hooks/keep.mjs"' },
                ],
            }],
        },
    };
    assert.equal(removeContinuityHooks(configuration), 1);
    assert.deepEqual(configuration.hooks.SessionStart[0].hooks, [
        { type: 'command', command: 'node "/managed/.agents/hooks/keep.mjs"' },
    ]);
});

test('an event left with no entries is dropped rather than left empty', () => {
    const configuration = {
        hooks: {
            UserPromptExpansion: [{ hooks: [{ type: 'command', command: COMPANION_COMMAND }] }],
        },
    };
    assert.equal(removeContinuityHooks(configuration), 1);
    assert.deepEqual(configuration.hooks, {});
});

test("Cursor's flat entry shape is removed the same way", () => {
    const configuration = { version: 1, hooks: { sessionStart: [{ command: COMPANION_COMMAND }] } };
    assert.equal(removeContinuityHooks(configuration), 1);
    assert.deepEqual(configuration.hooks, {});
});

test('a configuration holding no registration is left untouched', () => {
    const configuration = { hooks: { SessionStart: [{ hooks: [{ command: 'node "/keep.mjs"' }] }] } };
    assert.equal(removeContinuityHooks(configuration), 0);
    assert.deepEqual(configuration.hooks.SessionStart, [{ hooks: [{ command: 'node "/keep.mjs"' }] }]);
});
