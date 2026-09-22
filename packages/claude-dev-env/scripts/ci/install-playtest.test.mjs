import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

import { parseArguments, readEnvelope, selectHookCommand } from './install-playtest.mjs';
import { SANDBOX_GIT_CONFIG_BODY, SANDBOX_GIT_CONFIG_NAME } from './scratch-home-install.mjs';

const CI_DIRECTORY = dirname(fileURLToPath(import.meta.url));
const DRIVER_PATH = join(CI_DIRECTORY, 'install-playtest.mjs');
const DRIVER_TIMEOUT_MILLISECONDS = 300_000;
const SILENT_HOOK_SOURCE = '#!/usr/bin/env python3\nprint("")\n';

function runDriver(driverArguments) {
    return spawnSync(process.execPath, [DRIVER_PATH, ...driverArguments], {
        encoding: 'utf8',
        timeout: DRIVER_TIMEOUT_MILLISECONDS,
    });
}

test('the driver reads an envelope from every stage of a fresh install, and reports red when one stage writes none', () => {
    const scratchHome = mkdtempSync(join(tmpdir(), 'cde-playtest-home-'));
    const evidenceDirectory = mkdtempSync(join(tmpdir(), 'cde-playtest-evidence-'));
    try {
        const greenRun = runDriver(['--home', scratchHome, '--evidence', evidenceDirectory]);
        assert.equal(greenRun.status, 0, `${greenRun.stdout}\n${greenRun.stderr}`);
        assert.match(greenRun.stdout, /\[PASS\] playtest install .* sha256=[0-9a-f]{64}/);
        assert.match(greenRun.stdout, /\[PASS\] playtest session_start_hook .* sha256=[0-9a-f]{64}/);
        assert.match(greenRun.stdout, /\[PASS\] playtest blocking_hook .* sha256=[0-9a-f]{64}/);
        assert.ok(
            readFileSync(join(scratchHome, SANDBOX_GIT_CONFIG_NAME), 'utf8').startsWith(SANDBOX_GIT_CONFIG_BODY),
        );

        writeFileSync(
            join(scratchHome, '.claude', 'hooks', 'session', 'working_style_prompt.py'),
            SILENT_HOOK_SOURCE,
        );
        const redRun = runDriver(['--home', scratchHome, '--evidence', evidenceDirectory, '--skip-install']);
        assert.equal(redRun.status, 1, `${redRun.stdout}\n${redRun.stderr}`);
        assert.match(redRun.stdout, /\[FAIL\] playtest session_start_hook The hook wrote no SessionStart envelope/);
        assert.doesNotMatch(redRun.stdout, /\[PASS\] playtest session_start_hook/);
    } finally {
        rmSync(scratchHome, { recursive: true, force: true });
        rmSync(evidenceDirectory, { recursive: true, force: true });
    }
});

test('parseArguments reads the home, evidence and skip-install options', () => {
    assert.deepEqual(parseArguments([]), { homePath: null, evidencePath: null, shouldSkipInstall: false });
    assert.deepEqual(
        parseArguments(['--home', '/scratch/home', '--evidence', '/scratch/evidence', '--skip-install']),
        { homePath: '/scratch/home', evidencePath: '/scratch/evidence', shouldSkipInstall: true },
    );
});

test('selectHookCommand names the hook the installed roster declares', () => {
    const allCommands = [
        { matcher: '', command: 'python3 /home/.claude/hooks/session/task_tool_prompt.py' },
        { matcher: '', command: 'python3 /home/.claude/hooks/session/working_style_prompt.py' },
    ];
    assert.equal(
        selectHookCommand(allCommands, 'working_style_prompt.py'),
        'python3 /home/.claude/hooks/session/working_style_prompt.py',
    );
    assert.throws(
        () => selectHookCommand(allCommands, 'absent_hook.py'),
        /declares no absent_hook\.py/,
    );
});

test('readEnvelope refuses output that names another event or no envelope at all', () => {
    const sessionStartOutput = JSON.stringify({
        hookSpecificOutput: { hookEventName: 'SessionStart', additionalContext: 'guidance' },
    });
    assert.equal(readEnvelope(sessionStartOutput, 'SessionStart').additionalContext, 'guidance');
    assert.throws(() => readEnvelope('   ', 'SessionStart'), /wrote no SessionStart envelope/);
    assert.throws(
        () => readEnvelope(JSON.stringify({ hookSpecificOutput: { hookEventName: 'PreToolUse' } }), 'SessionStart'),
        /names PreToolUse rather than SessionStart/,
    );
});
