/**
 * C2 / P-03 — global-rule activation check.
 */

import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import {
    ALL_PROFILE_IDS,
    createDisposableRunRoots,
    removeDisposableRunRoots,
} from './harness/disposable-roots.mjs';
import {
    GLOBAL_RULE_MARKER_TOKEN,
    GLOBAL_RULE_FILE_NAME,
    installGlobalRuleFixture,
    isGlobalRuleFilePresent,
    runGlobalRuleActivationSession,
    countRuleFilesPresent,
} from './fixtures/global-rule-marker.mjs';

test('seeded global rule activates independently in main, editor, and mel', () => {
    const roots = createDisposableRunRoots({ profileIds: [...ALL_PROFILE_IDS] });
    try {
        for (const eachProfileId of ALL_PROFILE_IDS) {
            installGlobalRuleFixture(roots.profileRootById[eachProfileId]);
            const result = runGlobalRuleActivationSession({ roots, profileId: eachProfileId });
            assert.equal(result.filePresent, true);
            assert.equal(result.activation.simulation, true);
            assert.equal(result.activation.channel, 'session-probe');
            assert.equal(result.activation.isActivated, true);
            assert.equal(result.activation.classification, 'green');
            assert.ok(result.activation.loadedMarkers.includes(GLOBAL_RULE_MARKER_TOKEN));
            assert.ok(result.activation.allLoadedRuleNames.includes(GLOBAL_RULE_FILE_NAME));
        }
    } finally {
        removeDisposableRunRoots(roots.runRoot);
    }
});

test('missing global rule records reproducible red-missing-activation for each profile', () => {
    const roots = createDisposableRunRoots({ profileIds: [...ALL_PROFILE_IDS] });
    try {
        /** @type {string[]} */
        const allClassifications = [];
        for (const eachProfileId of ALL_PROFILE_IDS) {
            const result = runGlobalRuleActivationSession({ roots, profileId: eachProfileId });
            assert.equal(result.filePresent, false);
            assert.equal(result.activation.isActivated, false);
            assert.equal(result.activation.classification, 'red-missing-activation');
            assert.equal(result.activation.simulation, true);
            allClassifications.push(`${eachProfileId}:${result.activation.classification}`);
        }
        for (const eachProfileId of ALL_PROFILE_IDS) {
            const again = runGlobalRuleActivationSession({ roots, profileId: eachProfileId });
            assert.equal(again.activation.classification, 'red-missing-activation');
        }
        assert.deepEqual(allClassifications, [
            'main:red-missing-activation',
            'editor:red-missing-activation',
            'mel:red-missing-activation',
        ]);
    } finally {
        removeDisposableRunRoots(roots.runRoot);
    }
});

test('file presence alone cannot satisfy activation: empty global rule is red', () => {
    const roots = createDisposableRunRoots({ profileIds: ['main'] });
    try {
        const profileRoot = roots.profileRootById.main;
        const rulesDirectory = join(profileRoot, 'rules');
        mkdirSync(rulesDirectory, { recursive: true });
        writeFileSync(
            join(rulesDirectory, GLOBAL_RULE_FILE_NAME),
            '---\ndescription: empty\n---\n# no marker\n',
            'utf8',
        );
        assert.equal(isGlobalRuleFilePresent(profileRoot), true);
        assert.equal(countRuleFilesPresent(profileRoot), 1);

        const result = runGlobalRuleActivationSession({ roots, profileId: 'main' });
        assert.equal(result.filePresent, true);
        assert.equal(result.activation.isActivated, false);
        assert.equal(result.activation.classification, 'red-missing-activation');
        assert.equal(result.activation.simulation, true);
    } finally {
        removeDisposableRunRoots(roots.runRoot);
    }
});

test('path-scoped rules are not loaded as global activation', () => {
    const roots = createDisposableRunRoots({ profileIds: ['editor'] });
    try {
        const profileRoot = roots.profileRootById.editor;
        const rulesDirectory = join(profileRoot, 'rules');
        mkdirSync(rulesDirectory, { recursive: true });
        writeFileSync(
            join(rulesDirectory, 'scoped-only.md'),
            [
                '---',
                'paths:',
                '  - "packages/**"',
                '---',
                '',
                `Global rule marker: ${GLOBAL_RULE_MARKER_TOKEN}`,
                '',
            ].join('\n'),
            'utf8',
        );
        const result = runGlobalRuleActivationSession({ roots, profileId: 'editor' });
        assert.equal(result.activation.isActivated, false);
        assert.ok(!result.activation.allLoadedRuleNames.includes('scoped-only.md'));
    } finally {
        removeDisposableRunRoots(roots.runRoot);
    }
});
