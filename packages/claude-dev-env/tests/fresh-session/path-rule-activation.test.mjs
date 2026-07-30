/**
 * C3 / P-04 — path-scoped rule activation check.
 */

import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { mkdirSync } from 'node:fs';
import { join } from 'node:path';
import {
    ALL_PROFILE_IDS,
    createDisposableRunRoots,
    removeDisposableRunRoots,
} from './harness/disposable-roots.mjs';
import {
    PATH_RULE_MARKER_TOKEN,
    MATCHING_WORKSPACE_SEGMENT,
    installPathRuleFixture,
    runPathRuleActivationSession,
} from './fixtures/path-rule-marker.mjs';

test('path rule activates in matching workspace for main, editor, and mel', () => {
    const roots = createDisposableRunRoots({ profileIds: [...ALL_PROFILE_IDS] });
    try {
        for (const eachProfileId of ALL_PROFILE_IDS) {
            const fixture = installPathRuleFixture(roots.profileRootById[eachProfileId]);
            const result = runPathRuleActivationSession({
                roots,
                profileId: eachProfileId,
                workspacePath: fixture.matchingWorkspace,
                workspaceLabel: 'matching',
            });
            assert.equal(result.filePresent, true);
            assert.equal(result.activation.simulation, true);
            assert.equal(result.activation.channel, 'session-probe');
            assert.equal(result.activation.matchedPath, true);
            assert.equal(result.activation.isActivated, true);
            assert.equal(result.activation.classification, 'green');
            assert.ok(result.activation.loadedMarkers.includes(PATH_RULE_MARKER_TOKEN));
        }
    } finally {
        removeDisposableRunRoots(roots.runRoot);
    }
});

test('same path rule stays inactive in the control workspace for each profile', () => {
    const roots = createDisposableRunRoots({ profileIds: [...ALL_PROFILE_IDS] });
    try {
        for (const eachProfileId of ALL_PROFILE_IDS) {
            const fixture = installPathRuleFixture(roots.profileRootById[eachProfileId]);
            const result = runPathRuleActivationSession({
                roots,
                profileId: eachProfileId,
                workspacePath: fixture.controlWorkspace,
                workspaceLabel: 'control',
            });
            assert.equal(result.filePresent, true);
            assert.equal(result.activation.matchedPath, false);
            assert.equal(result.activation.isActivated, false);
            assert.equal(result.activation.classification, 'red-missing-activation');
            assert.equal(result.activation.simulation, true);
        }
    } finally {
        removeDisposableRunRoots(roots.runRoot);
    }
});

test('paired matching green and control red are reproducible for one profile', () => {
    const roots = createDisposableRunRoots({ profileIds: ['main'] });
    try {
        const fixture = installPathRuleFixture(roots.profileRootById.main);
        const matchingFirst = runPathRuleActivationSession({
            roots,
            profileId: 'main',
            workspacePath: fixture.matchingWorkspace,
            workspaceLabel: 'matching',
        });
        const controlFirst = runPathRuleActivationSession({
            roots,
            profileId: 'main',
            workspacePath: fixture.controlWorkspace,
            workspaceLabel: 'control',
        });
        const matchingSecond = runPathRuleActivationSession({
            roots,
            profileId: 'main',
            workspacePath: fixture.matchingWorkspace,
            workspaceLabel: 'matching',
        });
        const controlSecond = runPathRuleActivationSession({
            roots,
            profileId: 'main',
            workspacePath: fixture.controlWorkspace,
            workspaceLabel: 'control',
        });

        assert.equal(matchingFirst.activation.classification, 'green');
        assert.equal(matchingSecond.activation.classification, 'green');
        assert.equal(controlFirst.activation.classification, 'red-missing-activation');
        assert.equal(controlSecond.activation.classification, 'red-missing-activation');
        assert.equal(matchingFirst.activation.simulation, true);
        assert.equal(controlFirst.activation.simulation, true);
    } finally {
        removeDisposableRunRoots(roots.runRoot);
    }
});

test('missing path-rule fixture records red for matching workspace', () => {
    const roots = createDisposableRunRoots({ profileIds: ['editor'] });
    try {
        const profileRoot = roots.profileRootById.editor;
        const matchingWorkspace = join(profileRoot, 'workspaces', MATCHING_WORKSPACE_SEGMENT);
        mkdirSync(matchingWorkspace, { recursive: true });
        const result = runPathRuleActivationSession({
            roots,
            profileId: 'editor',
            workspacePath: matchingWorkspace,
            workspaceLabel: 'matching',
        });
        assert.equal(result.filePresent, false);
        assert.equal(result.activation.isActivated, false);
        assert.equal(result.activation.classification, 'red-missing-activation');
        assert.equal(result.activation.simulation, true);
    } finally {
        removeDisposableRunRoots(roots.runRoot);
    }
});
