import {
    existsSync,
    lstatSync,
    readdirSync,
    readlinkSync,
    rmSync,
    unlinkSync,
} from 'node:fs';
import { isAbsolute, join, resolve, sep } from 'node:path';

export const RETIRED_PSTACK_STORE_DIRECTORY_NAME = 'pstack';

/**
 * Name the store directory the retired pstack installer kept its releases in.
 *
 * @param {string} managedRoot The managed Claude root.
 * @returns {string} The retired store root.
 */
export function retiredPstackStoreRoot(managedRoot) {
    return join(managedRoot, RETIRED_PSTACK_STORE_DIRECTORY_NAME);
}

function pointsIntoStore(entryPath, storeRoot) {
    let entryStats;
    try {
        entryStats = lstatSync(entryPath);
    } catch {
        return false;
    }
    if (!entryStats.isSymbolicLink()) return false;
    let linkTarget;
    try {
        linkTarget = readlinkSync(entryPath);
    } catch {
        return false;
    }
    const resolvedTarget = isAbsolute(linkTarget)
        ? resolve(linkTarget)
        : resolve(join(entryPath, '..', linkTarget));
    return resolvedTarget.startsWith(resolve(storeRoot) + sep);
}

function removePointersUnder(skillsRoot, storeRoot) {
    if (!skillsRoot || !existsSync(skillsRoot)) return [];
    const removedPointerPaths = [];
    for (const entryName of readdirSync(skillsRoot)) {
        const entryPath = join(skillsRoot, entryName);
        if (!pointsIntoStore(entryPath, storeRoot)) continue;
        unlinkSync(entryPath);
        removedPointerPaths.push(entryPath);
    }
    return removedPointerPaths;
}

/**
 * Remove the retired pstack installation this package used to publish.
 *
 * The retired installer kept a release store under the managed root and
 * published one symlink per skill into it. Claude Code loads the `pstack`
 * pointer as a skills-directory plugin, so a pointer left behind collides with
 * the `pstack@pstack-claude` plugin the marketplace now installs.
 *
 * Only a symlink whose target resolves inside the store is removed, so a
 * directory a user keeps under a similar name stays in place. A pointer left
 * dangling by a store someone already deleted is removed too.
 *
 * @param {object} roots An `InstallRootResolution`.
 * @returns {{removedPointerPaths: string[], removedStorePath: string|null}} What this call removed.
 */
export function removeRetiredPstackInstallation(roots) {
    const storeRoot = retiredPstackStoreRoot(roots.managedRoot);
    const allSkillsRoots = [...new Set([
        roots.skillsLookupDirectory,
        roots.skillsInstallDirectory,
    ])];
    const removedPointerPaths = allSkillsRoots
        .flatMap(skillsRoot => removePointersUnder(skillsRoot, storeRoot));
    if (!existsSync(storeRoot)) {
        return { removedPointerPaths, removedStorePath: null };
    }
    rmSync(storeRoot, { recursive: true, force: true });
    return { removedPointerPaths, removedStorePath: storeRoot };
}
