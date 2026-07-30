/**
 * Install transaction journal and fault-injection recovery (control-plane E2 / P-18).
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
    FAULT_PHASES,
    INSTALL_FAULT_ENV,
    InstallTransactionFaultError,
    capturePriorInstallSnapshot,
    discardInstallTransactionJournal,
    readGlobalCoreHooksPath,
    resolveFaultPhaseFromEnvironment,
    restorePriorInstallSnapshot,
    runWithInstallTransaction,
    throwIfFaultPhase,
    writeGlobalCoreHooksPath,
} from './install-transaction.mjs';

const THIS_DIRECTORY = dirname(fileURLToPath(import.meta.url));
const INSTALLER_PATH = join(THIS_DIRECTORY, 'install.mjs');

function sandbox() {
    const root = mkdtempSync(join(tmpdir(), 'cdev-txn-'));
    const managedRoot = join(root, 'managed');
    mkdirSync(managedRoot, { recursive: true });
    return {
        root,
        managedRoot,
        settingsPath: join(managedRoot, 'settings.json'),
        manifestFilePath: join(managedRoot, '.claude-dev-env-manifest.json'),
        journalParent: join(managedRoot, '.claude-dev-env-txn'),
    };
}

function writeFileWithParents(filePath, contents) {
    mkdirSync(dirname(filePath), { recursive: true });
    writeFileSync(filePath, contents);
}

test('resolveFaultPhaseFromEnvironment accepts known phases and rejects unknown', () => {
    assert.equal(resolveFaultPhaseFromEnvironment({}), null);
    assert.equal(
        resolveFaultPhaseFromEnvironment({ [INSTALL_FAULT_ENV]: FAULT_PHASES.AFTER_SETTINGS_WRITE }),
        FAULT_PHASES.AFTER_SETTINGS_WRITE,
    );
    assert.throws(
        () => resolveFaultPhaseFromEnvironment({ [INSTALL_FAULT_ENV]: 'not-a-phase' }),
        /Unknown/,
    );
});

test('throwIfFaultPhase throws only on the matching phase', () => {
    assert.doesNotThrow(() => throwIfFaultPhase(FAULT_PHASES.AFTER_FILE_STAGING, null));
    assert.doesNotThrow(
        () => throwIfFaultPhase(FAULT_PHASES.AFTER_FILE_STAGING, FAULT_PHASES.AFTER_SETTINGS_WRITE),
    );
    assert.throws(
        () => throwIfFaultPhase(FAULT_PHASES.AFTER_GIT_CONFIG, FAULT_PHASES.AFTER_GIT_CONFIG),
        (error) => error instanceof InstallTransactionFaultError
            && error.phase === FAULT_PHASES.AFTER_GIT_CONFIG,
    );
});

test('capture and restore recover settings, manifest, files, and hooksPath', () => {
    const box = sandbox();
    const gitConfigPath = join(box.root, '.gitconfig');
    writeFileSync(gitConfigPath, '');
    const priorHooksDirectory = join(box.managedRoot, 'hooks', 'git-hooks');
    mkdirSync(priorHooksDirectory, { recursive: true });
    const env = {
        ...process.env,
        HOME: box.root,
        USERPROFILE: box.root,
        GIT_CONFIG_GLOBAL: gitConfigPath,
    };
    const io = { env, execFileSync };

    writeFileWithParents(box.settingsPath, '{"hooks":{"SessionStart":[]}}\n');
    const priorFile = join(box.managedRoot, 'rules', 'keep.md');
    writeFileWithParents(priorFile, 'prior-rules\n');
    writeFileWithParents(
        box.manifestFilePath,
        `${JSON.stringify({ files: [priorFile], skills: ['keep'] }, null, 2)}\n`,
    );
    writeGlobalCoreHooksPath(priorHooksDirectory, io);

    const snapshot = capturePriorInstallSnapshot({
        managedRoot: box.managedRoot,
        manifestFilePath: box.manifestFilePath,
        settingsPath: box.settingsPath,
        priorManifestFiles: [priorFile],
        journalParentDirectory: box.journalParent,
        io,
    });
    assert.equal(snapshot.settingsExisted, true);
    assert.equal(snapshot.manifestExisted, true);
    assert.equal(snapshot.priorHooksPath, priorHooksDirectory);
    assert.equal(snapshot.allFileEntries.length, 1);

    const newFile = join(box.managedRoot, 'rules', 'new.md');
    writeFileWithParents(newFile, 'new-content\n');
    writeFileSync(priorFile, 'corrupted\n');
    writeFileSync(box.settingsPath, '{"hooks":{"broken":true}}\n');
    writeFileSync(box.manifestFilePath, '{"files":[],"skills":[]}\n');
    writeGlobalCoreHooksPath(join(box.managedRoot, 'other-hooks'), io);

    restorePriorInstallSnapshot(snapshot, {
        allWrittenPaths: [newFile, priorFile, box.settingsPath, box.manifestFilePath],
        io,
    });

    assert.equal(readFileSync(priorFile, 'utf8'), 'prior-rules\n');
    assert.equal(readFileSync(box.settingsPath, 'utf8'), '{"hooks":{"SessionStart":[]}}\n');
    assert.deepEqual(JSON.parse(readFileSync(box.manifestFilePath, 'utf8')).skills, ['keep']);
    assert.equal(existsSync(newFile), false);
    assert.equal(readGlobalCoreHooksPath(io), priorHooksDirectory);

    discardInstallTransactionJournal(snapshot);
    rmSync(box.root, { recursive: true, force: true });
});

test('runWithInstallTransaction restores prior state on injected fault', () => {
    const box = sandbox();
    const gitConfigPath = join(box.root, '.gitconfig');
    writeFileSync(gitConfigPath, '');
    const env = {
        ...process.env,
        HOME: box.root,
        USERPROFILE: box.root,
        GIT_CONFIG_GLOBAL: gitConfigPath,
    };
    const io = { env, execFileSync };
    const priorFile = join(box.managedRoot, 'docs', 'a.md');
    writeFileWithParents(priorFile, 'keep-me\n');
    writeFileWithParents(box.settingsPath, '{"ok":true}\n');
    writeFileWithParents(
        box.manifestFilePath,
        `${JSON.stringify({ files: [priorFile], skills: [] })}\n`,
    );

    const snapshot = capturePriorInstallSnapshot({
        managedRoot: box.managedRoot,
        manifestFilePath: box.manifestFilePath,
        settingsPath: box.settingsPath,
        priorManifestFiles: [priorFile],
        journalParentDirectory: box.journalParent,
        io,
    });

    assert.throws(
        () => runWithInstallTransaction({
            snapshot,
            faultPhase: FAULT_PHASES.AFTER_SETTINGS_WRITE,
            io,
            runMutations: ({ throwIfFault, recordWrittenPath }) => {
                writeFileSync(priorFile, 'mutated\n');
                recordWrittenPath(priorFile);
                writeFileSync(box.settingsPath, '{"ok":false}\n');
                recordWrittenPath(box.settingsPath);
                throwIfFault(FAULT_PHASES.AFTER_SETTINGS_WRITE);
                writeFileSync(box.manifestFilePath, '{"files":[]}\n');
            },
        }),
        (error) => error instanceof InstallTransactionFaultError,
    );

    assert.equal(readFileSync(priorFile, 'utf8'), 'keep-me\n');
    assert.equal(readFileSync(box.settingsPath, 'utf8'), '{"ok":true}\n');
    assert.deepEqual(JSON.parse(readFileSync(box.manifestFilePath, 'utf8')).files, [priorFile]);
    rmSync(box.root, { recursive: true, force: true });
});

test('runWithInstallTransaction commits and discards journal on success', () => {
    const box = sandbox();
    const gitConfigPath = join(box.root, '.gitconfig');
    writeFileSync(gitConfigPath, '');
    const io = {
        env: {
            ...process.env,
            HOME: box.root,
            USERPROFILE: box.root,
            GIT_CONFIG_GLOBAL: gitConfigPath,
        },
        execFileSync,
    };
    const priorFile = join(box.managedRoot, 'docs', 'a.md');
    writeFileWithParents(priorFile, 'v1\n');
    writeFileWithParents(
        box.manifestFilePath,
        `${JSON.stringify({ files: [priorFile], skills: [] })}\n`,
    );
    const snapshot = capturePriorInstallSnapshot({
        managedRoot: box.managedRoot,
        manifestFilePath: box.manifestFilePath,
        settingsPath: box.settingsPath,
        priorManifestFiles: [priorFile],
        journalParentDirectory: box.journalParent,
        io,
    });
    const journalRoot = snapshot.journalRoot;

    runWithInstallTransaction({
        snapshot,
        faultPhase: null,
        io,
        runMutations: ({ throwIfFault, recordWrittenPath }) => {
            writeFileSync(priorFile, 'v2\n');
            recordWrittenPath(priorFile);
            throwIfFault(FAULT_PHASES.AFTER_FILE_STAGING);
        },
    });

    assert.equal(readFileSync(priorFile, 'utf8'), 'v2\n');
    assert.equal(existsSync(journalRoot), false);
    rmSync(box.root, { recursive: true, force: true });
});

/**
 * Spawn the real installer against a sandbox home with optional fault phase.
 *
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

function seedPriorInstall(homeDirectory) {
    const claudeDirectory = join(homeDirectory, '.claude');
    const rulesFile = join(claudeDirectory, 'rules', 'prior.md');
    writeFileWithParents(rulesFile, 'prior-body\n');
    writeFileWithParents(
        join(claudeDirectory, 'settings.json'),
        `${JSON.stringify({ hooks: { UserPromptSubmit: [] }, customMarker: 'prior-settings' }, null, 2)}\n`,
    );
    writeFileWithParents(
        join(claudeDirectory, '.claude-dev-env-manifest.json'),
        `${JSON.stringify({
            packageName: 'claude-dev-env',
            files: [rulesFile],
            skills: [],
        }, null, 2)}\n`,
    );
    writeFileSync(join(homeDirectory, '.gitconfig'), '');
    return { claudeDirectory, rulesFile };
}

test('installer fault after_file_staging restores prior managed installation', () => {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-txn-e2e-'));
    try {
        const { claudeDirectory, rulesFile } = seedPriorInstall(homeDirectory);
        const priorSettings = readFileSync(join(claudeDirectory, 'settings.json'), 'utf8');
        const priorManifest = readFileSync(
            join(claudeDirectory, '.claude-dev-env-manifest.json'),
            'utf8',
        );

        const failedRun = runInstaller(homeDirectory, ['--only', 'journal'], {
            faultPhase: FAULT_PHASES.AFTER_FILE_STAGING,
        });
        assert.notEqual(failedRun.status, 0, failedRun.stdout + failedRun.stderr);
        assert.match(`${failedRun.stdout}${failedRun.stderr}`, /fault|restored|aborted/i);

        assert.equal(readFileSync(rulesFile, 'utf8'), 'prior-body\n');
        assert.equal(readFileSync(join(claudeDirectory, 'settings.json'), 'utf8'), priorSettings);
        assert.equal(
            readFileSync(join(claudeDirectory, '.claude-dev-env-manifest.json'), 'utf8'),
            priorManifest,
        );
    } finally {
        rmSync(homeDirectory, { recursive: true, force: true });
    }
});

test('installer fault after_settings_write restores prior settings and files', () => {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-txn-e2e-settings-'));
    try {
        const { claudeDirectory, rulesFile } = seedPriorInstall(homeDirectory);
        const priorSettings = readFileSync(join(claudeDirectory, 'settings.json'), 'utf8');

        const failedRun = runInstaller(homeDirectory, [], {
            faultPhase: FAULT_PHASES.AFTER_SETTINGS_WRITE,
        });
        assert.notEqual(failedRun.status, 0, failedRun.stdout + failedRun.stderr);
        assert.equal(readFileSync(join(claudeDirectory, 'settings.json'), 'utf8'), priorSettings);
        assert.equal(readFileSync(rulesFile, 'utf8'), 'prior-body\n');
        assert.match(
            readFileSync(join(claudeDirectory, '.claude-dev-env-manifest.json'), 'utf8'),
            /prior\.md|prior-body|claude-dev-env/,
        );
    } finally {
        rmSync(homeDirectory, { recursive: true, force: true });
    }
});

test('installer fault after_manifest_write restores prior manifest', () => {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-txn-e2e-manifest-'));
    try {
        const { claudeDirectory } = seedPriorInstall(homeDirectory);
        const priorManifest = readFileSync(
            join(claudeDirectory, '.claude-dev-env-manifest.json'),
            'utf8',
        );

        const failedRun = runInstaller(homeDirectory, ['--only', 'journal'], {
            faultPhase: FAULT_PHASES.AFTER_MANIFEST_WRITE,
        });
        assert.notEqual(failedRun.status, 0, failedRun.stdout + failedRun.stderr);
        assert.equal(
            readFileSync(join(claudeDirectory, '.claude-dev-env-manifest.json'), 'utf8'),
            priorManifest,
        );
    } finally {
        rmSync(homeDirectory, { recursive: true, force: true });
    }
});

test('installer fault after_git_config restores prior core.hooksPath', () => {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-txn-e2e-git-'));
    try {
        seedPriorInstall(homeDirectory);
        const gitConfigPath = join(homeDirectory, '.gitconfig');
        const priorHooksPath = join(homeDirectory, 'prior-git-hooks');
        mkdirSync(priorHooksPath, { recursive: true });
        writeGlobalCoreHooksPath(priorHooksPath, {
            env: {
                ...process.env,
                HOME: homeDirectory,
                USERPROFILE: homeDirectory,
                GIT_CONFIG_GLOBAL: gitConfigPath,
            },
            execFileSync,
        });

        const failedRun = runInstaller(homeDirectory, [], {
            faultPhase: FAULT_PHASES.AFTER_GIT_CONFIG,
        });
        assert.notEqual(failedRun.status, 0, failedRun.stdout + failedRun.stderr);

        const restored = readGlobalCoreHooksPath({
            env: {
                ...process.env,
                HOME: homeDirectory,
                USERPROFILE: homeDirectory,
                GIT_CONFIG_GLOBAL: gitConfigPath,
            },
            execFileSync,
        });
        assert.equal(restored, priorHooksPath);
    } finally {
        rmSync(homeDirectory, { recursive: true, force: true });
    }
});

test('successful install after prior install leaves one manifest and no fault', () => {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-txn-e2e-ok-'));
    try {
        seedPriorInstall(homeDirectory);
        const okRun = runInstaller(homeDirectory, ['--only', 'journal']);
        assert.equal(okRun.status, 0, okRun.stdout + okRun.stderr);
        const manifestPath = join(homeDirectory, '.claude', '.claude-dev-env-manifest.json');
        assert.equal(existsSync(manifestPath), true);
        const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
        assert.ok(Array.isArray(manifest.files));
        assert.equal(existsSync(join(homeDirectory, '.claude', '.claude-dev-env-txn')), false);
    } finally {
        rmSync(homeDirectory, { recursive: true, force: true });
    }
});

