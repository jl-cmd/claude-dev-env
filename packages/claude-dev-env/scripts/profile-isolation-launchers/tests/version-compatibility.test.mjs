/**
 * CLI / Desktop version compatibility contract (control-plane K1 / P-26).
 */

import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { existsSync, readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import {
    classifyVersionCompatibility,
    shouldBlockLaunch,
    parseSemver,
    COMPATIBILITY_POLICY_VERSION,
    COMPATIBILITY_ACTION_BY_CLASS,
} from '../version-compatibility.mjs';
import {
    evaluateLauncherVersionCompatibility,
    formatCompatibilityPreflightFailure,
} from '../launcher-runtime.mjs';

const PACKAGE_ROOT = join(
    dirname(fileURLToPath(import.meta.url)),
    '..',
    '..',
    '..',
);

test('action table covers every compatibility class and fails closed', () => {
    const allExpectedClasses = [
        'equal',
        'patch-drift',
        'minor-drift',
        'major-drift',
        'missing-binary',
        'unreadable',
        'process-error',
        'non-semver',
    ];
    for (const eachClass of allExpectedClasses) {
        assert.ok(
            Object.hasOwn(COMPATIBILITY_ACTION_BY_CLASS, eachClass),
            `missing action for ${eachClass}`,
        );
    }
    assert.equal(COMPATIBILITY_ACTION_BY_CLASS.equal, 'pass');
    assert.equal(COMPATIBILITY_ACTION_BY_CLASS['patch-drift'], 'warn');
    assert.equal(COMPATIBILITY_ACTION_BY_CLASS['minor-drift'], 'block');
    assert.equal(COMPATIBILITY_ACTION_BY_CLASS['major-drift'], 'block');
    assert.equal(COMPATIBILITY_ACTION_BY_CLASS['missing-binary'], 'block');
    assert.equal(COMPATIBILITY_ACTION_BY_CLASS.unreadable, 'block');
    assert.equal(COMPATIBILITY_ACTION_BY_CLASS['process-error'], 'block');
    assert.equal(COMPATIBILITY_ACTION_BY_CLASS['non-semver'], 'block');
});

test('equal versions pass with both paths, versions, and policy version', () => {
    const result = classifyVersionCompatibility({
        cli: { path: 'C:\\cli\\claude.exe', versionText: '2.1.220' },
        desktop: { path: 'C:\\desktop\\claude.exe', versionText: '2.1.220' },
    });
    assert.equal(result.class, 'equal');
    assert.equal(result.action, 'pass');
    assert.equal(result.policyVersion, COMPATIBILITY_POLICY_VERSION);
    assert.equal(result.cliPath, 'C:\\cli\\claude.exe');
    assert.equal(result.desktopPath, 'C:\\desktop\\claude.exe');
    assert.equal(result.cliVersion, '2.1.220');
    assert.equal(result.desktopVersion, '2.1.220');
    assert.equal(shouldBlockLaunch(result), false);
});

test('patch drift warns and identifies the runtime pair', () => {
    const result = classifyVersionCompatibility({
        cli: { path: 'cli', versionText: '2.1.220' },
        desktop: { path: 'desktop', versionText: '2.1.219' },
    });
    assert.equal(result.class, 'patch-drift');
    assert.equal(result.action, 'warn');
    assert.match(result.message, /patch drift/i);
    assert.equal(shouldBlockLaunch(result), false);
});

test('minor and major drift block before mutation', () => {
    const minor = classifyVersionCompatibility({
        cli: { path: 'cli', versionText: '2.1.220' },
        desktop: { path: 'desktop', versionText: '2.0.100' },
    });
    assert.equal(minor.class, 'minor-drift');
    assert.equal(minor.action, 'block');
    assert.equal(shouldBlockLaunch(minor), true);

    const major = classifyVersionCompatibility({
        cli: { path: 'cli', versionText: '2.1.220' },
        desktop: { path: 'desktop', versionText: '1.9.0' },
    });
    assert.equal(major.class, 'major-drift');
    assert.equal(major.action, 'block');
    assert.equal(shouldBlockLaunch(major), true);
});

test('missing, unreadable, process-error, and non-semver block', () => {
    const missing = classifyVersionCompatibility({
        cli: { path: null, versionText: null, errorCode: 'missing' },
        desktop: { path: 'desktop', versionText: '2.1.220' },
    });
    assert.equal(missing.class, 'missing-binary');
    assert.equal(missing.action, 'block');

    const unreadable = classifyVersionCompatibility({
        cli: { path: 'cli', versionText: null, errorCode: 'unreadable' },
        desktop: { path: 'desktop', versionText: '2.1.220' },
    });
    assert.equal(unreadable.class, 'unreadable');
    assert.equal(unreadable.action, 'block');

    const processError = classifyVersionCompatibility({
        cli: {
            path: 'cli',
            versionText: null,
            errorCode: 'process-error',
            errorMessage: 'exit 127',
        },
        desktop: { path: 'desktop', versionText: '2.1.220' },
    });
    assert.equal(processError.class, 'process-error');
    assert.equal(processError.action, 'block');
    assert.match(processError.message, /exit 127/);

    const nonSemver = classifyVersionCompatibility({
        cli: { path: 'cli', versionText: 'unknown' },
        desktop: { path: 'desktop', versionText: '2.1.220' },
    });
    assert.equal(nonSemver.class, 'non-semver');
    assert.equal(nonSemver.action, 'block');
});

test('parseSemver reads the first major.minor.patch triple', () => {
    assert.deepEqual(parseSemver('2.1.220'), { major: 2, minor: 1, patch: 220 });
    assert.deepEqual(parseSemver('claude 2.1.219 (win)'), { major: 2, minor: 1, patch: 219 });
    assert.equal(parseSemver('unknown'), null);
    assert.equal(parseSemver(''), null);
});

test('launcher preflight evaluates probes and blocks incompatible pairs', () => {
    const blocked = evaluateLauncherVersionCompatibility({
        cli: { path: 'cli', versionText: '2.1.220' },
        desktop: { path: 'desktop', versionText: '1.0.0' },
    });
    assert.equal(blocked.class, 'major-drift');
    assert.equal(blocked.action, 'block');
    assert.equal(shouldBlockLaunch(blocked), true);
    const message = formatCompatibilityPreflightFailure(blocked);
    assert.match(message, /version compatibility/i);
    assert.match(message, /major drift/i);

    const allowed = evaluateLauncherVersionCompatibility({
        cli: { path: 'cli', versionText: '2.1.220' },
        desktop: { path: 'desktop', versionText: '2.1.220' },
    });
    assert.equal(allowed.action, 'pass');
});

test('live CLI version diagnostic records a real probe when CLAUDE_CLI_PATH is set', () => {
    const cliPath = process.env.CLAUDE_CLI_PATH;
    if (!cliPath || !existsSync(cliPath)) {
        // Policy matrix above is the unit evidence. Live readback is optional and
        // activated by CLAUDE_CLI_PATH so the suite stays free of host-private paths.
        const missing = classifyVersionCompatibility({
            cli: { path: null, versionText: null, errorCode: 'missing' },
            desktop: { path: null, versionText: null, errorCode: 'missing' },
        });
        assert.equal(missing.class, 'missing-binary');
        return;
    }
    const probe = spawnSync(cliPath, ['--version'], {
        encoding: 'utf8',
        timeout: 15_000,
    });
    const versionText = `${probe.stdout || ''}${probe.stderr || ''}`.trim();
    assert.equal(probe.error, undefined);
    assert.ok(versionText.length > 0, 'claude --version produced empty output');
    const parsed = parseSemver(versionText);
    assert.ok(parsed, `expected semver in: ${versionText}`);

    // Self-pair: equal pass against the same live CLI text (desktop diagnostic-only).
    const result = classifyVersionCompatibility({
        cli: { path: cliPath, versionText },
        desktop: { path: cliPath, versionText },
    });
    assert.equal(result.class, 'equal');
    assert.equal(result.action, 'pass');
    assert.equal(result.policyVersion, COMPATIBILITY_POLICY_VERSION);
});

test('package ships version-compatibility module and test paths', () => {
    const allPaths = [
        join(PACKAGE_ROOT, 'scripts/profile-isolation-launchers/version-compatibility.mjs'),
        join(PACKAGE_ROOT, 'scripts/profile-isolation-launchers/tests/version-compatibility.test.mjs'),
        join(PACKAGE_ROOT, 'scripts/profile-isolation-launchers/launcher-runtime.mjs'),
    ];
    for (const eachPath of allPaths) {
        assert.ok(existsSync(eachPath), `missing ${eachPath}`);
    }
    const runtimeSource = readFileSync(
        join(PACKAGE_ROOT, 'scripts/profile-isolation-launchers/launcher-runtime.mjs'),
        'utf8',
    );
    assert.match(runtimeSource, /version-compatibility\.mjs/);
    assert.match(runtimeSource, /evaluateLauncherVersionCompatibility/);
});
