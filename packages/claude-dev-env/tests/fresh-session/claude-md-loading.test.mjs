/**
 * C1 / P-02 — root CLAUDE.md activation check.
 *
 * Distinguishes installed CLAUDE.md presence from session-probe activation.
 */

import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { writeFileSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';
import {
    ALL_PROFILE_IDS,
    createDisposableRunRoots,
    removeDisposableRunRoots,
} from './harness/disposable-roots.mjs';
import {
    CLAUDE_MD_MARKER_TOKEN,
    installClaudeMdMarkerFixture,
    isClaudeMdFilePresent,
    runClaudeMdActivationSession,
} from './fixtures/claude-md-marker.mjs';

test('harness self-check: seeded marker activates in main, profile-a, and profile-b', () => {
    const roots = createDisposableRunRoots({ profileIds: [...ALL_PROFILE_IDS] });
    try {
        for (const eachProfileId of ALL_PROFILE_IDS) {
            installClaudeMdMarkerFixture(roots.profileRootById[eachProfileId]);
            const result = runClaudeMdActivationSession({ roots, profileId: eachProfileId });
            assert.equal(result.filePresent, true);
            assert.equal(result.activation.simulation, true);
            assert.equal(result.activation.channel, 'session-probe');
            assert.equal(result.activation.isActivated, true);
            assert.equal(result.activation.classification, 'green');
            assert.ok(result.activation.loadedMarkers.includes(CLAUDE_MD_MARKER_TOKEN));
        }
    } finally {
        removeDisposableRunRoots(roots.runRoot);
    }
});

test('missing CLAUDE.md records reproducible red-missing-activation for each profile', () => {
    const roots = createDisposableRunRoots({ profileIds: [...ALL_PROFILE_IDS] });
    /** @type {string[]} */
    const allClassifications = [];
    try {
        for (const eachProfileId of ALL_PROFILE_IDS) {
            const result = runClaudeMdActivationSession({ roots, profileId: eachProfileId });
            assert.equal(result.filePresent, false);
            assert.equal(result.activation.isActivated, false);
            assert.equal(result.activation.classification, 'red-missing-activation');
            assert.equal(result.activation.simulation, true);
            allClassifications.push(`${eachProfileId}:${result.activation.classification}`);
        }
        // Re-run for reproducibility of the red classification.
        for (const eachProfileId of ALL_PROFILE_IDS) {
            const again = runClaudeMdActivationSession({ roots, profileId: eachProfileId });
            assert.equal(again.activation.classification, 'red-missing-activation');
        }
        assert.deepEqual(allClassifications, [
            'main:red-missing-activation',
            'profile-a:red-missing-activation',
            'profile-b:red-missing-activation',
        ]);
    } finally {
        removeDisposableRunRoots(roots.runRoot);
    }
});

test('file presence alone cannot satisfy activation: empty CLAUDE.md is red', () => {
    const roots = createDisposableRunRoots({ profileIds: ['main'] });
    try {
        const profileRoot = roots.profileRootById.main;
        mkdirSync(profileRoot, { recursive: true });
        writeFileSync(join(profileRoot, 'CLAUDE.md'), '# empty hub with no marker\n', 'utf8');
        assert.equal(isClaudeMdFilePresent(profileRoot), true);

        const result = runClaudeMdActivationSession({ roots, profileId: 'main' });
        assert.equal(result.filePresent, true);
        assert.equal(result.activation.isActivated, false);
        assert.equal(result.activation.classification, 'red-missing-activation');
        assert.equal(result.activation.simulation, true);
        assert.deepEqual(result.activation.loadedMarkers, []);
    } finally {
        removeDisposableRunRoots(roots.runRoot);
    }
});

test('activation.simulation is load-bearing for the green path', () => {
    const roots = createDisposableRunRoots({ profileIds: ['profile-a'] });
    try {
        installClaudeMdMarkerFixture(roots.profileRootById['profile-a']);
        const result = runClaudeMdActivationSession({ roots, profileId: 'profile-a' });
        assert.equal(result.activation.isActivated, true);
        assert.equal(result.activation.simulation, true);
    } finally {
        removeDisposableRunRoots(roots.runRoot);
    }
});
