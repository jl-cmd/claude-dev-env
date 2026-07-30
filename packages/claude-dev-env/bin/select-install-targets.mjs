/**
 * Pure install-target selection for single-profile and selected multi-profile runs.
 *
 * Selection finishes before any filesystem mutation. The caller injects the
 * profiles root and the profile-id → directoryName map so tests need no live
 * env or disk fixtures.
 */

import { join, resolve, isAbsolute, normalize } from 'node:path';
import {
    resolveInstallRoot,
    parseExplicitTargetFromArgv,
    normalizePathForComparison,
} from './resolve-install-root.mjs';

export const MAIN_DEFAULT_TARGET_IDENTITY = 'main';
export const TARGET_IDENTITY_FLAG = '--target-identity';
export const PROFILE_FLAG = '--profile';
export const PROFILES_FLAG = '--profiles';
export const DEFAULT_PROFILES_ROOT_DIRECTORY_NAME = '.claude-profiles';
export const PROFILES_ROOT_ENVIRONMENT_VARIABLE = 'LLM_SETTINGS_PROFILES_ROOT';

/**
 * @typedef {{
 *   mode: 'main-default' | 'explicit-path' | 'profiles' | 'child-identity',
 *   allProfileIds: string[],
 *   explicitTarget: string | null,
 *   targetIdentity: string | null,
 * }} InstallTargetSelection
 */

/**
 * @typedef {{
 *   targetIdentity: string,
 *   managedRoot: string,
 *   source: string,
 *   profileId: string | null,
 * }} ResolvedInstallTarget
 */

/**
 * Parse target-selection flags from argv. Does not resolve paths.
 *
 * Rejects ambiguous combinations (path target + profile), empty profile lists,
 * and a child hop that still carries profile flags.
 *
 * @param {string[]} argv
 * @returns {InstallTargetSelection}
 */
export function parseInstallTargetSelectionFromArgv(argv) {
    const explicitTarget = parseExplicitTargetFromArgv(argv);
    const targetIdentity = parseTargetIdentityFromArgv(argv);
    const allProfileIds = parseProfileIdsFromArgv(argv);
    const hasProfileFlags = allProfileIds.length > 0
        || argvIncludesFlag(argv, PROFILE_FLAG)
        || argvIncludesFlag(argv, PROFILES_FLAG);

    if (targetIdentity && hasProfileFlags) {
        throw new Error(
            'child install hop rejects --profile/--profiles when --target-identity is set',
        );
    }
    if (explicitTarget && hasProfileFlags) {
        throw new Error(
            'ambiguous targets: use either --target <path> or --profile/--profiles, not both',
        );
    }
    if (hasProfileFlags && allProfileIds.length === 0) {
        throw new Error('--profile/--profiles requires at least one profile id');
    }
    if (allProfileIds.length > 0) {
        const allDuplicates = findDuplicateStrings(allProfileIds);
        if (allDuplicates.length > 0) {
            throw new Error(`duplicate profile id(s): ${allDuplicates.join(', ')}`);
        }
        return {
            mode: 'profiles',
            allProfileIds,
            explicitTarget: null,
            targetIdentity: null,
        };
    }
    if (targetIdentity) {
        return {
            mode: 'child-identity',
            allProfileIds: [],
            explicitTarget,
            targetIdentity,
        };
    }
    if (explicitTarget) {
        return {
            mode: 'explicit-path',
            allProfileIds: [],
            explicitTarget,
            targetIdentity: null,
        };
    }
    return {
        mode: 'main-default',
        allProfileIds: [],
        explicitTarget: null,
        targetIdentity: null,
    };
}

/**
 * Resolve the ordered list of install targets from a parsed selection.
 *
 * Dedupes on the resolved managed root path (case-insensitive on Windows) so
 * `--target` and a profile that names the same directory cannot both run.
 * Sanitizes each profile directoryName: absolute paths and `..` segments fail.
 *
 * @param {InstallTargetSelection} selection
 * @param {{
 *   homeDirectory: string,
 *   environment?: NodeJS.ProcessEnv | Record<string, string | undefined>,
 *   profilesRoot?: string | null,
 *   directoryNameByProfileId?: Record<string, string>,
 * }} options
 * @returns {ResolvedInstallTarget[]}
 */
export function resolveInstallTargets(selection, options) {
    const environment = options.environment ?? {};
    const homeDirectory = options.homeDirectory;
    const directoryNameByProfileId = options.directoryNameByProfileId ?? {};

    if (selection.mode === 'profiles') {
        const profilesRoot = resolveProfilesRootDirectory({
            homeDirectory,
            environment,
            profilesRoot: options.profilesRoot,
        });
        /** @type {ResolvedInstallTarget[]} */
        const allTargets = [];
        for (const eachProfileId of selection.allProfileIds) {
            const directoryName = directoryNameByProfileId[eachProfileId];
            if (typeof directoryName !== 'string' || !directoryName.trim()) {
                throw new Error(`unknown profile id: ${eachProfileId}`);
            }
            const safeDirectoryName = assertSafeProfileDirectoryName(directoryName);
            const managedRoot = resolve(join(profilesRoot, safeDirectoryName));
            allTargets.push({
                targetIdentity: eachProfileId,
                managedRoot,
                source: 'selected-profile',
                profileId: eachProfileId,
            });
        }
        return dedupeTargetsByManagedRoot(allTargets);
    }

    const explicitTarget = selection.mode === 'main-default' ? null : selection.explicitTarget;
    const resolution = resolveInstallRoot({
        homeDirectory,
        environment,
        explicitTarget,
    });
    const isChildIdentity = selection.mode === 'child-identity';
    return [{
        targetIdentity: isChildIdentity
            ? (selection.targetIdentity ?? MAIN_DEFAULT_TARGET_IDENTITY)
            : MAIN_DEFAULT_TARGET_IDENTITY,
        managedRoot: resolution.managedRoot,
        source: resolution.source,
        profileId: isChildIdentity ? selection.targetIdentity : null,
    }];
}

/**
 * Build the per-target ownership manifest record.
 *
 * @param {{
 *   packageName: string,
 *   packageVersion: string,
 *   targetIdentity: string,
 *   managedRoot: string,
 *   files: string[],
 *   skills?: string[] | null,
 *   installedAt?: string,
 * }} parameters
 * @returns {Record<string, unknown>}
 */
export function buildTargetManifestRecord(parameters) {
    /** @type {Record<string, unknown>} */
    const manifest = {
        package: parameters.packageName,
        version: parameters.packageVersion,
        installedAt: parameters.installedAt ?? new Date().toISOString(),
        targetIdentity: parameters.targetIdentity,
        managedRoot: parameters.managedRoot,
        files: parameters.files,
    };
    if (parameters.skills) {
        manifest.skills = parameters.skills;
    }
    return manifest;
}

/**
 * Strip target-selection flags so group parsing sees only install flags.
 *
 * @param {string[]} argv
 * @returns {string[]}
 */
export function stripTargetSelectionFlagsFromArgv(argv) {
    /** @type {string[]} */
    const remaining = [];
    for (let index = 0; index < argv.length; index += 1) {
        const token = argv[index];
        if (token === PROFILE_FLAG || token === PROFILES_FLAG || token === TARGET_IDENTITY_FLAG) {
            const value = argv[index + 1];
            if (value && !value.startsWith('--')) {
                index += 1;
            }
            continue;
        }
        if (
            token.startsWith(`${PROFILE_FLAG}=`)
            || token.startsWith(`${PROFILES_FLAG}=`)
            || token.startsWith(`${TARGET_IDENTITY_FLAG}=`)
        ) {
            continue;
        }
        if (token === '--target') {
            const value = argv[index + 1];
            if (value && !value.startsWith('--')) {
                index += 1;
            }
            continue;
        }
        if (token.startsWith('--target=')) {
            continue;
        }
        remaining.push(token);
    }
    return remaining;
}

/**
 * @param {{
 *   homeDirectory: string,
 *   environment?: NodeJS.ProcessEnv | Record<string, string | undefined>,
 *   profilesRoot?: string | null,
 * }} options
 * @returns {string}
 */
export function resolveProfilesRootDirectory(options) {
    if (typeof options.profilesRoot === 'string' && options.profilesRoot.trim()) {
        return resolve(options.profilesRoot);
    }
    const environment = options.environment ?? {};
    const fromEnvironment = environment[PROFILES_ROOT_ENVIRONMENT_VARIABLE];
    if (typeof fromEnvironment === 'string' && fromEnvironment.trim()) {
        return resolve(fromEnvironment.trim());
    }
    return resolve(join(options.homeDirectory, DEFAULT_PROFILES_ROOT_DIRECTORY_NAME));
}

/**
 * Reject absolute and parent-hop directoryName values on every host platform.
 *
 * Host `isAbsolute` plus Windows drive and UNC spellings so a Linux CI host
 * still rejects a profile map that smuggles an absolute Windows path.
 *
 * @param {string} directoryName
 * @returns {string}
 */
export function assertSafeProfileDirectoryName(directoryName) {
    const trimmed = directoryName.trim();
    if (!trimmed) {
        throw new Error('profile directoryName must be a non-empty relative name');
    }
    const hasWindowsDriveAbsolute = /^[A-Za-z]:[\\/]/.test(trimmed);
    const hasWindowsUncAbsolute = trimmed.startsWith('\\\\') || trimmed.startsWith('//');
    if (isAbsolute(trimmed) || hasWindowsDriveAbsolute || hasWindowsUncAbsolute) {
        throw new Error(`profile directoryName must be relative, got absolute: ${trimmed}`);
    }
    const allSegments = normalize(trimmed).split(/[/\\]/).filter(Boolean);
    if (allSegments.some((eachSegment) => eachSegment === '..')) {
        throw new Error(`profile directoryName rejects parent segments: ${trimmed}`);
    }
    return trimmed;
}

/**
 * @param {string[]} argv
 * @returns {string[]}
 */
function parseProfileIdsFromArgv(argv) {
    /** @type {string[]} */
    const allProfileIds = [];
    for (let index = 0; index < argv.length; index += 1) {
        const token = argv[index];
        if (token === PROFILE_FLAG || token === PROFILES_FLAG) {
            const value = argv[index + 1];
            if (!value || value.startsWith('--')) {
                throw new Error(`${token} requires a comma-separated profile id list`);
            }
            allProfileIds.push(...splitProfileIdList(value));
            index += 1;
            continue;
        }
        if (token.startsWith(`${PROFILE_FLAG}=`) || token.startsWith(`${PROFILES_FLAG}=`)) {
            const prefix = token.startsWith(`${PROFILE_FLAG}=`)
                ? `${PROFILE_FLAG}=`
                : `${PROFILES_FLAG}=`;
            const value = token.slice(prefix.length);
            if (!value) {
                throw new Error(`${prefix.slice(0, -1)} requires a comma-separated profile id list`);
            }
            allProfileIds.push(...splitProfileIdList(value));
        }
    }
    return allProfileIds;
}

/**
 * @param {string[]} argv
 * @returns {string | null}
 */
function parseTargetIdentityFromArgv(argv) {
    for (let index = 0; index < argv.length; index += 1) {
        const token = argv[index];
        if (token === TARGET_IDENTITY_FLAG) {
            const value = argv[index + 1];
            if (!value || value.startsWith('--')) {
                throw new Error(`${TARGET_IDENTITY_FLAG} requires an identity argument`);
            }
            return value;
        }
        if (token.startsWith(`${TARGET_IDENTITY_FLAG}=`)) {
            const value = token.slice(`${TARGET_IDENTITY_FLAG}=`.length);
            if (!value) {
                throw new Error(`${TARGET_IDENTITY_FLAG} requires an identity argument`);
            }
            return value;
        }
    }
    return null;
}

/**
 * @param {string} rawList
 * @returns {string[]}
 */
function splitProfileIdList(rawList) {
    return rawList
        .split(',')
        .map((eachId) => eachId.trim())
        .filter((eachId) => eachId.length > 0);
}

/**
 * @param {string[]} argv
 * @param {string} flagName
 * @returns {boolean}
 */
function argvIncludesFlag(argv, flagName) {
    return argv.some(
        (eachToken) => eachToken === flagName || eachToken.startsWith(`${flagName}=`),
    );
}

/**
 * @param {string[]} allValues
 * @returns {string[]}
 */
function findDuplicateStrings(allValues) {
    const seen = new Set();
    const allDuplicates = new Set();
    for (const eachValue of allValues) {
        if (seen.has(eachValue)) {
            allDuplicates.add(eachValue);
        }
        seen.add(eachValue);
    }
    return [...allDuplicates];
}

/**
 * @param {ResolvedInstallTarget[]} allTargets
 * @returns {ResolvedInstallTarget[]}
 */
function dedupeTargetsByManagedRoot(allTargets) {
    const seenRootByKey = new Map();
    /** @type {ResolvedInstallTarget[]} */
    const uniqueTargets = [];
    for (const eachTarget of allTargets) {
        const rootKey = normalizePathForComparison(eachTarget.managedRoot);
        if (seenRootByKey.has(rootKey)) {
            const priorIdentity = seenRootByKey.get(rootKey);
            throw new Error(
                `duplicate managed root for targets ${priorIdentity} and ${eachTarget.targetIdentity}: ${eachTarget.managedRoot}`,
            );
        }
        seenRootByKey.set(rootKey, eachTarget.targetIdentity);
        uniqueTargets.push(eachTarget);
    }
    return uniqueTargets;
}
