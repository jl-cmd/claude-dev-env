/**
 * CLAUDE.md marker fixture and session-probe activation for C1 / P-02.
 *
 * Activation evidence is produced only by a launched session probe that reads
 * CLAUDE.md content under CLAUDE_CONFIG_DIR. File presence alone never sets
 * activation.isActivated.
 */

import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { buildIsolatedProfileEnvironment } from '../harness/disposable-roots.mjs';

export const CLAUDE_MD_MARKER_TOKEN = 'FRESH_SESSION_CLAUDE_MD_MARKER_C1_7f3a9c';
export const CLAUDE_MD_MARKER_FILE_NAME = 'CLAUDE.md';

const THIS_DIRECTORY = dirname(fileURLToPath(import.meta.url));
export const CLAUDE_MD_PROBE_SCRIPT_PATH = join(THIS_DIRECTORY, 'claude-md-probe-cli.mjs');

/**
 * Write the disposable CLAUDE.md marker hub into a profile root.
 *
 * @param {string} profileRoot
 * @returns {{ markerPath: string, markerToken: string }}
 */
export function installClaudeMdMarkerFixture(profileRoot) {
    mkdirSync(profileRoot, { recursive: true });
    const markerPath = join(profileRoot, CLAUDE_MD_MARKER_FILE_NAME);
    const body = [
        '# Fresh-session CLAUDE.md marker fixture (C1)',
        '',
        'This file is disposable test content. It never ships to a live profile.',
        '',
        `When asked for the fresh-session CLAUDE.md marker, reply with exactly: ${CLAUDE_MD_MARKER_TOKEN}`,
        '',
    ].join('\n');
    writeFileSync(markerPath, body, 'utf8');
    return { markerPath, markerToken: CLAUDE_MD_MARKER_TOKEN };
}

/**
 * File-presence-only check. Must never be used as the activation pass criterion.
 *
 * @param {string} profileRoot
 * @returns {boolean}
 */
export function isClaudeMdFilePresent(profileRoot) {
    return existsSync(join(profileRoot, CLAUDE_MD_MARKER_FILE_NAME));
}

/**
 * Launch a session probe under the disposable profile environment and collect
 * activation evidence. The probe reads CLAUDE.md content; an empty or missing
 * file yields isActivated=false.
 *
 * @param {{
 *   roots: import('../harness/disposable-roots.mjs').DisposableRunRoots,
 *   profileId: string,
 * }} parameters
 * @returns {{
 *   profileId: string,
 *   filePresent: boolean,
 *   activation: {
 *     channel: string,
 *     simulation: boolean,
 *     loadedMarkers: string[],
 *     isActivated: boolean,
 *     classification: 'green' | 'red-missing-activation',
 *   },
 *   evidencePath: string,
 *   exitStatus: number | null,
 *   stdout: string,
 *   stderr: string,
 * }}
 */
export function runClaudeMdActivationSession(parameters) {
    const { roots, profileId } = parameters;
    const profileRoot = roots.profileRootById[profileId];
    if (!profileRoot) {
        throw new Error(`Unknown profile id: ${profileId}`);
    }

    const evidencePath = join(roots.evidenceRoot, `${profileId}-claude-md.json`);
    mkdirSync(dirname(evidencePath), { recursive: true });

    const environment = buildIsolatedProfileEnvironment(roots, profileId);
    environment.FRESH_SESSION_PROFILE_ID = profileId;
    environment.FRESH_SESSION_EVIDENCE_PATH = evidencePath;
    environment.FRESH_SESSION_CLAUDE_MD_MARKER = CLAUDE_MD_MARKER_TOKEN;

    const result = spawnSync(
        process.execPath,
        [CLAUDE_MD_PROBE_SCRIPT_PATH, '--probe', 'claude-md'],
        { env: environment, encoding: 'utf8' },
    );

    const filePresent = isClaudeMdFilePresent(profileRoot);
    /** @type {{ activation?: { loadedMarkers?: string[], isActivated?: boolean, simulation?: boolean, channel?: string } }} */
    let evidence = {};
    if (existsSync(evidencePath)) {
        evidence = JSON.parse(readFileSync(evidencePath, 'utf8'));
    }

    const loadedMarkers = evidence.activation?.loadedMarkers ?? [];
    const isActivated = Boolean(evidence.activation?.isActivated)
        && loadedMarkers.includes(CLAUDE_MD_MARKER_TOKEN);
    const classification = isActivated ? 'green' : 'red-missing-activation';

    return {
        profileId,
        filePresent,
        activation: {
            channel: evidence.activation?.channel ?? 'session-probe',
            simulation: evidence.activation?.simulation === true,
            loadedMarkers,
            isActivated,
            classification,
        },
        evidencePath,
        exitStatus: result.status,
        stdout: result.stdout ?? '',
        stderr: result.stderr ?? '',
    };
}
