/**
 * Two install roots that share one settings.json through a symlink keep one
 * hook entry per managed script, whatever order the roots install in.
 */

import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { join } from 'node:path';
import {
    mkdtempSync,
    mkdirSync,
    readFileSync,
    rmSync,
    symlinkSync,
    writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { managedHookScriptRelativePaths, mergeHooksIntoSettings } from './install.mjs';

const INSTALLER_PATH = fileURLToPath(new URL('./install.mjs', import.meta.url));
const PACKAGE_HOOKS_JSON_PATH = fileURLToPath(new URL('../hooks/hooks.json', import.meta.url));

function installEnvironment(homeDirectory) {
    return {
        ...process.env,
        HOME: homeDirectory,
        USERPROFILE: homeDirectory,
        CLAUDE_CONFIG_DIR: '',
        GIT_CONFIG_GLOBAL: join(homeDirectory, '.gitconfig'),
        CDE_INSTALL_PSTACK: '0',
        CDE_INSTALL_USAGE_WRAPUP: '0',
    };
}

function runCoreInstall(homeDirectory, extraArguments) {
    const installRun = spawnSync(
        process.execPath,
        [INSTALLER_PATH, '--only', 'core', ...extraArguments],
        { encoding: 'utf8', env: installEnvironment(homeDirectory) },
    );
    assert.equal(installRun.status, 0, installRun.stdout + installRun.stderr);
}

function allHookCommands(settingsPath) {
    const settings = JSON.parse(readFileSync(settingsPath, 'utf8'));
    const allCommands = [];
    for (const matcherGroups of Object.values(settings.hooks ?? {})) {
        for (const group of matcherGroups) {
            for (const hook of group.hooks ?? []) {
                if (typeof hook.command === 'string') allCommands.push(hook.command.replace(/\\/g, '/'));
            }
        }
    }
    return allCommands;
}

function entryCountByScript(settingsPath) {
    const hooksConfig = JSON.parse(readFileSync(PACKAGE_HOOKS_JSON_PATH, 'utf8'));
    const allCommands = allHookCommands(settingsPath);
    const countByScript = new Map();
    for (const relativePath of managedHookScriptRelativePaths(hooksConfig)) {
        const scriptPattern = new RegExp(`/hooks/${relativePath.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?=$|[\\s'";])`, 'g');
        const occurrences = allCommands.reduce(
            (total, command) => total + (command.match(scriptPattern) ?? []).length,
            0,
        );
        countByScript.set(relativePath, occurrences);
    }
    return countByScript;
}

function expectedCountByScript(hooksConfig) {
    const countByScript = new Map();
    for (const matcherGroups of Object.values(hooksConfig.hooks)) {
        for (const group of matcherGroups) {
            for (const hook of group.hooks) {
                for (const match of hook.command.matchAll(/\$\{CLAUDE_PLUGIN_ROOT\}\/hooks\/(\S+?\.(?:py|mjs))/g)) {
                    countByScript.set(match[1], (countByScript.get(match[1]) ?? 0) + 1);
                }
            }
        }
    }
    return countByScript;
}

function assertOneEntryPerHookRegistration(settingsPath, stageName) {
    const hooksConfig = JSON.parse(readFileSync(PACKAGE_HOOKS_JSON_PATH, 'utf8'));
    const expectedCounts = expectedCountByScript(hooksConfig);
    const actualCounts = entryCountByScript(settingsPath);
    assert.ok(expectedCounts.size > 0, 'the package ships managed hook scripts');
    for (const [relativePath, expectedCount] of expectedCounts) {
        assert.equal(
            actualCounts.get(relativePath),
            expectedCount,
            `${stageName}: ${relativePath} is registered once per hooks.json entry`,
        );
    }
}

function withSharedSettingsHome(runScenario) {
    return t => {
        const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-shared-settings-'));
        try {
            writeFileSync(join(homeDirectory, '.gitconfig'), '');
            const mainRoot = join(homeDirectory, '.claude');
            const profileRoot = join(homeDirectory, 'profiles', 'second');
            mkdirSync(mainRoot, { recursive: true });
            mkdirSync(profileRoot, { recursive: true });
            const mainSettingsPath = join(mainRoot, 'settings.json');
            writeFileSync(mainSettingsPath, '{}\n');
            try {
                symlinkSync(mainSettingsPath, join(profileRoot, 'settings.json'), 'file');
            } catch (linkError) {
                t.skip(`this host cannot create a file symlink (${linkError.code})`);
                return;
            }
            runScenario({ homeDirectory, profileRoot, mainSettingsPath });
        } finally {
            rmSync(homeDirectory, { recursive: true, force: true });
        }
    };
}

test(
    'main then profile then main keeps one entry per hook in the shared settings file',
    withSharedSettingsHome(({ homeDirectory, profileRoot, mainSettingsPath }) => {
        runCoreInstall(homeDirectory, []);
        assertOneEntryPerHookRegistration(mainSettingsPath, 'after the main install');
        runCoreInstall(homeDirectory, ['--target', profileRoot]);
        assertOneEntryPerHookRegistration(mainSettingsPath, 'after the profile install');
        runCoreInstall(homeDirectory, []);
        assertOneEntryPerHookRegistration(mainSettingsPath, 'after the main rerun');
    }),
);

test(
    'profile then main then profile keeps one entry per hook in the shared settings file',
    withSharedSettingsHome(({ homeDirectory, profileRoot, mainSettingsPath }) => {
        runCoreInstall(homeDirectory, ['--target', profileRoot]);
        assertOneEntryPerHookRegistration(mainSettingsPath, 'after the profile install');
        runCoreInstall(homeDirectory, []);
        assertOneEntryPerHookRegistration(mainSettingsPath, 'after the main install');
        runCoreInstall(homeDirectory, ['--target', profileRoot]);
        assertOneEntryPerHookRegistration(mainSettingsPath, 'after the profile rerun');
    }),
);

test('the merge prunes a hook of a root sharing the settings file and keeps one with its own file', t => {
    const sandboxRoot = mkdtempSync(join(tmpdir(), 'cdev-shared-settings-unit-'));
    try {
        const installRoot = join(sandboxRoot, 'install-root');
        const sharingRoot = join(sandboxRoot, 'sharing-root');
        const separateRoot = join(sandboxRoot, 'separate-root');
        for (const eachRoot of [installRoot, sharingRoot, separateRoot]) mkdirSync(eachRoot, { recursive: true });
        const settingsPath = join(installRoot, 'settings.json');
        writeFileSync(settingsPath, '{}\n');
        writeFileSync(join(separateRoot, 'settings.json'), '{}\n');
        try {
            symlinkSync(settingsPath, join(sharingRoot, 'settings.json'), 'file');
        } catch (linkError) {
            t.skip(`this host cannot create a file symlink (${linkError.code})`);
            return;
        }
        const hooksConfig = {
            hooks: {
                SessionStart: [{
                    matcher: '',
                    hooks: [{ type: 'command', command: 'python3 ${CLAUDE_PLUGIN_ROOT}/hooks/session/start.py' }],
                }],
            },
        };
        const forwardSlashed = rootPath => rootPath.replace(/\\/g, '/');
        const sharingCommand = `python3 "${forwardSlashed(sharingRoot)}/hooks/session/start.py"`;
        const separateCommand = `python3 "${forwardSlashed(separateRoot)}/hooks/session/start.py"`;
        const settings = {
            hooks: {
                SessionStart: [{
                    matcher: '',
                    hooks: [
                        { type: 'command', command: sharingCommand },
                        { type: 'command', command: separateCommand },
                    ],
                }],
            },
        };

        mergeHooksIntoSettings(settings, hooksConfig, forwardSlashed(installRoot), 'python3', settingsPath);

        const allCommands = settings.hooks.SessionStart.flatMap(group => group.hooks.map(hook => hook.command));
        assert.ok(!allCommands.includes(sharingCommand), 'the sharing root entry is pruned');
        assert.ok(allCommands.includes(separateCommand), 'the separate root entry stays');
        assert.equal(
            allCommands.filter(command => command.includes(`${forwardSlashed(installRoot)}/hooks/session/start.py`)).length,
            1,
            'the install root entry is written once',
        );
    } finally {
        rmSync(sandboxRoot, { recursive: true, force: true });
    }
});
