import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import {
    mkdtempSync,
    mkdirSync,
    writeFileSync,
    readFileSync,
    existsSync,
    rmSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
import {
    resolveInstallRoot,
    isAllowedInstallDestination,
} from './resolve-install-root.mjs';
import {
    DEFAULT_CURSOR_DIRECTORY_NAME,
    CURSOR_RULES_DIRECTORY_NAME,
} from './install-constants.mjs';

const THIS_DIRECTORY = dirname(fileURLToPath(import.meta.url));
const INSTALLER_PATH = join(THIS_DIRECTORY, 'install.mjs');
const PACKAGE_DIRECTORY = dirname(THIS_DIRECTORY);

function runInstaller(homeDirectory, extraArguments, environmentOverrides = {}) {
    return execFileSync('node', [INSTALLER_PATH, ...extraArguments], {
        cwd: PACKAGE_DIRECTORY,
        encoding: 'utf8',
        env: {
            ...process.env,
            HOME: homeDirectory,
            USERPROFILE: homeDirectory,
            CODEX_HOME: join(homeDirectory, '.codex'),
            CLAUDE_CONFIG_DIR: join(homeDirectory, '.claude'),
            GIT_CONFIG_GLOBAL: join(homeDirectory, '.gitconfig'),
            ...environmentOverrides,
        },
    });
}

function runSelector(selectorPath, selectionInput) {
    return JSON.parse(execFileSync('node', [selectorPath], {
        encoding: 'utf8',
        input: JSON.stringify(selectionInput),
    }));
}

test('resolveInstallRoot names ~/.cursor/rules and allows generated mdc files under it', () => {
    const homeDirectory = join(tmpdir(), 'cdev-cursor-rules-home');
    const resolution = resolveInstallRoot({
        homeDirectory,
        environment: {},
        explicitTarget: null,
    });
    const expectedDirectory = join(
        homeDirectory,
        DEFAULT_CURSOR_DIRECTORY_NAME,
        CURSOR_RULES_DIRECTORY_NAME,
    );
    assert.equal(resolution.cursorRulesInstallDirectory, expectedDirectory);
    assert.equal(
        isAllowedInstallDestination(join(expectedDirectory, 'asd-ste100-language.mdc'), resolution),
        true,
    );
    assert.equal(
        isAllowedInstallDestination(join(homeDirectory, '.ssh', 'id_rsa'), resolution),
        false,
    );
});

test('a full install writes stem-named Cursor rules and leaves a local extra mdc in place', () => {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-cursor-install-'));
    try {
        const extraRulePath = join(
            homeDirectory,
            DEFAULT_CURSOR_DIRECTORY_NAME,
            CURSOR_RULES_DIRECTORY_NAME,
            'user-local.mdc',
        );
        mkdirSync(dirname(extraRulePath), { recursive: true });
        writeFileSync(extraRulePath, 'keep-me\n');

        runInstaller(homeDirectory, []);

        const generatedPath = join(
            homeDirectory,
            DEFAULT_CURSOR_DIRECTORY_NAME,
            CURSOR_RULES_DIRECTORY_NAME,
            'asd-ste100-language.mdc',
        );
        assert.equal(existsSync(generatedPath), true);
        const generatedText = readFileSync(generatedPath, 'utf8');
        assert.equal(generatedText.includes('alwaysApply: true'), true);
        assert.equal(readFileSync(extraRulePath, 'utf8'), 'keep-me\n');
    } finally {
        rmSync(homeDirectory, { recursive: true, force: true });
    }
});

test('--only journal is rejected before Cursor rules change; --only core writes them', () => {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-cursor-groups-'));
    try {
        const generatedPath = join(
            homeDirectory,
            DEFAULT_CURSOR_DIRECTORY_NAME,
            CURSOR_RULES_DIRECTORY_NAME,
            'asd-ste100-language.mdc',
        );
        const preferencePath = join(
            homeDirectory,
            '.agents',
            'rules',
            'pstack-model-preferences.codex.json',
        );
        assert.throws(
            () => runInstaller(homeDirectory, ['--only', 'journal']),
            error => error.status === 1 && /Unknown group\(s\): journal/.test(error.stderr),
        );
        assert.equal(existsSync(generatedPath), false);
        assert.equal(existsSync(preferencePath), false);

        runInstaller(homeDirectory, ['--only', 'core']);
        assert.equal(existsSync(generatedPath), true);
        assert.equal(existsSync(preferencePath), true);
    } finally {
        rmSync(homeDirectory, { recursive: true, force: true });
    }
});

for (const targetName of [null, 'profile']) {
    test('pstack rules survive reinstall and sync for ' + (targetName ?? 'main'), () => {
        const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-pstack-'));
        try {
            const targetArguments = targetName
                ? ['--target', join(homeDirectory, targetName)]
                : [];
            const resolution = resolveInstallRoot({
                homeDirectory,
                environment: {},
                explicitTarget: targetName ? join(homeDirectory, targetName) : null,
            });
            const sharedPath = join(resolution.agentsHome, 'rules', 'pstack-models.mdc');
            const cursorPath = join(resolution.cursorRulesInstallDirectory, 'pstack-models.mdc');
            const preferencesPath = join(
                resolution.agentsHome,
                'rules',
                'pstack-model-preferences.codex.json',
            );
            const selectorPath = join(
                resolution.agentsHome,
                'scripts',
                'select_pstack_models.mjs',
            );
            const managedSelectorPath = join(
                resolution.managedRoot,
                'scripts',
                'select_pstack_models.mjs',
            );
            runInstaller(homeDirectory, [...targetArguments, '--only', 'core']);

            const installedText = readFileSync(sharedPath, 'utf8');
            assert.doesNotMatch(installedText, /gpt-|claude-|grok-/i);
            assert.match(installedText, /feature, refactoring: reliable code execution/);
            assert.match(installedText, /interrogate reviewers: independent adversarial review/);
            assert.match(installedText, /alwaysApply: true/);
            assert.match(installedText, /replaces the fixed model defaults in pstack skills/);
            assert.match(installedText, /Run the installed selector once for each agent/);
            assert.equal(readFileSync(cursorPath, 'utf8'), installedText);
            assert.equal(isAllowedInstallDestination(sharedPath, resolution), true);
            assert.equal(existsSync(selectorPath), true);

            const savedPreferences = JSON.parse(readFileSync(preferencesPath, 'utf8'));
            assert.deepEqual(savedPreferences, {
                host: 'codex',
                modelsByRole: {
                    'feature, refactoring': ['gpt-5.6-sol'],
                    'bug-fix': ['gpt-5.6-sol'],
                    'perf-issue': ['gpt-6-astra'],
                    hillclimb: ['gpt-6-astra'],
                    'judgment and prose': ['gpt-6-astra'],
                    'hardest tasks': ['gpt-6-astra'],
                    'how explorer': ['gpt-5.6-terra'],
                    'how explainer': ['gpt-5.6-sol'],
                    'how critics': ['gpt-5.6-terra', 'gpt-5.6-sol', 'gpt-6-astra'],
                    'why investigators': ['gpt-5.6-terra'],
                    'why synthesizer': ['gpt-6-astra'],
                    'reflect tooling': ['gpt-5.6-sol'],
                    'reflect judgment, divergent, synthesizer': ['gpt-6-astra'],
                    'arena runners': ['gpt-5.6-terra', 'gpt-5.6-sol', 'gpt-6-astra'],
                    'arena cross-judge pool': ['gpt-5.6-sol', 'gpt-6-astra'],
                    'swarm workers': ['gpt-5.6-luna'],
                    'architect runners': ['gpt-5.6-sol', 'gpt-6-astra'],
                    'interrogate reviewers': [
                        'gpt-5.6-terra',
                        'gpt-5.6-sol',
                        'gpt-6-astra',
                    ],
                },
            });
            for (const role of Object.keys(savedPreferences.modelsByRole)) {
                assert.equal(installedText.includes(role + ':'), true);
            }
            const codexSelection = runSelector(selectorPath, {
                host: 'codex',
                inventoryHost: 'codex',
                role: 'feature, refactoring',
                delegationIndex: 0,
                availableModelIds: ['gpt-5.6-sol'],
                confirmedSuitableModelIds: [],
                parentFallback: {
                    isAllowed: false,
                    hasMaterialCapabilityLoss: false,
                },
            });
            assert.deepEqual(codexSelection.nativeSpawnArguments, {
                model: 'gpt-5.6-sol',
            });

            const foreignPreferencesPath = join(
                resolution.agentsHome,
                'rules',
                'pstack-model-preferences.claude.json',
            );
            writeFileSync(foreignPreferencesPath, JSON.stringify({
                host: 'claude',
                modelsByRole: {
                    'feature, refactoring': ['confirmed-claude-model'],
                },
            }));
            const foreignSelection = runSelector(selectorPath, {
                host: 'claude',
                inventoryHost: 'claude',
                role: 'feature, refactoring',
                delegationIndex: 0,
                availableModelIds: ['confirmed-claude-model'],
                confirmedSuitableModelIds: [],
                parentFallback: {
                    isAllowed: false,
                    hasMaterialCapabilityLoss: false,
                },
            });
            assert.deepEqual(foreignSelection.nativeSpawnArguments, {
                model: 'confirmed-claude-model',
            });

            const manifest = JSON.parse(readFileSync(resolution.manifestFilePath, 'utf8'));
            assert.equal(manifest.files.includes(sharedPath), true);
            assert.equal(manifest.files.includes(managedSelectorPath), true);
            assert.equal(manifest.files.includes(preferencesPath), false);
            assert.equal(manifest.files.includes(foreignPreferencesPath), false);

            writeFileSync(sharedPath, 'stale');
            writeFileSync(preferencesPath, JSON.stringify({
                host: 'codex',
                modelsByRole: {
                    'feature, refactoring': ['user-edited-codex-model'],
                },
            }));
            runInstaller(homeDirectory, [...targetArguments, '--only', 'core']);
            assert.equal(readFileSync(sharedPath, 'utf8'), installedText);
            assert.deepEqual(
                JSON.parse(readFileSync(preferencesPath, 'utf8'))
                    .modelsByRole['feature, refactoring'],
                ['user-edited-codex-model'],
            );
            assert.deepEqual(
                JSON.parse(readFileSync(foreignPreferencesPath, 'utf8'))
                    .modelsByRole['feature, refactoring'],
                ['confirmed-claude-model'],
            );

            const syncArguments = [
                join(resolution.managedRoot, 'scripts', 'sync_to_cursor.py'),
                '--claude-root', resolution.managedRoot,
                '--cursor-root', resolution.cursorInstallDirectory,
                '--quiet',
            ];
            execFileSync('python', syncArguments);
            execFileSync('python', [...syncArguments, '--check']);
            assert.equal(readFileSync(cursorPath, 'utf8'), installedText);
            assert.equal(readFileSync(sharedPath, 'utf8'), installedText);
            if (targetName) {
                assert.equal(
                    existsSync(join(homeDirectory, '.agents', 'rules', 'pstack-models.mdc')),
                    false,
                );
            }

            runInstaller(homeDirectory, [...targetArguments, '--uninstall']);
            assert.equal(existsSync(sharedPath), false);
            assert.equal(existsSync(cursorPath), false);
            assert.equal(existsSync(selectorPath), false);
            assert.equal(existsSync(preferencesPath), true);
            assert.equal(existsSync(foreignPreferencesPath), true);
        } finally {
            rmSync(homeDirectory, { recursive: true, force: true });
        }
    });
}

test('a blocked shared rule destination rolls back generated Cursor files', () => {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-pstack-rollback-'));
    try {
        const sharedRulesPath = join(homeDirectory, '.agents', 'rules');
        mkdirSync(dirname(sharedRulesPath), { recursive: true });
        writeFileSync(sharedRulesPath, 'keep-existing-file');
        assert.throws(() => runInstaller(homeDirectory, ['--only', 'core']));
        assert.equal(readFileSync(sharedRulesPath, 'utf8'), 'keep-existing-file');
        assert.equal(existsSync(join(homeDirectory, '.cursor', 'rules', 'pstack-models.mdc')), false);
        assert.equal(existsSync(join(homeDirectory, '.cursor', '.sync-manifest.json')), false);
    } finally {
        rmSync(homeDirectory, { recursive: true, force: true });
    }
});

test('a failed install rolls back a newly seeded Codex preference file', () => {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-pstack-seed-rollback-'));
    try {
        const preferencesPath = join(
            homeDirectory,
            '.agents',
            'rules',
            'pstack-model-preferences.codex.json',
        );
        assert.throws(() => runInstaller(
            homeDirectory,
            ['--only', 'core'],
            { CLAUDE_DEV_ENV_INSTALL_FAULT: 'after_file_staging' },
        ));
        assert.equal(existsSync(preferencesPath), false);
    } finally {
        rmSync(homeDirectory, { recursive: true, force: true });
    }
});
