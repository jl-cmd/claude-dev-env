/**
 * Launch transports for the fresh-session harness.
 *
 * Fake transport is the default CI path. Real CLI is opt-in via
 * FRESH_SESSION_REAL_CLI=1 or { realCli: true }.
 */

import { spawnSync } from 'node:child_process';
import { existsSync, writeFileSync, mkdirSync, readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
    buildIsolatedProfileEnvironment,
} from './disposable-roots.mjs';

const HARNESS_DIRECTORY = dirname(fileURLToPath(import.meta.url));
export const FAKE_CLI_PATH = join(HARNESS_DIRECTORY, 'fake-cli.mjs');

const REAL_CLI_DEFAULT_BY_PROFILE = Object.freeze({
    main: 'claude',
    editor: 'claude-editor',
    mel: 'claude-mel',
});

/**
 * Resolve whether the run uses the real Claude CLI.
 *
 * @param {{realCli?: boolean}} [options]
 * @returns {boolean}
 */
export function shouldUseRealCli(options = {}) {
    if (options.realCli === true) return true;
    if (options.realCli === false) return false;
    const flag = process.env.FRESH_SESSION_REAL_CLI ?? '';
    return flag === '1' || flag.toLowerCase() === 'true';
}

/**
 * Resolve the real Claude binary for a profile id.
 *
 * @param {string} profileId
 * @returns {string}
 */
export function resolveRealCliBinary(profileId) {
    if (profileId === 'main') {
        return process.env.FRESH_SESSION_MAIN_CLI
            ?? process.env.CLAUDE_CLI_BINARY
            ?? REAL_CLI_DEFAULT_BY_PROFILE.main;
    }
    if (profileId === 'editor') {
        return process.env.FRESH_SESSION_EDITOR_CLI
            ?? REAL_CLI_DEFAULT_BY_PROFILE.editor;
    }
    if (profileId === 'mel') {
        return process.env.FRESH_SESSION_MEL_CLI
            ?? REAL_CLI_DEFAULT_BY_PROFILE.mel;
    }
    throw new Error(`No real CLI mapping for profile ${profileId}`);
}

/**
 * @param {NodeJS.ProcessEnv} environment
 * @returns {{HOME: string|undefined, USERPROFILE: string|undefined, CLAUDE_CONFIG_DIR: string|undefined, GIT_CONFIG_GLOBAL: string|undefined}}
 */
function isolationEnvironmentSnapshot(environment) {
    return {
        HOME: environment.HOME,
        USERPROFILE: environment.USERPROFILE,
        CLAUDE_CONFIG_DIR: environment.CLAUDE_CONFIG_DIR,
        GIT_CONFIG_GLOBAL: environment.GIT_CONFIG_GLOBAL,
    };
}

/**
 * @param {string} binary
 * @param {string[]} args
 * @param {NodeJS.ProcessEnv} environment
 * @param {{shell?: boolean}} [spawnOptions]
 * @returns {{exitStatus: number|null, stdout: string, stderr: string}}
 */
function spawnCliProcess(binary, args, environment, spawnOptions = {}) {
    const result = spawnSync(binary, args, {
        env: environment,
        encoding: 'utf8',
        shell: spawnOptions.shell === true,
    });
    return {
        exitStatus: result.status,
        stdout: result.stdout ?? '',
        stderr: result.stderr ?? '',
    };
}

/**
 * @param {string} evidencePath
 * @param {Record<string, unknown>} record
 * @returns {void}
 */
function writeEvidenceFile(evidencePath, record) {
    writeFileSync(evidencePath, `${JSON.stringify(record, null, 2)}\n`, 'utf8');
}

/**
 * Run one profile through fake or real transport and write evidence.
 *
 * @param {{
 *   roots: import('./disposable-roots.mjs').DisposableRunRoots,
 *   profileId: string,
 *   realCli?: boolean,
 *   cliArguments?: string[],
 *   failProfile?: string,
 * }} parameters
 * @returns {{
 *   profileId: string,
 *   transport: 'fake' | 'real',
 *   command: string[],
 *   cliVersion: string | null,
 *   profileRoot: string,
 *   exitStatus: number | null,
 *   evidencePath: string,
 *   stdout: string,
 *   stderr: string,
 *   diagnostic: string | null,
 * }}
 */
export function runProfileSession(parameters) {
    const { roots, profileId } = parameters;
    const profileRoot = roots.profileRootById[profileId];
    if (!profileRoot) {
        throw new Error(`Profile root missing for ${profileId}`);
    }

    const evidencePath = join(roots.evidenceRoot, `${profileId}.json`);
    mkdirSync(dirname(evidencePath), { recursive: true });

    const environment = buildIsolatedProfileEnvironment(roots, profileId);
    environment.FRESH_SESSION_PROFILE_ID = profileId;
    environment.FRESH_SESSION_EVIDENCE_PATH = evidencePath;
    // Drop inherited fail flags so a parent shell cannot poison the run.
    delete environment.FRESH_SESSION_FAIL_PROFILE;
    if (parameters.failProfile) {
        environment.FRESH_SESSION_FAIL_PROFILE = parameters.failProfile;
    }

    const useReal = shouldUseRealCli({ realCli: parameters.realCli });
    const cliArguments = parameters.cliArguments ?? ['--version'];
    const transport = useReal ? 'real' : 'fake';

    /** @type {string[]} */
    let command;
    /** @type {{exitStatus: number|null, stdout: string, stderr: string}} */
    let spawnResult;

    if (useReal) {
        const binary = resolveRealCliBinary(profileId);
        command = [binary, ...cliArguments];
        spawnResult = spawnCliProcess(binary, cliArguments, environment, {
            shell: process.platform === 'win32',
        });
    } else {
        command = [process.execPath, FAKE_CLI_PATH, ...cliArguments];
        spawnResult = spawnCliProcess(process.execPath, [FAKE_CLI_PATH, ...cliArguments], environment);
    }

    const { exitStatus, stdout, stderr } = spawnResult;
    let cliVersion = stdout.trim().split(/\r?\n/)[0] || null;
    let diagnostic = exitStatus === 0
        ? null
        : `${transport}-cli: profile ${profileId} exited ${exitStatus}`;

    if (!useReal && existsSync(evidencePath)) {
        const evidence = JSON.parse(readFileSync(evidencePath, 'utf8'));
        cliVersion = evidence?.cliVersion ?? cliVersion;
        if (exitStatus !== 0) {
            diagnostic = evidence?.diagnostic ?? diagnostic;
        }
    }

    const record = {
        transport,
        profileId,
        command,
        cliVersion,
        profileRoot,
        exitStatus,
        evidencePath,
        stdout,
        stderr,
        diagnostic,
        recordedAt: new Date().toISOString(),
        environment: isolationEnvironmentSnapshot(environment),
    };
    writeEvidenceFile(evidencePath, record);

    return {
        profileId,
        transport,
        command,
        cliVersion,
        profileRoot,
        exitStatus,
        evidencePath,
        stdout,
        stderr,
        diagnostic,
    };
}
