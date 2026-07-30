/**
 * Disposable isolation roots for fresh-session harness runs.
 *
 * Every profile run gets its own HOME, USERPROFILE, CLAUDE_CONFIG_DIR, and
 * GIT_CONFIG_GLOBAL under a throwaway tree so live ~/.claude and
 * ~/.claude-profiles stay untouched.
 */

import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

export const ALL_PROFILE_IDS = Object.freeze(['main', 'editor', 'mel']);

/**
 * @typedef {{
 *   runRoot: string,
 *   homeDirectory: string,
 *   userProfileDirectory: string,
 *   gitConfigGlobalPath: string,
 *   profilesRoot: string,
 *   evidenceRoot: string,
 *   profileRootById: Record<string, string>,
 * }} DisposableRunRoots
 */

/**
 * Create a disposable run tree for the named profiles.
 *
 * @param {{profileIds?: string[], prefix?: string}} [options]
 * @returns {DisposableRunRoots}
 */
export function createDisposableRunRoots(options = {}) {
    const profileIds = options.profileIds ?? [...ALL_PROFILE_IDS];
    const prefix = options.prefix ?? 'fresh-session-';
    const runRoot = mkdtempSync(join(tmpdir(), prefix));
    const homeDirectory = join(runRoot, 'home');
    const userProfileDirectory = homeDirectory;
    const gitConfigGlobalPath = join(runRoot, 'gitconfig-global');
    const profilesRoot = join(runRoot, 'claude-profiles');
    const evidenceRoot = join(runRoot, 'evidence');

    mkdirSync(homeDirectory, { recursive: true });
    mkdirSync(profilesRoot, { recursive: true });
    mkdirSync(evidenceRoot, { recursive: true });
    writeFileSync(gitConfigGlobalPath, '[safe]\n\tdirectory = *\n', 'utf8');

    /** @type {Record<string, string>} */
    const profileRootById = {};
    for (const eachProfileId of profileIds) {
        const profileRoot = join(profilesRoot, eachProfileId);
        mkdirSync(profileRoot, { recursive: true });
        profileRootById[eachProfileId] = profileRoot;
    }

    return {
        runRoot,
        homeDirectory,
        userProfileDirectory,
        gitConfigGlobalPath,
        profilesRoot,
        evidenceRoot,
        profileRootById,
    };
}

/**
 * Build the environment block for one profile launch.
 *
 * @param {DisposableRunRoots} roots
 * @param {string} profileId
 * @param {NodeJS.ProcessEnv} [baseEnvironment]
 * @returns {NodeJS.ProcessEnv}
 */
export function buildIsolatedProfileEnvironment(roots, profileId, baseEnvironment = process.env) {
    const profileRoot = roots.profileRootById[profileId];
    if (!profileRoot) {
        throw new Error(`Unknown profile id for disposable roots: ${profileId}`);
    }
    return {
        ...baseEnvironment,
        HOME: roots.homeDirectory,
        USERPROFILE: roots.userProfileDirectory,
        CLAUDE_CONFIG_DIR: profileRoot,
        GIT_CONFIG_GLOBAL: roots.gitConfigGlobalPath,
        // Block accidental use of live profile roots.
        CLAUDE_PROFILES_ROOT: roots.profilesRoot,
    };
}

/**
 * Remove a disposable run tree. Live profile paths are never accepted.
 *
 * @param {string} runRoot
 * @returns {void}
 */
export function removeDisposableRunRoots(runRoot) {
    if (!runRoot || typeof runRoot !== 'string') {
        throw new Error('removeDisposableRunRoots requires a run root path');
    }
    const normalized = runRoot.replace(/\\/g, '/').toLowerCase();
    const tempRoot = tmpdir().replace(/\\/g, '/').toLowerCase();
    const isUnderTemp = normalized.startsWith(tempRoot);
    const isFreshSessionTree = normalized.includes('/fresh-session-');
    if (!isUnderTemp && !isFreshSessionTree) {
        throw new Error(`Refusing to remove non-disposable path: ${runRoot}`);
    }
    rmSync(runRoot, { recursive: true, force: true });
}
