/**
 * Install-root resolver contract tests (control-plane A2 / P-11).
 */

import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { join, resolve } from 'node:path';
import { mkdtempSync, rmSync, mkdirSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import { CODEX_RULES_SHIPPED_FILE_NAME } from './install-constants.mjs';
import {
    resolveInstallRoot,
    isPathWithinManagedRoot,
    isAllowedInstallDestination,
    parseExplicitTargetFromArgv,
    CLAUDE_CONFIG_DIR_ENVIRONMENT_VARIABLE,
    DEFAULT_CLAUDE_DIRECTORY_NAME,
} from './resolve-install-root.mjs';

const BIN_DIRECTORY = fileURLToPath(new URL('.', import.meta.url));
const INSTALL_MODULE_PATH = join(BIN_DIRECTORY, 'install.mjs');

test('default target remains join(homeDirectory, .claude)', () => {
    const homeDirectory = resolve(join(tmpdir(), 'a2-home-default'));
    const resolution = resolveInstallRoot({
        homeDirectory,
        environment: {},
        explicitTarget: null,
    });
    assert.equal(resolution.managedRoot, resolve(join(homeDirectory, DEFAULT_CLAUDE_DIRECTORY_NAME)));
    assert.equal(resolution.source, 'default-home');
});

test('CLAUDE_CONFIG_DIR selects the profile root over the home default', () => {
    const homeDirectory = resolve(join(tmpdir(), 'a2-home-config'));
    const profileRoot = resolve(join(tmpdir(), 'a2-profile-a'));
    const resolution = resolveInstallRoot({
        homeDirectory,
        environment: { [CLAUDE_CONFIG_DIR_ENVIRONMENT_VARIABLE]: profileRoot },
        explicitTarget: null,
    });
    assert.equal(resolution.managedRoot, profileRoot);
    assert.equal(resolution.source, 'claude-config-dir');
    assert.notEqual(
        resolution.managedRoot,
        resolve(join(homeDirectory, DEFAULT_CLAUDE_DIRECTORY_NAME)),
    );
});

test('explicit target has precedence over CLAUDE_CONFIG_DIR and the home default', () => {
    const homeDirectory = resolve(join(tmpdir(), 'a2-home-explicit'));
    const profileRoot = resolve(join(tmpdir(), 'a2-profile-b'));
    const explicitTarget = resolve(join(tmpdir(), 'a2-explicit-target'));
    const resolution = resolveInstallRoot({
        homeDirectory,
        environment: { [CLAUDE_CONFIG_DIR_ENVIRONMENT_VARIABLE]: profileRoot },
        explicitTarget,
    });
    assert.equal(resolution.managedRoot, explicitTarget);
    assert.equal(resolution.source, 'explicit-target');
});

test('isPathWithinManagedRoot requires a separator boundary', () => {
    const managedRoot = resolve(join(tmpdir(), 'containment-root', '.claude'));
    const insideFile = join(managedRoot, 'rules', 'plain-language.md');
    const evilSibling = `${managedRoot}-evil`;
    const evilChild = join(`${managedRoot}-evil`, 'rules', 'x.md');

    assert.equal(isPathWithinManagedRoot(managedRoot, managedRoot), true);
    assert.equal(isPathWithinManagedRoot(insideFile, managedRoot), true);
    assert.equal(isPathWithinManagedRoot(evilSibling, managedRoot), false);
    assert.equal(isPathWithinManagedRoot(evilChild, managedRoot), false);
});

test('declared external mypy.ini is allowed; unrelated external paths are not', () => {
    const homeDirectory = resolve(join(tmpdir(), 'a2-home-external'));
    const resolution = resolveInstallRoot({
        homeDirectory,
        environment: {},
    });
    assert.equal(
        isAllowedInstallDestination(resolution.mypyIniInstallPath, resolution),
        true,
    );
    assert.equal(
        isAllowedInstallDestination(join(homeDirectory, '.ssh', 'id_rsa'), resolution),
        false,
    );
    assert.equal(
        isAllowedInstallDestination(join(resolution.managedRoot, 'hooks', 'x.py'), resolution),
        true,
    );
    assert.equal(
        isAllowedInstallDestination(
            join(resolution.codexRulesInstallDirectory, CODEX_RULES_SHIPPED_FILE_NAME),
            resolution,
        ),
        true,
    );
});

test('parseExplicitTargetFromArgv reads --target and --target=', () => {
    assert.equal(parseExplicitTargetFromArgv(['--only', 'core']), null);
    assert.equal(parseExplicitTargetFromArgv(['--target', 'C:\\tmp\\root']), 'C:\\tmp\\root');
    assert.equal(parseExplicitTargetFromArgv(['--target=C:\\tmp\\root2']), 'C:\\tmp\\root2');
    assert.throws(
        () => parseExplicitTargetFromArgv(['--target']),
        /--target requires a path argument/,
    );
});

test('installer destinations for disposable main, profile-a, and profile-b stay inside the managed root', () => {
    const runRoot = mkdtempSync(join(tmpdir(), 'a2-disposable-'));
    try {
        for (const eachProfileId of ['main', 'profile-a', 'profile-b']) {
            const profileRoot = join(runRoot, eachProfileId);
            mkdirSync(profileRoot, { recursive: true });
            const homeDirectory = join(runRoot, `${eachProfileId}-home`);
            mkdirSync(homeDirectory, { recursive: true });

            const resolution = resolveInstallRoot({
                homeDirectory,
                environment: { [CLAUDE_CONFIG_DIR_ENVIRONMENT_VARIABLE]: profileRoot },
            });
            assert.equal(resolution.managedRoot, resolve(profileRoot));
            assert.equal(resolution.source, 'claude-config-dir');

            const allManagedWritePaths = [
                join(resolution.managedRoot, 'rules', 'sample.md'),
                join(resolution.managedRoot, 'hooks', 'blocking', 'x.py'),
                join(resolution.managedRoot, 'CLAUDE.md'),
                resolution.manifestFilePath,
            ];
            for (const eachWritePath of allManagedWritePaths) {
                assert.equal(
                    isAllowedInstallDestination(eachWritePath, resolution),
                    true,
                    `${eachProfileId}: ${eachWritePath}`,
                );
            }
            assert.equal(
                isAllowedInstallDestination(resolution.mypyIniInstallPath, resolution),
                true,
            );
        }
    } finally {
        rmSync(runRoot, { recursive: true, force: true });
    }
});

test('install.mjs module resolves CLAUDE_HOME through the shared resolver (import smoke)', async () => {
    // Guard: the install module must import resolve-install-root so destinations
    // cannot bypass the resolver by re-hardcoding join(homedir(), '.claude').
    const source = readFileSync(INSTALL_MODULE_PATH, 'utf8');
    assert.match(source, /resolve-install-root\.mjs/);
    assert.match(source, /resolveInstallRoot/);
    assert.ok(
        !/const CLAUDE_HOME = join\(homedir\(\), ['"]\.claude['"]\)/.test(source),
        'install.mjs must not hardcode CLAUDE_HOME = join(homedir(), \'.claude\')',
    );
});
