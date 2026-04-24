import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { mkdtempSync, rmSync, readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { installMypyIniForClaudeHooks } from './install_mypy_ini.mjs';


function makeTemporaryHomeWithClaudeHooks() {
    const temporaryHomeDirectory = mkdtempSync(join(tmpdir(), 'cdev-mypy-ini-test-'));
    const claudeHooksDirectory = join(temporaryHomeDirectory, '.claude', 'hooks');
    mkdirSync(claudeHooksDirectory, { recursive: true });
    return { temporaryHomeDirectory, claudeHooksDirectory };
}


test('installMypyIniForClaudeHooks creates a new .mypy.ini when none exists', () => {
    const { temporaryHomeDirectory, claudeHooksDirectory } = makeTemporaryHomeWithClaudeHooks();
    try {
        const installResult = installMypyIniForClaudeHooks({
            homeDirectory: temporaryHomeDirectory,
            claudeHooksDirectory,
        });

        assert.equal(installResult.action, 'created');
        assert.equal(installResult.path, join(temporaryHomeDirectory, '.mypy.ini'));

        const writtenContent = readFileSync(installResult.path, 'utf8');
        assert.match(writtenContent, /^\[mypy\]$/m);
        assert.match(writtenContent, /^mypy_path = /m);

        const claudeHooksAsForwardSlashes = claudeHooksDirectory.replace(/\\/g, '/');
        assert.ok(
            writtenContent.includes(claudeHooksAsForwardSlashes),
            `expected content to include ${claudeHooksAsForwardSlashes}`,
        );
    } finally {
        rmSync(temporaryHomeDirectory, { recursive: true, force: true });
    }
});


test('installMypyIniForClaudeHooks leaves existing file untouched when already configured', () => {
    const { temporaryHomeDirectory, claudeHooksDirectory } = makeTemporaryHomeWithClaudeHooks();
    try {
        const claudeHooksAsForwardSlashes = claudeHooksDirectory.replace(/\\/g, '/');
        const preExistingContent = `[mypy]\nmypy_path = ${claudeHooksAsForwardSlashes}\nstrict = True\n`;
        const mypyIniPath = join(temporaryHomeDirectory, '.mypy.ini');
        writeFileSync(mypyIniPath, preExistingContent);

        const installResult = installMypyIniForClaudeHooks({
            homeDirectory: temporaryHomeDirectory,
            claudeHooksDirectory,
        });

        assert.equal(installResult.action, 'already-configured');
        assert.equal(installResult.path, mypyIniPath);

        const contentAfterInstall = readFileSync(mypyIniPath, 'utf8');
        assert.equal(contentAfterInstall, preExistingContent);
    } finally {
        rmSync(temporaryHomeDirectory, { recursive: true, force: true });
    }
});


test('installMypyIniForClaudeHooks treats an existing mypy_path that is a strict prefix of the expected path as not configured', () => {
    const { temporaryHomeDirectory, claudeHooksDirectory } = makeTemporaryHomeWithClaudeHooks();
    try {
        const claudeHooksAsForwardSlashes = claudeHooksDirectory.replace(/\\/g, '/');
        const prefixCollidingPath = `${claudeHooksAsForwardSlashes}-old`;
        const preExistingContent = `[mypy]\nmypy_path = ${prefixCollidingPath}\nstrict = True\n`;
        const mypyIniPath = join(temporaryHomeDirectory, '.mypy.ini');
        writeFileSync(mypyIniPath, preExistingContent);

        const installResult = installMypyIniForClaudeHooks({
            homeDirectory: temporaryHomeDirectory,
            claudeHooksDirectory,
        });

        assert.equal(installResult.action, 'skipped-existing');
        assert.equal(installResult.path, mypyIniPath);
        assert.equal(
            installResult.expectedLine,
            `mypy_path = ${claudeHooksAsForwardSlashes}`,
        );

        const contentAfterInstall = readFileSync(mypyIniPath, 'utf8');
        assert.equal(contentAfterInstall, preExistingContent);
    } finally {
        rmSync(temporaryHomeDirectory, { recursive: true, force: true });
    }
});


test('installMypyIniForClaudeHooks does not overwrite existing .mypy.ini that lacks the expected mypy_path', () => {
    const { temporaryHomeDirectory, claudeHooksDirectory } = makeTemporaryHomeWithClaudeHooks();
    try {
        const preExistingContent = `[mypy]\nmypy_path = /some/other/project\nstrict = True\n`;
        const mypyIniPath = join(temporaryHomeDirectory, '.mypy.ini');
        writeFileSync(mypyIniPath, preExistingContent);

        const installResult = installMypyIniForClaudeHooks({
            homeDirectory: temporaryHomeDirectory,
            claudeHooksDirectory,
        });

        assert.equal(installResult.action, 'skipped-existing');
        assert.equal(installResult.path, mypyIniPath);
        assert.ok(
            installResult.expectedLine.includes(claudeHooksDirectory.replace(/\\/g, '/')),
            `expected expectedLine to include ${claudeHooksDirectory.replace(/\\/g, '/')}`,
        );

        const contentAfterInstall = readFileSync(mypyIniPath, 'utf8');
        assert.equal(contentAfterInstall, preExistingContent);
    } finally {
        rmSync(temporaryHomeDirectory, { recursive: true, force: true });
    }
});
