import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { evaluateUntrackedFileGate } from './clean_pack_artifacts.mjs';

const PACKAGE_MANIFEST_NAME = 'package.json';


function createTemporaryGitRepository(directoryNamePrefix) {
    const repositoryRoot = mkdtempSync(join(tmpdir(), directoryNamePrefix));
    const gitOptions = { cwd: repositoryRoot, stdio: 'ignore' };
    execFileSync('git', ['init', '--initial-branch=main'], gitOptions);
    execFileSync('git', ['config', 'user.email', 'test@example.com'], gitOptions);
    execFileSync('git', ['config', 'user.name', 'Test'], gitOptions);
    execFileSync('git', ['config', 'commit.gpgsign', 'false'], gitOptions);
    execFileSync('git', ['config', 'core.autocrlf', 'false'], gitOptions);
    return repositoryRoot;
}


function commitAllChanges(repositoryRoot, commitMessage) {
    execFileSync('git', ['add', '.'], { cwd: repositoryRoot, stdio: 'ignore' });
    execFileSync('git', ['commit', '-m', commitMessage], { cwd: repositoryRoot, stdio: 'ignore' });
}


function writePackageManifestWithFilesField(packageRoot, filesFieldEntries) {
    const manifest = { name: 'fixture-package', version: '0.0.0', files: filesFieldEntries };
    writeFileSync(join(packageRoot, PACKAGE_MANIFEST_NAME), JSON.stringify(manifest, null, 2));
}


test('evaluateUntrackedFileGate flags an untracked file inside a files-listed directory', () => {
    const packageRoot = createTemporaryGitRepository('cdev-pack-untracked-inside-');
    try {
        writePackageManifestWithFilesField(packageRoot, ['hooks/']);
        mkdirSync(join(packageRoot, 'hooks', 'validation'), { recursive: true });
        writeFileSync(join(packageRoot, 'hooks', 'validation', 'tracked.py'), 'tracked\n');
        commitAllChanges(packageRoot, 'init');

        writeFileSync(join(packageRoot, 'hooks', 'validation', 'eval_5_export.txt'), 'leaked transcript\n');

        const gateResult = evaluateUntrackedFileGate(packageRoot);

        assert.equal(gateResult.exitCode, 1);
        assert.ok(
            gateResult.messageLines.some((eachLine) => eachLine.includes('hooks/validation/eval_5_export.txt')),
        );
    } finally {
        rmSync(packageRoot, { recursive: true, force: true });
    }
});


test('evaluateUntrackedFileGate ignores an untracked file outside every files-listed directory', () => {
    const packageRoot = createTemporaryGitRepository('cdev-pack-untracked-outside-');
    try {
        writePackageManifestWithFilesField(packageRoot, ['hooks/']);
        mkdirSync(join(packageRoot, 'hooks'), { recursive: true });
        writeFileSync(join(packageRoot, 'hooks', 'tracked.py'), 'tracked\n');
        commitAllChanges(packageRoot, 'init');

        mkdirSync(join(packageRoot, 'notes'), { recursive: true });
        writeFileSync(join(packageRoot, 'notes', 'scratch.txt'), 'not shipped\n');

        const gateResult = evaluateUntrackedFileGate(packageRoot);

        assert.equal(gateResult.exitCode, 0);
    } finally {
        rmSync(packageRoot, { recursive: true, force: true });
    }
});


test('evaluateUntrackedFileGate flags a git-ignored file inside a files-listed directory', () => {
    const packageRoot = createTemporaryGitRepository('cdev-pack-ignored-inside-');
    try {
        writeFileSync(join(packageRoot, '.gitignore'), '*.txt\n');
        writePackageManifestWithFilesField(packageRoot, ['hooks/']);
        mkdirSync(join(packageRoot, 'hooks', 'validation'), { recursive: true });
        writeFileSync(join(packageRoot, 'hooks', 'validation', 'tracked.py'), 'tracked\n');
        commitAllChanges(packageRoot, 'init');

        writeFileSync(join(packageRoot, 'hooks', 'validation', 'eval_6_export.txt'), 'leaked transcript\n');

        const gateResult = evaluateUntrackedFileGate(packageRoot);

        assert.equal(gateResult.exitCode, 1);
        assert.ok(
            gateResult.messageLines.some((eachLine) => eachLine.includes('hooks/validation/eval_6_export.txt')),
        );
    } finally {
        rmSync(packageRoot, { recursive: true, force: true });
    }
});


test('evaluateUntrackedFileGate flags an untracked file matching an exact filename entry', () => {
    const packageRoot = createTemporaryGitRepository('cdev-pack-exact-filename-');
    try {
        writePackageManifestWithFilesField(packageRoot, ['hooks/', 'CLAUDE.md']);
        mkdirSync(join(packageRoot, 'hooks'), { recursive: true });
        writeFileSync(join(packageRoot, 'hooks', 'tracked.py'), 'tracked\n');
        commitAllChanges(packageRoot, 'init');

        writeFileSync(join(packageRoot, 'CLAUDE.md'), 'untracked instructions\n');

        const gateResult = evaluateUntrackedFileGate(packageRoot);

        assert.equal(gateResult.exitCode, 1);
        assert.ok(gateResult.messageLines.some((eachLine) => eachLine.includes('CLAUDE.md')));
    } finally {
        rmSync(packageRoot, { recursive: true, force: true });
    }
});


test('evaluateUntrackedFileGate exits zero on a clean tree', () => {
    const packageRoot = createTemporaryGitRepository('cdev-pack-clean-');
    try {
        writePackageManifestWithFilesField(packageRoot, ['hooks/']);
        mkdirSync(join(packageRoot, 'hooks'), { recursive: true });
        writeFileSync(join(packageRoot, 'hooks', 'tracked.py'), 'tracked\n');
        commitAllChanges(packageRoot, 'init');

        const gateResult = evaluateUntrackedFileGate(packageRoot);

        assert.equal(gateResult.exitCode, 0);
        assert.equal(gateResult.messageLines.length, 1);
    } finally {
        rmSync(packageRoot, { recursive: true, force: true });
    }
});


test('evaluateUntrackedFileGate exits zero and prints the skip line for a non-git directory', () => {
    const standaloneDirectory = mkdtempSync(join(tmpdir(), 'cdev-pack-no-git-'));
    try {
        const gateResult = evaluateUntrackedFileGate(standaloneDirectory);

        assert.equal(gateResult.exitCode, 0);
        assert.ok(gateResult.messageLines[0].includes('skipping'));
    } finally {
        rmSync(standaloneDirectory, { recursive: true, force: true });
    }
});
