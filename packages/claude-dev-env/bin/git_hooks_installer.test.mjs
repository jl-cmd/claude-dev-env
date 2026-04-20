import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { mkdtempSync, rmSync, existsSync, readFileSync, mkdirSync, statSync, symlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import {
    writeGitHookShim,
    writeAllGitHookShims,
    configureGlobalGitHooksPath,
    KNOWN_GIT_HOOK_NAMES,
} from './git_hooks_installer.mjs';


function makeTemporaryGitHooksDirectory() {
    const temporaryRoot = mkdtempSync(join(tmpdir(), 'cdev-git-hooks-test-'));
    const gitHooksDirectory = join(temporaryRoot, 'git-hooks');
    mkdirSync(gitHooksDirectory, { recursive: true });
    return { temporaryRoot, gitHooksDirectory };
}


test('writeGitHookShim creates a file with the git-native name and imports the matching module', () => {
    const { temporaryRoot, gitHooksDirectory } = makeTemporaryGitHooksDirectory();
    try {
        const shimPath = writeGitHookShim({
            gitHooksDirectory,
            gitNativeHookName: 'pre-commit',
            pythonModuleName: 'pre_commit',
        });
        assert.equal(shimPath, join(gitHooksDirectory, 'pre-commit'));
        assert.ok(existsSync(shimPath));
        const shimContent = readFileSync(shimPath, 'utf8');
        assert.ok(shimContent.startsWith('#!/usr/bin/env python3\n'));
        assert.match(shimContent, /import\s+pre_commit/);
        assert.match(shimContent, /pre_commit\.main\(\)/);
    } finally {
        rmSync(temporaryRoot, { recursive: true, force: true });
    }
});


test('writeAllGitHookShims creates one shim per known hook name', () => {
    const { temporaryRoot, gitHooksDirectory } = makeTemporaryGitHooksDirectory();
    try {
        const createdShimPaths = writeAllGitHookShims({ gitHooksDirectory });
        assert.equal(createdShimPaths.length, KNOWN_GIT_HOOK_NAMES.length);
        for (const gitNativeHookName of KNOWN_GIT_HOOK_NAMES) {
            const expectedShimPath = join(gitHooksDirectory, gitNativeHookName);
            assert.ok(
                existsSync(expectedShimPath),
                `missing shim at ${expectedShimPath}`,
            );
        }
    } finally {
        rmSync(temporaryRoot, { recursive: true, force: true });
    }
});


test('configureGlobalGitHooksPath sets the path when nothing is currently configured', () => {
    const commandsRun = [];
    const gitConfigReaderReturningEmpty = () => '';
    const gitConfigWriter = (value) => {
        commandsRun.push(['set', value]);
    };

    const result = configureGlobalGitHooksPath({
        targetGitHooksDirectory: '/home/example/.claude/hooks/git-hooks',
        readCurrentHooksPath: gitConfigReaderReturningEmpty,
        writeHooksPath: gitConfigWriter,
    });

    assert.equal(result.action, 'set');
    assert.deepEqual(commandsRun, [['set', '/home/example/.claude/hooks/git-hooks']]);
});


test('configureGlobalGitHooksPath reports already-set when the current value matches the target', () => {
    const commandsRun = [];
    const gitConfigReaderReturningOurPath = () => '/home/example/.claude/hooks/git-hooks';
    const gitConfigWriter = (value) => {
        commandsRun.push(['set', value]);
    };

    const result = configureGlobalGitHooksPath({
        targetGitHooksDirectory: '/home/example/.claude/hooks/git-hooks',
        readCurrentHooksPath: gitConfigReaderReturningOurPath,
        writeHooksPath: gitConfigWriter,
    });

    assert.equal(result.action, 'already-set');
    assert.deepEqual(commandsRun, []);
});


test('configureGlobalGitHooksPath skips and reports reason when a foreign path is already configured', () => {
    const commandsRun = [];
    const gitConfigReaderReturningHuskyPath = () => '/home/example/project/.husky';
    const gitConfigWriter = (value) => {
        commandsRun.push(['set', value]);
    };

    const result = configureGlobalGitHooksPath({
        targetGitHooksDirectory: '/home/example/.claude/hooks/git-hooks',
        readCurrentHooksPath: gitConfigReaderReturningHuskyPath,
        writeHooksPath: gitConfigWriter,
    });

    assert.equal(result.action, 'skip');
    assert.match(result.reason, /\.husky/);
    assert.deepEqual(commandsRun, []);
});


test('configureGlobalGitHooksPath normalizes trailing whitespace before comparing current to target', () => {
    const gitConfigReaderReturningOurPathWithNewline = () => '/home/example/.claude/hooks/git-hooks\n';
    const gitConfigWriter = () => {};

    const result = configureGlobalGitHooksPath({
        targetGitHooksDirectory: '/home/example/.claude/hooks/git-hooks',
        readCurrentHooksPath: gitConfigReaderReturningOurPathWithNewline,
        writeHooksPath: gitConfigWriter,
    });

    assert.equal(result.action, 'already-set');
});


test('configureGlobalGitHooksPath detects already-set when target has Windows backslashes and stored value has forward slashes', () => {
    const commandsRun = [];
    const gitConfigReaderReturningForwardSlashPath = () => 'C:/Users/example/.claude/hooks/git-hooks';
    const gitConfigWriter = (value) => {
        commandsRun.push(value);
    };

    const result = configureGlobalGitHooksPath({
        targetGitHooksDirectory: 'C:\\Users\\example\\.claude\\hooks\\git-hooks',
        readCurrentHooksPath: gitConfigReaderReturningForwardSlashPath,
        writeHooksPath: gitConfigWriter,
    });

    assert.equal(result.action, 'already-set');
    assert.deepEqual(commandsRun, []);
});


test('configureGlobalGitHooksPath writes forward-slash path when setting on Windows', () => {
    const writtenPaths = [];
    const gitConfigReaderReturningEmpty = () => '';
    const gitConfigWriter = (value) => {
        writtenPaths.push(value);
    };

    configureGlobalGitHooksPath({
        targetGitHooksDirectory: 'C:\\Users\\example\\.claude\\hooks\\git-hooks',
        readCurrentHooksPath: gitConfigReaderReturningEmpty,
        writeHooksPath: gitConfigWriter,
    });

    assert.deepEqual(writtenPaths, ['C:/Users/example/.claude/hooks/git-hooks']);
});


test('writeGitHookShim output is executable on POSIX (mode includes user-execute bit)', () => {
    if (process.platform === 'win32') {
        return;
    }
    const { temporaryRoot, gitHooksDirectory } = makeTemporaryGitHooksDirectory();
    try {
        const shimPath = writeGitHookShim({
            gitHooksDirectory,
            gitNativeHookName: 'pre-commit',
            pythonModuleName: 'pre_commit',
        });
        const stats = statSync(shimPath);
        const userExecuteBit = 0o100;
        assert.ok((stats.mode & userExecuteBit) !== 0, 'shim missing user-execute bit');
    } finally {
        rmSync(temporaryRoot, { recursive: true, force: true });
    }
});


test('writeGitHookShim rejects hooks directory that is a symlink (loopP5c-5)', () => {
    if (process.platform === 'win32') {
        return;
    }
    const temporaryRoot = mkdtempSync(join(tmpdir(), 'cdev-git-hooks-test-'));
    try {
        const realDirectory = join(temporaryRoot, 'real-hooks');
        const symlinkPath = join(temporaryRoot, 'symlink-hooks');
        mkdirSync(realDirectory, { recursive: true });
        symlinkSync(realDirectory, symlinkPath);
        assert.throws(
            () => writeGitHookShim({
                gitHooksDirectory: symlinkPath,
                gitNativeHookName: 'pre-commit',
                pythonModuleName: 'pre_commit',
            }),
            (err) => err.message.includes('symlink'),
        );
    } finally {
        rmSync(temporaryRoot, { recursive: true, force: true });
    }
});


