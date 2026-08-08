/**
 * Managed permission defaults: pack inclusion, install merge, idempotence, uninstall.
 */

import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import {
    mkdtempSync,
    rmSync,
    writeFileSync,
    readFileSync,
    existsSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

import {
    managedDenyEntriesFromPackageSettings,
    mergeManagedPermissionsIntoSettings,
    pruneManagedPermissionsFromSettings,
} from './merge_managed_permissions.mjs';

const PACKAGE_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const PACKAGE_SETTINGS_PATH = join(PACKAGE_ROOT, 'settings.json');
const INSTALL_ENTRY = join(PACKAGE_ROOT, 'bin', 'install.mjs');

const EXPECTED_DENY_ENTRIES = [];
const SAMPLE_MANAGED_DENY_ENTRIES = ['Edit($HOME/.claude/managed-test/**)'];
const LEGACY_MANAGED_DENY_ENTRIES = [
    'Edit($HOME/.claude/verification/**)',
    'Write($HOME/.claude/code-review-stamps/**)',
    'Edit($HOME/.claude/code-review-stamps/**)',
    'MultiEdit($HOME/.claude/code-review-stamps/**)',
];
const USER_OWNED_DENY_ENTRY = 'Bash(rm -rf /)';

function packageDenyEntries() {
    const packageSettings = JSON.parse(readFileSync(PACKAGE_SETTINGS_PATH, 'utf8'));
    return managedDenyEntriesFromPackageSettings(packageSettings);
}

function runInstallerInSandbox(sandboxHome, installerArguments = []) {
    const gitConfigGlobal = join(sandboxHome, '.gitconfig-sandbox');
    writeFileSync(gitConfigGlobal, '[safe]\n\tdirectory = *\n');
    return spawnSync(process.execPath, [INSTALL_ENTRY, ...installerArguments], {
        cwd: PACKAGE_ROOT,
        encoding: 'utf8',
        env: {
            ...process.env,
            HOME: sandboxHome,
            USERPROFILE: sandboxHome,
            GIT_CONFIG_GLOBAL: gitConfigGlobal,
        },
    });
}

test('package settings.json publishes no managed deny entries', () => {
    const denyEntries = packageDenyEntries();
    assert.deepEqual(denyEntries, EXPECTED_DENY_ENTRIES);
});

test('an array-valued permissions field is replaced so managed denies survive a round trip', () => {
    const targetSettings = { permissions: [] };
    const result = mergeManagedPermissionsIntoSettings(targetSettings, SAMPLE_MANAGED_DENY_ENTRIES);
    assert.equal(result.addedCount, SAMPLE_MANAGED_DENY_ENTRIES.length);
    assert.equal(Array.isArray(targetSettings.permissions), false);
    const roundTripped = JSON.parse(JSON.stringify(targetSettings));
    assert.deepEqual(roundTripped.permissions.deny, SAMPLE_MANAGED_DENY_ENTRIES);
});

test('npm pack includes package settings.json in the published artifact', () => {
    const packResult = spawnSync('npm', ['pack', '--dry-run', '--json'], {
        cwd: PACKAGE_ROOT,
        encoding: 'utf8',
        shell: process.platform === 'win32',
    });
    assert.equal(packResult.status, 0, packResult.stderr || packResult.stdout);
    const packPayload = JSON.parse(packResult.stdout);
    const files = Array.isArray(packPayload)
        ? packPayload[0]?.files ?? []
        : packPayload.files ?? [];
    const paths = files.map((eachFile) => (
        typeof eachFile === 'string' ? eachFile : eachFile.path
    ));
    assert.ok(
        paths.some((eachPath) => eachPath === 'settings.json' || eachPath.endsWith('/settings.json')),
        `settings.json missing from pack files: ${paths.filter((p) => String(p).includes('settings')).join(', ') || 'none'}`,
    );
});

test('mergeManagedPermissionsIntoSettings adds each managed deny exactly once', () => {
    const target = {
        permissions: {
            allow: ['Bash(git status)'],
            deny: ['Bash(rm -rf /)'],
        },
    };
    const first = mergeManagedPermissionsIntoSettings(target, SAMPLE_MANAGED_DENY_ENTRIES);
    assert.equal(first.addedCount, SAMPLE_MANAGED_DENY_ENTRIES.length);
    assert.equal(first.alreadyPresentCount, 0);
    const managedDenyCount = target.permissions.deny.filter((each) => (
        SAMPLE_MANAGED_DENY_ENTRIES.includes(each)
    )).length;
    assert.equal(managedDenyCount, SAMPLE_MANAGED_DENY_ENTRIES.length);
    assert.ok(target.permissions.deny.includes('Bash(rm -rf /)'));
    assert.deepEqual(target.permissions.allow, ['Bash(git status)']);

    const second = mergeManagedPermissionsIntoSettings(target, SAMPLE_MANAGED_DENY_ENTRIES);
    assert.equal(second.addedCount, 0);
    assert.equal(second.alreadyPresentCount, SAMPLE_MANAGED_DENY_ENTRIES.length);
    assert.equal(
        target.permissions.deny.filter((each) => each === SAMPLE_MANAGED_DENY_ENTRIES[0]).length,
        1,
    );
});

test('pruneManagedPermissionsFromSettings removes only package-owned deny entries', () => {
    const target = {
        permissions: {
            allow: ['Bash(git status)'],
            ask: ['Edit(./**)'],
            deny: [
                'Bash(rm -rf /)',
                ...SAMPLE_MANAGED_DENY_ENTRIES,
            ],
        },
    };
    const outcome = pruneManagedPermissionsFromSettings(target, SAMPLE_MANAGED_DENY_ENTRIES);
    assert.equal(outcome.removedCount, SAMPLE_MANAGED_DENY_ENTRIES.length);
    assert.deepEqual(target.permissions.deny, ['Bash(rm -rf /)']);
    assert.deepEqual(target.permissions.allow, ['Bash(git status)']);
    assert.deepEqual(target.permissions.ask, ['Edit(./**)']);
});

test('sandbox install keeps default managed denies empty on repeat', () => {
    const sandboxHome = mkdtempSync(join(tmpdir(), 'cde-settings-defaults-'));
    try {
        const firstInstall = runInstallerInSandbox(sandboxHome, []);
        assert.equal(firstInstall.status, 0, firstInstall.stderr || firstInstall.stdout);

        const settingsPath = join(sandboxHome, '.claude', 'settings.json');
        assert.ok(existsSync(settingsPath), 'settings.json written');
        const firstSettings = JSON.parse(readFileSync(settingsPath, 'utf8'));
        const firstDeny = firstSettings.permissions?.deny ?? [];
        assert.deepEqual(firstDeny, EXPECTED_DENY_ENTRIES);

        const manifestPath = join(sandboxHome, '.claude', '.claude-dev-env-manifest.json');
        const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
        assert.deepEqual(manifest.managedPermissions?.deny ?? [], EXPECTED_DENY_ENTRIES);

        const secondInstall = runInstallerInSandbox(sandboxHome, []);
        assert.equal(secondInstall.status, 0, secondInstall.stderr || secondInstall.stdout);
        const secondSettings = JSON.parse(readFileSync(settingsPath, 'utf8'));
        const secondDeny = secondSettings.permissions?.deny ?? [];
        assert.deepEqual(secondDeny, EXPECTED_DENY_ENTRIES);
    } finally {
        rmSync(sandboxHome, { recursive: true, force: true });
    }
});

test('a normal upgrade retires manifest-owned denies and preserves user entries', () => {
    const sandboxHome = mkdtempSync(join(tmpdir(), 'cde-settings-upgrade-'));
    try {
        const initialInstall = runInstallerInSandbox(sandboxHome, []);
        assert.equal(initialInstall.status, 0, initialInstall.stderr || initialInstall.stdout);

        const settingsPath = join(sandboxHome, '.claude', 'settings.json');
        const settings = JSON.parse(readFileSync(settingsPath, 'utf8'));
        settings.permissions = {
            allow: ['Bash(git status)'],
            ask: ['Edit(./**)'],
            deny: [USER_OWNED_DENY_ENTRY, ...LEGACY_MANAGED_DENY_ENTRIES],
        };
        writeFileSync(settingsPath, JSON.stringify(settings, null, 4) + '\n');

        const manifestPath = join(sandboxHome, '.claude', '.claude-dev-env-manifest.json');
        const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
        manifest.managedPermissions = { deny: LEGACY_MANAGED_DENY_ENTRIES };
        writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + '\n');

        const upgradedInstall = runInstallerInSandbox(sandboxHome, []);
        assert.equal(upgradedInstall.status, 0, upgradedInstall.stderr || upgradedInstall.stdout);

        const upgradedSettings = JSON.parse(readFileSync(settingsPath, 'utf8'));
        assert.deepEqual(upgradedSettings.permissions?.deny, [USER_OWNED_DENY_ENTRY]);
        assert.deepEqual(upgradedSettings.permissions?.allow, ['Bash(git status)']);
        assert.deepEqual(upgradedSettings.permissions?.ask, ['Edit(./**)']);

        const upgradedManifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
        assert.equal(Object.hasOwn(upgradedManifest, 'managedPermissions'), false);
    } finally {
        rmSync(sandboxHome, { recursive: true, force: true });
    }
});

test('sandbox uninstall removes only package-owned permission entries and keeps user entries', () => {
    const sandboxHome = mkdtempSync(join(tmpdir(), 'cde-settings-uninstall-'));
    try {
        const install = runInstallerInSandbox(sandboxHome, []);
        assert.equal(install.status, 0, install.stderr || install.stdout);

        const settingsPath = join(sandboxHome, '.claude', 'settings.json');
        const settings = JSON.parse(readFileSync(settingsPath, 'utf8'));
        settings.permissions = settings.permissions ?? {};
        settings.permissions.allow = [...(settings.permissions.allow ?? []), 'Bash(git status)'];
        settings.permissions.ask = [...(settings.permissions.ask ?? []), 'Edit(./**)'];
        settings.permissions.deny = [...(settings.permissions.deny ?? []), 'Bash(rm -rf /)'];
        writeFileSync(settingsPath, JSON.stringify(settings, null, 4) + '\n');

        const uninstall = runInstallerInSandbox(sandboxHome, ['--uninstall']);
        assert.equal(uninstall.status, 0, uninstall.stderr || uninstall.stdout);

        assert.ok(existsSync(settingsPath), 'settings.json remains for user entries');
        const after = JSON.parse(readFileSync(settingsPath, 'utf8'));
        const denyAfter = after.permissions?.deny ?? [];
        for (const eachEntry of EXPECTED_DENY_ENTRIES) {
            assert.ok(!denyAfter.includes(eachEntry), `managed deny still present: ${eachEntry}`);
        }
        assert.ok(denyAfter.includes('Bash(rm -rf /)'), 'user deny preserved');
        assert.ok((after.permissions?.allow ?? []).includes('Bash(git status)'), 'user allow preserved');
        assert.ok((after.permissions?.ask ?? []).includes('Edit(./**)'), 'user ask preserved');
    } finally {
        rmSync(sandboxHome, { recursive: true, force: true });
    }
});
