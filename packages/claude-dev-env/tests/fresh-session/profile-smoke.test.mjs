/**
 * Fresh-session profile smoke tests (main, editor, mel).
 *
 * Uses the fake CLI transport by default so CI never touches live profiles.
 */

import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { existsSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import {
    ALL_PROFILE_IDS,
    createDisposableRunRoots,
    buildIsolatedProfileEnvironment,
    removeDisposableRunRoots,
} from './harness/disposable-roots.mjs';
import { runProfileSession, shouldUseRealCli, FAKE_CLI_PATH } from './harness/transport.mjs';
import {
    parseHarnessArguments,
    runFreshSessionHarness,
} from './harness/run-fresh-session.mjs';

test('disposable roots set HOME, USERPROFILE, CLAUDE_CONFIG_DIR, and GIT_CONFIG_GLOBAL under a temp tree', () => {
    const roots = createDisposableRunRoots({ profileIds: ['main'] });
    try {
        const environment = buildIsolatedProfileEnvironment(roots, 'main');
        assert.equal(environment.HOME, roots.homeDirectory);
        assert.equal(environment.USERPROFILE, roots.userProfileDirectory);
        assert.equal(environment.CLAUDE_CONFIG_DIR, roots.profileRootById.main);
        assert.equal(environment.GIT_CONFIG_GLOBAL, roots.gitConfigGlobalPath);
        assert.ok(roots.runRoot.startsWith(tmpdir()) || roots.runRoot.includes('fresh-session'));
        assert.ok(existsSync(roots.profileRootById.main));
        assert.ok(String(environment.CLAUDE_CONFIG_DIR).startsWith(roots.profilesRoot));
    } finally {
        removeDisposableRunRoots(roots.runRoot);
    }
});

test('fake transport records command, version, profile root, exit status, and evidence path for each profile', () => {
    const roots = createDisposableRunRoots({ profileIds: [...ALL_PROFILE_IDS] });
    try {
        for (const eachProfileId of ALL_PROFILE_IDS) {
            const result = runProfileSession({
                roots,
                profileId: eachProfileId,
                realCli: false,
            });
            assert.equal(result.transport, 'fake');
            assert.equal(result.exitStatus, 0);
            assert.ok(result.cliVersion, 'cli version recorded');
            assert.ok(result.command.includes(FAKE_CLI_PATH) || result.command[0] === process.execPath);
            assert.equal(result.profileRoot, roots.profileRootById[eachProfileId]);
            assert.ok(existsSync(result.evidencePath), 'evidence file written');
            const evidence = JSON.parse(readFileSync(result.evidencePath, 'utf8'));
            assert.equal(evidence.profileId, eachProfileId);
            assert.equal(evidence.exitStatus, 0);
            assert.equal(
                evidence.environment.CLAUDE_CONFIG_DIR,
                roots.profileRootById[eachProfileId],
            );
        }
    } finally {
        removeDisposableRunRoots(roots.runRoot);
    }
});

test('failed profile produces profile-specific diagnostic and nonzero exit status', () => {
    const roots = createDisposableRunRoots({ profileIds: ['editor', 'mel'] });
    try {
        const failed = runProfileSession({
            roots,
            profileId: 'editor',
            realCli: false,
            failProfile: 'editor',
        });
        assert.notEqual(failed.exitStatus, 0);
        assert.ok(failed.diagnostic);
        assert.match(failed.diagnostic, /editor/);

        const passed = runProfileSession({
            roots,
            profileId: 'mel',
            realCli: false,
            failProfile: 'editor',
        });
        assert.equal(passed.exitStatus, 0);
        assert.equal(passed.diagnostic, null);
    } finally {
        removeDisposableRunRoots(roots.runRoot);
    }
});

test('repeated harness runs produce equivalent evidence shape for main, editor, and mel', () => {
    const first = runFreshSessionHarness({
        profileIds: [...ALL_PROFILE_IDS],
        checkTransport: true,
        realCli: false,
        keepRoots: true,
        failProfile: null,
    });
    const second = runFreshSessionHarness({
        profileIds: [...ALL_PROFILE_IDS],
        checkTransport: true,
        realCli: false,
        keepRoots: true,
        failProfile: null,
    });
    try {
        assert.equal(first.exitCode, 0);
        assert.equal(second.exitCode, 0);
        assert.equal(first.results.length, 3);
        assert.equal(second.results.length, 3);
        for (let index = 0; index < 3; index += 1) {
            const left = first.results[index];
            const right = second.results[index];
            assert.equal(left.profileId, right.profileId);
            assert.equal(left.transport, right.transport);
            assert.equal(left.exitStatus, right.exitStatus);
            assert.equal(left.cliVersion, right.cliVersion);
            assert.deepEqual(left.command, right.command);
        }
    } finally {
        removeDisposableRunRoots(first.runRoot);
        removeDisposableRunRoots(second.runRoot);
    }
});

test('parseHarnessArguments reads --profiles and --check transport', () => {
    const parsed = parseHarnessArguments([
        '--profiles',
        'main,editor,mel',
        '--check',
        'transport',
    ]);
    assert.deepEqual(parsed.profileIds, ['main', 'editor', 'mel']);
    assert.equal(parsed.checkTransport, true);
    assert.equal(shouldUseRealCli({ realCli: false }), false);
});

test('parseHarnessArguments rejects an empty profile list', () => {
    assert.throws(
        () => parseHarnessArguments(['--profiles', '']),
        /At least one profile id is required/,
    );
});

test('inherited FRESH_SESSION_FAIL_PROFILE does not poison a clean profile run', () => {
    const previous = process.env.FRESH_SESSION_FAIL_PROFILE;
    process.env.FRESH_SESSION_FAIL_PROFILE = 'main';
    const roots = createDisposableRunRoots({ profileIds: ['main'] });
    try {
        const result = runProfileSession({
            roots,
            profileId: 'main',
            realCli: false,
        });
        assert.equal(result.exitStatus, 0);
        assert.equal(result.diagnostic, null);
    } finally {
        removeDisposableRunRoots(roots.runRoot);
        if (previous === undefined) {
            delete process.env.FRESH_SESSION_FAIL_PROFILE;
        } else {
            process.env.FRESH_SESSION_FAIL_PROFILE = previous;
        }
    }
});


test('live profile paths are never used as CLAUDE_CONFIG_DIR under fake transport', () => {
    const roots = createDisposableRunRoots({ profileIds: ['main'] });
    try {
        const result = runProfileSession({ roots, profileId: 'main', realCli: false });
        const configDir = result.profileRoot.replace(/\\/g, '/').toLowerCase();
        const runRoot = roots.runRoot.replace(/\\/g, '/').toLowerCase();
        assert.equal(result.profileRoot, roots.profileRootById.main);
        assert.ok(configDir.startsWith(runRoot));
        assert.ok(configDir.includes('fresh-session') || configDir.startsWith(tmpdir().replace(/\\/g, '/').toLowerCase()));
    } finally {
        removeDisposableRunRoots(roots.runRoot);
    }
});
