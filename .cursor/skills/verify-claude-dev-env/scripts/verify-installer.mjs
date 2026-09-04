#!/usr/bin/env node

import { spawnSync } from 'node:child_process';
import { mkdirSync, statSync, writeFileSync } from 'node:fs';
import { homedir, tmpdir } from 'node:os';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import {
    AUDIT_DIRECTORY_NAME,
    CONVERSION_DIRECTORY_NAME,
    DOCTOR_COMMAND,
    DOCTOR_COMMAND_LABEL,
    DOCTOR_FILE_NAME,
    DRIVER_COMMAND_LABEL,
    DRIVER_FAILURE_EXIT_STATUS,
    DRIVER_FILE_NAME,
    DRIVER_SKILL_NAME,
    DRIVER_TIMEOUT_MILLISECONDS,
    EVIDENCE_DIRECTORY_NAME,
    EVIDENCE_LABEL,
    FALLBACK_PYTHON_COMMAND,
    GIT_COMMAND,
    GIT_VERSION_ARGUMENT,
    PACKAGE_DIRECTORY_NAME,
    PACKAGE_NAME,
    POSIX_PYTHON_COMMAND,
    PYTHON_VERSION_ARGUMENTS,
    REQUIRED_NODE_MAJOR_VERSION,
    RUN_COMMAND,
    SUCCESS_EXIT_STATUS,
    TRANSCRIPT_FILE_NAME,
    USAGE_EXIT_STATUS,
    WINDOWS_PYTHON_ARGUMENTS,
    WINDOWS_PYTHON_COMMAND,
} from './verify_installer_constants/constants.mjs';

const REPOSITORY_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../../../..');

function buildVerificationPaths(repositoryRoot = REPOSITORY_ROOT) {
    const packageRoot = join(repositoryRoot, PACKAGE_DIRECTORY_NAME, PACKAGE_NAME);
    const driverPath = join(
        packageRoot,
        '.agents',
        'skills',
        DRIVER_SKILL_NAME,
        DRIVER_FILE_NAME,
    );
    const evidenceRoot = join(
        repositoryRoot,
        AUDIT_DIRECTORY_NAME,
        CONVERSION_DIRECTORY_NAME,
        EVIDENCE_DIRECTORY_NAME,
    );
    return {
        repositoryRoot,
        packageRoot,
        driverPath,
        evidenceRoot,
        transcriptPath: join(evidenceRoot, TRANSCRIPT_FILE_NAME),
        doctorPath: join(evidenceRoot, DOCTOR_FILE_NAME),
    };
}

function redactPath(sourceText, searchText, replacementText) {
    if (process.platform !== 'win32') {
        return sourceText.split(searchText).join(replacementText);
    }
    const foldedSource = sourceText.toLowerCase();
    const foldedSearch = searchText.toLowerCase();
    const parts = [];
    let offset = 0;
    let matchOffset = foldedSource.indexOf(foldedSearch, offset);
    while (matchOffset >= 0) {
        parts.push(sourceText.slice(offset, matchOffset), replacementText);
        offset = matchOffset + searchText.length;
        matchOffset = foldedSource.indexOf(foldedSearch, offset);
    }
    parts.push(sourceText.slice(offset));
    return parts.join('');
}

function sanitizeTranscript(transcript, paths = buildVerificationPaths()) {
    const redactions = [
        [paths.repositoryRoot, '<repository-root>'],
        [paths.packageRoot, '<package-root>'],
        [paths.evidenceRoot, '<evidence-root>'],
        [tmpdir(), '<temporary-directory>'],
        [homedir(), '<home-directory>'],
    ];
    let sanitizedText = String(transcript ?? '');
    for (const [sourceText, replacementText] of redactions) {
        for (const spelling of new Set([sourceText, sourceText.replaceAll('\\', '/')])) {
            sanitizedText = redactPath(sanitizedText, spelling, replacementText);
        }
    }
    return sanitizedText;
}

function pathHasType(filePath, expectedType) {
    try {
        return statSync(filePath)[expectedType]();
    } catch {
        return false;
    }
}

function runProbe(command, argumentsList) {
    const probeRun = spawnSync(command, argumentsList, {
        cwd: REPOSITORY_ROOT,
        encoding: 'utf8',
        stdio: ['ignore', 'pipe', 'pipe'],
        windowsHide: true,
    });
    return {
        command,
        argumentsList,
        exitStatus: probeRun.status ?? DRIVER_FAILURE_EXIT_STATUS,
        standardOutput: probeRun.stdout ?? '',
        standardError: probeRun.stderr ?? '',
        errorMessage: probeRun.error?.message ?? '',
    };
}

function findPythonProbe() {
    const pythonProbes = process.platform === 'win32'
        ? [
            [WINDOWS_PYTHON_COMMAND, WINDOWS_PYTHON_ARGUMENTS],
            [POSIX_PYTHON_COMMAND, PYTHON_VERSION_ARGUMENTS],
            [FALLBACK_PYTHON_COMMAND, PYTHON_VERSION_ARGUMENTS],
        ]
        : [
            [POSIX_PYTHON_COMMAND, PYTHON_VERSION_ARGUMENTS],
            [FALLBACK_PYTHON_COMMAND, PYTHON_VERSION_ARGUMENTS],
        ];
    for (const [command, argumentsList] of pythonProbes) {
        const probeRun = runProbe(command, argumentsList);
        if (probeRun.exitStatus === SUCCESS_EXIT_STATUS) {
            return probeRun;
        }
    }
    return null;
}

function buildDoctorRecord(paths = buildVerificationPaths()) {
    const gitProbe = runProbe(GIT_COMMAND, [GIT_VERSION_ARGUMENT]);
    const pythonProbe = findPythonProbe();
    const nodeMajorVersion = Number.parseInt(process.versions.node.split('.')[0], 10);
    const checks = {
        driverExists: pathHasType(paths.driverPath, 'isFile'),
        packageExists: pathHasType(paths.packageRoot, 'isDirectory'),
        nodeVersionSupported: nodeMajorVersion >= REQUIRED_NODE_MAJOR_VERSION,
        gitAvailable: gitProbe.exitStatus === SUCCESS_EXIT_STATUS,
        pythonAvailable: pythonProbe !== null,
    };
    const isReady = Object.values(checks).every(Boolean);
    return {
        generatedAt: new Date().toISOString(),
        isReady,
        checks,
        nodeVersion: process.versions.node,
        gitVersion: sanitizeTranscript(gitProbe.standardOutput.trim()),
        pythonVersion: pythonProbe
            ? sanitizeTranscript(`${pythonProbe.standardOutput}${pythonProbe.standardError}`.trim())
            : '',
        paths: {
            driver: relative(paths.repositoryRoot, paths.driverPath).replaceAll('\\', '/'),
            package: relative(paths.repositoryRoot, paths.packageRoot).replaceAll('\\', '/'),
        },
    };
}

function buildTranscriptRecord(driverRun, paths = buildVerificationPaths()) {
    const standardOutput = sanitizeTranscript(driverRun.stdout ?? '', paths);
    const standardError = sanitizeTranscript(driverRun.stderr ?? '', paths);
    const exitStatus = driverRun.status ?? DRIVER_FAILURE_EXIT_STATUS;
    return {
        generatedAt: new Date().toISOString(),
        command: `node ${relative(paths.repositoryRoot, paths.driverPath).replaceAll('\\', '/')}`,
        exitStatus,
        isSuccess: exitStatus === SUCCESS_EXIT_STATUS,
        standardOutput,
        standardError,
        spawnError: sanitizeTranscript(driverRun.error?.message ?? '', paths),
    };
}

function writeEvidence(filePath, evidenceRecord) {
    mkdirSync(dirname(filePath), { recursive: true });
    writeFileSync(filePath, `${JSON.stringify(evidenceRecord, null, 2)}\n`, 'utf8');
}

function runDoctor(paths = buildVerificationPaths()) {
    const doctorRecord = buildDoctorRecord(paths);
    writeEvidence(paths.doctorPath, doctorRecord);
    console.log(`${DOCTOR_COMMAND_LABEL}: ${doctorRecord.isReady ? 'ready' : 'not ready'}`);
    console.log(`${EVIDENCE_LABEL}: ${relative(paths.repositoryRoot, paths.doctorPath).replaceAll('\\', '/')}`);
    return doctorRecord.isReady ? SUCCESS_EXIT_STATUS : DRIVER_FAILURE_EXIT_STATUS;
}

function runInstaller(paths = buildVerificationPaths()) {
    if (!pathHasType(paths.driverPath, 'isFile')) {
        const missingDriverRecord = buildTranscriptRecord({
            status: DRIVER_FAILURE_EXIT_STATUS,
            stderr: 'The isolated installer driver does not exist.',
        }, paths);
        writeEvidence(paths.transcriptPath, missingDriverRecord);
        console.error(missingDriverRecord.standardError);
        return DRIVER_FAILURE_EXIT_STATUS;
    }
    const driverRun = spawnSync(process.execPath, [paths.driverPath], {
        cwd: paths.packageRoot,
        encoding: 'utf8',
        stdio: ['ignore', 'pipe', 'pipe'],
        timeout: DRIVER_TIMEOUT_MILLISECONDS,
        killSignal: 'SIGTERM',
        windowsHide: true,
    });
    const transcriptRecord = buildTranscriptRecord(driverRun, paths);
    writeEvidence(paths.transcriptPath, transcriptRecord);
    console.log(`${DRIVER_COMMAND_LABEL}: ${transcriptRecord.command}`);
    console.log(transcriptRecord.standardOutput);
    if (transcriptRecord.standardError) {
        console.error(transcriptRecord.standardError);
    }
    console.log(`${EVIDENCE_LABEL}: ${relative(paths.repositoryRoot, paths.transcriptPath).replaceAll('\\', '/')}`);
    return transcriptRecord.exitStatus;
}

function printUsage() {
    console.error('Usage: node .cursor/skills/verify-claude-dev-env/scripts/verify-installer.mjs doctor|run');
}

function runMain(argumentsList = process.argv.slice(2)) {
    const command = argumentsList[0];
    if (command === DOCTOR_COMMAND) {
        return runDoctor();
    }
    if (command === RUN_COMMAND) {
        return runInstaller();
    }
    printUsage();
    return USAGE_EXIT_STATUS;
}

function parseCommand(argumentsList) {
    return argumentsList[0] ?? '';
}

export {
    buildDoctorRecord,
    buildTranscriptRecord,
    buildVerificationPaths,
    findPythonProbe,
    parseCommand,
    runMain,
    sanitizeTranscript,
};

const isEntryPoint = process.argv[1]
    && resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isEntryPoint) {
    process.exitCode = runMain(process.argv.slice(2));
}
