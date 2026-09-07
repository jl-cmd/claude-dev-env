import { test } from 'node:test';
import { strict as assert } from 'node:assert';

import {
    expandHomeDirectoryTokens,
    expandHomeDirectoryTokensInSettings,
} from './expand_home_directory_tokens.mjs';


test('expandHomeDirectoryTokens expands $HOME, ${HOME}, and ~/', () => {
    assert.equal(
        expandHomeDirectoryTokens(
            'python $HOME/.claude/hooks/session/fix_worktree_hookspath.py',
            'C:\\Users\\x',
        ),
        'python C:/Users/x/.claude/hooks/session/fix_worktree_hookspath.py',
    );
    assert.equal(
        expandHomeDirectoryTokens('python ${HOME}/.claude/hooks/a.py', '/home/x'),
        'python /home/x/.claude/hooks/a.py',
    );
    assert.equal(
        expandHomeDirectoryTokens('python ~/.claude/hooks/a.py', '/home/x'),
        'python /home/x/.claude/hooks/a.py',
    );
    assert.equal(
        expandHomeDirectoryTokens('echo $HOMEPATH', 'C:/Users/x'),
        'echo $HOMEPATH',
    );
});


test('expandHomeDirectoryTokens inserts dollar characters in home paths literally', () => {
    const homeWithReplaceMetacharacters = 'C:/Users/$&evil$1';
    assert.equal(
        expandHomeDirectoryTokens('python $HOME/.claude/a.py', homeWithReplaceMetacharacters),
        'python C:/Users/$&evil$1/.claude/a.py',
    );
    assert.equal(
        expandHomeDirectoryTokens('python ${HOME}/.claude/a.py', homeWithReplaceMetacharacters),
        'python C:/Users/$&evil$1/.claude/a.py',
    );
    assert.equal(
        expandHomeDirectoryTokens('python ~/.claude/a.py', homeWithReplaceMetacharacters),
        'python C:/Users/$&evil$1/.claude/a.py',
    );
});


test('expandHomeDirectoryTokens expands ${HOME} before $HOME so braces stay intact', () => {
    assert.equal(
        expandHomeDirectoryTokens('python ${HOME}/.claude/a.py', '/home/x'),
        'python /home/x/.claude/a.py',
    );
});


test('expandHomeDirectoryTokens strips trailing slashes from the home directory', () => {
    assert.equal(
        expandHomeDirectoryTokens('python $HOME/.claude/a.py', 'C:/Users/x/'),
        'python C:/Users/x/.claude/a.py',
    );
});


test('expandHomeDirectoryTokensInSettings skips non-array hook event values', () => {
    const settings = {
        hooks: {
            SessionStart: 'not-an-array',
            PreToolUse: [
                {
                    matcher: 'Write',
                    hooks: [{ type: 'command', command: 'python $HOME/.claude/hooks/a.py' }],
                },
            ],
        },
    };
    expandHomeDirectoryTokensInSettings(settings, 'C:/Users/x');
    assert.equal(settings.hooks.SessionStart, 'not-an-array');
    assert.equal(
        settings.hooks.PreToolUse[0].hooks[0].command,
        'python C:/Users/x/.claude/hooks/a.py',
    );
});


test('expandHomeDirectoryTokensInSettings rewrites hooks and statusLine', () => {
    const settings = {
        hooks: {
            SessionStart: [
                {
                    matcher: '',
                    hooks: [
                        {
                            type: 'command',
                            command: 'python $HOME/.claude/hooks/session/fix_worktree_hookspath.py',
                        },
                    ],
                },
            ],
        },
        statusLine: {
            type: 'command',
            command: 'python "$HOME/.claude/statusline-command.py"',
        },
    };
    expandHomeDirectoryTokensInSettings(settings, 'C:/Users/x');
    assert.equal(
        settings.hooks.SessionStart[0].hooks[0].command,
        'python C:/Users/x/.claude/hooks/session/fix_worktree_hookspath.py',
    );
    assert.equal(
        settings.statusLine.command,
        'python "C:/Users/x/.claude/statusline-command.py"',
    );
});


test('expandHomeDirectoryTokens expands a tilde path that follows a semicolon or an opening parenthesis', () => {
    assert.equal(
        expandHomeDirectoryTokens('cd /repo;~/.claude/hooks/x.py', '/home/x'),
        'cd /repo;/home/x/.claude/hooks/x.py',
    );
    assert.equal(
        expandHomeDirectoryTokens('(~/.claude/hooks/x.py)', '/home/x'),
        '(/home/x/.claude/hooks/x.py)',
    );
});
