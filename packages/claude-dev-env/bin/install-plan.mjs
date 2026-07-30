/**
 * Read-only installation plan and preflight for claude-dev-env.
 *
 * Builds a frozen plan before any write. E2 consumes it through the install
 * executor. Plan construction performs zero writes.
 *
 * ::
 *
 *     plan = buildInstallPlan({ packageRoot, managedRoot, ... })
 *     // preflight failed: InstallPlanPreflightError, disk unchanged
 *     // ok: frozen plan with pythonCommand, priorManifest, mutation kinds
 *
 * Manifest parse stays tolerant. Settings JSON is checked only when hooks install.
 */

import { existsSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { SETTINGS_FILE_NAME } from './install-constants.mjs';

export const PREFLIGHT_ERROR_CODES = Object.freeze({
    SOURCE_CONFLICTS: 'source_conflicts',
    MISSING_PYTHON: 'missing_python',
    MALFORMED_SETTINGS: 'malformed_settings',
    INVALID_MANAGED_ROOT: 'invalid_managed_root',
});

export const MISSING_PYTHON_ERROR_MESSAGE =
    'ERROR: No usable Python 3 found. Install Python 3.8+ from python.org and ensure py, python3, or python is on PATH. On Windows the Microsoft Store python.exe alias is rejected because it cannot run hooks.';

export const MALFORMED_SETTINGS_ERROR_MESSAGE =
    'ERROR: settings.json is malformed JSON. Fix it and rerun.';

export const SETTINGS_NOT_OBJECT_ERROR_MESSAGE =
    'ERROR: settings.json holds a value other than a JSON object. Fix it and rerun.';

const MANIFEST_FILES_KEY = 'files';
const MANIFEST_SKILLS_KEY = 'skills';

/**
 * Preflight failure that leaves the managed installation untouched.
 */
export class InstallPlanPreflightError extends Error {
    /**
     * @param {string} message
     * @param {{ code: string, conflicts?: Array<{ statusCode: string, path: string }> }} details
     */
    constructor(message, details) {
        super(message);
        this.name = 'InstallPlanPreflightError';
        this.code = details.code;
        this.conflicts = details.conflicts || [];
    }
}

/**
 * Whether the selected groups install hook files and merge settings.
 *
 * @param {string[]|null} selectedGroups
 * @param {Record<string, object>} installGroups
 * @returns {boolean}
 */
export function planShouldInstallHooks(selectedGroups, installGroups) {
    if (!selectedGroups) {
        return true;
    }
    const allActiveGroups = selectedGroups.map((eachName) => installGroups[eachName]).filter(Boolean);
    if (allActiveGroups.some((eachGroup) => eachGroup.includeAllHooks)) {
        return true;
    }
    return allActiveGroups.some(
        (eachGroup) => Array.isArray(eachGroup.includeHookFiles) && eachGroup.includeHookFiles.length > 0,
    );
}

/**
 * Read prior manifest lists without throwing on bad JSON.
 *
 * @param {string} manifestFilePath
 * @param {{ existsSync?: typeof existsSync, readFileSync?: typeof readFileSync }} [io]
 * @returns {{ files: string[]|null, skills: string[]|null }}
 */
export function readPriorManifestArraysFromPath(manifestFilePath, io = {}) {
    const exists = io.existsSync || existsSync;
    const readFile = io.readFileSync || readFileSync;
    const missingRecord = { files: null, skills: null };
    if (!manifestFilePath || !exists(manifestFilePath)) {
        return missingRecord;
    }
    try {
        const priorManifest = JSON.parse(readFile(manifestFilePath, 'utf8'));
        return {
            files: Array.isArray(priorManifest[MANIFEST_FILES_KEY]) ? priorManifest[MANIFEST_FILES_KEY] : null,
            skills: Array.isArray(priorManifest[MANIFEST_SKILLS_KEY]) ? priorManifest[MANIFEST_SKILLS_KEY] : null,
        };
    } catch {
        return missingRecord;
    }
}

/**
 * Fail when managedRoot is empty or points at a non-directory path.
 *
 * @param {string} managedRoot
 * @param {{ existsSync?: typeof existsSync, statSync?: typeof statSync }} [io]
 * @returns {void}
 */
export function preflightManagedRoot(managedRoot, io = {}) {
    const exists = io.existsSync || existsSync;
    const stat = io.statSync || statSync;
    if (typeof managedRoot !== 'string' || managedRoot.trim() === '') {
        throw new InstallPlanPreflightError(
            'ERROR: install managed root is empty or missing.',
            { code: PREFLIGHT_ERROR_CODES.INVALID_MANAGED_ROOT },
        );
    }
    if (!exists(managedRoot)) {
        return;
    }
    let stats;
    try {
        stats = stat(managedRoot);
    } catch {
        throw new InstallPlanPreflightError(
            `ERROR: install managed root is not readable: ${managedRoot}`,
            { code: PREFLIGHT_ERROR_CODES.INVALID_MANAGED_ROOT },
        );
    }
    if (!stats.isDirectory()) {
        throw new InstallPlanPreflightError(
            `ERROR: install managed root is not a directory: ${managedRoot}`,
            { code: PREFLIGHT_ERROR_CODES.INVALID_MANAGED_ROOT },
        );
    }
}

/**
 * Parse existing settings.json when the run will merge hooks.
 *
 * @param {string} settingsPath
 * @param {boolean} shouldInstallHooks
 * @param {{ existsSync?: typeof existsSync, readFileSync?: typeof readFileSync }} [io]
 * @returns {void}
 */
export function preflightSettingsIfNeeded(settingsPath, shouldInstallHooks, io = {}) {
    if (!shouldInstallHooks) {
        return;
    }
    const exists = io.existsSync || existsSync;
    const readFile = io.readFileSync || readFileSync;
    if (!exists(settingsPath)) {
        return;
    }
    const raw = readFile(settingsPath, 'utf8').trim();
    if (!raw) {
        return;
    }
    let settings;
    try {
        settings = JSON.parse(raw);
    } catch {
        throw new InstallPlanPreflightError(MALFORMED_SETTINGS_ERROR_MESSAGE, {
            code: PREFLIGHT_ERROR_CODES.MALFORMED_SETTINGS,
        });
    }
    if (!settings || typeof settings !== 'object' || Array.isArray(settings)) {
        throw new InstallPlanPreflightError(SETTINGS_NOT_OBJECT_ERROR_MESSAGE, {
            code: PREFLIGHT_ERROR_CODES.MALFORMED_SETTINGS,
        });
    }
}

/**
 * Build a frozen installation plan after read-only preflight.
 *
 * @param {{
 *   packageRoot: string,
 *   managedRoot: string,
 *   manifestFilePath: string,
 *   targetIdentity: string,
 *   selectedGroups: string[]|null,
 *   isUpdateRefresh: boolean,
 *   installGroups: Record<string, object>,
 *   collectSourceConflicts: (packageRoot: string) => Array<{ statusCode: string, path: string }>,
 *   detectPythonCommand: () => string|null,
 *   packageName?: string,
 *   io?: {
 *     existsSync?: typeof existsSync,
 *     readFileSync?: typeof readFileSync,
 *     statSync?: typeof statSync,
 *   },
 * }} input
 * @returns {Readonly<object>}
 */
export function buildInstallPlan(input) {
    const io = input.io || {};
    const exists = io.existsSync || existsSync;
    const packageName = input.packageName || 'claude-dev-env';

    preflightManagedRoot(input.managedRoot, io);

    const priorManifest = readPriorManifestArraysFromPath(input.manifestFilePath, io);
    const shouldInstallHooks = planShouldInstallHooks(input.selectedGroups, input.installGroups);
    const settingsPath = join(input.managedRoot, SETTINGS_FILE_NAME);

    const allConflicts = input.collectSourceConflicts(input.packageRoot);
    if (allConflicts.length > 0) {
        const conflictLines = allConflicts
            .map((eachConflict) => `  ${eachConflict.statusCode} ${eachConflict.path}`)
            .join('\n');
        throw new InstallPlanPreflightError(
            `\nERROR: ${packageName} source has unmerged conflicts under ${input.packageRoot}:\n\n`
            + `${conflictLines}\n\n`
            + 'Resolve the conflicts in the package source before running the installer.\n'
            + 'Installing from a conflicted source can copy stale or broken files into ~/.claude/.\n',
            {
                code: PREFLIGHT_ERROR_CODES.SOURCE_CONFLICTS,
                conflicts: allConflicts,
            },
        );
    }

    const pythonCommand = input.detectPythonCommand();
    if (!pythonCommand) {
        throw new InstallPlanPreflightError(MISSING_PYTHON_ERROR_MESSAGE, {
            code: PREFLIGHT_ERROR_CODES.MISSING_PYTHON,
        });
    }

    preflightSettingsIfNeeded(settingsPath, shouldInstallHooks, io);

    const isUpdateRefresh = Boolean(input.isUpdateRefresh);
    const shouldPurgeBeforeReinstall = isUpdateRefresh
        && !input.selectedGroups
        && exists(input.manifestFilePath);

    return Object.freeze({
        packageRoot: input.packageRoot,
        managedRoot: input.managedRoot,
        manifestFilePath: input.manifestFilePath,
        targetIdentity: input.targetIdentity,
        selectedGroups: input.selectedGroups,
        isUpdateRefresh,
        shouldPurgeBeforeReinstall,
        pythonCommand,
        shouldInstallHooks,
        priorManifest: Object.freeze({
            files: priorManifest.files,
            skills: priorManifest.skills,
        }),
        settingsPath,
        packageName,
    });
}

/**
 * High-level mutation kinds the executor applies for this plan (E2 surface).
 *
 * @param {{
 *   shouldPurgeBeforeReinstall: boolean,
 *   shouldInstallHooks: boolean,
 *   selectedGroups: string[]|null,
 * }} plan
 * @returns {ReadonlyArray<string>}
 */
export function describeInstallMutations(plan) {
    /** @type {string[]} */
    const allMutations = [];
    if (plan.shouldPurgeBeforeReinstall) {
        allMutations.push('purge_managed_installation');
    }
    allMutations.push('ensure_managed_root', 'copy_content_trees', 'copy_skills');
    if (plan.shouldInstallHooks) {
        allMutations.push(
            'copy_hook_files',
            'merge_hooks_settings',
            'install_git_hooks',
            'install_mypy_ini',
        );
    }
    allMutations.push('copy_claude_hub');
    if (!plan.selectedGroups) {
        allMutations.push('prune_retired_and_stale');
    }
    allMutations.push('write_manifest');
    return Object.freeze(allMutations);
}
