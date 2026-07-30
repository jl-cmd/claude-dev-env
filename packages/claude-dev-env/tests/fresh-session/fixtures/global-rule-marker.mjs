/**
 * Global-rule fixture and session-probe activation for C2 / P-03.
 */

import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { buildIsolatedProfileEnvironment } from '../harness/disposable-roots.mjs';

export const GLOBAL_RULE_MARKER_TOKEN = 'FRESH_SESSION_GLOBAL_RULE_MARKER_C2_b41e02';
export const GLOBAL_RULE_FILE_NAME = 'fresh-session-global-c2.md';

const THIS_DIRECTORY = dirname(fileURLToPath(import.meta.url));
export const GLOBAL_RULE_PROBE_SCRIPT_PATH = join(THIS_DIRECTORY, 'global-rule-probe-cli.mjs');

/**
 * @param {string} profileRoot
 * @returns {{ rulePath: string, markerToken: string }}
 */
export function installGlobalRuleFixture(profileRoot) {
    const rulesDirectory = join(profileRoot, 'rules');
    mkdirSync(rulesDirectory, { recursive: true });
    const rulePath = join(rulesDirectory, GLOBAL_RULE_FILE_NAME);
    const body = [
        '---',
        'description: Disposable global-rule activation fixture (C2)',
        '---',
        '',
        '# Fresh-session global rule fixture',
        '',
        'This rule has no paths: frontmatter, so a real session would load it globally.',
        '',
        `Global rule marker: ${GLOBAL_RULE_MARKER_TOKEN}`,
        '',
    ].join('\n');
    writeFileSync(rulePath, body, 'utf8');
    return { rulePath, markerToken: GLOBAL_RULE_MARKER_TOKEN };
}

/**
 * @param {string} profileRoot
 * @returns {boolean}
 */
export function isGlobalRuleFilePresent(profileRoot) {
    return existsSync(join(profileRoot, 'rules', GLOBAL_RULE_FILE_NAME));
}

/**
 * @param {{
 *   roots: import('../harness/disposable-roots.mjs').DisposableRunRoots,
 *   profileId: string,
 * }} parameters
 */
export function runGlobalRuleActivationSession(parameters) {
    const { roots, profileId } = parameters;
    const profileRoot = roots.profileRootById[profileId];
    if (!profileRoot) {
        throw new Error(`Unknown profile id: ${profileId}`);
    }

    const evidencePath = join(roots.evidenceRoot, `${profileId}-global-rule.json`);
    mkdirSync(dirname(evidencePath), { recursive: true });

    const environment = buildIsolatedProfileEnvironment(roots, profileId);
    environment.FRESH_SESSION_PROFILE_ID = profileId;
    environment.FRESH_SESSION_EVIDENCE_PATH = evidencePath;
    environment.FRESH_SESSION_GLOBAL_RULE_MARKER = GLOBAL_RULE_MARKER_TOKEN;

    const result = spawnSync(
        process.execPath,
        [GLOBAL_RULE_PROBE_SCRIPT_PATH, '--probe', 'global-rule'],
        { env: environment, encoding: 'utf8' },
    );

    const filePresent = isGlobalRuleFilePresent(profileRoot);
    /** @type {{ activation?: { loadedMarkers?: string[], isActivated?: boolean, simulation?: boolean, channel?: string } }} */
    let evidence = {};
    if (existsSync(evidencePath)) {
        evidence = JSON.parse(readFileSync(evidencePath, 'utf8'));
    }

    const loadedMarkers = evidence.activation?.loadedMarkers ?? [];
    const isActivated = Boolean(evidence.activation?.isActivated)
        && loadedMarkers.includes(GLOBAL_RULE_MARKER_TOKEN);
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
            allLoadedRuleNames: evidence.activation?.allLoadedRuleNames ?? [],
        },
        evidencePath,
        exitStatus: result.status,
        stdout: result.stdout ?? '',
        stderr: result.stderr ?? '',
    };
}

/**
 * Count rule files under profileRoot/rules (presence-only helper).
 *
 * @param {string} profileRoot
 * @returns {number}
 */
export function countRuleFilesPresent(profileRoot) {
    const rulesDirectory = join(profileRoot, 'rules');
    if (!existsSync(rulesDirectory)) {
        return 0;
    }
    return readdirSync(rulesDirectory).filter((each) => each.endsWith('.md')).length;
}
