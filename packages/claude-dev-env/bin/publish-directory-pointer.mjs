/**
 * Publish a Claude Code lookup path as a directory pointer to the agents home.
 *
 * Skills and agents live under the agents home. Claude Code still discovers
 * them at `managedRoot/skills` and `managedRoot/agents`, so the installer
 * writes those two paths as directory pointers (a POSIX symlink, or a Windows
 * junction). One helper owns the create, refresh, and relocate steps.
 */

import {
    existsSync,
    lstatSync,
    mkdirSync,
    readlinkSync,
    readdirSync,
    renameSync,
    rmSync,
    symlinkSync,
    unlinkSync,
} from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { normalizePathForComparison } from './resolve-install-root.mjs';

export const DIRECTORY_POINTER_TYPE_JUNCTION = 'junction';
export const DIRECTORY_POINTER_TYPE_DIR = 'dir';
export const POINTER_ACTION_ALREADY_POINTING = 'already-pointing';
export const POINTER_ACTION_CREATED = 'created';

/**
 * Directory-pointer type this host uses.
 *
 * Windows receives a junction so the pointer works without Developer Mode.
 * POSIX receives a directory symlink.
 *
 * @param {string} [platform]
 * @returns {typeof DIRECTORY_POINTER_TYPE_JUNCTION | typeof DIRECTORY_POINTER_TYPE_DIR}
 */
export function directoryPointerTypeForPlatform(platform = process.platform) {
    return platform === 'win32'
        ? DIRECTORY_POINTER_TYPE_JUNCTION
        : DIRECTORY_POINTER_TYPE_DIR;
}

/**
 * Report whether pointerPath is a directory pointer whose target is targetPath.
 *
 * @param {string} pointerPath
 * @param {string} targetPath
 * @returns {boolean}
 */
export function isDirectoryPointerTo(pointerPath, targetPath) {
    const pathKind = readPathKind(pointerPath);
    if (pathKind !== 'symlink') {
        return false;
    }
    const linkTarget = readlinkSync(pointerPath);
    const resolvedLinkTarget = resolve(dirname(pointerPath), linkTarget);
    return normalizePathForComparison(resolvedLinkTarget)
        === normalizePathForComparison(resolve(targetPath));
}

/**
 * Make pointerPath a directory pointer to targetPath.
 *
 * A real directory already sitting at the lookup path is merged into the
 * target, then the pointer is written. A pointer that already aims at the
 * target is left in place.
 *
 * @param {string} pointerPath Claude Code lookup path (for example `~/.claude/skills`).
 * @param {string} targetPath Canonical directory (for example `~/.agents/skills`).
 * @param {{ pointerType?: string }} [options]
 * @returns {{ action: string, pointerPath: string, targetPath: string }}
 */
export function ensureDirectoryPointer(pointerPath, targetPath, options = {}) {
    const pointerType = options.pointerType ?? directoryPointerTypeForPlatform();
    const resolvedTarget = resolve(targetPath);
    const resolvedPointer = resolve(pointerPath);
    mkdirSync(resolvedTarget, { recursive: true });

    if (isDirectoryPointerTo(resolvedPointer, resolvedTarget)) {
        return {
            action: POINTER_ACTION_ALREADY_POINTING,
            pointerPath: resolvedPointer,
            targetPath: resolvedTarget,
        };
    }

    const pathKind = readPathKind(resolvedPointer);
    if (pathKind === 'symlink') {
        unlinkSync(resolvedPointer);
    } else if (pathKind === 'directory') {
        mergeDirectoryContents(resolvedPointer, resolvedTarget);
        rmSync(resolvedPointer, { recursive: true, force: true });
    } else if (pathKind === 'file') {
        throw new Error(
            `Cannot publish a directory pointer: ${resolvedPointer} is a file`,
        );
    }

    mkdirSync(dirname(resolvedPointer), { recursive: true });
    symlinkSync(resolvedTarget, resolvedPointer, pointerType);
    return {
        action: POINTER_ACTION_CREATED,
        pointerPath: resolvedPointer,
        targetPath: resolvedTarget,
    };
}

/**
 * Remove a directory pointer when it aims at the expected target.
 *
 * @param {string} pointerPath
 * @param {string} targetPath
 * @returns {boolean} True when this call unlinked the pointer.
 */
export function unlinkDirectoryPointerIfMatch(pointerPath, targetPath) {
    if (!isDirectoryPointerTo(pointerPath, targetPath)) {
        return false;
    }
    unlinkSync(pointerPath);
    return true;
}

/**
 * @param {string} absolutePath
 * @returns {'missing' | 'symlink' | 'directory' | 'file' | 'other'}
 */
function readPathKind(absolutePath) {
    let stats;
    try {
        stats = lstatSync(absolutePath);
    } catch (readError) {
        if (readError && readError.code === 'ENOENT') {
            return 'missing';
        }
        throw readError;
    }
    if (stats.isSymbolicLink()) {
        return 'symlink';
    }
    if (stats.isDirectory()) {
        return 'directory';
    }
    if (stats.isFile()) {
        return 'file';
    }
    return 'other';
}

/**
 * Move unique entries from sourceDirectory into destinationDirectory.
 *
 * An entry that already exists at the destination stays there. Nested
 * directories merge the same way. Leftover source entries are removed by the
 * caller with the source directory.
 *
 * @param {string} sourceDirectory
 * @param {string} destinationDirectory
 * @returns {void}
 */
function mergeDirectoryContents(sourceDirectory, destinationDirectory) {
    mkdirSync(destinationDirectory, { recursive: true });
    const allEntries = readdirSync(sourceDirectory, { withFileTypes: true });
    for (const eachEntry of allEntries) {
        const sourceChild = join(sourceDirectory, eachEntry.name);
        const destinationChild = join(destinationDirectory, eachEntry.name);
        if (!existsSync(destinationChild)) {
            renameSync(sourceChild, destinationChild);
            continue;
        }
        if (eachEntry.isDirectory() && readPathKind(destinationChild) === 'directory') {
            mergeDirectoryContents(sourceChild, destinationChild);
        }
    }
}
