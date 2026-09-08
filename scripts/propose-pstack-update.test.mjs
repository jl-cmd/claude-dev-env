import assert from 'node:assert/strict';
import { cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { proposePstackUpdate } from './propose-pstack-update.mjs';
import { installPstack } from '../packages/claude-dev-env/bin/pstack.mjs';

const repositoryRoot = join(dirname(fileURLToPath(import.meta.url)), '..');
const bundled = readFileSync(join(repositoryRoot, 'packages/claude-dev-env/scripts/pstack.lock.json'), 'utf8');

function fixture(t) {
    const root = mkdtempSync(join(tmpdir(), 'pstack update test '));
    t.after(() => rmSync(root, { recursive: true, force: true }));
    const lockPath = join(root, 'pstack.lock.json');
    writeFileSync(lockPath, bundled);
    return { root, lockPath, lock: JSON.parse(bundled) };
}

test('an unchanged upstream leaves the shared pin byte-identical and skips installation', t => {
    const f = fixture(t);
    assert.deepEqual(proposePstackUpdate(f.lockPath, {
        readCommit: repository => { assert.equal(repository, 'https://github.com/cursor/plugins.git'); return f.lock.commit; },
        install: () => assert.fail('unchanged revision must not install'),
    }), { status: 'unchanged', commit: f.lock.commit });
    assert.equal(readFileSync(f.lockPath, 'utf8'), bundled);
});

test('a candidate updates the pin only after a complete installation and cleans its temporary root', t => {
    const f = fixture(t);
    const source = join(f.root, 'source');
    for (const [component, names] of Object.entries(f.lock.requiredSkills)) {
        for (const name of names) {
            const path = join(source, component, 'skills', name, 'SKILL.md');
            mkdirSync(dirname(path), { recursive: true });
            writeFileSync(path, `---\nname: ${name}\ndescription: Fixture ${name}.\n---\nRead local evidence.\n`);
        }
    }
    let installRoot;
    const proposal = proposePstackUpdate(f.lockPath, {
        readCommit: () => 'a'.repeat(40),
        install: options => {
            assert.equal(readFileSync(f.lockPath, 'utf8'), bundled);
            assert.equal(options.strict, true);
            installRoot = options.root;
            return installPstack(options, { fetchSource: (_lock, destination) => cpSync(source, destination, { recursive: true }) });
        },
    });
    assert.deepEqual(proposal, { status: 'proposed', commit: 'a'.repeat(40), skillCount: 5 });
    assert.deepEqual(JSON.parse(readFileSync(f.lockPath, 'utf8')), { ...f.lock, commit: 'a'.repeat(40) });
    assert.equal(existsSync(installRoot), false);
});

test('invalid upstream and failed installation preserve the shared pin', t => {
    const f = fixture(t);
    assert.throws(() => proposePstackUpdate(f.lockPath, {
        readCommit: () => 'main', install: () => assert.fail('invalid revision must not install'),
    }), /Unsupported pstack lock/);
    let installRoot;
    assert.throws(() => proposePstackUpdate(f.lockPath, {
        readCommit: () => 'b'.repeat(40), install: options => { installRoot = options.root; throw new Error('Missing dependency'); },
    }), /Missing dependency/);
    assert.equal(readFileSync(f.lockPath, 'utf8'), bundled);
    assert.equal(existsSync(dirname(installRoot)), false);
});
