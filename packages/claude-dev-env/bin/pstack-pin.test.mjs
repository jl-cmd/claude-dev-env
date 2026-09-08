import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync, symlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { adapterDigest, validateLock } from '../scripts/pstack/install.mjs';

const packageRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');

test('bundled revision matches the adapter shipped in this package', () => {
    const pin = validateLock(JSON.parse(readFileSync(join(packageRoot, 'scripts/pstack/verified.json'), 'utf8')));
    assert.equal(pin.adapterDigest, adapterDigest(packageRoot));
});

test('CLI runs through a linked executable directory', t => {
    const directory = mkdtempSync(join(tmpdir(), 'pstack entry '));
    t.after(() => rmSync(directory, { recursive: true, force: true }));
    const linkedBin = join(directory, 'bin');
    symlinkSync(join(packageRoot, 'bin'), linkedBin, process.platform === 'win32' ? 'junction' : 'dir');
    const output = execFileSync(process.execPath, [join(linkedBin, 'pstack.mjs'), '--help'], { encoding: 'utf8' });
    assert.match(output, /Usage: cde-pstack/);
});
