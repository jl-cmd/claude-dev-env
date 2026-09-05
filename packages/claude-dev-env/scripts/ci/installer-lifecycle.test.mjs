import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const CI_DIRECTORY = dirname(fileURLToPath(import.meta.url));
const DRIVER_PATH = join(CI_DIRECTORY, 'installer-lifecycle.mjs');
const DRIVER_TIMEOUT_MILLISECONDS = 60_000;

 test('the installer lifecycle driver completes in an isolated home', () => {
    const lifecycleProcess = spawnSync(process.execPath, [DRIVER_PATH], {
        encoding: 'utf8',
        timeout: DRIVER_TIMEOUT_MILLISECONDS,
    });
    assert.equal(lifecycleProcess.status, 0, `${lifecycleProcess.stdout}\n${lifecycleProcess.stderr}`);
    assert.match(lifecycleProcess.stdout, /ALL CHECKS PASSED/);
    assert.match(lifecycleProcess.stdout, /Sandbox removed:/);
});

test('the Windows adapter invokes the CI-owned lifecycle driver', () => {
    const adapterSource = readFileSync(join(CI_DIRECTORY, 'windows-installer-lifecycle.ps1'), 'utf8');
    assert.match(adapterSource, /\$driverPath = Join-Path \$PSScriptRoot 'installer-lifecycle\.mjs'/);
    assert.doesNotMatch(adapterSource, /skills\\run-claude-dev-env/);
});
