import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import {
    mkdirSync,
    mkdtempSync,
    readFileSync,
    rmSync,
    statSync,
    utimesSync,
    writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
    ALL_EXCLUDED_IMAGE_EXTENSIONS,
    PSTACK_VENDOR_MANIFEST_RELATIVE_PATH,
    applyPstackVendorPlan,
    buildPstackSyncRecord,
    buildPstackVendorPlan,
    repositoryRootFor,
} from '../scripts/sync_pstack_vendor.mjs';

function writeTree(treeRoot, allFilesByRelativePath) {
    for (const [eachRelativePath, eachText] of Object.entries(allFilesByRelativePath)) {
        const filePath = join(treeRoot, eachRelativePath);
        mkdirSync(dirname(filePath), { recursive: true });
        writeFileSync(filePath, eachText);
    }
    return treeRoot;
}

function withTemporaryRoots(runAssertions) {
    const workingDirectory = mkdtempSync(join(tmpdir(), 'cdev-pstack-sync-'));
    try {
        const upstreamRoot = join(workingDirectory, 'upstream', 'pstack');
        const vendorParentDirectory = join(workingDirectory, 'vendor');
        const vendorRoot = join(vendorParentDirectory, 'pstack');
        mkdirSync(upstreamRoot, { recursive: true });
        mkdirSync(vendorRoot, { recursive: true });
        runAssertions({ upstreamRoot, vendorRoot, vendorParentDirectory });
    } finally {
        rmSync(workingDirectory, { recursive: true, force: true });
    }
}

test('the excluded image extensions are the seven this repository refuses to track', () => {
    assert.deepEqual(ALL_EXCLUDED_IMAGE_EXTENSIONS, [
        '.png',
        '.jpg',
        '.jpeg',
        '.gif',
        '.webp',
        '.svg',
        '.ico',
    ]);
});

test('an empty vendor root marks every text file write and every image skip', () => {
    withTemporaryRoots(({ upstreamRoot, vendorRoot }) => {
        writeTree(upstreamRoot, {
            'README.md': 'upstream readme\n',
            'assets/logo.png': 'binary\n',
            'docs/guide/images/router.jpg': 'binary\n',
            'skills/how/SKILL.md': 'how\n',
        });

        const plan = buildPstackVendorPlan({ upstreamRoot, vendorRoot });

        assert.deepEqual(plan.entries, [
            { relativePath: 'README.md', action: 'write' },
            { relativePath: 'assets/logo.png', action: 'skip' },
            { relativePath: 'docs/guide/images/router.jpg', action: 'skip' },
            { relativePath: 'skills/how/SKILL.md', action: 'write' },
        ]);
    });
});

test('applying that plan copies the text files and leaves the images out', () => {
    withTemporaryRoots(({ upstreamRoot, vendorRoot }) => {
        writeTree(upstreamRoot, {
            'README.md': 'upstream readme\n',
            'assets/logo.png': 'binary\n',
        });

        const counts = applyPstackVendorPlan(
            buildPstackVendorPlan({ upstreamRoot, vendorRoot }),
            { upstreamRoot, vendorRoot },
        );

        assert.deepEqual(counts, {
            writtenCount: 1,
            removedCount: 0,
            skippedCount: 1,
            unchangedCount: 0,
        });
        assert.equal(readFileSync(join(vendorRoot, 'README.md'), 'utf8'), 'upstream readme\n');
        assert.equal(statSync(join(vendorRoot, 'assets', 'logo.png'), { throwIfNoEntry: false }), undefined);
    });
});

test('a vendored file upstream no longer carries is marked remove and is deleted', () => {
    withTemporaryRoots(({ upstreamRoot, vendorRoot }) => {
        writeTree(upstreamRoot, { 'README.md': 'same\n' });
        writeTree(vendorRoot, { 'README.md': 'same\n', 'docs/dropped.md': 'gone next run\n' });

        const plan = buildPstackVendorPlan({ upstreamRoot, vendorRoot });
        const counts = applyPstackVendorPlan(plan, { upstreamRoot, vendorRoot });

        assert.deepEqual(plan.entries, [
            { relativePath: 'README.md', action: 'unchanged' },
            { relativePath: 'docs/dropped.md', action: 'remove' },
        ]);
        assert.equal(counts.removedCount, 1);
        assert.equal(statSync(join(vendorRoot, 'docs', 'dropped.md'), { throwIfNoEntry: false }), undefined);
    });
});

test('a byte-identical file is unchanged and keeps its modification time', () => {
    withTemporaryRoots(({ upstreamRoot, vendorRoot }) => {
        writeTree(upstreamRoot, { 'README.md': 'same bytes\n' });
        writeTree(vendorRoot, { 'README.md': 'same bytes\n' });
        const vendorFilePath = join(vendorRoot, 'README.md');
        const markerSeconds = 1000000000;
        utimesSync(vendorFilePath, markerSeconds, markerSeconds);

        const plan = buildPstackVendorPlan({ upstreamRoot, vendorRoot });
        applyPstackVendorPlan(plan, { upstreamRoot, vendorRoot });

        assert.deepEqual(plan.entries, [{ relativePath: 'README.md', action: 'unchanged' }]);
        assert.equal(Math.round(statSync(vendorFilePath).mtimeMs / 1000), markerSeconds);
    });
});

test('a second plan over the applied tree asks for no write and no removal', () => {
    withTemporaryRoots(({ upstreamRoot, vendorRoot }) => {
        writeTree(upstreamRoot, {
            'README.md': 'upstream readme\n',
            'assets/logo.png': 'binary\n',
            'skills/how/SKILL.md': 'how\n',
        });
        writeTree(vendorRoot, { 'docs/dropped.md': 'gone next run\n' });
        applyPstackVendorPlan(
            buildPstackVendorPlan({ upstreamRoot, vendorRoot }),
            { upstreamRoot, vendorRoot },
        );

        const secondPlan = buildPstackVendorPlan({ upstreamRoot, vendorRoot });

        assert.deepEqual(secondPlan.entries, [
            { relativePath: 'README.md', action: 'unchanged' },
            { relativePath: 'assets/logo.png', action: 'skip' },
            { relativePath: 'skills/how/SKILL.md', action: 'unchanged' },
        ]);
    });
});

test('the sync record carries the vendored manifest version and the sorted skipped paths', () => {
    withTemporaryRoots(({ upstreamRoot, vendorRoot }) => {
        writeTree(upstreamRoot, {
            [PSTACK_VENDOR_MANIFEST_RELATIVE_PATH]: JSON.stringify({ version: '0.15.0' }),
            'docs/guide/images/router.jpg': 'binary\n',
            'assets/logo.png': 'binary\n',
        });
        const plan = buildPstackVendorPlan({ upstreamRoot, vendorRoot });
        applyPstackVendorPlan(plan, { upstreamRoot, vendorRoot });

        const record = buildPstackSyncRecord({ vendorRoot, plan, commit: 'abc123' });

        assert.deepEqual(record, {
            sourceUrl: 'https://github.com/cursor/plugins',
            subdirectory: 'pstack',
            commit: 'abc123',
            version: '0.15.0',
            skippedPaths: ['assets/logo.png', 'docs/guide/images/router.jpg'],
        });
    });
});

test('the repository root is three directories above the scripts folder', () => {
    const modulePath = join(
        dirname(dirname(fileURLToPath(import.meta.url))),
        'scripts',
        'sync_pstack_vendor.mjs',
    );

    const repositoryRoot = repositoryRootFor(modulePath);

    assert.equal(
        readFileSync(
            join(repositoryRoot, 'vendor', 'pstack', PSTACK_VENDOR_MANIFEST_RELATIVE_PATH),
            'utf8',
        ).includes('"name": "pstack"'),
        true,
    );
});
