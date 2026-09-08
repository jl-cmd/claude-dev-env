/**
 * Refresh `vendor/pstack/` from an upstream pstack checkout.
 *
 * The sync is a table of file decisions, built before anything touches disk:
 *
 *     upstream has README.md, vendor differs        -> write
 *     upstream has LICENSE, vendor byte-identical   -> unchanged
 *     upstream has assets/logo.png                  -> skip    (image)
 *     vendor has stale/old.md, upstream lost it     -> remove
 *
 * `buildPstackVendorPlan` reads both trees and returns those entries sorted by
 * path. `applyPstackVendorPlan` walks them. A second run over the same inputs
 * yields only `unchanged` and `skip`, so it writes nothing.
 *
 * The record beside the tree, `vendor/pstack.sync.json`, names the upstream
 * commit and the images left out. It carries no timestamp, so a second sync
 * leaves it byte for byte.
 */

import {
    cpSync,
    existsSync,
    mkdirSync,
    mkdtempSync,
    readdirSync,
    readFileSync,
    realpathSync,
    rmSync,
    statSync,
    unlinkSync,
    writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, extname, join, posix, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';

export const ALL_EXCLUDED_IMAGE_EXTENSIONS = Object.freeze([
    '.png',
    '.jpg',
    '.jpeg',
    '.gif',
    '.webp',
    '.svg',
    '.ico',
]);

export const PSTACK_SOURCE_URL = 'https://github.com/cursor/plugins';
export const PSTACK_SUBDIRECTORY_NAME = 'pstack';
export const PSTACK_VENDOR_MANIFEST_RELATIVE_PATH = posix.join('.cursor-plugin', 'plugin.json');
export const PSTACK_SYNC_RECORD_FILE_NAME = 'pstack.sync.json';

const FILE_ENCODING = 'utf8';
const RECORD_INDENT_SPACES = 2;
const GIT_DIRECTORY_NAME = '.git';
const SOURCE_ARGUMENT_NAME = '--source';
const COMMIT_ARGUMENT_NAME = '--commit';
const CLONE_DIRECTORY_PREFIX = 'cde-pstack-clone-';
const REPOSITORY_ROOT_DEPTH = 3;

function allRelativeFilePaths(treeRoot, relativeDirectory) {
    if (!existsSync(treeRoot)) return [];
    const absoluteDirectory = relativeDirectory === ''
        ? treeRoot
        : join(treeRoot, relativeDirectory.split(posix.sep).join(sep));
    const allPaths = [];
    for (const eachEntry of readdirSync(absoluteDirectory, { withFileTypes: true })) {
        if (eachEntry.name === GIT_DIRECTORY_NAME) continue;
        const eachRelativePath = relativeDirectory === ''
            ? eachEntry.name
            : posix.join(relativeDirectory, eachEntry.name);
        if (eachEntry.isDirectory()) {
            allPaths.push(...allRelativeFilePaths(treeRoot, eachRelativePath));
            continue;
        }
        allPaths.push(eachRelativePath);
    }
    return allPaths;
}

function absolutePathIn(treeRoot, relativePath) {
    return join(treeRoot, relativePath.split(posix.sep).join(sep));
}

function isExcludedImage(relativePath) {
    return ALL_EXCLUDED_IMAGE_EXTENSIONS.includes(extname(relativePath).toLowerCase());
}

function isByteIdentical(upstreamPath, vendorPath) {
    if (!existsSync(vendorPath)) return false;
    return readFileSync(upstreamPath).equals(readFileSync(vendorPath));
}

/**
 * Decide what the vendored tree needs so it matches an upstream checkout.
 *
 * ::
 *
 *     upstream: README.md, assets/logo.png     vendor: README.md (older), stale.md
 *     entries:  assets/logo.png -> skip
 *               README.md       -> write
 *               stale.md        -> remove
 *
 * Nothing on disk changes here. Every path is repository-relative to its own
 * tree root and written with forward slashes.
 *
 * @param {{upstreamRoot: string, vendorRoot: string}} roots The upstream
 *   checkout subdirectory and the vendored copy it feeds.
 * @returns {{entries: {relativePath: string, action: string}[]}} One entry per
 *   file in either tree, sorted by `relativePath`. `action` is `write`,
 *   `unchanged`, `skip`, or `remove`.
 */
export function buildPstackVendorPlan({ upstreamRoot, vendorRoot }) {
    const allUpstreamPaths = allRelativeFilePaths(upstreamRoot, '');
    const allUpstreamPathsSeen = new Set(allUpstreamPaths);
    const allEntries = allUpstreamPaths.map((eachRelativePath) => {
        if (isExcludedImage(eachRelativePath)) {
            return { relativePath: eachRelativePath, action: 'skip' };
        }
        const isSame = isByteIdentical(
            absolutePathIn(upstreamRoot, eachRelativePath),
            absolutePathIn(vendorRoot, eachRelativePath),
        );
        return { relativePath: eachRelativePath, action: isSame ? 'unchanged' : 'write' };
    });
    for (const eachRelativePath of allRelativeFilePaths(vendorRoot, '')) {
        if (allUpstreamPathsSeen.has(eachRelativePath)) continue;
        allEntries.push({ relativePath: eachRelativePath, action: 'remove' });
    }
    allEntries.sort((firstEntry, secondEntry) => (
        firstEntry.relativePath < secondEntry.relativePath ? -1 : 1
    ));
    return { entries: allEntries };
}

/**
 * Carry out a plan against the vendored tree.
 *
 * A `write` entry copies the upstream bytes over. A `remove` entry deletes the
 * vendored file. An `unchanged` or `skip` entry is left alone, so the file
 * keeps its modification time.
 *
 * @param {{entries: {relativePath: string, action: string}[]}} plan The plan
 *   `buildPstackVendorPlan` returned.
 * @param {{upstreamRoot: string, vendorRoot: string}} roots The same two tree
 *   roots the plan was built from.
 * @returns {{writtenCount: number, removedCount: number, skippedCount: number,
 *   unchangedCount: number}} How many entries each action covered.
 */
export function applyPstackVendorPlan(plan, { upstreamRoot, vendorRoot }) {
    const allCounts = { writtenCount: 0, removedCount: 0, skippedCount: 0, unchangedCount: 0 };
    for (const eachEntry of plan.entries) {
        const vendorPath = absolutePathIn(vendorRoot, eachEntry.relativePath);
        if (eachEntry.action === 'write') {
            mkdirSync(dirname(vendorPath), { recursive: true });
            cpSync(absolutePathIn(upstreamRoot, eachEntry.relativePath), vendorPath);
            allCounts.writtenCount += 1;
            continue;
        }
        if (eachEntry.action === 'remove') {
            unlinkSync(vendorPath);
            allCounts.removedCount += 1;
            continue;
        }
        if (eachEntry.action === 'skip') allCounts.skippedCount += 1;
        if (eachEntry.action === 'unchanged') allCounts.unchangedCount += 1;
    }
    return allCounts;
}

/**
 * Describe a finished sync, for the record beside the vendored tree.
 *
 * The plugin version comes from the vendored manifest, so the record and the
 * tree cannot drift apart. Every field is derived from the inputs, so a second
 * sync over the same commit builds the same record.
 *
 * @param {{vendorRoot: string, plan: {entries: {relativePath: string,
 *   action: string}[]}, commit: string}} inputs The vendored tree, the plan
 *   just applied, and the upstream commit it came from.
 * @returns {{sourceUrl: string, subdirectory: string, commit: string,
 *   version: string, skippedPaths: string[]}} The record content, with the
 *   skipped image paths sorted.
 */
export function buildPstackSyncRecord({ vendorRoot, plan, commit }) {
    const manifestPath = absolutePathIn(vendorRoot, PSTACK_VENDOR_MANIFEST_RELATIVE_PATH);
    const manifest = JSON.parse(readFileSync(manifestPath, FILE_ENCODING));
    const allSkippedPaths = plan.entries
        .filter((eachEntry) => eachEntry.action === 'skip')
        .map((eachEntry) => eachEntry.relativePath)
        .sort();
    return {
        sourceUrl: PSTACK_SOURCE_URL,
        subdirectory: PSTACK_SUBDIRECTORY_NAME,
        commit,
        version: manifest.version,
        skippedPaths: allSkippedPaths,
    };
}

/**
 * Write a sync record beside the vendored tree.
 *
 * @param {string} vendorParentDirectory The directory holding `pstack/`.
 * @param {object} record The record `buildPstackSyncRecord` returned.
 * @returns {string} The path the record was written to.
 */
export function writePstackSyncRecord(vendorParentDirectory, record) {
    const recordPath = join(vendorParentDirectory, PSTACK_SYNC_RECORD_FILE_NAME);
    writeFileSync(
        recordPath,
        JSON.stringify(record, null, RECORD_INDENT_SPACES) + '\n',
        FILE_ENCODING,
    );
    return recordPath;
}

/**
 * Read the repository root this script was installed under.
 *
 * @param {string} modulePath This module's own path.
 * @returns {string} The directory that holds `vendor/`.
 */
export function repositoryRootFor(modulePath) {
    let currentDirectory = dirname(modulePath);
    for (let eachStep = 0; eachStep < REPOSITORY_ROOT_DEPTH; eachStep += 1) {
        currentDirectory = dirname(currentDirectory);
    }
    return currentDirectory;
}

function namedArgument(allArguments, argumentName) {
    const nameIndex = allArguments.indexOf(argumentName);
    if (nameIndex === -1) return '';
    return allArguments[nameIndex + 1] || '';
}

function commitFor(sourceCheckout, requestedCommit) {
    if (requestedCommit) return requestedCommit;
    return execFileSync('git', ['-C', sourceCheckout, 'rev-parse', 'HEAD'], {
        encoding: FILE_ENCODING,
    }).trim();
}

function main() {
    const allArguments = process.argv.slice(2);
    const requestedSource = namedArgument(allArguments, SOURCE_ARGUMENT_NAME);
    const requestedCommit = namedArgument(allArguments, COMMIT_ARGUMENT_NAME);
    let cloneDirectory = '';
    let sourceCheckout = requestedSource;
    if (!sourceCheckout) {
        cloneDirectory = mkdtempSync(join(tmpdir(), CLONE_DIRECTORY_PREFIX));
        execFileSync('git', ['clone', '--depth', '1', PSTACK_SOURCE_URL, cloneDirectory], {
            stdio: 'inherit',
        });
        sourceCheckout = cloneDirectory;
    }
    try {
        const upstreamRoot = join(sourceCheckout, PSTACK_SUBDIRECTORY_NAME);
        if (!statSync(upstreamRoot).isDirectory()) {
            throw new Error(`${upstreamRoot} is not a directory.`);
        }
        const repositoryRoot = repositoryRootFor(fileURLToPath(import.meta.url));
        const vendorParentDirectory = join(repositoryRoot, 'vendor');
        const vendorRoot = join(vendorParentDirectory, PSTACK_SUBDIRECTORY_NAME);
        const plan = buildPstackVendorPlan({ upstreamRoot, vendorRoot });
        const allCounts = applyPstackVendorPlan(plan, { upstreamRoot, vendorRoot });
        const commit = commitFor(sourceCheckout, requestedCommit);
        const record = buildPstackSyncRecord({ vendorRoot, plan, commit });
        const recordPath = writePstackSyncRecord(vendorParentDirectory, record);
        console.log(
            `Synced pstack ${record.version} at ${record.commit}: `
            + `${allCounts.writtenCount} written, ${allCounts.removedCount} removed, `
            + `${allCounts.skippedCount} images skipped, `
            + `${allCounts.unchangedCount} unchanged.`,
        );
        console.log(`Record: ${recordPath}`);
    } finally {
        if (cloneDirectory) rmSync(cloneDirectory, { recursive: true, force: true });
    }
}

function isEntryPoint(invokedPath) {
    if (!invokedPath) return false;
    try {
        return realpathSync(fileURLToPath(import.meta.url)) === realpathSync(invokedPath);
    } catch {
        return fileURLToPath(import.meta.url) === invokedPath;
    }
}

if (isEntryPoint(process.argv[1])) main();
