/**
 * Real-filesystem tests for Claude lookup pointers into the agents home.
 */

import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import {
    existsSync,
    lstatSync,
    mkdirSync,
    mkdtempSync,
    readFileSync,
    realpathSync,
    rmSync,
    writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import {
    DIRECTORY_POINTER_TYPE_DIR,
    DIRECTORY_POINTER_TYPE_JUNCTION,
    POINTER_ACTION_ALREADY_POINTING,
    POINTER_ACTION_CREATED,
    directoryPointerTypeForPlatform,
    ensureDirectoryPointer,
    isDirectoryPointerTo,
    unlinkDirectoryPointerIfMatch,
} from './publish-directory-pointer.mjs';

function makeSandbox() {
    const root = mkdtempSync(join(tmpdir(), 'cdev-pointer-'));
    return {
        root,
        pointerPath: join(root, 'lookup', 'skills'),
        targetPath: join(root, 'canonical', 'skills'),
    };
}

test('directoryPointerTypeForPlatform uses a junction on Windows and a dir pointer elsewhere', () => {
    assert.equal(directoryPointerTypeForPlatform('win32'), DIRECTORY_POINTER_TYPE_JUNCTION);
    assert.equal(directoryPointerTypeForPlatform('linux'), DIRECTORY_POINTER_TYPE_DIR);
    assert.equal(directoryPointerTypeForPlatform('darwin'), DIRECTORY_POINTER_TYPE_DIR);
});

test('ensureDirectoryPointer writes a lookup pointer whose files are the canonical files', () => {
    const sandbox = makeSandbox();
    try {
        mkdirSync(sandbox.targetPath, { recursive: true });
        const canonicalFile = join(sandbox.targetPath, 'notes.md');
        writeFileSync(canonicalFile, 'canonical body\n');

        const publication = ensureDirectoryPointer(sandbox.pointerPath, sandbox.targetPath);
        assert.equal(publication.action, POINTER_ACTION_CREATED);
        assert.equal(lstatSync(sandbox.pointerPath).isSymbolicLink(), true);
        assert.equal(isDirectoryPointerTo(sandbox.pointerPath, sandbox.targetPath), true);
        assert.equal(
            readFileSync(join(sandbox.pointerPath, 'notes.md'), 'utf8'),
            'canonical body\n',
        );
        assert.equal(
            realpathSync(join(sandbox.pointerPath, 'notes.md')),
            realpathSync(canonicalFile),
        );
    } finally {
        rmSync(sandbox.root, { recursive: true, force: true });
    }
});

test('ensureDirectoryPointer leaves a correct pointer in place', () => {
    const sandbox = makeSandbox();
    try {
        const firstPublication = ensureDirectoryPointer(sandbox.pointerPath, sandbox.targetPath);
        assert.equal(firstPublication.action, POINTER_ACTION_CREATED);
        const secondPublication = ensureDirectoryPointer(sandbox.pointerPath, sandbox.targetPath);
        assert.equal(secondPublication.action, POINTER_ACTION_ALREADY_POINTING);
        assert.equal(isDirectoryPointerTo(sandbox.pointerPath, sandbox.targetPath), true);
    } finally {
        rmSync(sandbox.root, { recursive: true, force: true });
    }
});

test('ensureDirectoryPointer relocates a real lookup directory into the agents home', () => {
    const sandbox = makeSandbox();
    try {
        mkdirSync(sandbox.pointerPath, { recursive: true });
        writeFileSync(join(sandbox.pointerPath, 'personal.md'), 'user skill\n');
        mkdirSync(sandbox.targetPath, { recursive: true });
        writeFileSync(join(sandbox.targetPath, 'shipped.md'), 'package skill\n');

        ensureDirectoryPointer(sandbox.pointerPath, sandbox.targetPath);

        assert.equal(lstatSync(sandbox.pointerPath).isSymbolicLink(), true);
        assert.equal(
            readFileSync(join(sandbox.targetPath, 'personal.md'), 'utf8'),
            'user skill\n',
        );
        assert.equal(
            readFileSync(join(sandbox.pointerPath, 'personal.md'), 'utf8'),
            'user skill\n',
        );
        assert.equal(
            readFileSync(join(sandbox.pointerPath, 'shipped.md'), 'utf8'),
            'package skill\n',
        );
        assert.equal(existsSync(join(sandbox.targetPath, 'personal.md')), true);
    } finally {
        rmSync(sandbox.root, { recursive: true, force: true });
    }
});

test('unlinkDirectoryPointerIfMatch removes only a pointer that aims at the expected target', () => {
    const sandbox = makeSandbox();
    try {
        ensureDirectoryPointer(sandbox.pointerPath, sandbox.targetPath);
        writeFileSync(join(sandbox.targetPath, 'kept.md'), 'kept\n');
        assert.equal(
            unlinkDirectoryPointerIfMatch(sandbox.pointerPath, sandbox.targetPath),
            true,
        );
        assert.equal(existsSync(sandbox.pointerPath), false);
        assert.equal(readFileSync(join(sandbox.targetPath, 'kept.md'), 'utf8'), 'kept\n');
        assert.equal(
            unlinkDirectoryPointerIfMatch(sandbox.pointerPath, sandbox.targetPath),
            false,
        );
    } finally {
        rmSync(sandbox.root, { recursive: true, force: true });
    }
});
