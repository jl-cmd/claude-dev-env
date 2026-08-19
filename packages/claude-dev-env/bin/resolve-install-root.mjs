/**
 * Pure install-root resolver for the claude-dev-env installer.
 *
 * Precedence (highest first):
 *   1. explicitTarget — CLI --target or a caller-supplied absolute path
 *   2. CLAUDE_CONFIG_DIR from the environment (profile isolation root)
 *   3. join(homeDirectory, '.claude') — main-profile default
 *
 * CLAUDE_HOME is never honored as a profile root.
 */

import { homedir } from 'node:os';
import { join, normalize, resolve, sep } from 'node:path';
import {
    MYPY_INI_FILE_NAME,
    CODEX_HOME_ENVIRONMENT_VARIABLE,
    DEFAULT_CODEX_DIRECTORY_NAME,
    CODEX_RULES_DIRECTORY_NAME,
    DEFAULT_CURSOR_DIRECTORY_NAME,
    CURSOR_RULES_DIRECTORY_NAME,
} from './install-constants.mjs';

export const CLAUDE_CONFIG_DIR_ENVIRONMENT_VARIABLE = 'CLAUDE_CONFIG_DIR';
export const DEFAULT_CLAUDE_DIRECTORY_NAME = '.claude';
export const MANIFEST_FILE_NAME = '.claude-dev-env-manifest.json';

/**
 * @typedef {{
 *   explicitTarget?: string | null,
 *   environment?: NodeJS.ProcessEnv | Record<string, string | undefined>,
 *   homeDirectory?: string,
 * }} ResolveInstallRootOptions
 */

/**
 * @typedef {{
 *   managedRoot: string,
 *   source: 'explicit-target' | 'claude-config-dir' | 'default-home',
 *   homeDirectory: string,
 *   manifestFilePath: string,
 *   mypyIniInstallPath: string,
 *   allDeclaredExternalPaths: string[],
 *   allDeclaredExternalDirectories: string[],
 *   codexRulesInstallDirectory: string,
 *   cursorInstallDirectory: string,
 *   cursorRulesInstallDirectory: string,
 * }} InstallRootResolution
 */

/**
 * Resolve the managed install root and declared external destinations.
 *
 * @param {ResolveInstallRootOptions} [options]
 * @returns {InstallRootResolution}
 */
export function resolveInstallRoot(options = {}) {
    const homeDirectory = options.homeDirectory ?? homedir();
    const environment = options.environment ?? process.env;
    const explicitTarget = normalizeOptionalPath(options.explicitTarget);

    /** @type {InstallRootResolution['source']} */
    let source;
    /** @type {string} */
    let managedRoot;

    if (explicitTarget) {
        managedRoot = explicitTarget;
        source = 'explicit-target';
    } else {
        const configDir = normalizeOptionalPath(
            environment[CLAUDE_CONFIG_DIR_ENVIRONMENT_VARIABLE],
        );
        if (configDir) {
            managedRoot = configDir;
            source = 'claude-config-dir';
        } else {
            managedRoot = resolve(join(homeDirectory, DEFAULT_CLAUDE_DIRECTORY_NAME));
            source = 'default-home';
        }
    }

    const mypyIniInstallPath = resolve(join(homeDirectory, MYPY_INI_FILE_NAME));
    const codexHomeDirectory = normalizeOptionalPath(
        environment[CODEX_HOME_ENVIRONMENT_VARIABLE],
    ) ?? resolve(join(homeDirectory, DEFAULT_CODEX_DIRECTORY_NAME));
    const codexRulesInstallDirectory = resolve(
        join(codexHomeDirectory, CODEX_RULES_DIRECTORY_NAME),
    );
    const cursorInstallDirectory = resolve(
        join(homeDirectory, DEFAULT_CURSOR_DIRECTORY_NAME),
    );
    const cursorRulesInstallDirectory = resolve(
        join(cursorInstallDirectory, CURSOR_RULES_DIRECTORY_NAME),
    );
    return {
        managedRoot,
        source,
        homeDirectory: resolve(homeDirectory),
        manifestFilePath: join(managedRoot, MANIFEST_FILE_NAME),
        mypyIniInstallPath,
        allDeclaredExternalPaths: [mypyIniInstallPath],
        allDeclaredExternalDirectories: [codexRulesInstallDirectory, cursorInstallDirectory],
        codexRulesInstallDirectory,
        cursorInstallDirectory,
        cursorRulesInstallDirectory,
    };
}

/**
 * True when candidatePath is the managed root or a descendant of it.
 * Requires a separator boundary so `.claude-extra` is not inside `.claude`.
 *
 * @param {string} candidatePath
 * @param {string} managedRoot
 * @returns {boolean}
 */
export function isPathWithinManagedRoot(candidatePath, managedRoot) {
    if (!candidatePath || !managedRoot) {
        return false;
    }
    const normalizedCandidate = normalizePathForComparison(candidatePath);
    const normalizedRoot = normalizePathForComparison(managedRoot);
    if (normalizedCandidate === normalizedRoot) {
        return true;
    }
    const rootWithSeparator = normalizedRoot.endsWith('/')
        ? normalizedRoot
        : `${normalizedRoot}/`;
    return normalizedCandidate.startsWith(rootWithSeparator);
}

/**
 * True when a write destination is allowed: inside the managed root, the
 * home-directory `.mypy.ini`, a file under the Codex rules directory, or a file
 * under the Cursor rules directory.
 *
 * @param {string} candidatePath
 * @param {InstallRootResolution} resolution
 * @returns {boolean}
 */
export function isAllowedInstallDestination(candidatePath, resolution) {
    if (isPathWithinManagedRoot(candidatePath, resolution.managedRoot)) {
        return true;
    }
    const normalizedCandidate = normalizePathForComparison(candidatePath);
    if (resolution.allDeclaredExternalPaths.some(
        (eachExternalPath) => normalizePathForComparison(eachExternalPath) === normalizedCandidate,
    )) {
        return true;
    }
    return (resolution.allDeclaredExternalDirectories ?? []).some(
        (eachExternalDirectory) => isPathWithinManagedRoot(candidatePath, eachExternalDirectory),
    );
}

/**
 * Parse an explicit --target value from argv tokens.
 *
 * @param {string[]} argv
 * @returns {string | null}
 */
export function parseExplicitTargetFromArgv(argv) {
    for (let index = 0; index < argv.length; index += 1) {
        const token = argv[index];
        if (token === '--target') {
            const targetPath = argv[index + 1];
            if (!targetPath || targetPath.startsWith('--')) {
                throw new Error('--target requires a path argument');
            }
            return targetPath;
        }
        if (token.startsWith('--target=')) {
            const targetPath = token.slice('--target='.length);
            if (!targetPath) {
                throw new Error('--target requires a path argument');
            }
            return targetPath;
        }
    }
    return null;
}

/**
 * @param {string | null | undefined} maybePath
 * @returns {string | null}
 */
function normalizeOptionalPath(maybePath) {
    if (typeof maybePath !== 'string') {
        return null;
    }
    const trimmed = maybePath.trim();
    if (!trimmed) {
        return null;
    }
    return resolve(trimmed);
}

/**
 * Compare-key for a filesystem path: resolve, forward-slash, case-fold on win32.
 *
 * @param {string} filesystemPath
 * @returns {string}
 */
export function normalizePathForComparison(filesystemPath) {
    const resolved = resolve(normalize(filesystemPath));
    let withForwardSlashes = resolved.split(sep).join('/');
    if (process.platform === 'win32') {
        withForwardSlashes = withForwardSlashes.toLowerCase();
    }
    if (withForwardSlashes.length > 1 && withForwardSlashes.endsWith('/')) {
        withForwardSlashes = withForwardSlashes.slice(0, -1);
    }
    return withForwardSlashes;
}
