import test from 'node:test';
import assert from 'node:assert/strict';

import { resolveDriverPaths } from './driver.mjs';

test('resolveDriverPaths should reach the repository root from the skill scripts directory', () => {
    const paths = resolveDriverPaths('C:/workspace/.cursor/skills/verify-claude-dev-env/scripts');

    assert.equal(paths.repositoryRoot.replaceAll('\\', '/'), 'C:/workspace');
});

test('resolveDriverPaths should point the package root at the published package', () => {
    const paths = resolveDriverPaths('C:/workspace/.cursor/skills/verify-claude-dev-env/scripts');

    assert.equal(
        paths.packageRoot.replaceAll('\\', '/'),
        'C:/workspace/packages/claude-dev-env',
    );
});

test('resolveDriverPaths should name the installer entry point inside the package', () => {
    const paths = resolveDriverPaths('C:/workspace/.cursor/skills/verify-claude-dev-env/scripts');

    assert.equal(
        paths.installEntry.replaceAll('\\', '/'),
        'C:/workspace/packages/claude-dev-env/bin/install.mjs',
    );
});
