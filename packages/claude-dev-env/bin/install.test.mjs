import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync, mkdirSync, writeFileSync, symlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

import {
    collectPackageSourceConflicts,
    CONTENT_DIRECTORIES,
    pythonCandidatesForPlatform,
    isWindowsStorePythonStub,
    interpreterCommandFromPath,
    invokedAsEntryPoint,
    managedHookScriptRelativePaths,
    managedHookScriptRelativePathsFromSourceRoots,
    commandReferencesManagedHook,
    mergeHooksIntoSettings,
    pruneManagedHooksFromSettings,
} from './install.mjs';


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
        isWindowsStorePythonStub('C:/Users/jon/AppData/Local/Microsoft/WindowsApps/python.exe'),
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
    assert.equal([...relativePaths].length, 2);
});


test('commandReferencesManagedHook matches managed scripts written with $HOME, ~, ${HOME}, and absolute path styles', () => {
    const managedPaths = new Set(['notification/attention_needed_notify.py']);
    assert.ok(commandReferencesManagedHook('python $HOME/.claude/hooks/notification/attention_needed_notify.py', managedPaths));
    assert.ok(commandReferencesManagedHook('python ~/.claude/hooks/notification/attention_needed_notify.py', managedPaths));
    assert.ok(commandReferencesManagedHook('python ${HOME}/.claude/hooks/notification/attention_needed_notify.py', managedPaths));
    assert.ok(commandReferencesManagedHook('py -3 C:/Users/jonlo/.claude/hooks/notification/attention_needed_notify.py', managedPaths));
    assert.ok(commandReferencesManagedHook('python /Users/jon/.claude/hooks/notification/attention_needed_notify.py', managedPaths));
});


test('commandReferencesManagedHook matches Windows backslash paths', () => {
    const managedPaths = new Set(['blocking/hedging_language_blocker.py']);
    assert.ok(commandReferencesManagedHook('py -3 C:\\Users\\jonlo\\.claude\\hooks\\blocking\\hedging_language_blocker.py', managedPaths));
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
        "py -3 -c \"import sys; sys.path.insert(0, r'C:/Users/jonlo/.claude/hooks'); from validators.run_all_validators import main; sys.exit(main())\"";
    assert.ok(commandReferencesManagedHook(rewrittenInlineCommand, managedPaths));
});


test('commandReferencesManagedHook leaves an unmanaged inline -c command that imports a different module untouched', () => {
    const managedPaths = new Set(['blocking/code_rules_enforcer.py']);
    const userInlineCommand =
        "python -c \"import sys; sys.path.insert(0, r'/home/me/tools'); from my_tools.runner import main; sys.exit(main())\"";
    assert.equal(commandReferencesManagedHook(userInlineCommand, managedPaths), false);
});


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
    const pluginRootDir = 'C:/Users/jonlo/.claude';

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

    mergeHooksIntoSettings(settings, hooksConfig, 'C:/Users/jonlo/.claude', 'py -3');
    mergeHooksIntoSettings(settings, hooksConfig, 'C:/Users/jonlo/.claude', 'py -3');

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
                        { command: 'py -3 C:\\Users\\jonlo\\.claude\\hooks\\notification\\attention_needed_notify.py', timeout: 15 },
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
        assert.equal([...relativePaths].length, 2);
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
            hooks: { PreToolUse: [{ matcher: 'Bash', hooks: [{ command: 'python3 ${CLAUDE_PLUGIN_ROOT}/hooks/blocking/pwsh_enforcer.py' }] }] },
        });

        const relativePaths = managedHookScriptRelativePathsFromSourceRoots([builtinRoot, dependencyRoot]);

        assert.ok(relativePaths.has('blocking/code_rules_enforcer.py'));
        assert.ok(relativePaths.has('blocking/pwsh_enforcer.py'));
        assert.equal([...relativePaths].length, 2);
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
                            { command: 'py -3 C:\\Users\\jonlo\\.claude\\hooks\\blocking\\code_rules_enforcer.py', timeout: 30 },
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
