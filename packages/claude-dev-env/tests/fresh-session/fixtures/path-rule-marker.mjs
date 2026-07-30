/**
 * Path-scoped rule fixture and paired workspace probe for C3 / P-04.
 */

import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, relative, sep } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { buildIsolatedProfileEnvironment } from '../harness/disposable-roots.mjs';

export const PATH_RULE_MARKER_TOKEN = 'FRESH_SESSION_PATH_RULE_MARKER_C3_d91a44';
export const PATH_RULE_FILE_NAME = 'fresh-session-path-c3.md';
export const MATCHING_WORKSPACE_SEGMENT = 'matching-workspace';
export const CONTROL_WORKSPACE_SEGMENT = 'control-workspace';

const THIS_DIRECTORY = dirname(fileURLToPath(import.meta.url));
export const PATH_RULE_PROBE_SCRIPT_PATH = join(THIS_DIRECTORY, 'path-rule-probe-cli.mjs');

/**
 * @param {string} profileRoot
 * @returns {{
 *   rulePath: string,
 *   matchingWorkspace: string,
 *   controlWorkspace: string,
 *   markerToken: string,
 * }}
 */
export function installPathRuleFixture(profileRoot) {
    const rulesDirectory = join(profileRoot, 'rules');
    mkdirSync(rulesDirectory, { recursive: true });
    const matchingWorkspace = join(profileRoot, 'workspaces', MATCHING_WORKSPACE_SEGMENT);
    const controlWorkspace = join(profileRoot, 'workspaces', CONTROL_WORKSPACE_SEGMENT);
    mkdirSync(matchingWorkspace, { recursive: true });
    mkdirSync(controlWorkspace, { recursive: true });
    writeFileSync(join(matchingWorkspace, 'sample.py'), 'print("matching")\n', 'utf8');
    writeFileSync(join(controlWorkspace, 'sample.py'), 'print("control")\n', 'utf8');

    const rulePath = join(rulesDirectory, PATH_RULE_FILE_NAME);
    const body = [
        '---',
        'description: Disposable path-scoped activation fixture (C3)',
        'paths:',
        `  - "**/${MATCHING_WORKSPACE_SEGMENT}/**"`,
        '---',
        '',
        '# Fresh-session path-scoped rule fixture',
        '',
        `Path rule marker: ${PATH_RULE_MARKER_TOKEN}`,
        '',
    ].join('\n');
    writeFileSync(rulePath, body, 'utf8');
    return {
        rulePath,
        matchingWorkspace,
        controlWorkspace,
        markerToken: PATH_RULE_MARKER_TOKEN,
    };
}

/**
 * @param {{
 *   roots: import('../harness/disposable-roots.mjs').DisposableRunRoots,
 *   profileId: string,
 *   workspacePath: string,
 *   workspaceLabel: 'matching' | 'control',
 * }} parameters
 */
export function runPathRuleActivationSession(parameters) {
    const { roots, profileId, workspacePath, workspaceLabel } = parameters;
    const profileRoot = roots.profileRootById[profileId];
    if (!profileRoot) {
        throw new Error(`Unknown profile id: ${profileId}`);
    }

    const evidencePath = join(
        roots.evidenceRoot,
        `${profileId}-path-rule-${workspaceLabel}.json`,
    );
    mkdirSync(dirname(evidencePath), { recursive: true });

    const environment = buildIsolatedProfileEnvironment(roots, profileId);
    environment.FRESH_SESSION_PROFILE_ID = profileId;
    environment.FRESH_SESSION_EVIDENCE_PATH = evidencePath;
    environment.FRESH_SESSION_PATH_RULE_MARKER = PATH_RULE_MARKER_TOKEN;
    environment.FRESH_SESSION_WORKSPACE_PATH = workspacePath;
    environment.FRESH_SESSION_MATCHING_SEGMENT = MATCHING_WORKSPACE_SEGMENT;

    const result = spawnSync(
        process.execPath,
        [PATH_RULE_PROBE_SCRIPT_PATH, '--probe', 'path-rule'],
        { env: environment, encoding: 'utf8', cwd: workspacePath },
    );

    /** @type {{ activation?: {
     *   loadedMarkers?: string[],
     *   isActivated?: boolean,
     *   simulation?: boolean,
     *   channel?: string,
     *   matchedPath?: boolean,
     * } }}
     */
    let evidence = {};
    if (existsSync(evidencePath)) {
        evidence = JSON.parse(readFileSync(evidencePath, 'utf8'));
    }

    const loadedMarkers = evidence.activation?.loadedMarkers ?? [];
    const isActivated = Boolean(evidence.activation?.isActivated)
        && loadedMarkers.includes(PATH_RULE_MARKER_TOKEN);
    const classification = isActivated ? 'green' : 'red-missing-activation';

    return {
        profileId,
        workspaceLabel,
        workspacePath,
        filePresent: existsSync(join(profileRoot, 'rules', PATH_RULE_FILE_NAME)),
        activation: {
            channel: evidence.activation?.channel ?? 'session-probe',
            simulation: evidence.activation?.simulation === true,
            loadedMarkers,
            isActivated,
            classification,
            matchedPath: Boolean(evidence.activation?.matchedPath),
        },
        evidencePath,
        exitStatus: result.status,
        stdout: result.stdout ?? '',
        stderr: result.stderr ?? '',
        relativeWorkspace: relative(profileRoot, workspacePath).split(sep).join('/'),
    };
}
