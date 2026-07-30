#!/usr/bin/env node
/**
 * Fresh-session harness entrypoint.
 *
 * Usage:
 *   node tests/fresh-session/harness/run-fresh-session.mjs --profiles main,editor,mel --check transport
 *   node tests/fresh-session/harness/run-fresh-session.mjs --profiles main --real-cli
 *
 * Default transport is the fake CLI. Real CLI is opt-in.
 */

import { writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import {
    ALL_PROFILE_IDS,
    createDisposableRunRoots,
    removeDisposableRunRoots,
} from './disposable-roots.mjs';
import { runProfileSession, shouldUseRealCli } from './transport.mjs';

/**
 * @param {string[]} argv
 * @returns {{
 *   profileIds: string[],
 *   checkTransport: boolean,
 *   realCli: boolean,
 *   keepRoots: boolean,
 *   failProfile: string | null,
 * }}
 */
export function parseHarnessArguments(argv) {
    let profileIds = [...ALL_PROFILE_IDS];
    let checkTransport = false;
    let realCli = shouldUseRealCli();
    let keepRoots = false;
    /** @type {string | null} */
    let failProfile = null;

    for (let index = 0; index < argv.length; index += 1) {
        const token = argv[index];
        if (token === '--profiles') {
            const value = argv[index + 1] ?? '';
            index += 1;
            profileIds = value.split(',').map((each) => each.trim()).filter(Boolean);
        } else if (token.startsWith('--profiles=')) {
            profileIds = token
                .slice('--profiles='.length)
                .split(',')
                .map((each) => each.trim())
                .filter(Boolean);
        } else if (token === '--check' && argv[index + 1] === 'transport') {
            checkTransport = true;
            index += 1;
        } else if (token === '--check=transport') {
            checkTransport = true;
        } else if (token === '--real-cli') {
            realCli = true;
        } else if (token === '--keep-roots') {
            keepRoots = true;
        } else if (token === '--fail-profile') {
            failProfile = argv[index + 1] ?? null;
            index += 1;
        } else if (token === '--help' || token === '-h') {
            process.stdout.write(
                'Usage: node run-fresh-session.mjs --profiles main,editor,mel [--check transport] [--real-cli]\n',
            );
            process.exit(0);
        }
    }

    for (const eachProfileId of profileIds) {
        if (!ALL_PROFILE_IDS.includes(eachProfileId)) {
            throw new Error(`Unsupported profile id: ${eachProfileId}`);
        }
    }

    return { profileIds, checkTransport, realCli, keepRoots, failProfile };
}

/**
 * Run the harness for the given options.
 *
 * @param {ReturnType<typeof parseHarnessArguments>} options
 * @returns {{
 *   exitCode: number,
 *   results: ReturnType<typeof runProfileSession>[],
 *   runRoot: string,
 *   summaryPath: string,
 * }}
 */
export function runFreshSessionHarness(options) {
    const roots = createDisposableRunRoots({ profileIds: options.profileIds });
    /** @type {ReturnType<typeof runProfileSession>[]} */
    const results = [];

    try {
        for (const eachProfileId of options.profileIds) {
            const result = runProfileSession({
                roots,
                profileId: eachProfileId,
                realCli: options.realCli,
                failProfile: options.failProfile ?? undefined,
            });
            results.push(result);
            const mark = result.exitStatus === 0 ? 'PASS' : 'FAIL';
            process.stdout.write(
                `[${mark}] profile=${result.profileId} transport=${result.transport} `
                + `exit=${result.exitStatus} evidence=${result.evidencePath}\n`,
            );
            if (result.diagnostic) {
                process.stderr.write(`  diagnostic: ${result.diagnostic}\n`);
            }
        }

        if (options.checkTransport) {
            for (const eachResult of results) {
                if (!eachResult.cliVersion) {
                    throw new Error(`CLI version missing for profile ${eachResult.profileId}`);
                }
                if (!eachResult.command || eachResult.command.length === 0) {
                    throw new Error(`Command missing for profile ${eachResult.profileId}`);
                }
                if (!eachResult.profileRoot) {
                    throw new Error(`Profile root missing for profile ${eachResult.profileId}`);
                }
            }
            process.stdout.write('transport check: ok\n');
        }

        const failed = results.filter((each) => each.exitStatus !== 0);
        const summaryPath = join(roots.evidenceRoot, 'summary.json');
        writeFileSync(
            summaryPath,
            `${JSON.stringify({
                profiles: options.profileIds,
                realCli: options.realCli,
                results: results.map((each) => ({
                    profileId: each.profileId,
                    transport: each.transport,
                    command: each.command,
                    cliVersion: each.cliVersion,
                    profileRoot: each.profileRoot,
                    exitStatus: each.exitStatus,
                    evidencePath: each.evidencePath,
                    diagnostic: each.diagnostic,
                })),
                failedCount: failed.length,
            }, null, 2)}\n`,
            'utf8',
        );

        return {
            exitCode: failed.length === 0 ? 0 : 1,
            results,
            runRoot: roots.runRoot,
            summaryPath,
        };
    } finally {
        if (!options.keepRoots) {
            removeDisposableRunRoots(roots.runRoot);
        } else {
            process.stdout.write(`kept disposable roots: ${roots.runRoot}\n`);
        }
    }
}

function main() {
    try {
        const options = parseHarnessArguments(process.argv.slice(2));
        const outcome = runFreshSessionHarness(options);
        process.stdout.write(`summary: ${outcome.summaryPath}\n`);
        process.exit(outcome.exitCode);
    } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        process.stderr.write(`fresh-session harness error: ${message}\n`);
        process.exit(2);
    }
}

const isDirectRun = process.argv[1]
    && import.meta.url === pathToFileURL(process.argv[1]).href;

if (isDirectRun) {
    main();
}
