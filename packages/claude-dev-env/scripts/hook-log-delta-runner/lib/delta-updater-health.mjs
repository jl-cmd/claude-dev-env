import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';

import {
  DELTA_UPDATER_HEALTH_CLASSIFICATION_SINGLETON_NON_ZERO,
  DELTA_UPDATER_HEALTH_FILE_NAME,
  DELTA_UPDATER_HEALTH_HONESTY_NOTE,
  TELEMETRY_STATE_RELATIVE_DIRECTORY,
} from '../config/profile-isolation-constants.mjs';

/**
 * @typedef {{
 *   recordedAtIso: string,
 *   exitCode: number,
 *   classification: string,
 *   honestyNote: string,
 * }} DeltaUpdaterHealthRecord
 */

/**
 * @typedef {{
 *   exitCode: number | null,
 *   didRecordHealth: boolean,
 *   allHealthFilePaths: string[],
 * }} DeltaUpdaterHealthObservation
 */

/**
 * Resolve the singleton-class health file under profile telemetry state.
 *
 * @param {string} profileRootDirectoryPath
 * @returns {string}
 */
export function resolveDeltaUpdaterHealthFilePath(profileRootDirectoryPath) {
  return join(
    profileRootDirectoryPath,
    TELEMETRY_STATE_RELATIVE_DIRECTORY,
    DELTA_UPDATER_HEALTH_FILE_NAME,
  );
}

/**
 * Record a non-zero singleton-class public-updater exit to profile state health.
 * Does not claim create-failure vs busy discrimination — public pin shares one surface.
 *
 * @param {{
 *   profileRootDirectoryPath: string,
 *   exitCode: number,
 *   recordedAtIso?: string,
 * }} parameters
 * @returns {Promise<DeltaUpdaterHealthRecord>}
 */
export async function recordSingletonClassNonZeroExit({
  profileRootDirectoryPath,
  exitCode,
  recordedAtIso = new Date().toISOString(),
}) {
  const healthRecord = {
    recordedAtIso,
    exitCode,
    classification: DELTA_UPDATER_HEALTH_CLASSIFICATION_SINGLETON_NON_ZERO,
    honestyNote: DELTA_UPDATER_HEALTH_HONESTY_NOTE,
  };
  const healthFilePath = resolveDeltaUpdaterHealthFilePath(profileRootDirectoryPath);
  await mkdir(dirname(healthFilePath), { recursive: true });
  await writeFile(healthFilePath, `${JSON.stringify(healthRecord, null, 2)}\n`, 'utf8');
  return healthRecord;
}

/**
 * Observe a public updater exit and record non-zero singleton-class exits to health.
 *
 * @param {{
 *   allProfileRootDirectoryPaths: string[],
 *   runUpdater: () => Promise<{ exitCode: number | null }>,
 * }} parameters
 * @returns {Promise<DeltaUpdaterHealthObservation>}
 */
export async function runDeltaUpdaterObservingHealth({
  allProfileRootDirectoryPaths,
  runUpdater,
}) {
  const updaterRun = await runUpdater();
  const exitCode = updaterRun.exitCode;
  if (typeof exitCode !== 'number' || exitCode === 0) {
    return {
      exitCode,
      didRecordHealth: false,
      allHealthFilePaths: [],
    };
  }
  /** @type {string[]} */
  const allHealthFilePaths = [];
  for (const eachProfileRootDirectoryPath of allProfileRootDirectoryPaths) {
    await recordSingletonClassNonZeroExit({
      profileRootDirectoryPath: eachProfileRootDirectoryPath,
      exitCode,
    });
    allHealthFilePaths.push(
      resolveDeltaUpdaterHealthFilePath(eachProfileRootDirectoryPath),
    );
  }
  return {
    exitCode,
    didRecordHealth: true,
    allHealthFilePaths,
  };
}

/**
 * @param {string} profileRootDirectoryPath
 * @returns {Promise<DeltaUpdaterHealthRecord | null>}
 */
export async function readDeltaUpdaterHealthRecord(profileRootDirectoryPath) {
  try {
    const healthRaw = await readFile(
      resolveDeltaUpdaterHealthFilePath(profileRootDirectoryPath),
      'utf8',
    );
    return /** @type {DeltaUpdaterHealthRecord} */ (JSON.parse(healthRaw));
  } catch {
    return null;
  }
}
