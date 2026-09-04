import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, existsSync, rmSync } from 'node:fs';
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

function runInstaller(homeDirectory, extraArguments) {
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
        },
    });
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

test('--only journal skips Cursor rule generation; --only core writes them', () => {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-cursor-groups-'));
    try {
        const generatedPath = join(
            homeDirectory,
            DEFAULT_CURSOR_DIRECTORY_NAME,
            CURSOR_RULES_DIRECTORY_NAME,
            'asd-ste100-language.mdc',
        );
        runInstaller(homeDirectory, ['--only', 'journal']);
        assert.equal(existsSync(generatedPath), false);

        runInstaller(homeDirectory, ['--only', 'core']);
        assert.equal(existsSync(generatedPath), true);
    } finally {
        rmSync(homeDirectory, { recursive: true, force: true });
    }
});

for (const targetName of [null, 'profile']) {
    test(`pstack rules survive reinstall and sync for ${targetName ?? 'main'}`, () => {
        const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-pstack-'));
        try {
            const targetArguments = targetName ? ['--target', join(homeDirectory, targetName)] : [];
            const resolution = resolveInstallRoot({
                homeDirectory,
                environment: {},
                explicitTarget: targetName ? join(homeDirectory, targetName) : null,
            });
            const sharedPath = join(resolution.agentsHome, 'rules', 'pstack-models.mdc');
            const cursorPath = join(resolution.cursorRulesInstallDirectory, 'pstack-models.mdc');
            const expectedRoles = [
                'feature, refactoring: gpt-5.6-sol',
                'bug-fix: gpt-5.6-sol',
                'perf-issue: gpt-6-astra',
                'hillclimb: gpt-6-astra',
                'judgment and prose: gpt-6-astra',
                'hardest tasks: gpt-6-astra',
                'how explorer: gpt-5.6-terra',
                'how explainer: gpt-5.6-sol',
                'how critics: gpt-5.6-terra, gpt-5.6-sol, gpt-6-astra',
                'why investigators: gpt-5.6-terra',
                'why synthesizer: gpt-6-astra',
                'reflect tooling: gpt-5.6-sol',
                'reflect judgment, divergent, synthesizer: gpt-6-astra',
                'arena runners: gpt-5.6-terra, gpt-5.6-sol, gpt-6-astra',
                'arena cross-judge pool: gpt-5.6-sol, gpt-6-astra',
                'swarm workers: gpt-5.6-luna',
                'architect runners: gpt-5.6-sol, gpt-6-astra',
                'interrogate reviewers: gpt-5.6-terra, gpt-5.6-sol, gpt-6-astra',
            ];
            runInstaller(homeDirectory, [...targetArguments, '--only', 'core']);
            const installedText = readFileSync(sharedPath, 'utf8');
            assert.deepEqual(installedText.split(/\r?\n/).filter(line => line.includes(': gpt-')), expectedRoles);
            assert.match(installedText, /alwaysApply: true/);
            assert.equal(readFileSync(cursorPath, 'utf8'), installedText);
            assert.equal(isAllowedInstallDestination(sharedPath, resolution), true);
            const manifest = JSON.parse(readFileSync(resolution.manifestFilePath, 'utf8'));
            assert.equal(manifest.files.includes(sharedPath), true);
            writeFileSync(sharedPath, 'stale');
            runInstaller(homeDirectory, [...targetArguments, '--only', 'core']);
            assert.equal(readFileSync(sharedPath, 'utf8'), installedText);
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
                assert.equal(existsSync(join(homeDirectory, '.agents', 'rules', 'pstack-models.mdc')), false);
            }
            runInstaller(homeDirectory, [...targetArguments, '--uninstall']);
            assert.equal(existsSync(sharedPath), false);
            assert.equal(existsSync(cursorPath), false);
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
