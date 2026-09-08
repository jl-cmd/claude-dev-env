import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { installPstack, validateLock } from './install.mjs';

test('lock validation requires a commit, adapter digest and declared verification', () => {
    const lock = {
        schemaVersion: 1, adapterVersion: 1,
        upstreamCommit: 'a'.repeat(40), adapterDigest: 'b'.repeat(64),
        verification: 'install-contract',
    };
    assert.equal(validateLock(lock).upstreamCommit, 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa');
    for (const changedField of [
        { upstreamCommit: 'main' }, { adapterDigest: 'b'.repeat(63) },
        { verification: 'live-host' }, { schemaVersion: 2 },
    ]) {
        assert.throws(() => validateLock({ ...lock, ...changedField }), /Invalid pstack lock/);
    }
});

test('an unsupported host fails before the installer creates workspace files', async t => {
    const directory = mkdtempSync(join(tmpdir(), 'pstack invalid host '));
    t.after(() => rmSync(directory, { recursive: true, force: true }));
    const root = join(directory, 'workspace');
    await assert.rejects(installPstack({ root, host: 'unsupported' }), /Choose --host claude, codex or cursor/);
    assert.equal(existsSync(root), false);
});
