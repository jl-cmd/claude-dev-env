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
        isAllowedInstallDestination(join(expectedDirectory, 'plain-language.mdc'), resolution),
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
            'plain-language.mdc',
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
            'plain-language.mdc',
        );
        runInstaller(homeDirectory, ['--only', 'journal']);
        assert.equal(existsSync(generatedPath), false);

        runInstaller(homeDirectory, ['--only', 'core']);
        assert.equal(existsSync(generatedPath), true);
    } finally {
        rmSync(homeDirectory, { recursive: true, force: true });
    }
});
