/**
 * Uninstall plan preflight and transactional recovery (control-plane F / P-19).
 */

import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import {
    existsSync,
    mkdtempSync,
    mkdirSync,
    readFileSync,
    rmSync,
    writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync, spawnSync } from 'node:child_process';
import {
    buildUninstallPlan,
    InstallPlanPreflightError,
    MALFORMED_SETTINGS_ERROR_MESSAGE,
    PREFLIGHT_ERROR_CODES,
    SETTINGS_NOT_OBJECT_ERROR_MESSAGE,
} from './install-plan.mjs';
import {
    FAULT_PHASES,
    INSTALL_FAULT_ENV,
    InstallTransactionFaultError,
    readGlobalCoreHooksPath,
    writeGlobalCoreHooksPath,
} from './install-transaction.mjs';

const THIS_DIRECTORY = dirname(fileURLToPath(import.meta.url));
const INSTALLER_PATH = join(THIS_DIRECTORY, 'install.mjs');
const MANIFEST_FILE_NAME = '.claude-dev-env-manifest.json';
const SETTINGS_FILE_NAME = 'settings.json';
const USER_OWNED_MARKER = 'user-owned-body\n';
const PRIOR_RULES_BODY = 'prior-rules-body\n';
const PRIOR_SETTINGS_MARKER = 'prior-uninstall-settings';

/**
 * @returns {{ root: string, managedRoot: string, settingsPath: string, manifestFilePath: string }}
 */
function sandbox() {
    const root = mkdtempSync(join(tmpdir(), 'cdev-uninstall-txn-'));
    const managedRoot = join(root, 'managed');
    mkdirSync(managedRoot, { recursive: true });
    return {
        root,
        managedRoot,
        settingsPath: join(managedRoot, SETTINGS_FILE_NAME),
        manifestFilePath: join(managedRoot, MANIFEST_FILE_NAME),
    };
}

/**
 * @param {string} filePath
 * @param {string} contents
 */
function writeFileWithParents(filePath, contents) {
    mkdirSync(dirname(filePath), { recursive: true });
    writeFileSync(filePath, contents);
}

/**
 * @param {string} homeDirectory
 * @param {string[]} extraArguments
 * @param {{ faultPhase?: string|null }} [options]
 */
function runInstaller(homeDirectory, extraArguments, options = {}) {
    const childEnvironment = {
        ...process.env,
        HOME: homeDirectory,
        USERPROFILE: homeDirectory,
        GIT_CONFIG_GLOBAL: join(homeDirectory, '.gitconfig'),
        CODEX_HOME: join(homeDirectory, '.codex'),
    };
    if (options.faultPhase) {
        childEnvironment[INSTALL_FAULT_ENV] = options.faultPhase;
    } else {
        delete childEnvironment[INSTALL_FAULT_ENV];
    }
    return spawnSync(process.execPath, [INSTALLER_PATH, ...extraArguments], {
        cwd: THIS_DIRECTORY,
        encoding: 'utf8',
        env: childEnvironment,
    });
}

/**
 * @param {string} homeDirectory
 * @returns {{ claudeDirectory: string, rulesFile: string, userOwnedFile: string }}
 */
function seedPriorInstall(homeDirectory) {
    const claudeDirectory = join(homeDirectory, '.claude');
    const rulesFile = join(claudeDirectory, 'rules', 'prior.md');
    const userOwnedFile = join(claudeDirectory, 'rules', 'user-owned.md');
    writeFileWithParents(rulesFile, PRIOR_RULES_BODY);
    writeFileWithParents(userOwnedFile, USER_OWNED_MARKER);
    writeFileWithParents(
        join(claudeDirectory, SETTINGS_FILE_NAME),
        `${JSON.stringify({
            hooks: { UserPromptSubmit: [] },
            customMarker: PRIOR_SETTINGS_MARKER,
        }, null, 2)}\n`,
    );
    writeFileWithParents(
        join(claudeDirectory, MANIFEST_FILE_NAME),
        `${JSON.stringify({
            packageName: 'claude-dev-env',
            files: [rulesFile],
            skills: [],
        }, null, 2)}\n`,
    );
    writeFileSync(join(homeDirectory, '.gitconfig'), '');
    return { claudeDirectory, rulesFile, userOwnedFile };
}

test('buildUninstallPlan rejects malformed settings before any plan freezes', () => {
    const box = sandbox();
    try {
        const rulesFile = join(box.managedRoot, 'rules', 'a.md');
        writeFileWithParents(rulesFile, 'x\n');
        writeFileSync(box.settingsPath, '{not-json\n');
        writeFileSync(
            box.manifestFilePath,
            `${JSON.stringify({ files: [rulesFile], skills: [] })}\n`,
        );
        assert.throws(
            () => buildUninstallPlan({
                managedRoot: box.managedRoot,
                manifestFilePath: box.manifestFilePath,
                requireManifest: true,
                isRemovableRecord: () => true,
            }),
            (error) => error instanceof InstallPlanPreflightError
                && error.code === PREFLIGHT_ERROR_CODES.MALFORMED_SETTINGS
                && error.message === MALFORMED_SETTINGS_ERROR_MESSAGE,
        );
        assert.equal(existsSync(rulesFile), true);
        assert.equal(readFileSync(box.settingsPath, 'utf8'), '{not-json\n');
    } finally {
        rmSync(box.root, { recursive: true, force: true });
    }
});

test('buildUninstallPlan rejects non-object settings before any plan freezes', () => {
    const box = sandbox();
    try {
        const rulesFile = join(box.managedRoot, 'rules', 'a.md');
        writeFileWithParents(rulesFile, 'x\n');
        writeFileSync(box.settingsPath, '["array-not-object"]\n');
        writeFileSync(
            box.manifestFilePath,
            `${JSON.stringify({ files: [rulesFile], skills: [] })}\n`,
        );
        assert.throws(
            () => buildUninstallPlan({
                managedRoot: box.managedRoot,
                manifestFilePath: box.manifestFilePath,
                requireManifest: true,
                isRemovableRecord: () => true,
            }),
            (error) => error instanceof InstallPlanPreflightError
                && error.code === PREFLIGHT_ERROR_CODES.MALFORMED_SETTINGS
                && error.message === SETTINGS_NOT_OBJECT_ERROR_MESSAGE,
        );
        assert.equal(existsSync(rulesFile), true);
    } finally {
        rmSync(box.root, { recursive: true, force: true });
    }
});

test('buildUninstallPlan freezes removable files and skips non-removable records', () => {
    const box = sandbox();
    try {
        const removable = join(box.managedRoot, 'rules', 'keep.md');
        const foreign = join(box.root, 'outside.txt');
        writeFileWithParents(removable, 'managed\n');
        writeFileSync(foreign, 'foreign\n');
        writeFileSync(box.settingsPath, '{"hooks":{}}\n');
        writeFileSync(
            box.manifestFilePath,
            `${JSON.stringify({ files: [removable, foreign], skills: ['s'] })}\n`,
        );
        const plan = buildUninstallPlan({
            managedRoot: box.managedRoot,
            manifestFilePath: box.manifestFilePath,
            requireManifest: true,
            isRemovableRecord: (eachPath) => eachPath === removable,
        });
        assert.ok(Object.isFrozen(plan));
        assert.deepEqual(plan.removableFiles, [removable]);
        assert.deepEqual(plan.skippedFiles, [foreign]);
        assert.equal(plan.settingsPath, box.settingsPath);
        assert.equal(plan.manifestExisted, true);
    } finally {
        rmSync(box.root, { recursive: true, force: true });
    }
});

test('installer refuses malformed settings before removing managed files', () => {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-uninstall-malformed-'));
    try {
        const { claudeDirectory, rulesFile, userOwnedFile } = seedPriorInstall(homeDirectory);
        writeFileSync(join(claudeDirectory, SETTINGS_FILE_NAME), '{broken\n');

        const failedRun = runInstaller(homeDirectory, ['--uninstall']);
        assert.notEqual(failedRun.status, 0, failedRun.stdout + failedRun.stderr);
        assert.match(`${failedRun.stdout}${failedRun.stderr}`, /malformed/i);
        assert.equal(readFileSync(rulesFile, 'utf8'), PRIOR_RULES_BODY);
        assert.equal(readFileSync(userOwnedFile, 'utf8'), USER_OWNED_MARKER);
        assert.equal(existsSync(join(claudeDirectory, MANIFEST_FILE_NAME)), true);
    } finally {
        rmSync(homeDirectory, { recursive: true, force: true });
    }
});

test('installer refuses non-object settings before removing managed files', () => {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-uninstall-nonobj-'));
    try {
        const { claudeDirectory, rulesFile } = seedPriorInstall(homeDirectory);
        writeFileSync(join(claudeDirectory, SETTINGS_FILE_NAME), '"string-settings"\n');

        const failedRun = runInstaller(homeDirectory, ['--uninstall']);
        assert.notEqual(failedRun.status, 0, failedRun.stdout + failedRun.stderr);
        assert.match(`${failedRun.stdout}${failedRun.stderr}`, /object/i);
        assert.equal(readFileSync(rulesFile, 'utf8'), PRIOR_RULES_BODY);
        assert.equal(existsSync(join(claudeDirectory, MANIFEST_FILE_NAME)), true);
    } finally {
        rmSync(homeDirectory, { recursive: true, force: true });
    }
});

test('uninstall fault after_file_staging restores files, settings, and manifest', () => {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-uninstall-files-'));
    try {
        const { claudeDirectory, rulesFile, userOwnedFile } = seedPriorInstall(homeDirectory);
        const priorSettings = readFileSync(join(claudeDirectory, SETTINGS_FILE_NAME), 'utf8');
        const priorManifest = readFileSync(join(claudeDirectory, MANIFEST_FILE_NAME), 'utf8');

        const failedRun = runInstaller(homeDirectory, ['--uninstall'], {
            faultPhase: FAULT_PHASES.AFTER_FILE_STAGING,
        });
        assert.notEqual(failedRun.status, 0, failedRun.stdout + failedRun.stderr);
        assert.match(`${failedRun.stdout}${failedRun.stderr}`, /fault|restored|aborted/i);
        assert.equal(readFileSync(rulesFile, 'utf8'), PRIOR_RULES_BODY);
        assert.equal(readFileSync(userOwnedFile, 'utf8'), USER_OWNED_MARKER);
        assert.equal(readFileSync(join(claudeDirectory, SETTINGS_FILE_NAME), 'utf8'), priorSettings);
        assert.equal(readFileSync(join(claudeDirectory, MANIFEST_FILE_NAME), 'utf8'), priorManifest);
    } finally {
        rmSync(homeDirectory, { recursive: true, force: true });
    }
});

test('uninstall fault after_settings_write restores prior settings and files', () => {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-uninstall-settings-'));
    try {
        const { claudeDirectory, rulesFile } = seedPriorInstall(homeDirectory);
        const priorSettings = readFileSync(join(claudeDirectory, SETTINGS_FILE_NAME), 'utf8');

        const failedRun = runInstaller(homeDirectory, ['--uninstall'], {
            faultPhase: FAULT_PHASES.AFTER_SETTINGS_WRITE,
        });
        assert.notEqual(failedRun.status, 0, failedRun.stdout + failedRun.stderr);
        assert.equal(readFileSync(join(claudeDirectory, SETTINGS_FILE_NAME), 'utf8'), priorSettings);
        assert.equal(readFileSync(rulesFile, 'utf8'), PRIOR_RULES_BODY);
        assert.equal(existsSync(join(claudeDirectory, MANIFEST_FILE_NAME)), true);
        assert.match(
            readFileSync(join(claudeDirectory, MANIFEST_FILE_NAME), 'utf8'),
            /prior\.md|claude-dev-env/,
        );
    } finally {
        rmSync(homeDirectory, { recursive: true, force: true });
    }
});

test('uninstall fault after_manifest_write restores prior manifest and files', () => {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-uninstall-manifest-'));
    try {
        const { claudeDirectory, rulesFile } = seedPriorInstall(homeDirectory);
        const priorManifest = readFileSync(join(claudeDirectory, MANIFEST_FILE_NAME), 'utf8');

        const failedRun = runInstaller(homeDirectory, ['--uninstall'], {
            faultPhase: FAULT_PHASES.AFTER_MANIFEST_WRITE,
        });
        assert.notEqual(failedRun.status, 0, failedRun.stdout + failedRun.stderr);
        assert.equal(readFileSync(join(claudeDirectory, MANIFEST_FILE_NAME), 'utf8'), priorManifest);
        assert.equal(readFileSync(rulesFile, 'utf8'), PRIOR_RULES_BODY);
    } finally {
        rmSync(homeDirectory, { recursive: true, force: true });
    }
});

test('uninstall fault after_git_config restores prior core.hooksPath', () => {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-uninstall-git-'));
    try {
        seedPriorInstall(homeDirectory);
        const gitConfigPath = join(homeDirectory, '.gitconfig');
        const priorHooksPath = join(homeDirectory, '.claude', 'hooks', 'git-hooks');
        mkdirSync(priorHooksPath, { recursive: true });
        const io = {
            env: {
                ...process.env,
                HOME: homeDirectory,
                USERPROFILE: homeDirectory,
                GIT_CONFIG_GLOBAL: gitConfigPath,
            },
            execFileSync,
        };
        writeGlobalCoreHooksPath(priorHooksPath, io);

        const failedRun = runInstaller(homeDirectory, ['--uninstall'], {
            faultPhase: FAULT_PHASES.AFTER_GIT_CONFIG,
        });
        assert.notEqual(failedRun.status, 0, failedRun.stdout + failedRun.stderr);

        const restored = readGlobalCoreHooksPath(io);
        assert.equal(restored, priorHooksPath);
    } finally {
        rmSync(homeDirectory, { recursive: true, force: true });
    }
});

test('retry after restored uninstall fault completes and clears the installation', () => {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-uninstall-retry-'));
    try {
        const { claudeDirectory, rulesFile, userOwnedFile } = seedPriorInstall(homeDirectory);

        const failedRun = runInstaller(homeDirectory, ['--uninstall'], {
            faultPhase: FAULT_PHASES.AFTER_SETTINGS_WRITE,
        });
        assert.notEqual(failedRun.status, 0, failedRun.stdout + failedRun.stderr);
        assert.equal(existsSync(rulesFile), true);
        assert.equal(existsSync(join(claudeDirectory, MANIFEST_FILE_NAME)), true);

        const okRun = runInstaller(homeDirectory, ['--uninstall']);
        assert.equal(okRun.status, 0, okRun.stdout + okRun.stderr);
        assert.equal(existsSync(rulesFile), false);
        assert.equal(existsSync(join(claudeDirectory, MANIFEST_FILE_NAME)), false);
        assert.equal(readFileSync(userOwnedFile, 'utf8'), USER_OWNED_MARKER);
        assert.equal(existsSync(join(claudeDirectory, '.claude-dev-env-txn')), false);
    } finally {
        rmSync(homeDirectory, { recursive: true, force: true });
    }
});

test('uninstall of a selected managed root leaves a sibling root unchanged', () => {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-uninstall-target-'));
    try {
        const managedRootsParent = join(homeDirectory, 'managed-roots');
        const profileARoot = join(managedRootsParent, 'profile-a');
        const profileBRoot = join(managedRootsParent, 'profile-b');
        mkdirSync(profileARoot, { recursive: true });
        mkdirSync(profileBRoot, { recursive: true });

        const profileARules = join(profileARoot, 'rules', 'profile-a.md');
        const profileBRules = join(profileBRoot, 'rules', 'profile-b.md');
        writeFileWithParents(profileARules, 'profile-a-body\n');
        writeFileWithParents(profileBRules, 'profile-b-body\n');
        writeFileWithParents(
            join(profileARoot, SETTINGS_FILE_NAME),
            `${JSON.stringify({ hooks: {}, marker: 'profile-a' }, null, 2)}\n`,
        );
        writeFileWithParents(
            join(profileBRoot, SETTINGS_FILE_NAME),
            `${JSON.stringify({ hooks: {}, marker: 'profile-b' }, null, 2)}\n`,
        );
        writeFileWithParents(
            join(profileARoot, MANIFEST_FILE_NAME),
            `${JSON.stringify({
                packageName: 'claude-dev-env',
                targetIdentity: 'profile-a',
                files: [profileARules],
                skills: [],
            }, null, 2)}\n`,
        );
        writeFileWithParents(
            join(profileBRoot, MANIFEST_FILE_NAME),
            `${JSON.stringify({
                packageName: 'claude-dev-env',
                targetIdentity: 'profile-b',
                files: [profileBRules],
                skills: [],
            }, null, 2)}\n`,
        );
        writeFileSync(join(homeDirectory, '.gitconfig'), '');

        const failedOnFault = runInstaller(
            homeDirectory,
            ['--target', profileARoot, '--uninstall'],
            { faultPhase: FAULT_PHASES.AFTER_FILE_STAGING },
        );
        assert.notEqual(failedOnFault.status, 0, failedOnFault.stdout + failedOnFault.stderr);
        assert.equal(readFileSync(profileARules, 'utf8'), 'profile-a-body\n');
        assert.equal(readFileSync(profileBRules, 'utf8'), 'profile-b-body\n');
        assert.equal(existsSync(join(profileBRoot, MANIFEST_FILE_NAME)), true);

        const okRun = runInstaller(
            homeDirectory,
            ['--target', profileARoot, '--uninstall'],
        );
        assert.equal(okRun.status, 0, okRun.stdout + okRun.stderr);
        assert.equal(existsSync(profileARules), false);
        assert.equal(existsSync(join(profileARoot, MANIFEST_FILE_NAME)), false);
        assert.equal(readFileSync(profileBRules, 'utf8'), 'profile-b-body\n');
        assert.equal(existsSync(join(profileBRoot, MANIFEST_FILE_NAME)), true);
        assert.match(readFileSync(join(profileBRoot, SETTINGS_FILE_NAME), 'utf8'), /profile-b/);
    } finally {
        rmSync(homeDirectory, { recursive: true, force: true });
    }
});

test('InstallTransactionFaultError remains the fault type for uninstall phases', () => {
    const error = new InstallTransactionFaultError(FAULT_PHASES.AFTER_SETTINGS_WRITE);
    assert.equal(error.phase, FAULT_PHASES.AFTER_SETTINGS_WRITE);
    assert.equal(error.name, 'InstallTransactionFaultError');
});
