import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync, mkdirSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { collectPackageSourceConflicts, CONTENT_DIRECTORIES } from './install.mjs';


function createTemporaryGitRepository() {
    const repositoryRoot = mkdtempSync(join(tmpdir(), 'cdev-installer-validation-'));
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
    execFileSync('git', ['commit', '-m', commitMessage], {
        cwd: repositoryRoot,
        stdio: 'ignore',
    });
}


function tryMergeAllowingConflict(repositoryRoot, branchName) {
    try {
        execFileSync('git', ['merge', '--no-edit', branchName], {
            cwd: repositoryRoot,
            stdio: 'ignore',
        });
    } catch {
        return;
    }
}


test('collectPackageSourceConflicts returns empty list when working tree is clean', () => {
    const repositoryRoot = createTemporaryGitRepository();
    try {
        const packageDirectory = join(repositoryRoot, 'packages', 'thing');
        mkdirSync(packageDirectory, { recursive: true });
        writeFileSync(join(packageDirectory, 'README.md'), 'hello\n');
        commitAllChanges(repositoryRoot, 'init');

        const conflicts = collectPackageSourceConflicts(packageDirectory);
        assert.deepEqual(conflicts, []);
    } finally {
        rmSync(repositoryRoot, { recursive: true, force: true });
    }
});


test('collectPackageSourceConflicts surfaces both-modified paths under the package directory', () => {
    const repositoryRoot = createTemporaryGitRepository();
    try {
        const packageDirectory = join(repositoryRoot, 'packages', 'thing');
        mkdirSync(packageDirectory, { recursive: true });
        const conflictedFile = join(packageDirectory, 'shared.txt');
        writeFileSync(conflictedFile, 'base content\n');
        commitAllChanges(repositoryRoot, 'base');

        execFileSync('git', ['checkout', '-b', 'branch-a'], { cwd: repositoryRoot, stdio: 'ignore' });
        writeFileSync(conflictedFile, 'a side\n');
        commitAllChanges(repositoryRoot, 'a');

        execFileSync('git', ['checkout', '-b', 'branch-b', 'main'], { cwd: repositoryRoot, stdio: 'ignore' });
        writeFileSync(conflictedFile, 'b side\n');
        commitAllChanges(repositoryRoot, 'b');

        tryMergeAllowingConflict(repositoryRoot, 'branch-a');

        const conflicts = collectPackageSourceConflicts(packageDirectory);
        assert.equal(conflicts.length, 1);
        assert.equal(conflicts[0].statusCode, 'UU');
        assert.match(conflicts[0].path, /shared\.txt/);
    } finally {
        rmSync(repositoryRoot, { recursive: true, force: true });
    }
});


test('collectPackageSourceConflicts ignores conflicts outside the package directory', () => {
    const repositoryRoot = createTemporaryGitRepository();
    try {
        const packageDirectory = join(repositoryRoot, 'packages', 'thing');
        const otherDirectory = join(repositoryRoot, 'packages', 'other');
        mkdirSync(packageDirectory, { recursive: true });
        mkdirSync(otherDirectory, { recursive: true });
        writeFileSync(join(packageDirectory, 'inside.txt'), 'inside\n');
        const otherFile = join(otherDirectory, 'outside.txt');
        writeFileSync(otherFile, 'base outside\n');
        commitAllChanges(repositoryRoot, 'init');

        execFileSync('git', ['checkout', '-b', 'side'], { cwd: repositoryRoot, stdio: 'ignore' });
        writeFileSync(otherFile, 'side change\n');
        commitAllChanges(repositoryRoot, 'side');

        execFileSync('git', ['checkout', 'main'], { cwd: repositoryRoot, stdio: 'ignore' });
        writeFileSync(otherFile, 'main change\n');
        commitAllChanges(repositoryRoot, 'main');

        tryMergeAllowingConflict(repositoryRoot, 'side');

        const conflicts = collectPackageSourceConflicts(packageDirectory);
        assert.deepEqual(conflicts, []);
    } finally {
        rmSync(repositoryRoot, { recursive: true, force: true });
    }
});


test('collectPackageSourceConflicts returns empty when directory is not inside a git repo', () => {
    const standaloneDirectory = mkdtempSync(join(tmpdir(), 'cdev-installer-no-git-'));
    try {
        const conflicts = collectPackageSourceConflicts(standaloneDirectory);
        assert.deepEqual(conflicts, []);
    } finally {
        rmSync(standaloneDirectory, { recursive: true, force: true });
    }
});


test('CONTENT_DIRECTORIES includes _shared so installer copies _shared/pr-loop/ to ~/.claude/_shared/', () => {
    assert.ok(
        CONTENT_DIRECTORIES.includes('_shared'),
        '_shared must be in CONTENT_DIRECTORIES so the installer copies _shared/pr-loop/ alongside skills/',
    );
});


test('collectPackageSourceConflicts surfaces both-added and deleted-by-them entries', () => {
    const repositoryRoot = createTemporaryGitRepository();
    try {
        const packageDirectory = join(repositoryRoot, 'packages', 'thing');
        mkdirSync(packageDirectory, { recursive: true });
        writeFileSync(join(packageDirectory, 'shared.txt'), 'base\n');
        writeFileSync(join(packageDirectory, 'about_to_disappear.txt'), 'will be removed\n');
        commitAllChanges(repositoryRoot, 'base');

        execFileSync('git', ['checkout', '-b', 'theirs'], { cwd: repositoryRoot, stdio: 'ignore' });
        rmSync(join(packageDirectory, 'about_to_disappear.txt'));
        writeFileSync(join(packageDirectory, 'fresh.txt'), 'theirs version\n');
        commitAllChanges(repositoryRoot, 'theirs');

        execFileSync('git', ['checkout', '-b', 'ours', 'main'], { cwd: repositoryRoot, stdio: 'ignore' });
        writeFileSync(join(packageDirectory, 'about_to_disappear.txt'), 'ours edit\n');
        writeFileSync(join(packageDirectory, 'fresh.txt'), 'ours version\n');
        commitAllChanges(repositoryRoot, 'ours');

        tryMergeAllowingConflict(repositoryRoot, 'theirs');

        const conflicts = collectPackageSourceConflicts(packageDirectory);
        const allStatusCodes = new Set(conflicts.map(conflictEntry => conflictEntry.statusCode));
        assert.ok(allStatusCodes.has('UD'), `expected UD in ${[...allStatusCodes].join(',')}`);
        assert.ok(allStatusCodes.has('AA'), `expected AA in ${[...allStatusCodes].join(',')}`);
    } finally {
        rmSync(repositoryRoot, { recursive: true, force: true });
    }
});
