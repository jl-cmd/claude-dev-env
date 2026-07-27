import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { execFileSync } from 'node:child_process';
import {
    mkdtempSync,
    rmSync,
    mkdirSync,
    writeFileSync,
    symlinkSync,
    readFileSync,
    readdirSync,
    existsSync,
    copyFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { pathToFileURL } from 'node:url';

import {
    collectPackageSourceConflicts,
    CONTENT_DIRECTORIES,
    CORE_INCLUDE_DIRECTORIES,
    CORE_SKILLS,
    INSTALL_GROUPS,
    FOLDED_HOOK_RELATIVE_PATHS,
    POST_FOLDED_HOOK_RELATIVE_PATHS,
    RETIRED_CLAUDE_REVIEW_HOOK_RELATIVE_PATHS,
    pythonCandidatesForPlatform,
    isWindowsStorePythonStub,
    interpreterCommandFromPath,
    invokedAsEntryPoint,
    managedHookScriptRelativePaths,
    managedHookScriptRelativePathsFromSourceRoots,
    commandReferencesManagedHook,
    mergeHooksIntoSettings,
    pruneManagedHooksFromSettings,
    pruneStaleInstalledFiles,
    comparisonKeyForPath,
    collectFiles,
    copyTree,
    caseOnlyRenameSourceName,
    retiredManagedHookRelativePaths,
    pruneRetiredHookEntriesFromSettings,
    retainNewestRunBackupOnly,
} from './install.mjs';
import {
    expandHomeDirectoryTokens,
    expandHomeDirectoryTokensInSettings,
} from './expand_home_directory_tokens.mjs';


function createTemporaryGitRepository() {
    const repositoryRoot = mkdtempSync(join(tmpdir(), 'cdev-installer-validation-'));
    const gitOptions = { cwd: repositoryRoot, stdio: 'ignore' };
    execFileSync('git', ['init', '--initial-branch=main'], gitOptions);
    execFileSync('git', ['config', 'user.email', 'test@example.com'], gitOptions);
    execFileSync('git', ['config', 'user.name', 'Test'], gitOptions);
    execFileSync('git', ['config', 'commit.gpgsign', 'false'], gitOptions);
    execFileSync('git', ['config', 'core.autocrlf', 'false'], gitOptions);
    return repositoryRoot;
}


function commitAllChanges(repositoryRoot, commitMessage) {
    execFileSync('git', ['add', '.'], { cwd: repositoryRoot, stdio: 'ignore' });
    execFileSync('git', ['commit', '-m', commitMessage], {
        cwd: repositoryRoot,
        stdio: 'ignore',
    });
}


function tryMergeAllowingConflict(repositoryRoot, branchName) {
    try {
        execFileSync('git', ['merge', '--no-edit', branchName], {
            cwd: repositoryRoot,
            stdio: 'ignore',
        });
    } catch {
        return;
    }
}


test('collectPackageSourceConflicts returns empty list when working tree is clean', () => {
    const repositoryRoot = createTemporaryGitRepository();
    try {
        const packageDirectory = join(repositoryRoot, 'packages', 'thing');
        mkdirSync(packageDirectory, { recursive: true });
        writeFileSync(join(packageDirectory, 'README.md'), 'hello\n');
        commitAllChanges(repositoryRoot, 'init');

        const conflicts = collectPackageSourceConflicts(packageDirectory);
        assert.deepEqual(conflicts, []);
    } finally {
        rmSync(repositoryRoot, { recursive: true, force: true });
    }
});


test('collectPackageSourceConflicts surfaces both-modified paths under the package directory', () => {
    const repositoryRoot = createTemporaryGitRepository();
    try {
        const packageDirectory = join(repositoryRoot, 'packages', 'thing');
        mkdirSync(packageDirectory, { recursive: true });
        const conflictedFile = join(packageDirectory, 'shared.txt');
        writeFileSync(conflictedFile, 'base content\n');
        commitAllChanges(repositoryRoot, 'base');

        execFileSync('git', ['checkout', '-b', 'branch-a'], { cwd: repositoryRoot, stdio: 'ignore' });
        writeFileSync(conflictedFile, 'a side\n');
        commitAllChanges(repositoryRoot, 'a');

        execFileSync('git', ['checkout', '-b', 'branch-b', 'main'], { cwd: repositoryRoot, stdio: 'ignore' });
        writeFileSync(conflictedFile, 'b side\n');
        commitAllChanges(repositoryRoot, 'b');

        tryMergeAllowingConflict(repositoryRoot, 'branch-a');

        const conflicts = collectPackageSourceConflicts(packageDirectory);
        assert.equal(conflicts.length, 1);
        assert.equal(conflicts[0].statusCode, 'UU');
        assert.match(conflicts[0].path, /shared\.txt/);
    } finally {
        rmSync(repositoryRoot, { recursive: true, force: true });
    }
});


test('collectPackageSourceConflicts ignores conflicts outside the package directory', () => {
    const repositoryRoot = createTemporaryGitRepository();
    try {
        const packageDirectory = join(repositoryRoot, 'packages', 'thing');
        const otherDirectory = join(repositoryRoot, 'packages', 'other');
        mkdirSync(packageDirectory, { recursive: true });
        mkdirSync(otherDirectory, { recursive: true });
        writeFileSync(join(packageDirectory, 'inside.txt'), 'inside\n');
        const otherFile = join(otherDirectory, 'outside.txt');
        writeFileSync(otherFile, 'base outside\n');
        commitAllChanges(repositoryRoot, 'init');

        execFileSync('git', ['checkout', '-b', 'side'], { cwd: repositoryRoot, stdio: 'ignore' });
        writeFileSync(otherFile, 'side change\n');
        commitAllChanges(repositoryRoot, 'side');

        execFileSync('git', ['checkout', 'main'], { cwd: repositoryRoot, stdio: 'ignore' });
        writeFileSync(otherFile, 'main change\n');
        commitAllChanges(repositoryRoot, 'main');

        tryMergeAllowingConflict(repositoryRoot, 'side');

        const conflicts = collectPackageSourceConflicts(packageDirectory);
        assert.deepEqual(conflicts, []);
    } finally {
        rmSync(repositoryRoot, { recursive: true, force: true });
    }
});


test('collectPackageSourceConflicts returns empty when directory is not inside a git repo', () => {
    const standaloneDirectory = mkdtempSync(join(tmpdir(), 'cdev-installer-no-git-'));
    try {
        const conflicts = collectPackageSourceConflicts(standaloneDirectory);
        assert.deepEqual(conflicts, []);
    } finally {
        rmSync(standaloneDirectory, { recursive: true, force: true });
    }
});


test('CONTENT_DIRECTORIES includes _shared so installer copies _shared/pr-loop/ to ~/.claude/_shared/', () => {
    assert.ok(
        CONTENT_DIRECTORIES.includes('_shared'),
        '_shared must be in CONTENT_DIRECTORIES so the installer copies _shared/pr-loop/ alongside skills/',
    );
});


test('core includeDirectories ships _shared and scripts for advisor protocol and CLI fallback', () => {
    assert.ok(
        CORE_INCLUDE_DIRECTORIES.includes('_shared'),
        '_shared must ship with --only core so advisor-protocol.md lands for team-advisor/orchestrator',
    );
    assert.ok(
        CORE_INCLUDE_DIRECTORIES.includes('scripts'),
        'scripts must ship with --only core so claude_chain_runner.py is available for advisor CLI fallback',
    );
});


test('CORE_SKILLS ships issue-tracker so the core group installs the skill the SessionStart injector needs', () => {
    assert.ok(
        CORE_SKILLS.includes('issue-tracker'),
        'issue-tracker must be in CORE_SKILLS so --only core ships it alongside the SessionStart hooks',
    );
    assert.ok(
        INSTALL_GROUPS.core.skills.includes('issue-tracker'),
        'the resolved core group must ship issue-tracker',
    );
    assert.equal(
        INSTALL_GROUPS.core.skills,
        CORE_SKILLS,
        'the core group skills array must read CORE_SKILLS so the two never drift',
    );
});


test('CONTENT_DIRECTORIES includes audit-rubrics so installer copies category rubrics and prompts to ~/.claude/audit-rubrics/', () => {
    assert.ok(
        CONTENT_DIRECTORIES.includes('audit-rubrics'),
        'audit-rubrics must be in CONTENT_DIRECTORIES so bugteam can resolve $HOME/.claude/audit-rubrics/{category_rubrics,prompts}/',
    );
});


test('collectPackageSourceConflicts surfaces both-added and deleted-by-them entries', () => {
    const repositoryRoot = createTemporaryGitRepository();
    try {
        const packageDirectory = join(repositoryRoot, 'packages', 'thing');
        mkdirSync(packageDirectory, { recursive: true });
        writeFileSync(join(packageDirectory, 'shared.txt'), 'base\n');
        writeFileSync(join(packageDirectory, 'about_to_disappear.txt'), 'will be removed\n');
        commitAllChanges(repositoryRoot, 'base');

        execFileSync('git', ['checkout', '-b', 'theirs'], { cwd: repositoryRoot, stdio: 'ignore' });
        rmSync(join(packageDirectory, 'about_to_disappear.txt'));
        writeFileSync(join(packageDirectory, 'fresh.txt'), 'theirs version\n');
        commitAllChanges(repositoryRoot, 'theirs');

        execFileSync('git', ['checkout', '-b', 'ours', 'main'], { cwd: repositoryRoot, stdio: 'ignore' });
        writeFileSync(join(packageDirectory, 'about_to_disappear.txt'), 'ours edit\n');
        writeFileSync(join(packageDirectory, 'fresh.txt'), 'ours version\n');
        commitAllChanges(repositoryRoot, 'ours');

        tryMergeAllowingConflict(repositoryRoot, 'theirs');

        const conflicts = collectPackageSourceConflicts(packageDirectory);
        const allStatusCodes = new Set(conflicts.map(conflictEntry => conflictEntry.statusCode));
        assert.ok(allStatusCodes.has('UD'), `expected UD in ${[...allStatusCodes].join(',')}`);
        assert.ok(allStatusCodes.has('AA'), `expected AA in ${[...allStatusCodes].join(',')}`);
    } finally {
        rmSync(repositoryRoot, { recursive: true, force: true });
    }
});


test('pythonCandidatesForPlatform prefers py -3 ahead of python on win32 so the Microsoft Store stub is never probed first', () => {
    const commands = pythonCandidatesForPlatform('win32').map(candidate => candidate.command);
    assert.equal(commands[0], 'py -3');
    assert.ok(commands.indexOf('py -3') < commands.indexOf('python'));
});


test('pythonCandidatesForPlatform keeps python3 first on non-Windows platforms', () => {
    const commands = pythonCandidatesForPlatform('linux').map(candidate => candidate.command);
    assert.equal(commands[0], 'python3');
});


test('pythonCandidatesForPlatform still offers python as a win32 fallback when py -3 and python3 are absent', () => {
    const commands = pythonCandidatesForPlatform('win32').map(candidate => candidate.command);
    assert.ok(commands.includes('python'));
});


test('isWindowsStorePythonStub flags the Microsoft Store WindowsApps alias paths', () => {
    assert.equal(
        isWindowsStorePythonStub('C:\\Program Files\\WindowsApps\\PythonSoftwareFoundation.Python.3.13_3.13.3824.0_x64__qbz5n2kfra8p0\\python3.13.exe'),
        true,
    );
    assert.equal(
        isWindowsStorePythonStub('C:/Users/example/AppData/Local/Microsoft/WindowsApps/python.exe'),
        true,
    );
});


test('isWindowsStorePythonStub does not flag a real interpreter install path', () => {
    assert.equal(isWindowsStorePythonStub('C:\\Python313\\python.exe'), false);
    assert.equal(isWindowsStorePythonStub('/usr/bin/python3'), false);
});


test('interpreterCommandFromPath forward-slashes a Windows interpreter path and leaves a space-free path unquoted', () => {
    assert.equal(interpreterCommandFromPath('C:\\Python313\\python.exe'), 'C:/Python313/python.exe');
});


test('interpreterCommandFromPath quotes an interpreter path that contains a space', () => {
    assert.equal(
        interpreterCommandFromPath('C:\\Program Files\\Python313\\python.exe'),
        '"C:/Program Files/Python313/python.exe"',
    );
});


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


test('mergeHooksIntoSettings expands residual $HOME in preserved user hooks', () => {
    const hooksConfig = {
        hooks: {
            SessionStart: [
                {
                    matcher: '',
                    hooks: [
                        {
                            type: 'command',
                            command: 'python3 ${CLAUDE_PLUGIN_ROOT}/hooks/session/session_env_cleanup.py',
                        },
                    ],
                },
            ],
        },
    };
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
    };
    mergeHooksIntoSettings(settings, hooksConfig, 'C:/Users/x/.claude', 'C:/Python313/python.exe');
    const allCommands = settings.hooks.SessionStart[0].hooks.map(eachHook => eachHook.command);
    assert.ok(
        allCommands.includes(
            'python C:/Users/x/.claude/hooks/session/fix_worktree_hookspath.py',
        ),
    );
    assert.ok(
        allCommands.includes(
            'C:/Python313/python.exe C:/Users/x/.claude/hooks/session/session_env_cleanup.py',
        ),
    );
    for (const eachCommand of allCommands) {
        assert.equal(eachCommand.includes('$HOME'), false);
        assert.equal(eachCommand.includes('${HOME}'), false);
    }
});


test('mergeHooksIntoSettings inserts dollar characters in plugin root and interpreter literally', () => {
    const pluginRootWithReplaceMetacharacters = 'C:/Users/$&evil$1/.claude';
    const pythonWithReplaceMetacharacters = 'C:/Users/$&evil$1/Python/python.exe';
    const hooksConfig = {
        hooks: {
            SessionStart: [
                {
                    matcher: '',
                    hooks: [
                        {
                            type: 'command',
                            command: 'python3 ${CLAUDE_PLUGIN_ROOT}/hooks/session/session_env_cleanup.py',
                        },
                    ],
                },
            ],
        },
    };
    const settings = {};
    mergeHooksIntoSettings(
        settings,
        hooksConfig,
        pluginRootWithReplaceMetacharacters,
        pythonWithReplaceMetacharacters,
    );
    const rewrittenCommand = settings.hooks.SessionStart[0].hooks[0].command;
    assert.equal(
        rewrittenCommand,
        'C:/Users/$&evil$1/Python/python.exe C:/Users/$&evil$1/.claude/hooks/session/session_env_cleanup.py',
    );
    assert.equal(rewrittenCommand.includes('${CLAUDE_PLUGIN_ROOT}'), false);
});


test('mergeHooksIntoSettings substitutes a quoted absolute interpreter path for the python3 prefix', () => {
    const hooksConfig = {
        hooks: {
            PostToolUse: [
                {
                    matcher: 'Edit',
                    hooks: [{ type: 'command', command: 'python3 ${CLAUDE_PLUGIN_ROOT}/hooks/workflow/auto_formatter.py' }],
                },
            ],
        },
    };
    const settings = {};
    mergeHooksIntoSettings(settings, hooksConfig, 'C:/Users/x/.claude', '"C:/Program Files/Python313/python.exe"');
    assert.equal(
        settings.hooks.PostToolUse[0].hooks[0].command,
        '"C:/Program Files/Python313/python.exe" C:/Users/x/.claude/hooks/workflow/auto_formatter.py',
    );
});


test('mergeHooksIntoSettings prunes a prior py -3 managed hook when reinstalling with an absolute interpreter path', () => {
    const hooksConfig = {
        hooks: {
            PostToolUse: [
                {
                    matcher: 'Edit',
                    hooks: [{ type: 'command', command: 'python3 ${CLAUDE_PLUGIN_ROOT}/hooks/workflow/auto_formatter.py' }],
                },
            ],
        },
    };
    const settings = {
        hooks: {
            PostToolUse: [
                {
                    matcher: 'Edit',
                    hooks: [{ type: 'command', command: 'py -3 C:/Users/x/.claude/hooks/workflow/auto_formatter.py' }],
                },
            ],
        },
    };
    mergeHooksIntoSettings(settings, hooksConfig, 'C:/Users/x/.claude', 'C:/Python313/python.exe');
    assert.deepEqual(
        settings.hooks.PostToolUse[0].hooks.map(hook => hook.command),
        ['C:/Python313/python.exe C:/Users/x/.claude/hooks/workflow/auto_formatter.py'],
    );
});


test('mergeHooksIntoSettings prunes retired Claude review hooks while preserving user hooks', () => {
    const hooksConfig = {
        hooks: {
            PreToolUse: [
                {
                    matcher: 'Bash|PowerShell',
                    hooks: [
                        {
                            command: 'python3 ${CLAUDE_PLUGIN_ROOT}/hooks/blocking/verified_commit_gate.py',
                        },
                    ],
                },
            ],
        },
    };
    const userHookCommand = 'python C:/Users/x/.config/my-hook.py';
    const settings = {
        hooks: {
            PreToolUse: [
                {
                    matcher: 'Bash|PowerShell',
                    hooks: [
                        { command: 'python C:/Users/x/.claude/hooks/blocking/code_review_push_gate.py' },
                        { command: 'python C:/Users/x/.claude/hooks/blocking/code_review_pr_create_gate.py' },
                        { command: 'python C:/Users/x/.claude/hooks/blocking/code_review_stamp_directory_write_blocker.py' },
                        { command: userHookCommand },
                    ],
                },
            ],
        },
    };

    mergeHooksIntoSettings(settings, hooksConfig, 'C:/Users/x/.claude', 'py -3');

    const allCommands = settings.hooks.PreToolUse.flatMap(group => group.hooks.map(hook => hook.command));
    assert.equal(allCommands.some(command => command.includes('code_review_')), false);
    assert.ok(allCommands.includes(userHookCommand));
    assert.ok(allCommands.some(command => command.includes('verified_commit_gate.py')));
});


test('invokedAsEntryPoint is true when the module url matches the invoked script path', () => {
    const scriptPath = process.platform === 'win32' ? 'C:\\pkg\\bin\\install.mjs' : '/pkg/bin/install.mjs';
    assert.equal(invokedAsEntryPoint(pathToFileURL(scriptPath).href, scriptPath), true);
});


test('invokedAsEntryPoint is false when the module is imported by another script', () => {
    const modulePath = process.platform === 'win32' ? 'C:\\pkg\\bin\\install.mjs' : '/pkg/bin/install.mjs';
    const entryScriptPath = process.platform === 'win32' ? 'C:\\pkg\\bin\\install.test.mjs' : '/pkg/bin/install.test.mjs';
    assert.equal(invokedAsEntryPoint(pathToFileURL(modulePath).href, entryScriptPath), false);
});


test('invokedAsEntryPoint is false when there is no invoked script path', () => {
    assert.equal(invokedAsEntryPoint('file:///pkg/bin/install.mjs', undefined), false);
});


test('invokedAsEntryPoint is true when the module is reached through a bin symlink', () => {
    const linkRoot = mkdtempSync(join(tmpdir(), 'cdev-bin-symlink-'));
    try {
        const realModulePath = join(linkRoot, 'install.mjs');
        const symlinkLauncherPath = join(linkRoot, 'claude-dev-env');
        writeFileSync(realModulePath, 'export const sentinel = true;\n');
        symlinkSync(realModulePath, symlinkLauncherPath);
        const realModuleUrl = pathToFileURL(realModulePath).href;
        assert.equal(invokedAsEntryPoint(realModuleUrl, symlinkLauncherPath), true);
    } finally {
        rmSync(linkRoot, { recursive: true, force: true });
    }
});


test('invokedAsEntryPoint is false when a sibling script imports the real module', () => {
    const importerRoot = mkdtempSync(join(tmpdir(), 'cdev-bin-importer-'));
    try {
        const realModulePath = join(importerRoot, 'install.mjs');
        const importerScriptPath = join(importerRoot, 'install.test.mjs');
        writeFileSync(realModulePath, 'export const sentinel = true;\n');
        writeFileSync(importerScriptPath, 'import "./install.mjs";\n');
        const realModuleUrl = pathToFileURL(realModulePath).href;
        assert.equal(invokedAsEntryPoint(realModuleUrl, importerScriptPath), false);
    } finally {
        rmSync(importerRoot, { recursive: true, force: true });
    }
});


const SAMPLE_HOOKS_CONFIG = {
    hooks: {
        Stop: [
            {
                matcher: '',
                hooks: [
                    { command: 'python3 ${CLAUDE_PLUGIN_ROOT}/hooks/notification/attention_needed_notify.py', timeout: 15 },
                    { command: 'python3 ${CLAUDE_PLUGIN_ROOT}/hooks/blocking/hedging_language_blocker.py', timeout: 10 },
                ],
            },
        ],
        PreToolUse: [
            {
                matcher: 'Write',
                hooks: [
                    { command: 'python3 -c "import sys; sys.path.insert(0, r\'${CLAUDE_PLUGIN_ROOT}/hooks\'); print(1)"', timeout: 5 },
                ],
            },
        ],
    },
};


test('managedHookScriptRelativePaths collects every installed hook script path and ignores inline -c commands', () => {
    const relativePaths = managedHookScriptRelativePaths(SAMPLE_HOOKS_CONFIG);
    assert.ok(relativePaths.has('notification/attention_needed_notify.py'));
    assert.ok(relativePaths.has('blocking/hedging_language_blocker.py'));
    for (const foldedPath of FOLDED_HOOK_RELATIVE_PATHS) {
        assert.ok(relativePaths.has(foldedPath), `folded hook ${foldedPath} must always be in the managed set`);
    }
});


test('managedHookScriptRelativePaths includes retired Claude review hooks for upgrade cleanup', () => {
    const relativePaths = managedHookScriptRelativePaths(SAMPLE_HOOKS_CONFIG);
    for (const retiredPath of RETIRED_CLAUDE_REVIEW_HOOK_RELATIVE_PATHS) {
        assert.ok(relativePaths.has(retiredPath), `retired hook ${retiredPath} must remain prunable`);
    }
});


test('commandReferencesManagedHook matches managed scripts written with $HOME, ~, ${HOME}, and absolute path styles', () => {
    const managedPaths = new Set(['notification/attention_needed_notify.py']);
    assert.ok(commandReferencesManagedHook('python $HOME/.claude/hooks/notification/attention_needed_notify.py', managedPaths));
    assert.ok(commandReferencesManagedHook('python ~/.claude/hooks/notification/attention_needed_notify.py', managedPaths));
    assert.ok(commandReferencesManagedHook('python ${HOME}/.claude/hooks/notification/attention_needed_notify.py', managedPaths));
    assert.ok(commandReferencesManagedHook('py -3 C:/Users/example/.claude/hooks/notification/attention_needed_notify.py', managedPaths));
    assert.ok(commandReferencesManagedHook('python /Users/example/.claude/hooks/notification/attention_needed_notify.py', managedPaths));
});


test('commandReferencesManagedHook matches Windows backslash paths', () => {
    const managedPaths = new Set(['blocking/hedging_language_blocker.py']);
    assert.ok(commandReferencesManagedHook('py -3 C:\\Users\\example\\.claude\\hooks\\blocking\\hedging_language_blocker.py', managedPaths));
});


test('commandReferencesManagedHook leaves user hooks outside the managed set untouched', () => {
    const managedPaths = new Set(['notification/attention_needed_notify.py']);
    assert.equal(commandReferencesManagedHook('python /home/me/custom-tools/my_own_hook.py', managedPaths), false);
    assert.equal(commandReferencesManagedHook('py -3 ~/.claude/hooks/blocking/some_unmanaged_user_hook.py', managedPaths), false);
});


test('commandReferencesManagedHook leaves a user hook whose path is a managed tail plus a suffix untouched', () => {
    const managedPaths = new Set(['blocking/code_rules_enforcer.py']);
    assert.equal(commandReferencesManagedHook('python ~/.claude/hooks/blocking/code_rules_enforcer.py.bak', managedPaths), false);
    assert.equal(commandReferencesManagedHook('python ~/.claude/hooks/blocking/code_rules_enforcer.py2', managedPaths), false);
});


test('commandReferencesManagedHook leaves a command whose managed tail is mid-path untouched', () => {
    const managedPaths = new Set(['blocking/a.py']);
    assert.equal(commandReferencesManagedHook('python /x/.claude/hooks/blocking/a.py/extra/thing.py', managedPaths), false);
});


test('commandReferencesManagedHook matches a managed script followed by a whitespace-separated argument', () => {
    const managedPaths = new Set(['blocking/code_rules_enforcer.py']);
    assert.ok(commandReferencesManagedHook('python ~/.claude/hooks/blocking/code_rules_enforcer.py PreToolUse', managedPaths));
});


test('commandReferencesManagedHook matches the rewritten inline validators-runner hook that carries no script tail', () => {
    const managedPaths = new Set(['blocking/code_rules_enforcer.py']);
    const rewrittenInlineCommand =
        "py -3 -c \"import sys; sys.path.insert(0, r'C:/Users/example/.claude/hooks'); from validators.run_all_validators import main; sys.exit(main())\"";
    assert.ok(commandReferencesManagedHook(rewrittenInlineCommand, managedPaths));
});


test('commandReferencesManagedHook leaves an unmanaged inline -c command that imports a different module untouched', () => {
    const managedPaths = new Set(['blocking/code_rules_enforcer.py']);
    const userInlineCommand =
        "python -c \"import sys; sys.path.insert(0, r'/home/me/tools'); from my_tools.runner import main; sys.exit(main())\"";
    assert.equal(commandReferencesManagedHook(userInlineCommand, managedPaths), false);
});



function isPreToolUseDispatcherCommand(command) {
    // Basename-anchored match: bash_pre_tool_use_dispatcher.py must not count.
    return /(?:^|[/\\])pre_tool_use_dispatcher\.py(?![A-Za-z0-9_])/.test(command);
}

function countManagedRunAllValidatorsHooks(settings) {
    const writeEditGroups = (settings.hooks.PreToolUse || []).filter(
        group => group.matcher === 'Write|Edit'
    );
    let runAllValidatorsCount = 0;
    for (const group of writeEditGroups) {
        for (const hook of group.hooks) {
            if (hook.command.includes('run_all_validators')) {
                runAllValidatorsCount++;
            }
        }
    }
    return runAllValidatorsCount;
}


test('mergeHooksIntoSettings is idempotent for the inline -c validators hook across two installs', () => {
    const hooksConfig = {
        hooks: {
            'PreToolUse': [
                {
                    matcher: 'Write|Edit',
                    hooks: [
                        { command: 'python3 ${CLAUDE_PLUGIN_ROOT}/hooks/blocking/code_rules_enforcer.py', timeout: 30 },
                        {
                            command:
                                'python3 -c "import sys; sys.path.insert(0, r\'${CLAUDE_PLUGIN_ROOT}/hooks\'); from validators.run_all_validators import main; sys.exit(main())"',
                            timeout: 15,
                        },
                    ],
                },
            ],
        },
    };
    const settings = {};
    const pluginRootDir = 'C:/Users/example/.claude';

    mergeHooksIntoSettings(settings, hooksConfig, pluginRootDir, 'py -3');
    mergeHooksIntoSettings(settings, hooksConfig, pluginRootDir, 'py -3');

    assert.equal(countManagedRunAllValidatorsHooks(settings), 1);
    const writeEditGroup = settings.hooks.PreToolUse.find(group => group.matcher === 'Write|Edit');
    assert.equal(writeEditGroup.hooks.length, 2);
});


test('mergeHooksIntoSettings preserves user hooks in a managed matcher group across re-merges', () => {
    const hooksConfig = {
        hooks: {
            'PreToolUse': [
                {
                    matcher: 'Write|Edit',
                    hooks: [
                        {
                            command:
                                'python3 -c "import sys; sys.path.insert(0, r\'${CLAUDE_PLUGIN_ROOT}/hooks\'); from validators.run_all_validators import main; sys.exit(main())"',
                            timeout: 15,
                        },
                    ],
                },
            ],
        },
    };
    const userHookCommand = 'python /home/me/custom-tools/my_own_hook.py';
    const settings = {
        hooks: {
            PreToolUse: [
                { matcher: 'Write|Edit', hooks: [{ command: userHookCommand, timeout: 5 }] },
            ],
        },
    };

    mergeHooksIntoSettings(settings, hooksConfig, 'C:/Users/example/.claude', 'py -3');
    mergeHooksIntoSettings(settings, hooksConfig, 'C:/Users/example/.claude', 'py -3');

    const writeEditGroup = settings.hooks.PreToolUse.find(group => group.matcher === 'Write|Edit');
    const userHookSurvivors = writeEditGroup.hooks.filter(hook => hook.command === userHookCommand);
    assert.equal(userHookSurvivors.length, 1);
    assert.equal(countManagedRunAllValidatorsHooks(settings), 1);
});

test('pruneManagedHooksFromSettings removes a managed hook command written with the ~ home-path style', () => {
    const managedPaths = new Set(['blocking/code_rules_enforcer.py']);
    const settings = {
        hooks: {
            PreToolUse: [
                {
                    matcher: 'Write|Edit',
                    hooks: [
                        { command: 'python ~/.claude/hooks/blocking/code_rules_enforcer.py', timeout: 30 },
                    ],
                },
            ],
        },
    };

    pruneManagedHooksFromSettings(settings, managedPaths);

    assert.equal(settings.hooks, undefined);
});


test('pruneManagedHooksFromSettings removes managed hooks in every home-path and separator style while keeping user hooks', () => {
    const managedPaths = new Set(['notification/attention_needed_notify.py']);
    const userHookCommand = 'python /home/me/custom-tools/my_own_hook.py';
    const settings = {
        hooks: {
            Stop: [
                {
                    matcher: '',
                    hooks: [
                        { command: 'python $HOME/.claude/hooks/notification/attention_needed_notify.py', timeout: 15 },
                        { command: 'python ${HOME}/.claude/hooks/notification/attention_needed_notify.py', timeout: 15 },
                        { command: 'py -3 C:\\Users\\example\\.claude\\hooks\\notification\\attention_needed_notify.py', timeout: 15 },
                        { command: userHookCommand, timeout: 5 },
                    ],
                },
            ],
        },
    };

    pruneManagedHooksFromSettings(settings, managedPaths);

    const stopGroup = settings.hooks.Stop.find(group => group.matcher === '');
    assert.equal(stopGroup.hooks.length, 1);
    assert.equal(stopGroup.hooks[0].command, userHookCommand);
});

function writeHooksJsonAtRoot(sourceRoot, hooksConfig) {
    mkdirSync(join(sourceRoot, 'hooks'), { recursive: true });
    writeFileSync(join(sourceRoot, 'hooks', 'hooks.json'), JSON.stringify(hooksConfig));
}


test('managedHookScriptRelativePathsFromSourceRoots reads each root hooks.json so purge matches every installed script', () => {
    const sourceRoot = mkdtempSync(join(tmpdir(), 'cdev-purge-set-'));
    try {
        writeHooksJsonAtRoot(sourceRoot, SAMPLE_HOOKS_CONFIG);

        const relativePaths = managedHookScriptRelativePathsFromSourceRoots([sourceRoot]);

        assert.ok(relativePaths.has('notification/attention_needed_notify.py'));
        assert.ok(relativePaths.has('blocking/hedging_language_blocker.py'));
        for (const foldedPath of FOLDED_HOOK_RELATIVE_PATHS) {
            assert.ok(relativePaths.has(foldedPath), `folded hook ${foldedPath} must always be in the managed set`);
        }
    } finally {
        rmSync(sourceRoot, { recursive: true, force: true });
    }
});


test('managedHookScriptRelativePathsFromSourceRoots unions managed scripts across multiple package roots', () => {
    const builtinRoot = mkdtempSync(join(tmpdir(), 'cdev-purge-builtin-'));
    const dependencyRoot = mkdtempSync(join(tmpdir(), 'cdev-purge-dependency-'));
    try {
        writeHooksJsonAtRoot(builtinRoot, {
            hooks: { Stop: [{ matcher: '', hooks: [{ command: 'python3 ${CLAUDE_PLUGIN_ROOT}/hooks/blocking/code_rules_enforcer.py' }] }] },
        });
        writeHooksJsonAtRoot(dependencyRoot, {
            hooks: { PreToolUse: [{ matcher: 'Bash', hooks: [{ command: 'python3 ${CLAUDE_PLUGIN_ROOT}/hooks/blocking/example_hook.py' }] }] },
        });

        const relativePaths = managedHookScriptRelativePathsFromSourceRoots([builtinRoot, dependencyRoot]);

        assert.ok(relativePaths.has('blocking/code_rules_enforcer.py'));
        assert.ok(relativePaths.has('blocking/example_hook.py'));
        for (const foldedPath of FOLDED_HOOK_RELATIVE_PATHS) {
            assert.ok(relativePaths.has(foldedPath), `folded hook ${foldedPath} must always be in the managed set`);
        }
    } finally {
        rmSync(builtinRoot, { recursive: true, force: true });
        rmSync(dependencyRoot, { recursive: true, force: true });
    }
});


test('managedHookScriptRelativePathsFromSourceRoots skips roots whose hooks.json is absent', () => {
    const rootWithoutHooks = mkdtempSync(join(tmpdir(), 'cdev-purge-empty-'));
    try {
        const relativePaths = managedHookScriptRelativePathsFromSourceRoots([rootWithoutHooks]);
        assert.equal([...relativePaths].length, 0);
    } finally {
        rmSync(rootWithoutHooks, { recursive: true, force: true });
    }
});


test('purge set sourced from package hooks.json prunes standalone managed script hooks and keeps user hooks', () => {
    const sourceRoot = mkdtempSync(join(tmpdir(), 'cdev-purge-prune-'));
    try {
        writeHooksJsonAtRoot(sourceRoot, {
            hooks: {
                PreToolUse: [
                    {
                        matcher: 'Write|Edit',
                        hooks: [
                            { command: 'python3 ${CLAUDE_PLUGIN_ROOT}/hooks/blocking/code_rules_enforcer.py', timeout: 30 },
                        ],
                    },
                ],
            },
        });
        const userHookCommand = 'python /home/me/custom-tools/my_own_hook.py';
        const settings = {
            hooks: {
                PreToolUse: [
                    {
                        matcher: 'Write|Edit',
                        hooks: [
                            { command: 'py -3 C:\\Users\\example\\.claude\\hooks\\blocking\\code_rules_enforcer.py', timeout: 30 },
                            { command: userHookCommand, timeout: 5 },
                        ],
                    },
                ],
            },
        };

        const managedHookRelativePaths = managedHookScriptRelativePathsFromSourceRoots([sourceRoot]);
        pruneManagedHooksFromSettings(settings, managedHookRelativePaths);

        const writeEditGroup = settings.hooks.PreToolUse.find(group => group.matcher === 'Write|Edit');
        assert.equal(writeEditGroup.hooks.length, 1);
        assert.equal(writeEditGroup.hooks[0].command, userHookCommand);
    } finally {
        rmSync(sourceRoot, { recursive: true, force: true });
    }
});


const DISPATCHER_HOOKS_CONFIG = {
    hooks: {
        PreToolUse: [
            {
                matcher: 'Write|Edit',
                hooks: [
                    {
                        type: 'command',
                        command: 'python3 -c "import sys; sys.path.insert(0, r\'${CLAUDE_PLUGIN_ROOT}/hooks\'); from validators.run_all_validators import main; sys.exit(main())"',
                        timeout: 15,
                    },
                ],
            },
            {
                matcher: 'Write|Edit|MultiEdit',
                hooks: [
                    {
                        type: 'command',
                        command: 'python3 ${CLAUDE_PLUGIN_ROOT}/hooks/blocking/pre_tool_use_dispatcher.py',
                        timeout: 60,
                    },
                ],
            },
        ],
    },
};

const OLD_FOLDED_HOOKS_SETTINGS = {
    hooks: {
        PreToolUse: [
            {
                matcher: 'Write|Edit',
                hooks: [
                    { type: 'command', command: 'py -3 C:/Users/x/.claude/hooks/blocking/write_existing_file_blocker.py', timeout: 10 },
                    { type: 'command', command: 'py -3 C:/Users/x/.claude/hooks/blocking/sensitive_file_protector.py', timeout: 10 },
                    { type: 'command', command: 'py -3 C:/Users/x/.claude/hooks/validation/hook_format_validator.py', timeout: 15 },
                    { type: 'command', command: 'py -3 C:/Users/x/.claude/hooks/blocking/code_rules_enforcer.py', timeout: 30 },
                    { type: 'command', command: 'py -3 -c "import sys; sys.path.insert(0, r\'C:/Users/x/.claude/hooks\'); from validators.run_all_validators import main; sys.exit(main())"', timeout: 15 },
                    { type: 'command', command: 'py -3 C:/Users/x/.claude/hooks/blocking/tdd_enforcer.py', timeout: 10 },
                    { type: 'command', command: 'py -3 C:/Users/x/.claude/hooks/blocking/windows_rmtree_blocker.py', timeout: 10 },
                    { type: 'command', command: 'py -3 C:/Users/x/.claude/hooks/blocking/state_description_blocker.py', timeout: 10 },
                    { type: 'command', command: 'py -3 C:/Users/x/.claude/hooks/blocking/subprocess_budget_completeness.py', timeout: 10 },
                    { type: 'command', command: 'py -3 C:/Users/x/.claude/hooks/blocking/hook_prose_detector_consistency.py', timeout: 10 },
                    { type: 'command', command: 'py -3 C:/Users/x/.claude/hooks/blocking/verified_commit_message_accuracy_blocker.py', timeout: 10 },
                ],
            },
            {
                matcher: 'Write|Edit|MultiEdit',
                hooks: [
                    { type: 'command', command: 'py -3 C:/Users/x/.claude/hooks/blocking/workflow_substitution_slot_blocker.py', timeout: 10 },
                    { type: 'command', command: 'py -3 C:/Users/x/.claude/hooks/blocking/claude_md_orphan_file_blocker.py', timeout: 10 },
                    { type: 'command', command: 'py -3 C:/Users/x/.claude/hooks/blocking/pytest_testpaths_orphan_blocker.py', timeout: 10 },
                    { type: 'command', command: 'py -3 C:/Users/x/.claude/hooks/blocking/open_questions_in_plans_blocker.py', timeout: 10 },
                    { type: 'command', command: 'py -3 C:/Users/x/.claude/hooks/blocking/plain_language_blocker.py', timeout: 10 },
                ],
            },
        ],
    },
};


test('FOLDED_HOOK_RELATIVE_PATHS contains all 16 hooks removed from hooks.json plus the retired md_to_html_blocker', () => {
    assert.equal(FOLDED_HOOK_RELATIVE_PATHS.size, 17);
    assert.ok(FOLDED_HOOK_RELATIVE_PATHS.has('blocking/write_existing_file_blocker.py'));
    assert.ok(FOLDED_HOOK_RELATIVE_PATHS.has('blocking/plain_language_blocker.py'));
    assert.ok(FOLDED_HOOK_RELATIVE_PATHS.has('blocking/code_rules_enforcer.py'));
    assert.ok(FOLDED_HOOK_RELATIVE_PATHS.has('blocking/pytest_testpaths_orphan_blocker.py'));
    assert.ok(FOLDED_HOOK_RELATIVE_PATHS.has('blocking/md_to_html_blocker.py'));
});


test('FOLDED_HOOK_RELATIVE_PATHS lists every hook the PreToolUse dispatcher hosts', () => {
    const dispatcherHostedHooks = [
        'blocking/write_existing_file_blocker.py',
        'blocking/sensitive_file_protector.py',
        'validation/hook_format_validator.py',
        'blocking/code_rules_enforcer.py',
        'blocking/tdd_enforcer.py',
        'blocking/windows_rmtree_blocker.py',
        'blocking/state_description_blocker.py',
        'blocking/subprocess_budget_completeness.py',
        'blocking/hook_prose_detector_consistency.py',
        'blocking/verified_commit_message_accuracy_blocker.py',
        'blocking/workflow_substitution_slot_blocker.py',
        'blocking/claude_md_orphan_file_blocker.py',
        'blocking/env_var_table_code_drift_blocker.py',
        'blocking/pytest_testpaths_orphan_blocker.py',
        'blocking/open_questions_in_plans_blocker.py',
        'blocking/plain_language_blocker.py',
    ];
    const retiredHooks = [
        'blocking/md_to_html_blocker.py',
    ];
    for (const hostedPath of dispatcherHostedHooks) {
        assert.ok(
            FOLDED_HOOK_RELATIVE_PATHS.has(hostedPath),
            `dispatcher-hosted hook ${hostedPath} must be in FOLDED_HOOK_RELATIVE_PATHS so a reinstall prunes its stale standalone entry and it does not double-run`
        );
    }
    for (const retiredPath of retiredHooks) {
        assert.ok(
            FOLDED_HOOK_RELATIVE_PATHS.has(retiredPath),
            `retired hook ${retiredPath} must be in FOLDED_HOOK_RELATIVE_PATHS so a reinstall prunes its stale standalone entry pointing at a script no longer on disk`
        );
    }
    assert.equal(
        FOLDED_HOOK_RELATIVE_PATHS.size,
        dispatcherHostedHooks.length + retiredHooks.length,
        'FOLDED_HOOK_RELATIVE_PATHS must hold exactly the dispatcher-hosted hooks plus the retired hooks, no more, no fewer'
    );
});


test('managedHookScriptRelativePaths includes the dispatcher and all folded hooks so old entries are prunable', () => {
    const relativePaths = managedHookScriptRelativePaths(DISPATCHER_HOOKS_CONFIG);
    assert.ok(relativePaths.has('blocking/pre_tool_use_dispatcher.py'), 'dispatcher must be in managed set');
    for (const foldedPath of FOLDED_HOOK_RELATIVE_PATHS) {
        assert.ok(relativePaths.has(foldedPath), `folded hook ${foldedPath} must be in managed set`);
    }
});


test('mergeHooksIntoSettings into old folded-hooks settings yields exactly one dispatcher entry and no folded entries', () => {
    const settings = JSON.parse(JSON.stringify(OLD_FOLDED_HOOKS_SETTINGS));
    mergeHooksIntoSettings(settings, DISPATCHER_HOOKS_CONFIG, 'C:/Users/x/.claude', 'py -3');

    const allPreToolUseGroups = settings.hooks.PreToolUse || [];
    const allHookCommands = allPreToolUseGroups.flatMap(group => group.hooks.map(hook => hook.command));

    const allDispatcherCommands = allHookCommands.filter(isPreToolUseDispatcherCommand);
    assert.equal(allDispatcherCommands.length, 1, 'exactly one dispatcher entry must be present');

    for (const foldedPath of FOLDED_HOOK_RELATIVE_PATHS) {
        const foldedBasename = foldedPath.split('/').pop();
        const foldedCommands = allHookCommands.filter(
            cmd => cmd.includes(foldedBasename) && !cmd.includes('pre_tool_use_dispatcher')
        );
        assert.equal(foldedCommands.length, 0, `folded hook ${foldedBasename} must not appear as a separate entry`);
    }
});


test('mergeHooksIntoSettings into old folded-hooks settings preserves the inline validators runner', () => {
    const settings = JSON.parse(JSON.stringify(OLD_FOLDED_HOOKS_SETTINGS));
    mergeHooksIntoSettings(settings, DISPATCHER_HOOKS_CONFIG, 'C:/Users/x/.claude', 'py -3');

    assert.equal(
        countManagedRunAllValidatorsHooks(settings),
        1,
        'exactly one run_all_validators hook must remain in Write|Edit',
    );
});


test('mergeHooksIntoSettings is idempotent when run twice against an already-updated settings shape', () => {
    const settings = JSON.parse(JSON.stringify(OLD_FOLDED_HOOKS_SETTINGS));
    mergeHooksIntoSettings(settings, DISPATCHER_HOOKS_CONFIG, 'C:/Users/x/.claude', 'py -3');
    mergeHooksIntoSettings(settings, DISPATCHER_HOOKS_CONFIG, 'C:/Users/x/.claude', 'py -3');

    const allPreToolUseGroups = settings.hooks.PreToolUse || [];
    const allHookCommands = allPreToolUseGroups.flatMap(group => group.hooks.map(hook => hook.command));

    const allDispatcherCommands = allHookCommands.filter(isPreToolUseDispatcherCommand);
    assert.equal(allDispatcherCommands.length, 1, 'dispatcher must appear exactly once after two merges');
    assert.equal(countManagedRunAllValidatorsHooks(settings), 1, 'run_all_validators must appear exactly once after two merges');
});


test('shipped hooks.json matches the dispatcher design: dispatchers registered, run_all_validators retained, no folded hook standalone', () => {
    const shippedHooksConfig = JSON.parse(
        readFileSync(new URL('../hooks/hooks.json', import.meta.url), 'utf8')
    );

    const allPreToolUseGroups = shippedHooksConfig.hooks.PreToolUse || [];
    const allPreCommands = allPreToolUseGroups.flatMap(group => group.hooks.map(hook => hook.command));
    const preDispatcherCommands = allPreCommands.filter(isPreToolUseDispatcherCommand);
    assert.equal(preDispatcherCommands.length, 1, 'shipped hooks.json must register the PreToolUse dispatcher exactly once');

    assert.equal(
        countManagedRunAllValidatorsHooks(shippedHooksConfig),
        1,
        'shipped hooks.json must retain the inline run_all_validators runner in Write|Edit',
    );

    const allPostToolUseGroups = shippedHooksConfig.hooks.PostToolUse || [];
    const postDispatcherCommands = allPostToolUseGroups
        .flatMap(group => group.hooks.map(hook => hook.command))
        .filter(cmd => cmd.includes('post_tool_use_dispatcher.py'));
    assert.equal(postDispatcherCommands.length, 1, 'shipped hooks.json must register the PostToolUse dispatcher exactly once');

    const writePathCommands = allPreToolUseGroups
        .filter(group => /Write|Edit|MultiEdit/.test(group.matcher || ''))
        .flatMap(group => group.hooks.map(hook => hook.command));
    for (const foldedPath of FOLDED_HOOK_RELATIVE_PATHS) {
        const foldedBasename = foldedPath.split('/').pop();
        const standaloneFoldedCommands = writePathCommands.filter(
            cmd => cmd.includes(foldedBasename) && !cmd.includes('pre_tool_use_dispatcher')
        );
        assert.equal(
            standaloneFoldedCommands.length,
            0,
            `folded hook ${foldedBasename} must not ship as a standalone write-path PreToolUse entry`,
        );
    }
});


const POST_DISPATCHER_HOOKS_CONFIG = {
    hooks: {
        PostToolUse: [
            {
                matcher: 'Write|Edit',
                hooks: [
                    {
                        type: 'command',
                        command: 'python3 ${CLAUDE_PLUGIN_ROOT}/hooks/validation/post_tool_use_dispatcher.py',
                        timeout: 60,
                    },
                ],
            },
        ],
    },
};

const OLD_POST_FOLDED_HOOKS_SETTINGS = {
    hooks: {
        PostToolUse: [
            {
                matcher: 'Write|Edit',
                hooks: [
                    { type: 'command', command: 'py -3 C:/Users/x/.claude/hooks/validation/mypy_validator.py', timeout: 30 },
                    { type: 'command', command: 'py -3 C:/Users/x/.claude/hooks/workflow/auto_formatter.py', timeout: 30 },
                    { type: 'command', command: 'py -3 C:/Users/x/.claude/hooks/workflow/doc_gist_auto_publish.py C:/Users/x/.claude', timeout: 60 },
                ],
            },
        ],
    },
};


test('POST_FOLDED_HOOK_RELATIVE_PATHS contains the after-write hooks and the retired md_to_html_companion', () => {
    assert.equal(POST_FOLDED_HOOK_RELATIVE_PATHS.size, 4);
    assert.ok(POST_FOLDED_HOOK_RELATIVE_PATHS.has('validation/mypy_validator.py'));
    assert.ok(POST_FOLDED_HOOK_RELATIVE_PATHS.has('workflow/auto_formatter.py'));
    assert.ok(POST_FOLDED_HOOK_RELATIVE_PATHS.has('workflow/doc_gist_auto_publish.py'));
    assert.ok(POST_FOLDED_HOOK_RELATIVE_PATHS.has('workflow/md_to_html_companion.py'));
});


test('managedHookScriptRelativePaths includes the PostToolUse dispatcher and all post-folded hooks so old entries are prunable', () => {
    const relativePaths = managedHookScriptRelativePaths(POST_DISPATCHER_HOOKS_CONFIG);
    assert.ok(relativePaths.has('validation/post_tool_use_dispatcher.py'), 'PostToolUse dispatcher must be in managed set');
    for (const foldedPath of POST_FOLDED_HOOK_RELATIVE_PATHS) {
        assert.ok(relativePaths.has(foldedPath), `post-folded hook ${foldedPath} must be in managed set`);
    }
});


test('mergeHooksIntoSettings into the old three PostToolUse entries yields exactly one post_tool_use_dispatcher entry and none of the three', () => {
    const settings = JSON.parse(JSON.stringify(OLD_POST_FOLDED_HOOKS_SETTINGS));
    mergeHooksIntoSettings(settings, POST_DISPATCHER_HOOKS_CONFIG, 'C:/Users/x/.claude', 'py -3');

    const writeEditGroup = settings.hooks.PostToolUse.find(group => group.matcher === 'Write|Edit');
    const allCommands = writeEditGroup.hooks.map(hook => hook.command);

    const dispatcherCommands = allCommands.filter(cmd => cmd.includes('post_tool_use_dispatcher.py'));
    assert.equal(dispatcherCommands.length, 1, 'exactly one PostToolUse dispatcher entry must be present');

    for (const foldedPath of POST_FOLDED_HOOK_RELATIVE_PATHS) {
        const foldedBasename = foldedPath.split('/').pop();
        const foldedCommands = allCommands.filter(cmd => cmd.includes(foldedBasename));
        assert.equal(foldedCommands.length, 0, `post-folded hook ${foldedBasename} must not appear as a separate entry`);
    }
});


test('mergeHooksIntoSettings installs the PostToolUse dispatcher cleanly into an empty settings object', () => {
    const settings = {};
    mergeHooksIntoSettings(settings, POST_DISPATCHER_HOOKS_CONFIG, 'C:/Users/x/.claude', 'py -3');

    const writeEditGroup = settings.hooks.PostToolUse.find(group => group.matcher === 'Write|Edit');
    assert.equal(writeEditGroup.hooks.length, 1);
    assert.equal(
        writeEditGroup.hooks[0].command,
        'py -3 C:/Users/x/.claude/hooks/validation/post_tool_use_dispatcher.py',
    );
});


test('mergeHooksIntoSettings is idempotent for the PostToolUse dispatcher across two installs', () => {
    const settings = JSON.parse(JSON.stringify(OLD_POST_FOLDED_HOOKS_SETTINGS));
    mergeHooksIntoSettings(settings, POST_DISPATCHER_HOOKS_CONFIG, 'C:/Users/x/.claude', 'py -3');
    mergeHooksIntoSettings(settings, POST_DISPATCHER_HOOKS_CONFIG, 'C:/Users/x/.claude', 'py -3');

    const writeEditGroup = settings.hooks.PostToolUse.find(group => group.matcher === 'Write|Edit');
    const dispatcherCommands = writeEditGroup.hooks.filter(hook => hook.command.includes('post_tool_use_dispatcher.py'));
    assert.equal(dispatcherCommands.length, 1, 'PostToolUse dispatcher must appear exactly once after two merges');
    assert.equal(writeEditGroup.hooks.length, 1);
});


const PRE_DISPATCHER_ONLY_HOOKS_CONFIG = {
    hooks: {
        PreToolUse: [
            {
                matcher: 'Write|Edit|MultiEdit',
                hooks: [
                    {
                        type: 'command',
                        command: 'python3 ${CLAUDE_PLUGIN_ROOT}/hooks/blocking/pre_tool_use_dispatcher.py',
                        timeout: 60,
                    },
                ],
            },
        ],
    },
};

const SETTINGS_WITH_INLINE_RUNNER = {
    hooks: {
        PreToolUse: [
            {
                matcher: 'Write|Edit',
                hooks: [
                    {
                        type: 'command',
                        command: "py -3 -c \"import sys; sys.path.insert(0, r'C:/Users/x/.claude/hooks'); from validators.run_all_validators import main; sys.exit(main())\"",
                        timeout: 15,
                    },
                ],
            },
            {
                matcher: 'Write|Edit|MultiEdit',
                hooks: [
                    { type: 'command', command: 'py -3 C:/Users/x/.claude/hooks/blocking/pre_tool_use_dispatcher.py', timeout: 60 },
                ],
            },
        ],
    },
};


test('mergeHooksIntoSettings prunes the inline run_all_validators runner when the new shape no longer ships it', () => {
    const settings = JSON.parse(JSON.stringify(SETTINGS_WITH_INLINE_RUNNER));
    mergeHooksIntoSettings(settings, PRE_DISPATCHER_ONLY_HOOKS_CONFIG, 'C:/Users/x/.claude', 'py -3');

    assert.equal(countManagedRunAllValidatorsHooks(settings), 0, 'the inline validators runner must be pruned');

    const writeEditGroup = (settings.hooks.PreToolUse || []).find(group => group.matcher === 'Write|Edit');
    if (writeEditGroup) {
        const runnerSurvivors = writeEditGroup.hooks.filter(hook => hook.command.includes('run_all_validators'));
        assert.equal(runnerSurvivors.length, 0);
    }

    const dispatcherGroup = settings.hooks.PreToolUse.find(group => group.matcher === 'Write|Edit|MultiEdit');
    const dispatcherCommands = dispatcherGroup.hooks.filter(hook => isPreToolUseDispatcherCommand(hook.command));
    assert.equal(dispatcherCommands.length, 1, 'the PreToolUse dispatcher must remain exactly once');
});


const README_BASENAME_PATTERN = /^readme\.md$/i;


/**
 * Build a sandbox holding an installed skills root and a run backup root.
 *
 * @param {object} installedFiles Forward-slash relative paths under the skills root mapped to contents.
 * @returns {{root: string, skillsRoot: string, backupRoot: string}} The sandbox paths.
 */
function createStalePruneSandbox(installedFiles) {
    const root = mkdtempSync(join(tmpdir(), 'cdev-stale-prune-'));
    const skillsRoot = join(root, 'skills');
    const backupRoot = join(root, 'pruned', 'run-timestamp');
    mkdirSync(skillsRoot, { recursive: true });
    for (const [relativePath, contents] of Object.entries(installedFiles)) {
        const targetPath = join(skillsRoot, relativePath);
        mkdirSync(dirname(targetPath), { recursive: true });
        writeFileSync(targetPath, contents);
    }
    return { root, skillsRoot, backupRoot };
}


/**
 * Run a callable with console.warn captured, returning its value and the warnings.
 *
 * @param {Function} runnable The zero-argument callable to run.
 * @returns {{returnedValue: *, allWarnings: string[]}} The result and captured warnings.
 */
function captureWarnings(runnable) {
    const originalWarn = console.warn;
    const allWarnings = [];
    console.warn = (warningMessage) => allWarnings.push(String(warningMessage));
    try {
        return { returnedValue: runnable(), allWarnings };
    } finally {
        console.warn = originalWarn;
    }
}


test('pruneStaleInstalledFiles moves a file the prior manifest recorded and this run no longer writes', () => {
    const sandbox = createStalePruneSandbox({
        'demo/SKILL.md': '# demo\n',
        'demo/scripts/retired_module.py': 'from constants import OLD_NAME\n',
    });
    try {
        const keptFilePath = join(sandbox.skillsRoot, 'demo', 'SKILL.md');
        const staleFilePath = join(sandbox.skillsRoot, 'demo', 'scripts', 'retired_module.py');

        const pruneOutcome = pruneStaleInstalledFiles(
            [keptFilePath, staleFilePath],
            [keptFilePath],
            sandbox.skillsRoot,
            sandbox.backupRoot,
            { managedHomeDirectory: sandbox.root },
        );

        assert.equal(pruneOutcome.prunedCount, 1, 'exactly the one no-longer-written file moves');
        assert.deepEqual(pruneOutcome.failedPaths, [], 'a move that succeeds reports no failed path');
        assert.equal(existsSync(staleFilePath), false, 'the stale file leaves the installed tree');
        assert.equal(
            existsSync(join(sandbox.backupRoot, 'demo', 'scripts', 'retired_module.py')),
            true,
            'the stale file lands under its mirrored relative path in the backup root',
        );
        assert.equal(existsSync(keptFilePath), true, 'a file this run wrote stays in place');
    } finally {
        rmSync(sandbox.root, { recursive: true, force: true });
    }
});


test('pruneStaleInstalledFiles leaves a __pycache__ artifact the prior manifest never recorded in place', () => {
    const sandbox = createStalePruneSandbox({
        'demo/SKILL.md': '# demo\n',
        'demo/scripts/__pycache__/helper.cpython-312.pyc': 'compiled bytecode\n',
        'demo/notes.md': 'a file the user authored\n',
    });
    try {
        const shippedFilePath = join(sandbox.skillsRoot, 'demo', 'SKILL.md');
        const runtimeArtifactPath = join(
            sandbox.skillsRoot, 'demo', 'scripts', '__pycache__', 'helper.cpython-312.pyc',
        );
        const userFilePath = join(sandbox.skillsRoot, 'demo', 'notes.md');

        const pruneOutcome = pruneStaleInstalledFiles(
            [shippedFilePath],
            [shippedFilePath],
            sandbox.skillsRoot,
            sandbox.backupRoot,
            { managedHomeDirectory: sandbox.root },
        );

        assert.equal(pruneOutcome.prunedCount, 0, 'a file the installer never wrote is outside the diff');
        assert.equal(existsSync(runtimeArtifactPath), true, 'the compiled bytecode stays in place');
        assert.equal(existsSync(userFilePath), true, 'the user-authored file stays in place');
        assert.equal(existsSync(sandbox.backupRoot), false, 'an empty prune creates no backup root');
    } finally {
        rmSync(sandbox.root, { recursive: true, force: true });
    }
});


test('pruneStaleInstalledFiles returns zero and moves nothing when the prior manifest record is unknown', () => {
    const sandbox = createStalePruneSandbox({ 'demo/SKILL.md': '# demo\n' });
    try {
        const pruneOutcome = pruneStaleInstalledFiles(null, [], sandbox.skillsRoot, sandbox.backupRoot);

        assert.equal(pruneOutcome.prunedCount, 0, 'an unknown prior record holds the prune for that run');
        assert.deepEqual(pruneOutcome.failedPaths, [], 'an unknown prior record reports no failed path');
        assert.equal(existsSync(join(sandbox.skillsRoot, 'demo', 'SKILL.md')), true);
    } finally {
        rmSync(sandbox.root, { recursive: true, force: true });
    }
});


test('comparisonKeyForPath folds letter case when the filesystem does', () => {
    const lowercaseKey = comparisonKeyForPath('/home/user/.claude/skills/demo/readme.md', {
        isCaseInsensitive: true,
    });
    const uppercaseKey = comparisonKeyForPath('/home/user/.claude/skills/demo/README.md', {
        isCaseInsensitive: true,
    });

    assert.equal(lowercaseKey, uppercaseKey, 'two spellings of one name share a key');
});


test('comparisonKeyForPath keeps letter case when the filesystem does', () => {
    const lowercaseKey = comparisonKeyForPath('/home/user/.claude/skills/demo/readme.md', {
        isCaseInsensitive: false,
    });
    const uppercaseKey = comparisonKeyForPath('/home/user/.claude/skills/demo/README.md', {
        isCaseInsensitive: false,
    });

    assert.notEqual(lowercaseKey, uppercaseKey, 'two spellings name two distinct files');
});


test('pruneStaleInstalledFiles keeps a case-only renamed readme when keys fold case', () => {
    const sandbox = createStalePruneSandbox({
        'demo/README.md': '# demo readme\n',
    });
    try {
        const priorReadmePath = join(sandbox.skillsRoot, 'demo', 'Readme.md');
        const copiedReadmePath = join(sandbox.skillsRoot, 'demo', 'README.md');

        const pruneOutcome = pruneStaleInstalledFiles(
            [priorReadmePath],
            [copiedReadmePath],
            sandbox.skillsRoot,
            sandbox.backupRoot,
            { isCaseInsensitive: true, managedHomeDirectory: sandbox.root },
        );

        assert.equal(pruneOutcome.prunedCount, 0, 'the recorded spelling names the file this run wrote');
        assert.equal(existsSync(copiedReadmePath), true, 'the freshly shipped readme stays in place');
        assert.equal(existsSync(sandbox.backupRoot), false, 'nothing reaches the backup root');
    } finally {
        rmSync(sandbox.root, { recursive: true, force: true });
    }
});


test('should preserve a case-only rename on a case-insensitive filesystem (host-dependent)', () => {
    const sandbox = createStalePruneSandbox({
        'demo/Readme.md': 'the readme an earlier install wrote\n',
    });
    try {
        const shippedReadmeContents = '# demo readme\n';
        const shippedReadmeSource = join(sandbox.root, 'README.md');
        writeFileSync(shippedReadmeSource, shippedReadmeContents);
        const priorReadmePath = join(sandbox.skillsRoot, 'demo', 'Readme.md');
        const copiedReadmePath = join(sandbox.skillsRoot, 'demo', 'README.md');
        copyFileSync(shippedReadmeSource, copiedReadmePath);

        pruneStaleInstalledFiles(
            [priorReadmePath],
            [copiedReadmePath],
            sandbox.skillsRoot,
            sandbox.backupRoot,
            { managedHomeDirectory: sandbox.root },
        );

        const survivingReadmeNames = readdirSync(join(sandbox.skillsRoot, 'demo'))
            .filter(entryName => README_BASENAME_PATTERN.test(entryName));
        assert.equal(survivingReadmeNames.length, 1, 'the skill keeps exactly one readme');
        assert.equal(
            readFileSync(join(sandbox.skillsRoot, 'demo', survivingReadmeNames[0]), 'utf8'),
            shippedReadmeContents,
            'the surviving readme holds the freshly shipped content',
        );
    } finally {
        rmSync(sandbox.root, { recursive: true, force: true });
    }
});


test('pruneStaleInstalledFiles leaves a file in place and warns when the move fails', () => {
    const sandbox = createStalePruneSandbox({
        'demo/scripts/retired_module.py': 'stale module\n',
    });
    try {
        mkdirSync(dirname(sandbox.backupRoot), { recursive: true });
        writeFileSync(sandbox.backupRoot, 'a file standing where the backup root belongs\n');
        const staleFilePath = join(sandbox.skillsRoot, 'demo', 'scripts', 'retired_module.py');

        const { returnedValue, allWarnings } = captureWarnings(() => pruneStaleInstalledFiles(
            [staleFilePath],
            [],
            sandbox.skillsRoot,
            sandbox.backupRoot,
            { managedHomeDirectory: sandbox.root },
        ));

        assert.equal(returnedValue.prunedCount, 0, 'a failed move counts as nothing moved');
        assert.deepEqual(
            returnedValue.failedPaths,
            [staleFilePath],
            'the failed path is reported so the caller keeps it on the manifest record',
        );
        assert.equal(existsSync(staleFilePath), true, 'the file stays in the installed tree');
        assert.equal(allWarnings.length, 1, 'the failed move is reported once');
        assert.match(allWarnings[0], /leaving in place/, 'the warning states the file was left in place');
    } finally {
        rmSync(sandbox.root, { recursive: true, force: true });
    }
});


test('pruneStaleInstalledFiles leaves a directory standing where a file was recorded and warns', () => {
    const sandbox = createStalePruneSandbox({
        'demo/scripts/former_file/inner.py': 'content the user put inside\n',
    });
    try {
        const recordedFilePath = join(sandbox.skillsRoot, 'demo', 'scripts', 'former_file');

        const { returnedValue, allWarnings } = captureWarnings(() => pruneStaleInstalledFiles(
            [recordedFilePath],
            [],
            sandbox.skillsRoot,
            sandbox.backupRoot,
            { managedHomeDirectory: sandbox.root },
        ));

        assert.equal(returnedValue.prunedCount, 0, 'a directory is never renamed into the backup');
        assert.deepEqual(returnedValue.failedPaths, [], 'a skipped directory is no failed move');
        assert.equal(existsSync(join(recordedFilePath, 'inner.py')), true, 'the directory keeps its contents');
        assert.equal(allWarnings.length, 1, 'the skipped path is reported once');
    } finally {
        rmSync(sandbox.root, { recursive: true, force: true });
    }
});


test('pruneStaleInstalledFiles skips a path the user already deleted without warning', () => {
    const sandbox = createStalePruneSandbox({ 'demo/SKILL.md': '# demo\n' });
    try {
        const deletedFilePath = join(sandbox.skillsRoot, 'demo', 'scripts', 'already_gone.py');

        const { returnedValue, allWarnings } = captureWarnings(() => pruneStaleInstalledFiles(
            [deletedFilePath],
            [],
            sandbox.skillsRoot,
            sandbox.backupRoot,
            { managedHomeDirectory: sandbox.root },
        ));

        assert.equal(returnedValue.prunedCount, 0, 'a path that no longer exists moves nothing');
        assert.deepEqual(returnedValue.failedPaths, [], 'a path that vanished is no failed move');
        assert.deepEqual(allWarnings, [], 'an already-deleted path is skipped in silence');
    } finally {
        rmSync(sandbox.root, { recursive: true, force: true });
    }
});


test('pruneStaleInstalledFiles removes emptied parents up to the destination root and keeps a populated one', () => {
    const sandbox = createStalePruneSandbox({
        'kept/SKILL.md': '# kept\n',
        'kept/scripts/retired_module.py': 'stale module\n',
        'emptied/nested/only_module.py': 'the sole file under this tree\n',
    });
    try {
        const populatedParentStalePath = join(sandbox.skillsRoot, 'kept', 'scripts', 'retired_module.py');
        const solitaryStalePath = join(sandbox.skillsRoot, 'emptied', 'nested', 'only_module.py');

        const pruneOutcome = pruneStaleInstalledFiles(
            [populatedParentStalePath, solitaryStalePath],
            [join(sandbox.skillsRoot, 'kept', 'SKILL.md')],
            sandbox.skillsRoot,
            sandbox.backupRoot,
            { managedHomeDirectory: sandbox.root },
        );

        assert.equal(pruneOutcome.prunedCount, 2, 'both recorded files move');
        assert.equal(
            existsSync(join(sandbox.skillsRoot, 'kept', 'scripts')),
            false,
            'the emptied scripts directory is removed',
        );
        assert.equal(
            existsSync(join(sandbox.skillsRoot, 'kept')),
            true,
            'a parent still holding SKILL.md is left alone',
        );
        assert.equal(
            existsSync(join(sandbox.skillsRoot, 'emptied')),
            false,
            'the walk climbs through every emptied parent',
        );
        assert.equal(existsSync(sandbox.skillsRoot), true, 'the destination root itself stays');
    } finally {
        rmSync(sandbox.root, { recursive: true, force: true });
    }
});


test('pruneStaleInstalledFiles ignores a recorded path outside the destination root', () => {
    const sandbox = createStalePruneSandbox({ 'demo/SKILL.md': '# demo\n' });
    try {
        const outsideFilePath = join(sandbox.root, 'rules', 'some-rule.md');
        mkdirSync(dirname(outsideFilePath), { recursive: true });
        writeFileSync(outsideFilePath, 'a rule wired to another root\n');

        const pruneOutcome = pruneStaleInstalledFiles(
            [outsideFilePath],
            [],
            sandbox.skillsRoot,
            sandbox.backupRoot,
            { managedHomeDirectory: sandbox.root },
        );

        assert.equal(pruneOutcome.prunedCount, 0, 'only the wired root is pruned');
        assert.equal(existsSync(outsideFilePath), true, 'content under another root stays in place');
    } finally {
        rmSync(sandbox.root, { recursive: true, force: true });
    }
});


test('collectFiles returns the source file and skips the build artifacts beside it', () => {
    const sourceRoot = mkdtempSync(join(tmpdir(), 'cdev-collect-files-'));
    try {
        const sourceFilePath = join(sourceRoot, 'scripts', 'helper.py');
        mkdirSync(dirname(sourceFilePath), { recursive: true });
        writeFileSync(sourceFilePath, 'the module the package ships\n');
        const bytecodePath = join(sourceRoot, 'scripts', '__pycache__', 'helper.cpython-313.pyc');
        mkdirSync(dirname(bytecodePath), { recursive: true });
        writeFileSync(bytecodePath, 'compiled bytecode\n');

        const collectedFiles = collectFiles(sourceRoot);

        assert.deepEqual(
            collectedFiles,
            [sourceFilePath],
            'the walk returns the source file alone',
        );
    } finally {
        rmSync(sourceRoot, { recursive: true, force: true });
    }
});


test('collectFiles skips every named cache directory and loose bytecode file', () => {
    const sourceRoot = mkdtempSync(join(tmpdir(), 'cdev-collect-caches-'));
    try {
        const sourceFilePath = join(sourceRoot, 'SKILL.md');
        writeFileSync(sourceFilePath, '# a shipped skill\n');
        for (const cacheDirectoryName of ['.ruff_cache', '.pytest_cache', '.mypy_cache', 'node_modules']) {
            const cachedFilePath = join(sourceRoot, cacheDirectoryName, 'entry.json');
            mkdirSync(dirname(cachedFilePath), { recursive: true });
            writeFileSync(cachedFilePath, '{}\n');
        }
        writeFileSync(join(sourceRoot, '.DS_Store'), 'finder metadata\n');
        writeFileSync(join(sourceRoot, 'loose_module.pyc'), 'bytecode outside a cache\n');
        writeFileSync(join(sourceRoot, 'loose_module.pyo'), 'optimized bytecode\n');

        const collectedFiles = collectFiles(sourceRoot);

        assert.deepEqual(collectedFiles, [sourceFilePath], 'only the shipped file survives the walk');
    } finally {
        rmSync(sourceRoot, { recursive: true, force: true });
    }
});


const SHIPPED_README_NAME = 'README.md';
const INSTALLED_README_NAME = 'Readme.md';
const RETIRED_HOOK_RELATIVE_PATH = 'blocking/retired_gate.py';
const SANDBOX_HOOKS_ROOT = join('/home', 'user', '.claude', 'hooks');


test('caseOnlyRenameSourceName names the installed entry when the filesystem folds letter case', () => {
    const caseOnlyMatchName = caseOnlyRenameSourceName(
        SHIPPED_README_NAME,
        [INSTALLED_README_NAME, 'SKILL.md'],
        { isCaseInsensitive: true },
    );

    assert.equal(
        caseOnlyMatchName,
        INSTALLED_README_NAME,
        'the entry the copy would fill through its installed spelling is named for the rename',
    );
});


test('caseOnlyRenameSourceName renames nothing when the filesystem keeps letter case', () => {
    const caseOnlyMatchName = caseOnlyRenameSourceName(
        SHIPPED_README_NAME,
        [INSTALLED_README_NAME],
        { isCaseInsensitive: false },
    );

    assert.equal(caseOnlyMatchName, null, 'two spellings name two files, so the copy writes its own');
});


test('caseOnlyRenameSourceName renames nothing when the shipped spelling already sits on disk', () => {
    const caseOnlyMatchName = caseOnlyRenameSourceName(
        SHIPPED_README_NAME,
        [SHIPPED_README_NAME, INSTALLED_README_NAME],
        { isCaseInsensitive: true },
    );

    assert.equal(caseOnlyMatchName, null, 'the destination already carries the shipped spelling');
});


test('copyTree gives the destination entry the shipped letter case (host-dependent)', () => {
    const sandboxRoot = mkdtempSync(join(tmpdir(), 'cdev-copy-tree-case-'));
    try {
        const sourceDirectory = join(sandboxRoot, 'source');
        const destinationDirectory = join(sandboxRoot, 'destination');
        mkdirSync(sourceDirectory, { recursive: true });
        mkdirSync(destinationDirectory, { recursive: true });
        const shippedContents = '# the readme the package ships\n';
        writeFileSync(join(sourceDirectory, SHIPPED_README_NAME), shippedContents);
        writeFileSync(
            join(destinationDirectory, INSTALLED_README_NAME),
            'the readme an earlier install wrote\n',
        );

        copyTree(sourceDirectory, destinationDirectory);

        const survivingReadmeNames = readdirSync(destinationDirectory)
            .filter(entryName => README_BASENAME_PATTERN.test(entryName));
        assert.ok(
            survivingReadmeNames.includes(SHIPPED_README_NAME),
            'the destination carries the spelling the package ships',
        );
        assert.equal(
            readFileSync(join(destinationDirectory, SHIPPED_README_NAME), 'utf8'),
            shippedContents,
            'the entry under the shipped spelling holds the shipped bytes',
        );
    } finally {
        rmSync(sandboxRoot, { recursive: true, force: true });
    }
});


test('retiredManagedHookRelativePaths names the hook scripts a prior install wrote and this run leaves out', () => {
    const retiredScriptPath = join(SANDBOX_HOOKS_ROOT, 'blocking', 'retired_gate.py');
    const liveScriptPath = join(SANDBOX_HOOKS_ROOT, 'blocking', 'live_gate.py');
    const ruleFilePath = join('/home', 'user', '.claude', 'rules', 'a-rule.md');

    const retiredRelativePaths = retiredManagedHookRelativePaths(
        [retiredScriptPath, liveScriptPath, ruleFilePath],
        [liveScriptPath],
        SANDBOX_HOOKS_ROOT,
    );

    assert.deepEqual(
        [...retiredRelativePaths],
        [RETIRED_HOOK_RELATIVE_PATH],
        'the diff names the retired script alone, leaving the live script and every other root out',
    );
});


test('retiredManagedHookRelativePaths names nothing when no prior install recorded anything', () => {
    const retiredRelativePaths = retiredManagedHookRelativePaths(null, [], SANDBOX_HOOKS_ROOT);

    assert.equal(retiredRelativePaths.size, 0, 'with no record to diff, no entry counts as retired');
});


/**
 * Write a settings.json fixture and return its path.
 *
 * @param {object} settings The settings object to serialize.
 * @param {number} indentWidth The JSON indent width the fixture is written with.
 * @returns {{settingsPath: string, sandboxRoot: string}} The fixture path and its sandbox root.
 */
function createSettingsFixture(settings, indentWidth) {
    const sandboxRoot = mkdtempSync(join(tmpdir(), 'cdev-retired-hook-settings-'));
    const settingsPath = join(sandboxRoot, 'settings.json');
    writeFileSync(settingsPath, JSON.stringify(settings, null, indentWidth) + '\n');
    return { settingsPath, sandboxRoot };
}


test('pruneRetiredHookEntriesFromSettings removes the retired entry and keeps the user-authored one', () => {
    const retiredCommand = `python3 "$HOME/.claude/hooks/${RETIRED_HOOK_RELATIVE_PATH}"`;
    const userCommand = 'python3 my_own_gate.py --user-authored';
    const lookalikeCommand = `python3 "$HOME/.claude/hooks/${RETIRED_HOOK_RELATIVE_PATH}.bak"`;
    const { settingsPath, sandboxRoot } = createSettingsFixture({
        hooks: {
            PreToolUse: [{
                matcher: 'Write|Edit',
                hooks: [
                    { type: 'command', command: retiredCommand },
                    { type: 'command', command: userCommand },
                    { type: 'command', command: lookalikeCommand },
                ],
            }],
            PreCompact: [{
                matcher: '*',
                hooks: [{ type: 'command', command: retiredCommand }],
            }],
        },
    }, 4);
    try {
        const removedCount = pruneRetiredHookEntriesFromSettings(
            settingsPath, new Set([RETIRED_HOOK_RELATIVE_PATH]),
        );

        assert.equal(removedCount, 2, 'both entries running the retired script are removed');
        const settings = JSON.parse(readFileSync(settingsPath, 'utf8'));
        assert.deepEqual(
            settings.hooks.PreToolUse[0].hooks.map(hook => hook.command),
            [userCommand, lookalikeCommand],
            'the user entry and the suffix-path entry stay exactly as written',
        );
        assert.equal(
            Object.hasOwn(settings.hooks, 'PreCompact'),
            false,
            'an event type the current config leaves out is reached and, left empty, dropped',
        );
    } finally {
        rmSync(sandboxRoot, { recursive: true, force: true });
    }
});


test('pruneRetiredHookEntriesFromSettings keeps every settings shape the installer never wrote and still removes the retired entry', () => {
    const retiredCommand = `python3 "$HOME/.claude/hooks/${RETIRED_HOOK_RELATIVE_PATH}"`;
    const entryWithoutCommand = { type: 'command' };
    const entryWithNumericCommand = { type: 'command', command: 42 };
    const entryWithObjectCommand = { type: 'command', command: { path: 'gate.py' } };
    const groupWithoutHooksArray = { matcher: '*' };
    const eventValueThatIsNotAnArray = { enabled: true };
    const { settingsPath, sandboxRoot } = createSettingsFixture({
        hooks: {
            PreToolUse: [{
                matcher: 'Write|Edit',
                hooks: [
                    { type: 'command', command: retiredCommand },
                    entryWithoutCommand,
                    entryWithNumericCommand,
                    entryWithObjectCommand,
                ],
            }],
            Notification: [groupWithoutHooksArray],
            SessionStart: eventValueThatIsNotAnArray,
        },
    }, 4);
    try {
        const removedCount = pruneRetiredHookEntriesFromSettings(
            settingsPath, new Set([RETIRED_HOOK_RELATIVE_PATH]),
        );

        assert.equal(removedCount, 1, 'the one entry running the retired script is the only removal');
        const settings = JSON.parse(readFileSync(settingsPath, 'utf8'));
        assert.deepEqual(
            settings.hooks.PreToolUse[0].hooks,
            [entryWithoutCommand, entryWithNumericCommand, entryWithObjectCommand],
            'an entry whose command is absent, a number, or an object counts as unmanaged and stays',
        );
        assert.deepEqual(
            settings.hooks.Notification,
            [groupWithoutHooksArray],
            'a matcher group carrying no hooks array is handed back untouched',
        );
        assert.deepEqual(
            settings.hooks.SessionStart,
            eventValueThatIsNotAnArray,
            'an event type whose value is not an array of groups is left as the file holds it',
        );
    } finally {
        rmSync(sandboxRoot, { recursive: true, force: true });
    }
});


test('mergeHooksIntoSettings merges its groups into a settings file holding shapes it never wrote', () => {
    const entryWithoutCommand = { type: 'command' };
    const settings = {
        hooks: {
            Stop: [{ matcher: '', hooks: [entryWithoutCommand] }],
            Notification: [{ matcher: '*' }],
            SessionStart: { enabled: true },
        },
    };

    const groupCount = mergeHooksIntoSettings(
        settings, SAMPLE_HOOKS_CONFIG, '/home/user/.claude', 'python3',
    );

    assert.equal(groupCount, 2, 'both sample matcher groups merge');
    assert.deepEqual(
        settings.hooks.Stop[0].hooks[0],
        entryWithoutCommand,
        'the entry carrying no command string keeps its place ahead of the merged hooks',
    );
    assert.equal(
        settings.hooks.Stop[0].hooks.length,
        3,
        'the two managed Stop hooks append behind the entry the installer never wrote',
    );
    assert.deepEqual(
        settings.hooks.Notification,
        [{ matcher: '*' }],
        'an event the package does not ship stays exactly as the file holds it',
    );
});


test('mergeHooksIntoSettings replaces a non-list value at a shipped event type and warns', () => {
    const settings = { hooks: { PreToolUse: { enabled: true, note: 'user authored shape' } } };

    const { allWarnings } = captureWarnings(
        () => mergeHooksIntoSettings(settings, SAMPLE_HOOKS_CONFIG, '/home/user/.claude', 'python3'),
    );

    assert.deepEqual(
        settings.hooks.PreToolUse.map(group => group.matcher),
        ['Write'],
        'the shipped PreToolUse group takes the place of the value the file held',
    );
    assert.equal(
        allWarnings.filter(warning => warning.includes('PreToolUse')).length,
        1,
        'one warning names the event type whose value was replaced',
    );
    assert.match(
        allWarnings.find(warning => warning.includes('PreToolUse')),
        /not a list of hook groups/,
        'the warning states what the replaced value was',
    );
});


test('mergeHooksIntoSettings keeps a non-list value at an event type the package does not ship', () => {
    const unshippedEventValue = { enabled: true, note: 'user authored shape' };
    const settings = { hooks: { SessionStart: unshippedEventValue } };

    const { allWarnings } = captureWarnings(
        () => mergeHooksIntoSettings(settings, SAMPLE_HOOKS_CONFIG, '/home/user/.claude', 'python3'),
    );

    assert.deepEqual(
        settings.hooks.SessionStart,
        unshippedEventValue,
        'an event type the sample config ships no groups for keeps the value the file holds',
    );
    assert.deepEqual(allWarnings, [], 'the merge warns about nothing it leaves in place');
});


test('pruneManagedHooksFromSettings keeps every settings shape the installer never wrote', () => {
    const managedPaths = new Set(['notification/attention_needed_notify.py']);
    const managedCommand = 'python3 $HOME/.claude/hooks/notification/attention_needed_notify.py';
    const entryWithoutCommand = { type: 'command' };
    const settings = {
        hooks: {
            Stop: [{
                matcher: '',
                hooks: [{ type: 'command', command: managedCommand }, entryWithoutCommand],
            }],
            Notification: [{ matcher: '*' }],
            SessionStart: { enabled: true },
        },
    };

    pruneManagedHooksFromSettings(settings, managedPaths);

    assert.deepEqual(
        settings.hooks.Stop[0].hooks,
        [entryWithoutCommand],
        'the managed entry leaves and the entry carrying no command string stays',
    );
    assert.deepEqual(settings.hooks.Notification, [{ matcher: '*' }], 'the group with no hooks array stays');
    assert.deepEqual(settings.hooks.SessionStart, { enabled: true }, 'the non-array event value stays');
});


test('pruneRetiredHookEntriesFromSettings leaves settings.json byte-identical when it retires nothing', () => {
    const { settingsPath, sandboxRoot } = createSettingsFixture({
        hooks: {
            PreToolUse: [{
                matcher: 'Write|Edit',
                hooks: [{ type: 'command', command: 'python3 my_own_gate.py --user-authored' }],
            }],
        },
    }, 2);
    try {
        const bytesBefore = readFileSync(settingsPath, 'utf8');

        const removedCount = pruneRetiredHookEntriesFromSettings(
            settingsPath, new Set([RETIRED_HOOK_RELATIVE_PATH]),
        );

        assert.equal(removedCount, 0, 'no entry runs a retired script');
        assert.equal(
            readFileSync(settingsPath, 'utf8'),
            bytesBefore,
            'the file keeps its own formatting, so a run that retires nothing writes nothing',
        );
    } finally {
        rmSync(sandboxRoot, { recursive: true, force: true });
    }
});


const PRIOR_RUN_BACKUP_NAMES = ['2020-01-01T00-00-00-000Z', '2021-06-15T12-30-45-123Z'];
const THIS_RUN_BACKUP_NAME = '2026-07-25T18-04-11-923Z';
const MOVED_SKILL_BACKUP_SEGMENTS = ['skills', 'demo'];


/**
 * Build a pruned-backup directory holding two prior run backups and this run's
 * own root, with the directories a move creates ahead of its rename already there.
 *
 * @param {boolean} doesThisRunHoldMovedContent Whether this run's root holds a moved file.
 * @returns {{root: string, prunedDirectory: string, runBackupRoot: string, movedFilePath: string}} The sandbox paths.
 */
function createRunBackupSandbox(doesThisRunHoldMovedContent) {
    const root = mkdtempSync(join(tmpdir(), 'cdev-run-backup-'));
    const prunedDirectory = join(root, '.claude-dev-env-pruned');
    for (const priorRunName of PRIOR_RUN_BACKUP_NAMES) {
        const priorRunDirectory = join(prunedDirectory, priorRunName);
        mkdirSync(priorRunDirectory, { recursive: true });
        writeFileSync(join(priorRunDirectory, 'recovered.md'), `content ${priorRunName} holds\n`);
    }
    const runBackupRoot = join(prunedDirectory, THIS_RUN_BACKUP_NAME);
    mkdirSync(join(runBackupRoot, ...MOVED_SKILL_BACKUP_SEGMENTS), { recursive: true });
    const movedFilePath = join(runBackupRoot, ...MOVED_SKILL_BACKUP_SEGMENTS, 'SKILL.md');
    if (doesThisRunHoldMovedContent) writeFileSync(movedFilePath, '# a skill moved aside\n');
    return { root, prunedDirectory, runBackupRoot, movedFilePath };
}


/**
 * List the run backup directory names under a pruned-backup directory, sorted.
 *
 * @param {string} prunedDirectory The directory holding the run backups.
 * @returns {string[]} The directory names in sorted order.
 */
function listRunBackupNames(prunedDirectory) {
    return readdirSync(prunedDirectory, { withFileTypes: true })
        .filter(entry => entry.isDirectory())
        .map(entry => entry.name)
        .sort();
}


test('retainNewestRunBackupOnly keeps every prior run backup and clears the empty root of a run that moved nothing', () => {
    const sandbox = createRunBackupSandbox(false);
    try {
        retainNewestRunBackupOnly(sandbox.runBackupRoot, false);

        assert.deepEqual(
            listRunBackupNames(sandbox.prunedDirectory),
            [...PRIOR_RUN_BACKUP_NAMES].sort(),
            'every recovery point the user holds stays where it is',
        );
        assert.equal(
            existsSync(sandbox.runBackupRoot),
            false,
            'the empty directories the attempted moves created leave the pruned-backup directory',
        );
    } finally {
        rmSync(sandbox.root, { recursive: true, force: true });
    }
});


test('retainNewestRunBackupOnly retires every older run backup once this run holds moved content', () => {
    const sandbox = createRunBackupSandbox(true);
    try {
        retainNewestRunBackupOnly(sandbox.runBackupRoot, true);

        assert.deepEqual(
            listRunBackupNames(sandbox.prunedDirectory),
            [THIS_RUN_BACKUP_NAME],
            'the run that moved content leaves its own backup as the only recovery point',
        );
        assert.equal(
            existsSync(sandbox.movedFilePath),
            true,
            'the surviving backup holds the content this run moved aside',
        );
    } finally {
        rmSync(sandbox.root, { recursive: true, force: true });
    }
});


test('retainNewestRunBackupOnly keeps a run backup root that holds content when the run reports no move', () => {
    const sandbox = createRunBackupSandbox(true);
    try {
        retainNewestRunBackupOnly(sandbox.runBackupRoot, false);

        assert.deepEqual(
            listRunBackupNames(sandbox.prunedDirectory),
            [...PRIOR_RUN_BACKUP_NAMES, THIS_RUN_BACKUP_NAME].sort(),
            'every run backup stays, so clearing an empty root never reaches a file',
        );
        assert.equal(existsSync(sandbox.movedFilePath), true, 'the file inside the root stays');
    } finally {
        rmSync(sandbox.root, { recursive: true, force: true });
    }
});


test('pruneStaleInstalledFiles leaves the run backup root standing when the rename fails', () => {
    const sandbox = createStalePruneSandbox({
        'demo/scripts/retired_module.py': 'stale module\n',
    });
    try {
        const occupiedDestination = join(sandbox.backupRoot, 'demo', 'scripts', 'retired_module.py');
        mkdirSync(occupiedDestination, { recursive: true });
        writeFileSync(join(occupiedDestination, 'inner.md'), 'content standing where the move lands\n');
        const staleFilePath = join(sandbox.skillsRoot, 'demo', 'scripts', 'retired_module.py');

        const { returnedValue } = captureWarnings(() => pruneStaleInstalledFiles(
            [staleFilePath],
            [],
            sandbox.skillsRoot,
            sandbox.backupRoot,
            { managedHomeDirectory: sandbox.root },
        ));

        assert.equal(returnedValue.prunedCount, 0, 'a rename onto an occupied path moves nothing');
        assert.deepEqual(
            returnedValue.failedPaths,
            [staleFilePath],
            'the failed path is reported so the caller keeps it on the manifest record',
        );
        assert.equal(existsSync(staleFilePath), true, 'the file stays in the installed tree');
        assert.equal(
            existsSync(sandbox.backupRoot),
            true,
            'the mover creates the run backup root ahead of the rename, so retention reads the move count rather than the directory',
        );
    } finally {
        rmSync(sandbox.root, { recursive: true, force: true });
    }
});
