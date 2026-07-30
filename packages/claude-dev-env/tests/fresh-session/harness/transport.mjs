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
            ?? 'claude';
    }
    if (profileId === 'editor') {
        return process.env.FRESH_SESSION_EDITOR_CLI ?? 'claude-editor';
    }
    if (profileId === 'mel') {
        return process.env.FRESH_SESSION_MEL_CLI ?? 'claude-mel';
    }
    throw new Error(`No real CLI mapping for profile ${profileId}`);
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
    if (parameters.failProfile) {
        environment.FRESH_SESSION_FAIL_PROFILE = parameters.failProfile;
    }

    const useReal = shouldUseRealCli({ realCli: parameters.realCli });
    const cliArguments = parameters.cliArguments ?? ['--version'];

    /** @type {string[]} */
    let command;
    if (useReal) {
        const binary = resolveRealCliBinary(profileId);
        command = [binary, ...cliArguments];
        const result = spawnSync(binary, cliArguments, {
            env: environment,
            encoding: 'utf8',
            shell: process.platform === 'win32',
        });
        const exitStatus = result.status;
        const stdout = result.stdout ?? '';
        const stderr = result.stderr ?? '';
        const cliVersion = stdout.trim().split(/\r?\n/)[0] || null;
        const diagnostic = exitStatus === 0
            ? null
            : `real-cli: profile ${profileId} exited ${exitStatus}`;
        const record = {
            transport: 'real',
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
            environment: {
                HOME: environment.HOME,
                USERPROFILE: environment.USERPROFILE,
                CLAUDE_CONFIG_DIR: environment.CLAUDE_CONFIG_DIR,
                GIT_CONFIG_GLOBAL: environment.GIT_CONFIG_GLOBAL,
            },
        };
        writeFileSync(evidencePath, `${JSON.stringify(record, null, 2)}\n`, 'utf8');
        return {
            profileId,
            transport: 'real',
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

    command = [process.execPath, FAKE_CLI_PATH, ...cliArguments];
    const result = spawnSync(process.execPath, [FAKE_CLI_PATH, ...cliArguments], {
        env: environment,
        encoding: 'utf8',
    });
    const exitStatus = result.status;
    const stdout = result.stdout ?? '';
    const stderr = result.stderr ?? '';

    let evidence = null;
    if (existsSync(evidencePath)) {
        evidence = JSON.parse(readFileSync(evidencePath, 'utf8'));
    }
    const cliVersion = evidence?.cliVersion
        ?? (stdout.trim().split(/\r?\n/)[0] || null);
    const diagnostic = exitStatus === 0
        ? null
        : (evidence?.diagnostic ?? `fake-cli: profile ${profileId} exited ${exitStatus}`);

    const summary = {
        transport: 'fake',
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
        environment: {
            HOME: environment.HOME,
            USERPROFILE: environment.USERPROFILE,
            CLAUDE_CONFIG_DIR: environment.CLAUDE_CONFIG_DIR,
            GIT_CONFIG_GLOBAL: environment.GIT_CONFIG_GLOBAL,
        },
    };
    writeFileSync(evidencePath, `${JSON.stringify(summary, null, 2)}\n`, 'utf8');

    return {
        profileId,
        transport: 'fake',
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
