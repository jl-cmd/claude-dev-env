#!/usr/bin/env node
/**
 * Remove local Python bytecode, tool caches, and debug logs under this package
 * before `npm pack` / `npm publish` (wired as the package `prepack` script).
 *
 * Monorepo-root .gitignore does not apply when packing this directory, and the
 * package.json `files` whitelist still pulls directory trees, so a prepack wipe
 * is the reliable gate that keeps those artifacts out of the tarball.
 *
 * A fixed blocklist cannot anticipate every stray file type, so a second gate
 * runs after the scrub: it asks git which files under this package are
 * untracked or git-ignored, and fails the pack when any of them sits inside a
 * directory or filename the `files` whitelist ships.
 */
import { readdirSync, readFileSync, rmSync, statSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

import { invokedAsEntryPoint } from './install.mjs';

const packageRoot = join(fileURLToPath(new URL('..', import.meta.url)));

const DIRECTORY_NAMES_TO_REMOVE = new Set([
  '__pycache__',
  '.pytest_cache',
  '.mypy_cache',
  '.ruff_cache',
]);

const FILE_SUFFIXES_TO_REMOVE = ['.pyc', '.pyo', '.log'];

const PACKAGE_MANIFEST_FILENAME = 'package.json';
const PACKAGE_MANIFEST_FILES_FIELD = 'files';
const NEGATION_ENTRY_PREFIX = '!';
const DIRECTORY_ENTRY_SUFFIX = '/';

const GIT_EXECUTABLE_NAME = 'git';
const GIT_REPOSITORY_CHECK_ARGS = ['rev-parse', '--is-inside-work-tree'];
const GIT_LIST_UNTRACKED_ARGS = ['ls-files', '--others', '--exclude-standard'];
const GIT_LIST_IGNORED_ARGS = ['ls-files', '--others', '--ignored', '--exclude-standard'];

const UNTRACKED_FILE_GATE_SKIP_MESSAGE =
  'clean_pack_artifacts: skipping untracked-file gate (no git repository detected here)';
const UNTRACKED_FILE_GATE_ALL_CLEAR_MESSAGE =
  'clean_pack_artifacts: no untracked or git-ignored files found inside the npm files whitelist';
const UNTRACKED_FILE_GATE_EXPLANATION =
  'untracked or git-ignored file inside a package.json "files" path — commit it or delete it before packing';

/**
 * @param {string} fileName
 * @returns {boolean}
 */
function shouldRemoveFile(fileName) {
  if (fileName.startsWith('debug-') && fileName.endsWith('.log')) {
    return true;
  }
  if (fileName === 'pytestdebug.log') {
    return true;
  }
  return FILE_SUFFIXES_TO_REMOVE.some((suffix) => fileName.endsWith(suffix));
}

/**
 * @param {string} directoryPath
 * @returns {void}
 */
function walkAndRemove(directoryPath) {
  let entries;
  try {
    entries = readdirSync(directoryPath, { withFileTypes: true });
  } catch {
    return;
  }

  for (const eachEntry of entries) {
    const absolutePath = join(directoryPath, eachEntry.name);
    if (eachEntry.isDirectory()) {
      if (DIRECTORY_NAMES_TO_REMOVE.has(eachEntry.name)) {
        rmSync(absolutePath, { recursive: true, force: true });
        console.log(`  removed ${relative(packageRoot, absolutePath)}/`);
        continue;
      }
      if (eachEntry.name.endsWith('.egg-info')) {
        rmSync(absolutePath, { recursive: true, force: true });
        console.log(`  removed ${relative(packageRoot, absolutePath)}/`);
        continue;
      }
      walkAndRemove(absolutePath);
      continue;
    }
    if (eachEntry.isFile() && shouldRemoveFile(eachEntry.name)) {
      rmSync(absolutePath, { force: true });
      console.log(`  removed ${relative(packageRoot, absolutePath)}`);
    }
  }
}

/**
 * @param {string} packageDirectory
 * @returns {boolean}
 */
export function isGitRepositoryAvailable(packageDirectory) {
  try {
    execFileSync(GIT_EXECUTABLE_NAME, GIT_REPOSITORY_CHECK_ARGS, {
      cwd: packageDirectory,
      stdio: 'ignore',
    });
    return true;
  } catch {
    return false;
  }
}

/**
 * @param {string} packageDirectory
 * @returns {string[]}
 */
function shippedFilesFieldEntries(packageDirectory) {
  const manifestPath = join(packageDirectory, PACKAGE_MANIFEST_FILENAME);
  const manifestContents = JSON.parse(readFileSync(manifestPath, 'utf8'));
  const allFilesEntries = manifestContents[PACKAGE_MANIFEST_FILES_FIELD] || [];
  return allFilesEntries.filter((eachEntry) => !eachEntry.startsWith(NEGATION_ENTRY_PREFIX));
}

/**
 * @param {string} packageDirectory
 * @param {string[]} gitArguments
 * @returns {string[]}
 */
function listGitReportedPaths(packageDirectory, gitArguments) {
  const commandOutput = execFileSync(GIT_EXECUTABLE_NAME, gitArguments, {
    cwd: packageDirectory,
    stdio: ['ignore', 'pipe', 'ignore'],
  }).toString('utf8');
  return commandOutput
    .split('\n')
    .map((eachLine) => eachLine.trim())
    .filter((eachLine) => eachLine.length > 0);
}

/**
 * @param {string} relativePath
 * @param {string[]} shippedEntries
 * @returns {boolean}
 */
function pathFallsUnderShippedEntry(relativePath, shippedEntries) {
  return shippedEntries.some((eachEntry) => {
    if (eachEntry.endsWith(DIRECTORY_ENTRY_SUFFIX)) {
      return relativePath.startsWith(eachEntry);
    }
    return relativePath === eachEntry;
  });
}

/**
 * Finds untracked or git-ignored paths under packageDirectory that npm would
 * still pack, because they sit inside a `files`-listed directory or filename.
 *
 * @param {string} packageDirectory
 * @returns {string[]}
 */
export function findUntrackedPackedFiles(packageDirectory) {
  const shippedEntries = shippedFilesFieldEntries(packageDirectory);
  const untrackedPaths = listGitReportedPaths(packageDirectory, GIT_LIST_UNTRACKED_ARGS);
  const ignoredPaths = listGitReportedPaths(packageDirectory, GIT_LIST_IGNORED_ARGS);
  const allCandidatePaths = new Set([...untrackedPaths, ...ignoredPaths]);

  return [...allCandidatePaths]
    .filter((eachPath) => pathFallsUnderShippedEntry(eachPath, shippedEntries))
    .sort();
}

/**
 * Decides the untracked-file gate outcome for one package directory. Fails
 * open (exit 0, skip message) when git is unavailable or the directory is
 * not a git repository, so packing an extracted tarball still works.
 *
 * @param {string} packageDirectory
 * @returns {{ exitCode: number, messageLines: string[] }}
 */
export function evaluateUntrackedFileGate(packageDirectory) {
  if (!isGitRepositoryAvailable(packageDirectory)) {
    return { exitCode: 0, messageLines: [UNTRACKED_FILE_GATE_SKIP_MESSAGE] };
  }

  const offendingRelativePaths = findUntrackedPackedFiles(packageDirectory);
  if (offendingRelativePaths.length === 0) {
    return { exitCode: 0, messageLines: [UNTRACKED_FILE_GATE_ALL_CLEAR_MESSAGE] };
  }

  return {
    exitCode: 1,
    messageLines: offendingRelativePaths.map(
      (eachPath) => `clean_pack_artifacts: ${eachPath} — ${UNTRACKED_FILE_GATE_EXPLANATION}`,
    ),
  };
}

if (invokedAsEntryPoint(import.meta.url, process.argv[1])) {
  console.log(`clean_pack_artifacts: scrubbing ${packageRoot}`);
  walkAndRemove(packageRoot);

  // Keep the tree walk honest: a leftover cache directory is a prepack failure.
  for (const eachName of DIRECTORY_NAMES_TO_REMOVE) {
    try {
      const probe = join(packageRoot, eachName);
      if (statSync(probe).isDirectory()) {
        console.error(`clean_pack_artifacts: still present after scrub: ${eachName}`);
        process.exit(1);
      }
    } catch {
      // absent — expected
    }
  }

  const untrackedFileGateResult = evaluateUntrackedFileGate(packageRoot);
  const logLine = untrackedFileGateResult.exitCode === 0 ? console.log : console.error;
  for (const eachMessageLine of untrackedFileGateResult.messageLines) {
    logLine(eachMessageLine);
  }
  if (untrackedFileGateResult.exitCode !== 0) {
    process.exit(untrackedFileGateResult.exitCode);
  }
}
