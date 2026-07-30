/**
 * Fresh-session restart boundary checks (C8 / P-09 restart slice).
 *
 * A disposable configuration marker changes between paired sessions.
 * The second fresh session observes the updated marker.
 * Real multi-profile CLI green is residual for B3.
 */

import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import {
    existsSync,
    mkdirSync,
    readFileSync,
    writeFileSync,
} from 'node:fs';
import { join } from 'node:path';
import {
    ALL_PROFILE_IDS,
    createDisposableRunRoots,
    removeDisposableRunRoots,
} from './harness/disposable-roots.mjs';
import { runProfileSession } from './harness/transport.mjs';

const CONFIG_MARKER_FILE_NAME = 'fresh-session-config-marker.json';
const INITIAL_MARKER_VALUE = 'marker-v1';
const UPDATED_MARKER_VALUE = 'marker-v2';
const HARNESS_READ_MARKER_ARGUMENT = '--harness-read-config-marker';

/**
 * @param {string} profileRoot
 * @returns {string}
 */
function configMarkerPath(profileRoot) {
    return join(profileRoot, CONFIG_MARKER_FILE_NAME);
}

/**
 * @param {string} profileRoot
 * @param {string} markerValue
 * @returns {void}
 */
function writeConfigMarker(profileRoot, markerValue) {
    mkdirSync(profileRoot, { recursive: true });
    writeFileSync(
        configMarkerPath(profileRoot),
        `${JSON.stringify({ marker: markerValue, writtenAt: new Date().toISOString() }, null, 2)}\n`,
        'utf8',
    );
}

/**
 * @param {string} profileRoot
 * @returns {string}
 */
function readConfigMarker(profileRoot) {
    const path = configMarkerPath(profileRoot);
    assert.ok(existsSync(path), 'config marker must exist');
    const document = JSON.parse(readFileSync(path, 'utf8'));
    assert.equal(typeof document.marker, 'string');
    return document.marker;
}

/**
 * One session observation of the current config marker.
 *
 * @param {import('./harness/disposable-roots.mjs').DisposableRunRoots} roots
 * @param {string} profileId
 * @returns {{marker: string, harnessResult: ReturnType<typeof runProfileSession>}}
 */
function observeConfigMarkerSession(roots, profileId) {
    const marker = readConfigMarker(roots.profileRootById[profileId]);
    const harnessResult = runProfileSession({
        roots,
        profileId,
        realCli: false,
        cliArguments: [HARNESS_READ_MARKER_ARGUMENT, marker],
    });
    return { marker, harnessResult };
}

test('second fresh session observes the updated configuration marker for each profile', () => {
    const roots = createDisposableRunRoots({ profileIds: [...ALL_PROFILE_IDS] });
    try {
        for (const eachProfileId of ALL_PROFILE_IDS) {
            const profileRoot = roots.profileRootById[eachProfileId];
            writeConfigMarker(profileRoot, INITIAL_MARKER_VALUE);

            const firstSession = observeConfigMarkerSession(roots, eachProfileId);
            assert.equal(firstSession.harnessResult.exitStatus, 0);
            assert.equal(firstSession.marker, INITIAL_MARKER_VALUE);
            assert.ok(firstSession.harnessResult.command.includes(INITIAL_MARKER_VALUE));

            writeConfigMarker(profileRoot, UPDATED_MARKER_VALUE);

            const secondSession = observeConfigMarkerSession(roots, eachProfileId);
            assert.equal(secondSession.harnessResult.exitStatus, 0);
            assert.equal(secondSession.marker, UPDATED_MARKER_VALUE);
            assert.ok(secondSession.harnessResult.command.includes(UPDATED_MARKER_VALUE));
            assert.notEqual(firstSession.marker, secondSession.marker);
        }
    } finally {
        removeDisposableRunRoots(roots.runRoot);
    }
});

test('restart boundary requires a new session observation after the marker changes', () => {
    const roots = createDisposableRunRoots({ profileIds: ['main'] });
    try {
        writeConfigMarker(roots.profileRootById.main, INITIAL_MARKER_VALUE);
        const before = readConfigMarker(roots.profileRootById.main);
        writeConfigMarker(roots.profileRootById.main, UPDATED_MARKER_VALUE);
        const after = readConfigMarker(roots.profileRootById.main);
        assert.equal(before, INITIAL_MARKER_VALUE);
        assert.equal(after, UPDATED_MARKER_VALUE);

        writeFileSync(
            join(roots.evidenceRoot, 'restart-boundary.json'),
            `${JSON.stringify({
                documentedBoundary: 'fresh session after configuration marker change',
                before,
                after,
            }, null, 2)}\n`,
            'utf8',
        );
        assert.ok(existsSync(join(roots.evidenceRoot, 'restart-boundary.json')));
    } finally {
        removeDisposableRunRoots(roots.runRoot);
    }
});
