/**
 * Profile target-selection and per-target manifest contract (control-plane A3 / P-12).
 */

import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { join, resolve } from 'node:path';
import {
    mkdtempSync,
    rmSync,
    mkdirSync,
    writeFileSync,
    readFileSync,
    existsSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import {
    parseInstallTargetSelectionFromArgv,
    resolveInstallTargets,
    buildTargetManifestRecord,
    stripTargetSelectionFlagsFromArgv,
    resolveProfilesRootDirectory,
    assertSafeProfileDirectoryName,
    MAIN_DEFAULT_TARGET_IDENTITY,
    DEFAULT_PROFILES_ROOT_DIRECTORY_NAME,
} from './select-install-targets.mjs';
import { MANIFEST_FILE_NAME } from './resolve-install-root.mjs';

const BIN_DIRECTORY = fileURLToPath(new URL('.', import.meta.url));
const INSTALL_MODULE_PATH = join(BIN_DIRECTORY, 'install.mjs');

const DIRECTORY_NAME_BY_PROFILE_ID = {
    editor: 'editor',
    mel: 'mel',
    ev: 'ev',
    master: 'master',
    kimi: 'kimi',
};

test('main-default selection resolves a single main target under home/.claude', () => {
    const homeDirectory = resolve(join(tmpdir(), 'a3-home-main'));
    const selection = parseInstallTargetSelectionFromArgv([]);
    assert.equal(selection.mode, 'main-default');
    const allTargets = resolveInstallTargets(selection, {
        homeDirectory,
        environment: {},
        directoryNameByProfileId: DIRECTORY_NAME_BY_PROFILE_ID,
    });
    assert.equal(allTargets.length, 1);
    assert.equal(allTargets[0].targetIdentity, MAIN_DEFAULT_TARGET_IDENTITY);
    assert.equal(allTargets[0].managedRoot, resolve(join(homeDirectory, '.claude')));
    assert.equal(allTargets[0].source, 'default-home');
});

test('explicit --target is single-path mode and rejects combined --profile', () => {
    const selection = parseInstallTargetSelectionFromArgv(['--target', 'C:\\tmp\\a3-root']);
    assert.equal(selection.mode, 'explicit-path');
    assert.equal(selection.explicitTarget, 'C:\\tmp\\a3-root');
    assert.throws(
        () => parseInstallTargetSelectionFromArgv(['--target', 'C:\\tmp\\x', '--profile', 'editor']),
        /ambiguous targets/,
    );
});

test('selected multi-profile resolves one managed root per id under profiles root', () => {
    const homeDirectory = resolve(join(tmpdir(), 'a3-home-multi'));
    const profilesRoot = resolve(join(tmpdir(), 'a3-profiles-root'));
    const selection = parseInstallTargetSelectionFromArgv(['--profiles', 'editor,mel']);
    assert.equal(selection.mode, 'profiles');
    assert.deepEqual(selection.allProfileIds, ['editor', 'mel']);
    const allTargets = resolveInstallTargets(selection, {
        homeDirectory,
        environment: {},
        profilesRoot,
        directoryNameByProfileId: DIRECTORY_NAME_BY_PROFILE_ID,
    });
    assert.equal(allTargets.length, 2);
    assert.equal(allTargets[0].targetIdentity, 'editor');
    assert.equal(allTargets[0].managedRoot, resolve(join(profilesRoot, 'editor')));
    assert.equal(allTargets[1].targetIdentity, 'mel');
    assert.equal(allTargets[1].managedRoot, resolve(join(profilesRoot, 'mel')));
});

test('duplicate profile ids and unknown ids are rejected before mutation', () => {
    assert.throws(
        () => parseInstallTargetSelectionFromArgv(['--profiles', 'editor,editor']),
        /duplicate profile id/,
    );
    const selection = parseInstallTargetSelectionFromArgv(['--profile', 'does-not-exist']);
    assert.throws(
        () => resolveInstallTargets(selection, {
            homeDirectory: resolve(join(tmpdir(), 'a3-home-unknown')),
            profilesRoot: resolve(join(tmpdir(), 'a3-pr')),
            directoryNameByProfileId: DIRECTORY_NAME_BY_PROFILE_ID,
        }),
        /unknown profile id: does-not-exist/,
    );
});

test('child hop with --target-identity rejects residual --profile flags', () => {
    assert.throws(
        () => parseInstallTargetSelectionFromArgv([
            '--target', 'C:\\tmp\\child',
            '--target-identity', 'editor',
            '--profile', 'mel',
        ]),
        /child install hop rejects/,
    );
});

test('profile directoryName rejects absolute paths and parent segments', () => {
    assert.throws(
        () => assertSafeProfileDirectoryName('C:\\evil'),
        /must be relative/,
    );
    assert.throws(
        () => assertSafeProfileDirectoryName('..\\escape'),
        /parent segments/,
    );
    assert.equal(assertSafeProfileDirectoryName('editor'), 'editor');
});

test('buildTargetManifestRecord records package, version, identity, root, files, skills', () => {
    const managedRoot = resolve(join(tmpdir(), 'a3-manifest-root'));
    const manifest = buildTargetManifestRecord({
        packageName: 'claude-dev-env',
        packageVersion: '9.9.9-test',
        targetIdentity: 'editor',
        managedRoot,
        files: [join(managedRoot, 'rules', 'x.md')],
        skills: ['privacy-hygiene'],
        installedAt: '2026-07-30T00:00:00.000Z',
    });
    assert.equal(manifest.package, 'claude-dev-env');
    assert.equal(manifest.version, '9.9.9-test');
    assert.equal(manifest.targetIdentity, 'editor');
    assert.equal(manifest.managedRoot, managedRoot);
    assert.deepEqual(manifest.files, [join(managedRoot, 'rules', 'x.md')]);
    assert.deepEqual(manifest.skills, ['privacy-hygiene']);
    assert.equal(manifest.installedAt, '2026-07-30T00:00:00.000Z');
});

test('stripTargetSelectionFlagsFromArgv leaves install groups flags', () => {
    assert.deepEqual(
        stripTargetSelectionFlagsFromArgv([
            '--profiles', 'editor,mel',
            '--only', 'core',
            '--update',
        ]),
        ['--only', 'core', '--update'],
    );
});

test('resolveProfilesRootDirectory prefers explicit then env then home default', () => {
    const homeDirectory = resolve(join(tmpdir(), 'a3-home-pr'));
    assert.equal(
        resolveProfilesRootDirectory({ homeDirectory, environment: {} }),
        resolve(join(homeDirectory, DEFAULT_PROFILES_ROOT_DIRECTORY_NAME)),
    );
    const fromEnv = resolve(join(tmpdir(), 'a3-env-profiles'));
    assert.equal(
        resolveProfilesRootDirectory({
            homeDirectory,
            environment: { LLM_SETTINGS_PROFILES_ROOT: fromEnv },
        }),
        fromEnv,
    );
});

test('repeated and selected multi-profile dry runs write one ownership manifest per target', () => {
    const runRoot = mkdtempSync(join(tmpdir(), 'a3-multi-run-'));
    try {
        const profilesRoot = join(runRoot, 'profiles');
        const homeDirectory = join(runRoot, 'home');
        mkdirSync(homeDirectory, { recursive: true });
        const selection = parseInstallTargetSelectionFromArgv(['--profiles', 'editor,mel']);
        const allTargets = resolveInstallTargets(selection, {
            homeDirectory,
            profilesRoot,
            directoryNameByProfileId: DIRECTORY_NAME_BY_PROFILE_ID,
        });
        assert.equal(allTargets.length, 2);

        for (const eachTarget of allTargets) {
            mkdirSync(eachTarget.managedRoot, { recursive: true });
            const sampleFile = join(eachTarget.managedRoot, 'CLAUDE.md');
            writeFileSync(sampleFile, `# ${eachTarget.targetIdentity}\n`, 'utf8');
            const manifest = buildTargetManifestRecord({
                packageName: 'claude-dev-env',
                packageVersion: '0.0.0-a3',
                targetIdentity: eachTarget.targetIdentity,
                managedRoot: eachTarget.managedRoot,
                files: [sampleFile],
                skills: ['privacy-hygiene'],
            });
            const manifestPath = join(eachTarget.managedRoot, MANIFEST_FILE_NAME);
            writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');
        }

        // Second pass (repeat) overwrites each target's own manifest only.
        for (const eachTarget of allTargets) {
            const manifestPath = join(eachTarget.managedRoot, MANIFEST_FILE_NAME);
            const prior = JSON.parse(readFileSync(manifestPath, 'utf8'));
            assert.equal(prior.targetIdentity, eachTarget.targetIdentity);
            const refreshed = buildTargetManifestRecord({
                packageName: 'claude-dev-env',
                packageVersion: '0.0.0-a3-repeat',
                targetIdentity: eachTarget.targetIdentity,
                managedRoot: eachTarget.managedRoot,
                files: prior.files,
                skills: prior.skills,
            });
            writeFileSync(manifestPath, `${JSON.stringify(refreshed, null, 2)}\n`, 'utf8');
        }

        const editorManifest = JSON.parse(
            readFileSync(join(profilesRoot, 'editor', MANIFEST_FILE_NAME), 'utf8'),
        );
        const melManifest = JSON.parse(
            readFileSync(join(profilesRoot, 'mel', MANIFEST_FILE_NAME), 'utf8'),
        );
        assert.equal(editorManifest.targetIdentity, 'editor');
        assert.equal(melManifest.targetIdentity, 'mel');
        assert.equal(editorManifest.version, '0.0.0-a3-repeat');
        assert.equal(melManifest.version, '0.0.0-a3-repeat');
        assert.ok(!existsSync(join(profilesRoot, 'ev', MANIFEST_FILE_NAME)));
        assert.notEqual(editorManifest.managedRoot, melManifest.managedRoot);
    } finally {
        rmSync(runRoot, { recursive: true, force: true });
    }
});

test('install.mjs --help documents profile target selection', () => {
    const result = spawnSync(process.execPath, [INSTALL_MODULE_PATH, '--help'], {
        encoding: 'utf8',
        env: process.env,
    });
    assert.equal(result.status, 0, result.stderr);
    assert.match(result.stdout, /--profile/);
    assert.match(result.stdout, /--profiles/);
    assert.match(result.stdout, /--target/);
    assert.match(result.stdout, /targetIdentity|target identity|per target/i);
});

test('install.mjs wires select-install-targets for multi-profile entry', () => {
    const source = readFileSync(INSTALL_MODULE_PATH, 'utf8');
    assert.match(source, /select-install-targets\.mjs/);
    assert.match(source, /parseInstallTargetSelectionFromArgv/);
    assert.match(source, /resolveInstallTargets/);
    assert.match(source, /buildTargetManifestRecord|targetIdentity/);
});
