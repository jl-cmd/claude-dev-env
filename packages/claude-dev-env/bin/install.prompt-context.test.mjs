import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { readFileSync } from 'node:fs';

import { mergeHooksIntoSettings } from './install.mjs';

test('reinstall replaces both prompt hooks with one ordered context hook', () => {
    const hooksConfig = JSON.parse(readFileSync(new URL('../hooks/hooks.json', import.meta.url), 'utf8'));
    const userCommand = 'python C:/Users/example/hooks/user_hook.py';
    const settings = {
        hooks: {
            UserPromptSubmit: [
                {
                    matcher: '',
                    hooks: [
                        { type: 'command', command: userCommand },
                        {
                            type: 'command',
                            command: 'python C:/Users/example/.claude/hooks/session/style_reminder_prompt.py',
                        },
                        {
                            type: 'command',
                            command: 'python C:/Users/example/.claude/hooks/session/skill_loaded_reminder.py',
                        },
                    ],
                },
            ],
        },
    };

    mergeHooksIntoSettings(settings, hooksConfig, 'C:/Users/example/.claude', 'python');

    const userPromptHooks = settings.hooks.UserPromptSubmit.flatMap(eachGroup => eachGroup.hooks);
    assert.equal(userPromptHooks.length, 2);
    assert.equal(userPromptHooks[0].command, userCommand);
    assert.match(userPromptHooks[1].command, /style_reminder_prompt\.py --include-skill-reminder$/);
    assert.doesNotMatch(userPromptHooks[1].command, /skill_loaded_reminder/);

    const firstMerge = JSON.stringify(settings);
    mergeHooksIntoSettings(settings, hooksConfig, 'C:/Users/example/.claude', 'python');
    assert.equal(JSON.stringify(settings), firstMerge);
});
