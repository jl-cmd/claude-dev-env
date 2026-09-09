import test from 'node:test';
import assert from 'node:assert/strict';
import { cpSync, existsSync, lstatSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
import { installPstackRelease, shouldInstallPstackRelease } from './install.mjs';

const THIS_DIRECTORY = dirname(fileURLToPath(import.meta.url));
const PACKAGE_ROOT = resolve(THIS_DIRECTORY, '..');
const INSTALLER_PATH = join(THIS_DIRECTORY, 'install.mjs');
const BASE_LOCK = JSON.parse(readFileSync(join(PACKAGE_ROOT, 'scripts', 'pstack.lock.json'), 'utf8'));

function put(path, content) {
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, content);
}

function upstreamFixture(t) {
    const temporary = mkdtempSync(join(tmpdir(), 'cde-install-pstack-'));
    t.after(() => rmSync(temporary, { recursive: true, force: true }));
    const checkout = join(temporary, 'checkout');
    for (const [component, names] of Object.entries(BASE_LOCK.requiredSkills)) {
        for (const name of names) {
            put(
                join(checkout, component, 'skills', name, 'SKILL.md'),
                `---\nname: ${name}\ndescription: Test ${name}.\n---\n\nRun ${name}.\n`,
            );
        }
    }
    const managedRoot = join(temporary, 'home', '.claude');
    return {
        temporary,
        managedRoot,
        options: { root: managedRoot, lock: structuredClone(BASE_LOCK), packageRoot: PACKAGE_ROOT },
        dependencies: { fetchSource: (_lock, destination) => cpSync(checkout, destination, { recursive: true }) },
    };
}

test('the base install publishes the pstack poteto-mode entry into the managed skills home', t => {
    const fixture = upstreamFixture(t);

    const outcome = installPstackRelease(fixture.options, fixture.dependencies);

    assert.equal(outcome.status, 'installed');
    assert.equal(outcome.warning, null);
    const entryPath = join(fixture.managedRoot, 'skills', 'pstack-poteto-mode');
    assert.equal(lstatSync(entryPath).isSymbolicLink(), true);
    assert.equal(existsSync(join(entryPath, 'SKILL.md')), true);
});

test('an unreachable upstream reports a warning and keeps the base install going', t => {
    const fixture = upstreamFixture(t);

    const outcome = installPstackRelease(fixture.options, {
        fetchSource: () => { throw new Error('network unavailable'); },
    });

    assert.equal(outcome.status, 'failed');
    assert.equal(outcome.release, null);
    assert.match(outcome.warning, /network unavailable/);
});

test('--no-pstack and CDE_INSTALL_PSTACK=0 each turn the pstack step off', () => {
    assert.equal(shouldInstallPstackRelease([], {}), true);
    assert.equal(shouldInstallPstackRelease(['--no-pstack'], {}), false);
    assert.equal(shouldInstallPstackRelease([], { CDE_INSTALL_PSTACK: '0' }), false);
    assert.equal(shouldInstallPstackRelease([], { CDE_INSTALL_PSTACK: '1' }), true);
});

function runInstaller(homeDirectory, extraArguments, environmentOverrides = {}) {
    return execFileSync('node', [INSTALLER_PATH, ...extraArguments], {
        cwd: PACKAGE_ROOT,
        encoding: 'utf8',
        env: {
            ...process.env,
            HOME: homeDirectory,
            USERPROFILE: homeDirectory,
            CODEX_HOME: join(homeDirectory, '.codex'),
            CLAUDE_CONFIG_DIR: join(homeDirectory, '.claude'),
            GIT_CONFIG_GLOBAL: join(homeDirectory, '.gitconfig'),
            CDE_INSTALL_PSTACK: '1',
            GIT_ALLOW_PROTOCOL: 'none',
        },
        ...environmentOverrides,
    });
}

function withTemporaryHome(t, runAssertions) {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cde-install-pstack-run-'));
    t.after(() => rmSync(homeDirectory, { recursive: true, force: true }));
    runAssertions(homeDirectory);
}

test('a full install runs the pstack step and reports an upstream failure without stopping', t => {
    withTemporaryHome(t, homeDirectory => {
        const output = runInstaller(homeDirectory, []);

        assert.match(output, /Pstack:/);
        assert.equal(existsSync(join(homeDirectory, '.claude', 'pstack')), true);
    });
});

test('--no-pstack leaves the pstack store absent', t => {
    withTemporaryHome(t, homeDirectory => {
        const output = runInstaller(homeDirectory, ['--no-pstack']);

        assert.doesNotMatch(output, /Pstack:/);
        assert.equal(existsSync(join(homeDirectory, '.claude', 'pstack')), false);
    });
});
