#!/usr/bin/env node

import { spawn } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import { isAbsolute } from 'node:path';

import {
  DELTA_UPDATER_CLI_MANIFEST_FLAG,
  DELTA_UPDATER_CLI_PROFILE_ROOT_FLAG,
  DELTA_UPDATER_CLI_PYTHON_FLAG,
  DELTA_UPDATER_CLI_UPDATER_FLAG,
  DELTA_UPDATER_MANIFEST_PROFILE_ROOT_FIELD_NAME,
  DELTA_UPDATER_MANIFEST_PROFILES_FIELD_NAME,
} from '../config/profile-isolation-constants.mjs';
import { runDeltaUpdaterObservingHealth } from '../lib/delta-updater-health.mjs';

/**
 * @typedef {{
 *   manifestAbsolutePath: string,
 *   updaterScriptAbsolutePath: string,
 *   pythonExecutableAbsolutePath: string,
 *   allExplicitProfileRootDirectoryPaths: string[],
 * }} DeltaUpdaterCliOptions
 */

/**
 * @typedef {{
 *   profiles: Array<{ profile_root: string }>,
 * }} ValidatedDeltaUpdaterManifest
 */

/**
 * Parse absolute-path CLI flags for the scheduled-task delta updater entrypoint.
 *
 * ::
 *   parseDeltaUpdaterCliArguments([
 *     'node', 'run-hook-log-delta-updater.mjs',
 *     '--manifest', 'C:\\\\m.json',
 *     '--updater', 'C:\\\\u.py',
 *     '--python', 'C:\\\\python.exe',
 *   ])
 *   ok: returns absolute paths for manifest, updater, and python
 *
 * @param {string[]} argumentVector
 * @returns {DeltaUpdaterCliOptions}
 */
export function parseDeltaUpdaterCliArguments(argumentVector) {
  const allUserArguments = argumentVector.slice(2);
  /** @type {string | undefined} */
  let manifestAbsolutePath;
  /** @type {string | undefined} */
  let updaterScriptAbsolutePath;
  /** @type {string | undefined} */
  let pythonExecutableAbsolutePath;
  /** @type {string[]} */
  const allExplicitProfileRootDirectoryPaths = [];
  for (let argumentIndex = 0; argumentIndex < allUserArguments.length; argumentIndex += 1) {
    const eachArgument = allUserArguments[argumentIndex];
    const maybeNextArgument = allUserArguments[argumentIndex + 1];
    if (eachArgument === DELTA_UPDATER_CLI_MANIFEST_FLAG) {
      manifestAbsolutePath = requireAbsolutePathFlag(
        DELTA_UPDATER_CLI_MANIFEST_FLAG,
        maybeNextArgument,
      );
      argumentIndex += 1;
      continue;
    }
    if (eachArgument === DELTA_UPDATER_CLI_UPDATER_FLAG) {
      updaterScriptAbsolutePath = requireAbsolutePathFlag(
        DELTA_UPDATER_CLI_UPDATER_FLAG,
        maybeNextArgument,
      );
      argumentIndex += 1;
      continue;
    }
    if (eachArgument === DELTA_UPDATER_CLI_PYTHON_FLAG) {
      pythonExecutableAbsolutePath = requireAbsolutePathFlag(
        DELTA_UPDATER_CLI_PYTHON_FLAG,
        maybeNextArgument,
      );
      argumentIndex += 1;
      continue;
    }
    if (eachArgument === DELTA_UPDATER_CLI_PROFILE_ROOT_FLAG) {
      allExplicitProfileRootDirectoryPaths.push(
        requireAbsolutePathFlag(DELTA_UPDATER_CLI_PROFILE_ROOT_FLAG, maybeNextArgument),
      );
      argumentIndex += 1;
      continue;
    }
    throw new Error(`Unknown argument: ${eachArgument}`);
  }
  return requireCompleteCliOptions({
    manifestAbsolutePath,
    updaterScriptAbsolutePath,
    pythonExecutableAbsolutePath,
    allExplicitProfileRootDirectoryPaths,
  });
}

/**
 * Validate manifest shape: non-empty profiles with profile_root strings.
 *
 * ::
 *   validateDeltaUpdaterManifest({ profiles: [{ profile_root: 'C:\\\\p' }] })
 *   ok: returns the same profiles list
 *   validateDeltaUpdaterManifest({ profiles: [] })
 *   flag: throws for empty profiles
 *
 * @param {unknown} maybeManifest
 * @returns {ValidatedDeltaUpdaterManifest}
 */
export function validateDeltaUpdaterManifest(maybeManifest) {
  if (!isPlainObject(maybeManifest)) {
    throw new Error('delta updater manifest must be a JSON object');
  }
  const allProfiles = maybeManifest[DELTA_UPDATER_MANIFEST_PROFILES_FIELD_NAME];
  if (!Array.isArray(allProfiles) || allProfiles.length === 0) {
    throw new Error('delta updater manifest profiles must be a non-empty array');
  }
  /** @type {Array<{ profile_root: string }>} */
  const validatedProfiles = [];
  for (const eachProfile of allProfiles) {
    validatedProfiles.push(validateManifestProfileEntry(eachProfile));
  }
  return { profiles: validatedProfiles };
}

/**
 * Read and validate the delta-updater manifest JSON file.
 *
 * @param {string} manifestAbsolutePath
 * @returns {Promise<ValidatedDeltaUpdaterManifest>}
 */
export async function loadValidatedDeltaUpdaterManifest(manifestAbsolutePath) {
  const manifestRaw = await readFile(manifestAbsolutePath, 'utf8');
  return validateDeltaUpdaterManifest(JSON.parse(manifestRaw));
}

/**
 * Resolve profile roots from explicit flags or the validated manifest.
 *
 * @param {{
 *   allExplicitProfileRootDirectoryPaths: string[],
 *   validatedManifest: ValidatedDeltaUpdaterManifest,
 * }} parameters
 * @returns {string[]}
 */
export function resolveAllProfileRootDirectoryPaths({
  allExplicitProfileRootDirectoryPaths,
  validatedManifest,
}) {
  if (allExplicitProfileRootDirectoryPaths.length > 0) {
    return [...allExplicitProfileRootDirectoryPaths];
  }
  return validatedManifest.profiles.map(
    (eachProfile) => eachProfile[DELTA_UPDATER_MANIFEST_PROFILE_ROOT_FIELD_NAME],
  );
}

/**
 * Spawn the public Python delta updater with inherited environment.
 * Never logs environment contents (including secrets / DATABASE_URL).
 *
 * @param {{
 *   pythonExecutableAbsolutePath: string,
 *   updaterScriptAbsolutePath: string,
 *   manifestAbsolutePath: string,
 * }} parameters
 * @returns {Promise<number | null>}
 */
export function spawnPublicDeltaUpdater({
  pythonExecutableAbsolutePath,
  updaterScriptAbsolutePath,
  manifestAbsolutePath,
}) {
  return new Promise((resolvePromise, rejectPromise) => {
    const childProcess = spawn(
      pythonExecutableAbsolutePath,
      [
        updaterScriptAbsolutePath,
        DELTA_UPDATER_CLI_MANIFEST_FLAG,
        manifestAbsolutePath,
      ],
      {
        stdio: 'inherit',
        env: process.env,
        windowsHide: true,
      },
    );
    childProcess.on('error', (error) => {
      rejectPromise(error);
    });
    childProcess.on('close', (exitCode) => {
      resolvePromise(exitCode);
    });
  });
}

/**
 * Run the public updater under health observation and return its exit code.
 *
 * Prefer library-owned flow: runUpdater spawns inside runDeltaUpdaterObservingHealth.
 *
 * @param {string[]} argumentVector
 * @returns {Promise<number>}
 */
export async function runHookLogDeltaUpdaterCli(argumentVector) {
  const cliOptions = parseDeltaUpdaterCliArguments(argumentVector);
  const validatedManifest = await loadValidatedDeltaUpdaterManifest(
    cliOptions.manifestAbsolutePath,
  );
  const allProfileRootDirectoryPaths = resolveAllProfileRootDirectoryPaths({
    allExplicitProfileRootDirectoryPaths: cliOptions.allExplicitProfileRootDirectoryPaths,
    validatedManifest,
  });
  const observation = await runDeltaUpdaterObservingHealth({
    allProfileRootDirectoryPaths,
    runUpdater: async () => {
      const exitCode = await spawnPublicDeltaUpdater({
        pythonExecutableAbsolutePath: cliOptions.pythonExecutableAbsolutePath,
        updaterScriptAbsolutePath: cliOptions.updaterScriptAbsolutePath,
        manifestAbsolutePath: cliOptions.manifestAbsolutePath,
      });
      return { exitCode };
    },
  });
  return observation.exitCode ?? 0;
}

/**
 * @param {string} flagName
 * @param {string | undefined} maybeAbsolutePath
 * @returns {string}
 */
function requireAbsolutePathFlag(flagName, maybeAbsolutePath) {
  if (typeof maybeAbsolutePath !== 'string' || maybeAbsolutePath.trim() === '') {
    throw new Error(`${flagName} requires an absolute path argument`);
  }
  if (!isAbsolute(maybeAbsolutePath)) {
    throw new Error(`${flagName} must be an absolute path: ${maybeAbsolutePath}`);
  }
  return maybeAbsolutePath;
}

/**
 * @param {{
 *   manifestAbsolutePath: string | undefined,
 *   updaterScriptAbsolutePath: string | undefined,
 *   pythonExecutableAbsolutePath: string | undefined,
 *   allExplicitProfileRootDirectoryPaths: string[],
 * }} partialOptions
 * @returns {DeltaUpdaterCliOptions}
 */
function requireCompleteCliOptions(partialOptions) {
  if (partialOptions.manifestAbsolutePath === undefined) {
    throw new Error(`${DELTA_UPDATER_CLI_MANIFEST_FLAG} is required`);
  }
  if (partialOptions.updaterScriptAbsolutePath === undefined) {
    throw new Error(`${DELTA_UPDATER_CLI_UPDATER_FLAG} is required`);
  }
  if (partialOptions.pythonExecutableAbsolutePath === undefined) {
    throw new Error(`${DELTA_UPDATER_CLI_PYTHON_FLAG} is required`);
  }
  return {
    manifestAbsolutePath: partialOptions.manifestAbsolutePath,
    updaterScriptAbsolutePath: partialOptions.updaterScriptAbsolutePath,
    pythonExecutableAbsolutePath: partialOptions.pythonExecutableAbsolutePath,
    allExplicitProfileRootDirectoryPaths: partialOptions.allExplicitProfileRootDirectoryPaths,
  };
}

/**
 * @param {unknown} maybeProfile
 * @returns {{ profile_root: string }}
 */
function validateManifestProfileEntry(maybeProfile) {
  if (!isPlainObject(maybeProfile)) {
    throw new Error('each delta updater manifest profile must be an object');
  }
  const profileRootDirectoryPath = maybeProfile[DELTA_UPDATER_MANIFEST_PROFILE_ROOT_FIELD_NAME];
  if (typeof profileRootDirectoryPath !== 'string' || profileRootDirectoryPath.trim() === '') {
    throw new Error('each delta updater manifest profile_root must be a non-empty string');
  }
  return { profile_root: profileRootDirectoryPath };
}

/**
 * @param {unknown} candidate
 * @returns {candidate is Record<string, unknown>}
 */
function isPlainObject(candidate) {
  return typeof candidate === 'object' && candidate !== null && !Array.isArray(candidate);
}

const isExecutedDirectly =
  Boolean(process.argv[1]) && process.argv[1].endsWith('run-hook-log-delta-updater.mjs');

if (isExecutedDirectly) {
  try {
    const exitCode = await runHookLogDeltaUpdaterCli(process.argv);
    process.exit(exitCode);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    process.stderr.write(`${message}\n`);
    process.exit(1);
  }
}
