/**
 * Read-only installation plan and preflight contract (control-plane E1 / P-17).
 */

import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import {
    mkdtempSync,
    rmSync,
    mkdirSync,
    writeFileSync,
    readFileSync,
    existsSync,
    readdirSync,
    statSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import {
    buildInstallPlan,
    InstallPlanPreflightError,
    PREFLIGHT_ERROR_CODES,
    planShouldInstallHooks,
    describeInstallMutations,
    readPriorManifestArraysFromPath,
} from './install-plan.mjs';

const GROUPS = {
    core: { skills: ['a'], includeDirectories: ['rules'], includeAllHooks: true },
    journal: { skills: ['session-log'] },
};

function sandbox() {
    const root = mkdtempSync(join(tmpdir(), 'cdev-install-plan-'));
    const managedRoot = join(root, 'managed');
    const packageRoot = join(root, 'package');
    mkdirSync(managedRoot, { recursive: true });
    mkdirSync(packageRoot, { recursive: true });
    return { root, managedRoot, packageRoot };
}

function treeStamp(directoryPath) {
    if (!existsSync(directoryPath)) {
        return '';
    }
    const allParts = [];
    function walk(currentPath) {
        const stats = statSync(currentPath);
        if (stats.isDirectory()) {
            for (const eachName of readdirSync(currentPath).sort()) {
                walk(join(currentPath, eachName));
            }
            return;
        }
        allParts.push(`${currentPath}:${stats.size}:${stats.mtimeMs}`);
    }
    walk(directoryPath);
    return allParts.join('|');
}

function planInput(packageRoot, managedRoot, overrides = {}) {
    return {
        packageRoot,
        managedRoot,
        manifestFilePath: join(managedRoot, '.claude-dev-env-manifest.json'),
        targetIdentity: 'main',
        selectedGroups: null,
        isUpdateRefresh: false,
        installGroups: GROUPS,
        collectSourceConflicts: () => [],
        detectPythonCommand: () => 'python3',
        ...overrides,
    };
}

test('planShouldInstallHooks covers full, core, and journal', () => {
    assert.equal(planShouldInstallHooks(null, GROUPS), true);
    assert.equal(planShouldInstallHooks(['core'], GROUPS), true);
    assert.equal(planShouldInstallHooks(['journal'], GROUPS), false);
});

test('buildInstallPlan is zero-write and freezes a success plan', () => {
    const { root, managedRoot, packageRoot } = sandbox();
    try {
        writeFileSync(join(managedRoot, 'settings.json'), '{"hooks":{}}\n');
        writeFileSync(
            join(managedRoot, '.claude-dev-env-manifest.json'),
            JSON.stringify({ files: ['a'], skills: ['a'] }) + '\n',
        );
        const before = treeStamp(managedRoot) + '//' + treeStamp(packageRoot);
        const plan = buildInstallPlan(planInput(packageRoot, managedRoot));
        assert.equal(plan.pythonCommand, 'python3');
        assert.equal(plan.shouldInstallHooks, true);
        assert.equal(plan.shouldPurgeBeforeReinstall, false);
        assert.deepEqual(plan.priorManifest.skills, ['a']);
        assert.ok(Object.isFrozen(plan));
        assert.equal(treeStamp(managedRoot) + '//' + treeStamp(packageRoot), before);
    } finally {
        rmSync(root, { recursive: true, force: true });
    }
});

test('preflight fails closed without writing for conflicts, python, and bad root', () => {
    const { root, managedRoot, packageRoot } = sandbox();
    try {
        writeFileSync(join(managedRoot, 'marker.txt'), 'keep\n');
        const before = treeStamp(managedRoot);
        assert.throws(
            () => buildInstallPlan(planInput(packageRoot, managedRoot, {
                isUpdateRefresh: true,
                collectSourceConflicts: () => [{ statusCode: 'UU', path: 'x.md' }],
            })),
            (error) => error instanceof InstallPlanPreflightError
                && error.code === PREFLIGHT_ERROR_CODES.SOURCE_CONFLICTS,
        );
        assert.throws(
            () => buildInstallPlan(planInput(packageRoot, managedRoot, {
                detectPythonCommand: () => null,
            })),
            (error) => error instanceof InstallPlanPreflightError
                && error.code === PREFLIGHT_ERROR_CODES.MISSING_PYTHON,
        );
        assert.equal(treeStamp(managedRoot), before);
        assert.equal(readFileSync(join(managedRoot, 'marker.txt'), 'utf8'), 'keep\n');
        const fileAsRoot = join(root, 'file-root');
        writeFileSync(fileAsRoot, 'x\n');
        assert.throws(
            () => buildInstallPlan(planInput(packageRoot, fileAsRoot)),
            (error) => error.code === PREFLIGHT_ERROR_CODES.INVALID_MANAGED_ROOT,
        );
        assert.throws(
            () => buildInstallPlan(planInput(packageRoot, '')),
            (error) => error.code === PREFLIGHT_ERROR_CODES.INVALID_MANAGED_ROOT,
        );
    } finally {
        rmSync(root, { recursive: true, force: true });
    }
});

test('settings preflight is hooks-gated; broken manifest stays tolerant', () => {
    const { root, managedRoot, packageRoot } = sandbox();
    try {
        writeFileSync(join(managedRoot, 'settings.json'), '{not-json');
        assert.throws(
            () => buildInstallPlan(planInput(packageRoot, managedRoot, { selectedGroups: ['core'] })),
            (error) => error.code === PREFLIGHT_ERROR_CODES.MALFORMED_SETTINGS,
        );
        assert.equal(
            buildInstallPlan(planInput(packageRoot, managedRoot, { selectedGroups: ['journal'] }))
                .shouldInstallHooks,
            false,
        );
        const manifestFilePath = join(managedRoot, '.claude-dev-env-manifest.json');
        writeFileSync(manifestFilePath, '{broken');
        const plan = buildInstallPlan(planInput(packageRoot, managedRoot, {
            selectedGroups: ['journal'],
            manifestFilePath,
        }));
        assert.deepEqual(plan.priorManifest, { files: null, skills: null });
        assert.deepEqual(readPriorManifestArraysFromPath(manifestFilePath), {
            files: null,
            skills: null,
        });
    } finally {
        rmSync(root, { recursive: true, force: true });
    }
});

test('update plan marks purge and lists E2 mutation kinds; journal omits hooks', () => {
    const { root, managedRoot, packageRoot } = sandbox();
    try {
        const manifestFilePath = join(managedRoot, '.claude-dev-env-manifest.json');
        writeFileSync(manifestFilePath, JSON.stringify({ files: ['a'], skills: [] }) + '\n');
        writeFileSync(join(managedRoot, 'settings.json'), '{}\n');
        const plan = buildInstallPlan(planInput(packageRoot, managedRoot, {
            manifestFilePath,
            targetIdentity: 'editor',
            isUpdateRefresh: true,
        }));
        assert.equal(plan.shouldPurgeBeforeReinstall, true);
        const allMutations = describeInstallMutations(plan);
        assert.ok(allMutations.includes('purge_managed_installation'));
        assert.ok(allMutations.includes('merge_hooks_settings'));
        assert.ok(allMutations.includes('write_manifest'));
        assert.ok(Object.isFrozen(allMutations));
        const journalMutations = describeInstallMutations(
            buildInstallPlan(planInput(packageRoot, managedRoot, { selectedGroups: ['journal'] })),
        );
        assert.ok(!journalMutations.includes('merge_hooks_settings'));
        assert.ok(journalMutations.includes('copy_content_trees'));
    } finally {
        rmSync(root, { recursive: true, force: true });
    }
});
