import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { createPstackCandidate, publishPstackChannel } from './pstack-channel.mjs';
import { adapterDigest, readCentralLock } from '../packages/claude-dev-env/bin/pstack.mjs';

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const bundledPath = join(repositoryRoot, 'packages/claude-dev-env/scripts/pstack.lock.json');

function fixture(t) {
    const directory = mkdtempSync(join(tmpdir(), 'pstack channel '));
    t.after(() => rmSync(directory, { recursive: true, force: true }));
    const repository = join(directory, 'repository');
    const remote = join(directory, 'remote.git');
    mkdirSync(repository);
    const git = args => execFileSync('git', args, { cwd: repository, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }).trim();
    git(['init', '--quiet']);
    git(['init', '--quiet', '--bare', remote]);
    return { directory, repository, remote, git, lockPath: join(directory, 'pstack.lock.json') };
}

test('candidate records the upstream commit and exact adapter without changing the bundled pin', t => {
    const f = fixture(t);
    const bundled = readFileSync(bundledPath, 'utf8');
    for (const commit of [JSON.parse(bundled).commit, 'a'.repeat(40)]) {
        const record = createPstackCandidate(f.lockPath, { readCommit: repository => {
            assert.equal(repository, 'https://github.com/cursor/plugins.git');
            return commit;
        } });
        assert.equal(record.commit, commit);
        assert.equal(record.adapterDigest, adapterDigest());
        assert.equal(record.verification, 'install-contract');
        assert.deepEqual(JSON.parse(readFileSync(f.lockPath, 'utf8')), record);
        assert.equal(readFileSync(bundledPath, 'utf8'), bundled);
    }
});

test('invalid upstream leaves the candidate absent', t => {
    const f = fixture(t);
    assert.throws(() => createPstackCandidate(f.lockPath, { readCommit: () => 'main' }), /Unsupported pstack lock/);
    assert.equal(existsSync(f.lockPath), false);
});

test('channel creates, fast-forwards and reuses one record that the installer reads from Git', t => {
    const f = fixture(t);
    const options = { repositoryRoot: f.repository, remote: f.remote };
    createPstackCandidate(f.lockPath, { readCommit: () => 'a'.repeat(40) });
    assert.equal(publishPstackChannel(f.lockPath, options).status, 'published');
    const first = f.git(['ls-remote', f.remote, 'refs/heads/pstack-verified']).split(/\s+/)[0];
    assert.deepEqual(publishPstackChannel(f.lockPath, options), { status: 'unchanged', commit: 'a'.repeat(40) });
    const before = f.git(['ls-remote', f.remote, 'refs/heads/pstack-verified']);
    assert.equal(publishPstackChannel(f.lockPath, options).status, 'unchanged');
    assert.equal(f.git(['ls-remote', f.remote, 'refs/heads/pstack-verified']), before);
    const record = createPstackCandidate(f.lockPath, { readCommit: () => 'b'.repeat(40) });
    assert.equal(publishPstackChannel(f.lockPath, options).status, 'published');
    f.git(['fetch', '--quiet', f.remote, 'refs/heads/pstack-verified']);
    const second = f.git(['rev-parse', 'FETCH_HEAD']);
    assert.notEqual(first, second);
    assert.equal(f.git(['rev-parse', `${second}^`]), first);
    assert.deepEqual(f.git(['ls-tree', '--name-only', second]).split('\n'), ['pstack.lock.json']);
    const checkout = join(f.directory, 'reader');
    mkdirSync(checkout);
    assert.deepEqual(readCentralLock(checkout, f.remote), record);
    assert.equal(f.git(['ls-remote', f.remote, 'refs/heads/main']), '');
});

test('invalid or mismatched channel records leave the remote branch unchanged', t => {
    const f = fixture(t);
    const options = { repositoryRoot: f.repository, remote: f.remote };
    const candidate = createPstackCandidate(f.lockPath, { readCommit: () => 'a'.repeat(40) });
    publishPstackChannel(f.lockPath, options);
    const before = f.git(['ls-remote', f.remote]);
    for (const change of [{ adapterDigest: '0'.repeat(64) }, { verification: 'live-host' }, { commit: 'main' }]) {
        writeFileSync(f.lockPath, JSON.stringify({ ...candidate, ...change }));
        assert.throws(() => publishPstackChannel(f.lockPath, options));
        assert.equal(f.git(['ls-remote', f.remote]), before);
    }
    writeFileSync(f.lockPath, JSON.stringify(candidate));
    assert.throws(() => publishPstackChannel(f.lockPath, { ...options, remote: join(f.directory, 'missing.git') }));
    assert.equal(f.git(['ls-remote', f.remote]), before);
});

test('publication is gated on the installation matrix, trusted main events and explicit enablement', () => {
    const workflow = readFileSync(join(repositoryRoot, '.github/workflows/pstack-installation.yml'), 'utf8');
    const publication = workflow.slice(workflow.indexOf('  publish-channel:'));
    assert.match(publication, /needs: \[candidate, installation\]/);
    assert.match(publication, /github\.event_name == 'schedule' \|\| github\.event_name == 'workflow_dispatch'/);
    assert.match(publication, /github\.ref == 'refs\/heads\/main' && vars\.PSTACK_ENABLE_PROMOTION == 'true'/);
    assert.match(publication, /contents: write/);
    assert.match(publication, /name: pstack-candidate/);
    assert.doesNotMatch(publication, /always\(\)|continue-on-error/);
    assert.match(workflow, /os: \[ubuntu-latest, windows-latest\]/);
    assert.match(workflow, /pstack-codex-discovery\.test\.mjs/);
    assert.equal(existsSync(join(repositoryRoot, '.github/workflows/pstack-upstream.yml')), false);
});
