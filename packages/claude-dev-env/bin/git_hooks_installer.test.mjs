import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { mkdtempSync, rmSync, existsSync, readFileSync, mkdirSync, statSync, symlinkSync, writeFileSync } from 'node:fs';
import { execFileSync, spawnSync } from 'node:child_process';
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


test('known git hooks include post-commit for current-head notices', () => {
    assert.deepEqual(KNOWN_GIT_HOOK_NAMES, ['pre-commit', 'pre-push', 'post-commit']);
});


test('writeAllGitHookShims creates the post-commit shim', () => {
    const { temporaryRoot, gitHooksDirectory } = makeTemporaryGitHooksDirectory();
    try {
        writeAllGitHookShims({ gitHooksDirectory });
        assert.equal(existsSync(join(gitHooksDirectory, 'post-commit')), true);
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


test('generated advisory shims keep temporary Git commit and push available after module failure', () => {
    const { temporaryRoot, gitHooksDirectory } = makeTemporaryGitHooksDirectory();
    const repositoryRoot = join(temporaryRoot, 'repository');
    const bareRepositoryRoot = join(temporaryRoot, 'remote.git');
    const targetRemote = 'https://github.com/JonEcho/python-automation.git';
    try {
        writeFileSync(
            join(gitHooksDirectory, 'broken_advisory.py'),
            'def main():\n    raise RuntimeError("advisory failure")\n',
        );
        writeGitHookShim({
            gitHooksDirectory,
            gitNativeHookName: 'pre-commit',
            pythonModuleName: 'broken_advisory',
        });
        writeGitHookShim({
            gitHooksDirectory,
            gitNativeHookName: 'pre-push',
            pythonModuleName: 'broken_advisory',
        });
        mkdirSync(repositoryRoot);
        execFileSync('git', ['init', '--initial-branch=main', '--quiet'], { cwd: repositoryRoot });
        execFileSync('git', ['config', 'user.email', 'test@example.invalid'], { cwd: repositoryRoot });
        execFileSync('git', ['config', 'user.name', 'Verification Test'], { cwd: repositoryRoot });
        execFileSync('git', ['config', 'core.hooksPath', gitHooksDirectory], { cwd: repositoryRoot });
        writeFileSync(join(repositoryRoot, 'README.md'), 'check\n');
        execFileSync('git', ['add', 'README.md'], { cwd: repositoryRoot });

        const commitResult = spawnSync('git', ['commit', '-m', 'initial'], {
            cwd: repositoryRoot,
            encoding: 'utf8',
        });
        assert.equal(commitResult.status, 0);
        assert.match(commitResult.stderr, /advisory hook broken_advisory failed: advisory failure/);

        execFileSync('git', ['init', '--bare', '--quiet', bareRepositoryRoot], { cwd: temporaryRoot });
        execFileSync('git', ['remote', 'add', 'origin', targetRemote], { cwd: repositoryRoot });
        execFileSync('git', ['config', `url.${bareRepositoryRoot}.insteadOf`, targetRemote], {
            cwd: repositoryRoot,
        });
        const pushResult = spawnSync('git', ['push', 'origin', 'main'], {
            cwd: repositoryRoot,
            encoding: 'utf8',
        });
        assert.equal(pushResult.status, 0);
        assert.match(pushResult.stderr, /advisory hook broken_advisory failed: advisory failure/);
    } finally {
        rmSync(temporaryRoot, { recursive: true, force: true });
    }
});


test('generated advisory shim turns a nonzero module return into a success with a warning', () => {
    const { temporaryRoot, gitHooksDirectory } = makeTemporaryGitHooksDirectory();
    try {
        writeFileSync(
            join(gitHooksDirectory, 'nonzero_advisory.py'),
            'def main():\n    return 1\n',
        );
        const shimPath = writeGitHookShim({
            gitHooksDirectory,
            gitNativeHookName: 'pre-commit',
            pythonModuleName: 'nonzero_advisory',
        });
        const shimResult = spawnSync('python', [shimPath], {
            encoding: 'utf8',
        });
        assert.equal(shimResult.status, 0);
        assert.match(shimResult.stderr, /advisory hook nonzero_advisory returned non-zero: 1/);
    } finally {
        rmSync(temporaryRoot, { recursive: true, force: true });
    }
});


function runGeneratedAdvisoryModule(pythonModuleName, moduleSource) {
    const { temporaryRoot, gitHooksDirectory } = makeTemporaryGitHooksDirectory();
    try {
        if (moduleSource !== null) {
            writeFileSync(join(gitHooksDirectory, pythonModuleName + '.py'), moduleSource);
        }
        const shimPath = writeGitHookShim({
            gitHooksDirectory,
            gitNativeHookName: 'pre-commit',
            pythonModuleName,
        });
        return spawnSync('python', [shimPath], {
            encoding: 'utf8',
        });
    } finally {
        rmSync(temporaryRoot, { recursive: true, force: true });
    }
}


test('generated advisory shim reports a missing module and succeeds', () => {
    const shimResult = runGeneratedAdvisoryModule('missing_advisory', null);
    assert.equal(shimResult.status, 0);
    assert.match(shimResult.stderr, /advisory hook missing_advisory failed: No module named/);
});


test('generated advisory shim reports a syntax error and succeeds', () => {
    const shimResult = runGeneratedAdvisoryModule(
        'broken_syntax',
        'def main(:\n    return 1\n',
    );
    assert.equal(shimResult.status, 0);
    assert.match(shimResult.stderr, /advisory hook broken_syntax failed:/);
});


test('generated advisory shim reports ordinary SystemExit and succeeds', () => {
    const shimResult = runGeneratedAdvisoryModule(
        'ordinary_exit',
        'def main():\n    raise SystemExit(1)\n',
    );
    assert.equal(shimResult.status, 0);
    assert.match(shimResult.stderr, /advisory hook ordinary_exit failed: 1/);
});


test('generated advisory shim treats successful SystemExit as silent success', () => {
    for (const [pythonModuleName, moduleSource] of [
        ['zero_exit', 'def main():\n    raise SystemExit(0)\n'],
        ['empty_exit', 'def main():\n    raise SystemExit()\n'],
    ]) {
        const shimResult = runGeneratedAdvisoryModule(pythonModuleName, moduleSource);
        assert.equal(shimResult.status, 0);
        assert.equal(shimResult.stderr, '');
    }
});


test('generated advisory shim preserves cancellation SystemExit 130', () => {
    const shimResult = runGeneratedAdvisoryModule(
        'cancelled_exit',
        'def main():\n    raise SystemExit(130)\n',
    );
    assert.equal(shimResult.status, 130);
    assert.doesNotMatch(shimResult.stderr, /advisory hook cancelled_exit/);
});


test('generated advisory shim preserves KeyboardInterrupt cancellation', () => {
    const shimResult = runGeneratedAdvisoryModule(
        'keyboard_cancel',
        'def main():\n    raise KeyboardInterrupt()\n',
    );
    assert.notEqual(shimResult.status, 0);
    assert.match(shimResult.stderr, /KeyboardInterrupt/);
});
