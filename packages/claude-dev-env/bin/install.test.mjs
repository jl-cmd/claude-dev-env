import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync, mkdirSync, writeFileSync, symlinkSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

import {
    collectPackageSourceConflicts,
    CONTENT_DIRECTORIES,
    FOLDED_HOOK_RELATIVE_PATHS,
    POST_FOLDED_HOOK_RELATIVE_PATHS,
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
    for (const foldedPath of FOLDED_HOOK_RELATIVE_PATHS) {
        assert.ok(relativePaths.has(foldedPath), `folded hook ${foldedPath} must always be in the managed set`);
    }
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
            hooks: { PreToolUse: [{ matcher: 'Bash', hooks: [{ command: 'python3 ${CLAUDE_PLUGIN_ROOT}/hooks/blocking/pwsh_enforcer.py' }] }] },
        });

        const relativePaths = managedHookScriptRelativePathsFromSourceRoots([builtinRoot, dependencyRoot]);

        assert.ok(relativePaths.has('blocking/code_rules_enforcer.py'));
        assert.ok(relativePaths.has('blocking/pwsh_enforcer.py'));
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


test('FOLDED_HOOK_RELATIVE_PATHS contains all 15 hooks removed from hooks.json', () => {
    assert.equal(FOLDED_HOOK_RELATIVE_PATHS.size, 15);
    assert.ok(FOLDED_HOOK_RELATIVE_PATHS.has('blocking/write_existing_file_blocker.py'));
    assert.ok(FOLDED_HOOK_RELATIVE_PATHS.has('blocking/plain_language_blocker.py'));
    assert.ok(FOLDED_HOOK_RELATIVE_PATHS.has('blocking/code_rules_enforcer.py'));
    assert.ok(FOLDED_HOOK_RELATIVE_PATHS.has('blocking/pytest_testpaths_orphan_blocker.py'));
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
        'blocking/pytest_testpaths_orphan_blocker.py',
        'blocking/open_questions_in_plans_blocker.py',
        'blocking/plain_language_blocker.py',
    ];
    for (const hostedPath of dispatcherHostedHooks) {
        assert.ok(
            FOLDED_HOOK_RELATIVE_PATHS.has(hostedPath),
            `dispatcher-hosted hook ${hostedPath} must be in FOLDED_HOOK_RELATIVE_PATHS so a reinstall prunes its stale standalone entry and it does not double-run`
        );
    }
    assert.equal(
        FOLDED_HOOK_RELATIVE_PATHS.size,
        dispatcherHostedHooks.length,
        'FOLDED_HOOK_RELATIVE_PATHS must hold exactly the dispatcher-hosted hooks, no more, no fewer'
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

    const allDispatcherCommands = allHookCommands.filter(cmd => cmd.includes('pre_tool_use_dispatcher.py'));
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

    const allDispatcherCommands = allHookCommands.filter(cmd => cmd.includes('pre_tool_use_dispatcher.py'));
    assert.equal(allDispatcherCommands.length, 1, 'dispatcher must appear exactly once after two merges');
    assert.equal(countManagedRunAllValidatorsHooks(settings), 1, 'run_all_validators must appear exactly once after two merges');
});


test('shipped hooks.json matches the dispatcher design: dispatchers registered, run_all_validators retained, no folded hook standalone', () => {
    const shippedHooksConfig = JSON.parse(
        readFileSync(new URL('../hooks/hooks.json', import.meta.url), 'utf8')
    );

    const allPreToolUseGroups = shippedHooksConfig.hooks.PreToolUse || [];
    const allPreCommands = allPreToolUseGroups.flatMap(group => group.hooks.map(hook => hook.command));
    const preDispatcherCommands = allPreCommands.filter(cmd => cmd.includes('pre_tool_use_dispatcher.py'));
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


test('POST_FOLDED_HOOK_RELATIVE_PATHS contains the three after-write hooks folded into the PostToolUse dispatcher', () => {
    assert.equal(POST_FOLDED_HOOK_RELATIVE_PATHS.size, 3);
    assert.ok(POST_FOLDED_HOOK_RELATIVE_PATHS.has('validation/mypy_validator.py'));
    assert.ok(POST_FOLDED_HOOK_RELATIVE_PATHS.has('workflow/auto_formatter.py'));
    assert.ok(POST_FOLDED_HOOK_RELATIVE_PATHS.has('workflow/doc_gist_auto_publish.py'));
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
    const dispatcherCommands = dispatcherGroup.hooks.filter(hook => hook.command.includes('pre_tool_use_dispatcher.py'));
    assert.equal(dispatcherCommands.length, 1, 'the PreToolUse dispatcher must remain exactly once');
});
