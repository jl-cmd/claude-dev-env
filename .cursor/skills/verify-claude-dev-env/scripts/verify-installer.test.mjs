import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import {
    buildDoctorRecord,
    buildTranscriptRecord,
    buildVerificationPaths,
    parseCommand,
    sanitizeTranscript,
} from './verify-installer.mjs';
import {
    DOCTOR_COMMAND,
    DRIVER_FAILURE_EXIT_STATUS,
    RUN_COMMAND,
    SUCCESS_EXIT_STATUS,
} from './verify_installer_constants/constants.mjs';

test('buildVerificationPaths keeps the driver and evidence paths inside the repository', () => {
    const paths = buildVerificationPaths('C:/workspace');
    assert.equal(
        paths.driverPath.replaceAll('\\', '/'),
        'C:/workspace/packages/claude-dev-env/.agents/skills/run-claude-dev-env/driver.mjs',
    );
    assert.equal(
        paths.transcriptPath.replaceAll('\\', '/'),
        'C:/workspace/.audit/hook-linter-conversion/evidence/installer-transcript.json',
    );
});

test('sanitizeTranscript removes repository-specific absolute paths', () => {
    const paths = buildVerificationPaths('C:/workspace');
    const sanitizedText = sanitizeTranscript(
        'Sandbox C:/workspace/.audit and C:/workspace/packages/claude-dev-env',
        paths,
    );
    assert.equal(sanitizedText, 'Sandbox <repository-root>/.audit and <repository-root>/packages/claude-dev-env');
});

test('sanitizeTranscript folds Windows path case', () => {
    const paths = buildVerificationPaths('C:/workspace');
    const sanitizedText = sanitizeTranscript('Sandbox C:/WORKSPACE/.audit', paths);
    const expectedText = process.platform === 'win32'
        ? 'Sandbox <repository-root>/.audit'
        : 'Sandbox C:/WORKSPACE/.audit';
    assert.equal(sanitizedText, expectedText);
});

test('buildTranscriptRecord preserves driver success evidence', () => {
    const paths = buildVerificationPaths('C:/workspace');
    const transcriptRecord = buildTranscriptRecord({
        status: SUCCESS_EXIT_STATUS,
        stdout: 'ALL CHECKS PASSED\n',
        stderr: '',
    }, paths);
    assert.equal(transcriptRecord.exitStatus, SUCCESS_EXIT_STATUS);
    assert.equal(transcriptRecord.isSuccess, true);
    assert.match(transcriptRecord.standardOutput, /ALL CHECKS PASSED/);
});

test('buildTranscriptRecord records a driver failure without throwing', () => {
    const transcriptRecord = buildTranscriptRecord({
        status: null,
        stdout: '',
        stderr: 'driver failed',
        error: new Error('spawn failed at C:/workspace/driver.mjs'),
    }, buildVerificationPaths('C:/workspace'));
    assert.equal(transcriptRecord.exitStatus, DRIVER_FAILURE_EXIT_STATUS);
    assert.equal(transcriptRecord.isSuccess, false);
    assert.equal(transcriptRecord.spawnError, 'spawn failed at <repository-root>/driver.mjs');
});

test('buildDoctorRecord rejects paths with the wrong type', () => {
    const repositoryRoot = mkdtempSync(join(tmpdir(), 'verify-doctor-'));
    const driverPath = join(repositoryRoot, 'driver.mjs');
    const packageRoot = join(repositoryRoot, 'package');
    mkdirSync(driverPath);
    writeFileSync(packageRoot, '', 'utf8');
    try {
        const doctorRecord = buildDoctorRecord({
            repositoryRoot,
            packageRoot,
            driverPath,
            evidenceRoot: join(repositoryRoot, 'evidence'),
        });
        assert.equal(doctorRecord.checks.driverExists, false);
        assert.equal(doctorRecord.checks.packageExists, false);
        assert.equal(doctorRecord.isReady, false);
    } finally {
        rmSync(repositoryRoot, { force: true, recursive: true });
    }
});

test('parseCommand returns the first command token', () => {
    assert.equal(parseCommand([DOCTOR_COMMAND]), DOCTOR_COMMAND);
    assert.equal(parseCommand([RUN_COMMAND, 'extra']), RUN_COMMAND);
    assert.equal(parseCommand([]), '');
});
