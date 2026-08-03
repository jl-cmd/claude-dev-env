/**
 * Install and update transaction journal for claude-dev-env.
 *
 * Captures the prior managed installation, runs mutations, and restores
 * settings, manifest, managed files, and core.hooksPath when any phase fails.
 *
 * ::
 *
 *     const snapshot = capturePriorInstallSnapshot({ managedRoot, ... })
 *     try {
 *       runWithInstallTransaction({ snapshot, faultPhase, runMutations })
 *     } catch {
 *       // prior installation restored
 *     }
 */

import {
    copyFileSync,
    existsSync,
    lstatSync,
    mkdirSync,
    mkdtempSync,
    readdirSync,
    readlinkSync,
    rmdirSync,
    rmSync,
    symlinkSync,
    unlinkSync,
    writeFileSync,
} from 'node:fs';
import { dirname, join } from 'node:path';
import { execFileSync } from 'node:child_process';

/** Env var that forces a throw after a named mutation phase (tests only). */
export const INSTALL_FAULT_ENV = 'CLAUDE_DEV_ENV_INSTALL_FAULT';

/** Journal directory name under the managed root. */
export const TRANSACTION_JOURNAL_DIRECTORY_NAME = '.claude-dev-env-txn';

export const FAULT_PHASES = Object.freeze({
    AFTER_FILE_STAGING: 'after_file_staging',
    AFTER_SETTINGS_WRITE: 'after_settings_write',
    AFTER_GIT_CONFIG: 'after_git_config',
    AFTER_MANIFEST_WRITE: 'after_manifest_write',
    BEFORE_DURABLE_PROMOTION: 'before_durable_promotion',
    AFTER_LINK_PUBLICATION: 'after_link_publication',
});

const ALL_FAULT_PHASE_VALUES = Object.freeze(Object.values(FAULT_PHASES));

const META_FILE_NAME = 'meta.json';
const SETTINGS_BLOB_NAME = 'settings.json';
const MANIFEST_BLOB_NAME = 'manifest.json';
const FILES_DIRECTORY_NAME = 'files';
const ENTRY_KIND_FILE = 'file';
const ENTRY_KIND_SYMLINK = 'symlink';
const ENTRY_KIND_MISSING = 'missing';

/**
 * Fault injection that aborts the install after a named phase.
 */
export class InstallTransactionFaultError extends Error {
    /**
     * @param {string} phase
     */
    constructor(phase) {
        super(`Install fault injection at phase: ${phase}`);
        this.name = 'InstallTransactionFaultError';
        this.phase = phase;
    }
}

/**
 * Read the configured fault phase from the environment, or null.
 *
 * @param {NodeJS.ProcessEnv} [environment]
 * @returns {string|null}
 */
export function resolveFaultPhaseFromEnvironment(environment = process.env) {
    const rawPhase = environment[INSTALL_FAULT_ENV];
    if (!rawPhase) {
        return null;
    }
    if (!ALL_FAULT_PHASE_VALUES.includes(rawPhase)) {
        throw new Error(
            `Unknown ${INSTALL_FAULT_ENV} value "${rawPhase}". `
            + `Expected one of: ${ALL_FAULT_PHASE_VALUES.join(', ')}`,
        );
    }
    return rawPhase;
}

/**
 * Throw when the current phase matches the active fault phase.
 *
 * @param {string} currentPhase
 * @param {string|null|undefined} faultPhase
 * @returns {void}
 */
export function throwIfFaultPhase(currentPhase, faultPhase) {
    if (faultPhase && faultPhase === currentPhase) {
        throw new InstallTransactionFaultError(currentPhase);
    }
}

/**
 * Read global core.hooksPath, or null when unset.
 *
 * @param {{ execFileSync?: typeof execFileSync, env?: NodeJS.ProcessEnv }} [io]
 * @returns {string|null}
 */
export function readGlobalCoreHooksPath(io = {}) {
    const execFile = io.execFileSync || execFileSync;
    const environment = io.env || process.env;
    try {
        const value = execFile('git', ['config', '--global', '--get', 'core.hooksPath'], {
            encoding: 'utf8',
            stdio: ['ignore', 'pipe', 'pipe'],
            env: environment,
        });
        const trimmed = String(value).trim();
        return trimmed === '' ? null : trimmed;
    } catch (readError) {
        if (readError && readError.status === 1) {
            return null;
        }
        return null;
    }
}

/**
 * Write or clear global core.hooksPath.
 *
 * @param {string|null} hooksPath
 * @param {{ execFileSync?: typeof execFileSync, env?: NodeJS.ProcessEnv }} [io]
 * @returns {void}
 */
export function writeGlobalCoreHooksPath(hooksPath, io = {}) {
    const execFile = io.execFileSync || execFileSync;
    const environment = io.env || process.env;
    if (hooksPath === null || hooksPath === undefined || hooksPath === '') {
        try {
            execFile('git', ['config', '--global', '--unset', 'core.hooksPath'], {
                stdio: 'ignore',
                env: environment,
            });
        } catch (unsetError) {
            if (unsetError && (unsetError.status === 1 || unsetError.status === 5)) {
                return;
            }
            throw unsetError;
        }
        return;
    }
    execFile('git', ['config', '--global', 'core.hooksPath', hooksPath], {
        stdio: 'ignore',
        env: environment,
    });
}

/**
 * @param {string} absolutePath
 * @param {{ existsSync?: typeof existsSync, lstatSync?: typeof lstatSync, readlinkSync?: typeof readlinkSync }} io
 * @returns {{ kind: string, linkTarget?: string }}
 */
function classifyPath(absolutePath, io) {
    const exists = io.existsSync || existsSync;
    const lstat = io.lstatSync || lstatSync;
    const readlink = io.readlinkSync || readlinkSync;
    if (!exists(absolutePath)) {
        return { kind: ENTRY_KIND_MISSING };
    }
    const stats = lstat(absolutePath);
    if (stats.isSymbolicLink()) {
        return { kind: ENTRY_KIND_SYMLINK, linkTarget: readlink(absolutePath) };
    }
    if (stats.isFile()) {
        return { kind: ENTRY_KIND_FILE };
    }
    return { kind: ENTRY_KIND_MISSING };
}

/**
 * Capture prior settings, manifest, hooksPath, and package-owned files.
 *
 * @param {{
 *   managedRoot: string,
 *   manifestFilePath: string,
 *   settingsPath: string,
 *   priorManifestFiles?: string[]|null,
 *   journalParentDirectory?: string,
 *   io?: object,
 * }} input
 * @returns {object}
 */
export function capturePriorInstallSnapshot(input) {
    const io = input.io || {};
    const exists = io.existsSync || existsSync;
    const mkdir = io.mkdirSync || mkdirSync;
    const mkdtemp = io.mkdtempSync || mkdtempSync;
    const copyFile = io.copyFileSync || copyFileSync;
    const writeFile = io.writeFileSync || writeFileSync;

    const journalParent = input.journalParentDirectory
        || join(input.managedRoot, TRANSACTION_JOURNAL_DIRECTORY_NAME);
    mkdir(journalParent, { recursive: true });
    const journalRoot = mkdtemp(join(journalParent, 'run-'));
    const filesDirectory = join(journalRoot, FILES_DIRECTORY_NAME);
    mkdir(filesDirectory, { recursive: true });

    const settingsExisted = exists(input.settingsPath);
    if (settingsExisted) {
        copyFile(input.settingsPath, join(journalRoot, SETTINGS_BLOB_NAME));
    }

    const manifestExisted = exists(input.manifestFilePath);
    if (manifestExisted) {
        copyFile(input.manifestFilePath, join(journalRoot, MANIFEST_BLOB_NAME));
    }

    const priorHooksPath = readGlobalCoreHooksPath(io);
    /** @type {Array<{ absolutePath: string, kind: string, blobName?: string, linkTarget?: string }>} */
    const allFileEntries = [];
    const priorFiles = Array.isArray(input.priorManifestFiles) ? input.priorManifestFiles : [];
    let entryIndex = 0;
    for (const eachPath of priorFiles) {
        if (typeof eachPath !== 'string' || eachPath.trim() === '') {
            continue;
        }
        const classification = classifyPath(eachPath, io);
        if (classification.kind === ENTRY_KIND_FILE) {
            const blobName = String(entryIndex);
            copyFile(eachPath, join(filesDirectory, blobName));
            allFileEntries.push({
                absolutePath: eachPath,
                kind: ENTRY_KIND_FILE,
                blobName,
            });
            entryIndex += 1;
        } else if (classification.kind === ENTRY_KIND_SYMLINK) {
            allFileEntries.push({
                absolutePath: eachPath,
                kind: ENTRY_KIND_SYMLINK,
                linkTarget: classification.linkTarget,
            });
        } else {
            allFileEntries.push({
                absolutePath: eachPath,
                kind: ENTRY_KIND_MISSING,
            });
        }
    }

    const meta = {
        managedRoot: input.managedRoot,
        settingsPath: input.settingsPath,
        manifestFilePath: input.manifestFilePath,
        settingsExisted,
        manifestExisted,
        priorHooksPath,
        allFileEntries,
    };
    writeFile(join(journalRoot, META_FILE_NAME), `${JSON.stringify(meta, null, 2)}\n`);

    return Object.freeze({
        journalRoot,
        managedRoot: input.managedRoot,
        settingsPath: input.settingsPath,
        manifestFilePath: input.manifestFilePath,
        settingsExisted,
        manifestExisted,
        priorHooksPath,
        allFileEntries: Object.freeze(allFileEntries.map((eachEntry) => Object.freeze({ ...eachEntry }))),
    });
}

/**
 * Restore the captured prior installation and drop extra write-set paths.
 *
 * @param {ReturnType<typeof capturePriorInstallSnapshot>} snapshot
 * @param {{
 *   allWrittenPaths?: string[],
 *   io?: object,
 * }} [options]
 * @returns {void}
 */
export function restorePriorInstallSnapshot(snapshot, options = {}) {
    const io = options.io || {};
    const exists = io.existsSync || existsSync;
    const copyFile = io.copyFileSync || copyFileSync;
    const mkdir = io.mkdirSync || mkdirSync;
    const unlink = io.unlinkSync || unlinkSync;
    const symlink = io.symlinkSync || symlinkSync;
    const lstat = io.lstatSync || lstatSync;

    const filesDirectory = join(snapshot.journalRoot, FILES_DIRECTORY_NAME);
    for (const eachEntry of snapshot.allFileEntries) {
        try {
            if (exists(eachEntry.absolutePath)) {
                const stats = lstat(eachEntry.absolutePath);
                if (stats.isFile() || stats.isSymbolicLink()) {
                    unlink(eachEntry.absolutePath);
                }
            }
        } catch {
            // keep restoring remaining entries
        }
        if (eachEntry.kind === ENTRY_KIND_FILE && eachEntry.blobName) {
            mkdir(dirname(eachEntry.absolutePath), { recursive: true });
            copyFile(join(filesDirectory, eachEntry.blobName), eachEntry.absolutePath);
        } else if (eachEntry.kind === ENTRY_KIND_SYMLINK && eachEntry.linkTarget) {
            mkdir(dirname(eachEntry.absolutePath), { recursive: true });
            try {
                symlink(eachEntry.linkTarget, eachEntry.absolutePath);
            } catch {
                // platform may reject the link shape; leave missing
            }
        }
    }

    const priorPathSet = new Set(snapshot.allFileEntries.map((eachEntry) => eachEntry.absolutePath));
    const allWrittenPaths = Array.isArray(options.allWrittenPaths) ? options.allWrittenPaths : [];
    for (const eachWrittenPath of allWrittenPaths) {
        if (priorPathSet.has(eachWrittenPath)) {
            continue;
        }
        if (eachWrittenPath === snapshot.settingsPath || eachWrittenPath === snapshot.manifestFilePath) {
            continue;
        }
        try {
            if (exists(eachWrittenPath)) {
                const stats = lstat(eachWrittenPath);
                if (stats.isFile() || stats.isSymbolicLink()) {
                    unlink(eachWrittenPath);
                }
            }
        } catch {
            // keep restoring remaining entries
        }
    }

    if (snapshot.settingsExisted) {
        mkdir(dirname(snapshot.settingsPath), { recursive: true });
        copyFile(join(snapshot.journalRoot, SETTINGS_BLOB_NAME), snapshot.settingsPath);
    } else if (exists(snapshot.settingsPath)) {
        try {
            unlink(snapshot.settingsPath);
        } catch {
            // leave in place when unlink fails
        }
    }

    if (snapshot.manifestExisted) {
        mkdir(dirname(snapshot.manifestFilePath), { recursive: true });
        copyFile(join(snapshot.journalRoot, MANIFEST_BLOB_NAME), snapshot.manifestFilePath);
    } else if (exists(snapshot.manifestFilePath)) {
        try {
            unlink(snapshot.manifestFilePath);
        } catch {
            // leave in place when unlink fails
        }
    }

    writeGlobalCoreHooksPath(snapshot.priorHooksPath, io);
}

/**
 * Remove the journal directory after a successful commit.
 *
 * @param {ReturnType<typeof capturePriorInstallSnapshot>} snapshot
 * @param {{ rmSync?: typeof rmSync, readdirSync?: typeof readdirSync, rmdirSync?: typeof rmdirSync }} [io]
 * @returns {void}
 */
export function discardInstallTransactionJournal(snapshot, io = {}) {
    const removeTree = io.rmSync || rmSync;
    const readDirectory = io.readdirSync || readdirSync;
    const removeDirectory = io.rmdirSync || rmdirSync;
    try {
        removeTree(snapshot.journalRoot, { recursive: true, force: true });
    } catch {
        // journal cleanup is best-effort after a successful install
    }
    const journalParent = dirname(snapshot.journalRoot);
    try {
        if (readDirectory(journalParent).length === 0) {
            removeDirectory(journalParent);
        }
    } catch {
        // parent cleanup is best-effort
    }
}

/**
 * Run install mutations inside a snapshot/restore transaction.
 *
 * @param {{
 *   snapshot: ReturnType<typeof capturePriorInstallSnapshot>,
 *   faultPhase?: string|null,
 *   runMutations: (helpers: {
 *     throwIfFault: (phase: string) => void,
 *     recordWrittenPath: (absolutePath: string) => void,
 *     syncWrittenPaths: (allPaths: string[]) => void,
 *   }) => void,
 *   io?: object,
 * }} input
 * @returns {void}
 */
export function runWithInstallTransaction(input) {
    const io = input.io || {};
    /** @type {string[]} */
    const allWrittenPaths = [];
    const faultPhase = input.faultPhase === undefined
        ? resolveFaultPhaseFromEnvironment(process.env)
        : input.faultPhase;

    try {
        input.runMutations({
            throwIfFault: (phase) => throwIfFaultPhase(phase, faultPhase),
            recordWrittenPath: (absolutePath) => {
                if (typeof absolutePath === 'string' && absolutePath !== '') {
                    allWrittenPaths.push(absolutePath);
                }
            },
            syncWrittenPaths: (allPaths) => {
                allWrittenPaths.length = 0;
                for (const eachPath of allPaths) {
                    if (typeof eachPath === 'string' && eachPath !== '') {
                        allWrittenPaths.push(eachPath);
                    }
                }
            },
        });
        discardInstallTransactionJournal(input.snapshot, io);
    } catch (mutationError) {
        try {
            restorePriorInstallSnapshot(input.snapshot, { allWrittenPaths, io });
        } catch (restoreError) {
            const mutationMessage = mutationError instanceof Error
                ? mutationError.message
                : String(mutationError);
            const restoreMessage = restoreError instanceof Error
                ? restoreError.message
                : String(restoreError);
            throw new Error(
                `Install failed (${mutationMessage}) and restore also failed (${restoreMessage})`,
            );
        }
        try {
            discardInstallTransactionJournal(input.snapshot, io);
        } catch {
            // journal cleanup is best-effort after restore
        }
        throw mutationError;
    }
}
