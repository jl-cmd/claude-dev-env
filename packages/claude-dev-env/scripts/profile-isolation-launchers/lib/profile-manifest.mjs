import { join } from 'node:path';

import {
  loadProfilesManifestDocument,
  loadSharedAllowlistDocument,
  MCP_BUNDLE_FULL,
  MCP_BUNDLE_LEAN,
  MIGRATION_MODE_CLEAN_LOCAL_RUNTIME,
  MIGRATION_MODE_MATERIALIZE_FROM_LEGACY,
} from '../config/profile-isolation-constants.mjs';

/**
 * @typedef {{
 *   id: string,
 *   aliases: string[],
 *   directoryName: string,
 *   launcherNames: string[],
 *   fullLauncherNames: string[],
 *   migrationMode: string,
 *   mcpBundle: string,
 * }} ProfileDefinition
 */

/**
 * @typedef {{
 *   schemaVersion: number,
 *   profilesRootPlaceholder: string,
 *   sharedSourcePlaceholder: string,
 *   pluginSeedPlaceholder: string,
 *   migrationOrder: string[],
 *   profileById: Record<string, ProfileDefinition>,
 * }} ValidatedProfilesManifest
 */

/**
 * @typedef {{
 *   schemaVersion: number,
 *   allSharedRelativePaths: string[],
 *   allAlwaysLocalRelativePaths: string[],
 *   allDesktopExcludedPathFragments: string[],
 * }} ValidatedSharedAllowlist
 */

const ALL_ALLOWED_MIGRATION_MODES = new Set([
  MIGRATION_MODE_CLEAN_LOCAL_RUNTIME,
  MIGRATION_MODE_MATERIALIZE_FROM_LEGACY,
]);

const ALL_ALLOWED_MCP_BUNDLES = new Set([MCP_BUNDLE_LEAN, MCP_BUNDLE_FULL]);

/**
 * @param {unknown} maybeManifest
 * @returns {ValidatedProfilesManifest}
 */
export function validateProfilesManifest(maybeManifest) {
  if (!isPlainObject(maybeManifest)) {
    throw new Error('profiles manifest must be a JSON object');
  }
  const schemaVersion = maybeManifest.schemaVersion;
  if (schemaVersion !== 1) {
    throw new Error('profiles manifest schemaVersion must be 1');
  }
  if (!Array.isArray(maybeManifest.migrationOrder) || maybeManifest.migrationOrder.length === 0) {
    throw new Error('profiles manifest migrationOrder must be a non-empty array');
  }
  if (!isPlainObject(maybeManifest.profiles)) {
    throw new Error('profiles manifest profiles must be an object');
  }
  /** @type {Record<string, ProfileDefinition>} */
  const profileById = {};
  for (const [eachProfileKey, eachProfileValue] of Object.entries(maybeManifest.profiles)) {
    profileById[eachProfileKey] = validateProfileDefinition(eachProfileKey, eachProfileValue);
  }
  for (const eachOrderedProfileId of maybeManifest.migrationOrder) {
    if (typeof eachOrderedProfileId !== 'string' || !(eachOrderedProfileId in profileById)) {
      throw new Error(`migrationOrder references unknown profile id: ${String(eachOrderedProfileId)}`);
    }
  }
  return {
    schemaVersion,
    profilesRootPlaceholder: requireNonEmptyString(
      maybeManifest.profilesRootPlaceholder,
      'profilesRootPlaceholder',
    ),
    sharedSourcePlaceholder: requireNonEmptyString(
      maybeManifest.sharedSourcePlaceholder,
      'sharedSourcePlaceholder',
    ),
    pluginSeedPlaceholder: requireNonEmptyString(
      maybeManifest.pluginSeedPlaceholder,
      'pluginSeedPlaceholder',
    ),
    migrationOrder: maybeManifest.migrationOrder.map(String),
    profileById,
  };
}

/**
 * @param {unknown} maybeAllowlist
 * @returns {ValidatedSharedAllowlist}
 */
export function validateSharedAllowlist(maybeAllowlist) {
  if (!isPlainObject(maybeAllowlist)) {
    throw new Error('shared allowlist must be a JSON object');
  }
  if (maybeAllowlist.schemaVersion !== 1) {
    throw new Error('shared allowlist schemaVersion must be 1');
  }
  return {
    schemaVersion: 1,
    allSharedRelativePaths: requireStringArray(
      maybeAllowlist.allSharedRelativePaths,
      'allSharedRelativePaths',
    ),
    allAlwaysLocalRelativePaths: requireStringArray(
      maybeAllowlist.allAlwaysLocalRelativePaths,
      'allAlwaysLocalRelativePaths',
    ),
    allDesktopExcludedPathFragments: requireStringArray(
      maybeAllowlist.allDesktopExcludedPathFragments,
      'allDesktopExcludedPathFragments',
    ),
  };
}

/**
 * @returns {ValidatedProfilesManifest}
 */
export function loadAndValidateProfilesManifest() {
  return validateProfilesManifest(loadProfilesManifestDocument());
}

/**
 * @returns {ValidatedSharedAllowlist}
 */
export function loadAndValidateSharedAllowlist() {
  return validateSharedAllowlist(loadSharedAllowlistDocument());
}

/**
 * @param {ValidatedProfilesManifest} validatedManifest
 * @param {string} profileIdOrAlias
 * @returns {ProfileDefinition}
 */
export function resolveProfileDefinition(validatedManifest, profileIdOrAlias) {
  const normalizedIdentity = profileIdOrAlias.trim().toLowerCase();
  for (const eachProfile of Object.values(validatedManifest.profileById)) {
    if (eachProfile.id === normalizedIdentity) {
      return eachProfile;
    }
    if (eachProfile.aliases.includes(normalizedIdentity)) {
      return eachProfile;
    }
    if (eachProfile.launcherNames.includes(normalizedIdentity)) {
      return eachProfile;
    }
    if (eachProfile.fullLauncherNames.includes(normalizedIdentity)) {
      return eachProfile;
    }
  }
  throw new Error(`Unknown profile id or alias: ${profileIdOrAlias}`);
}

/**
 * @param {string} profilesRootDirectoryPath
 * @param {ProfileDefinition} profileDefinition
 * @returns {string}
 */
export function resolveProfileRootDirectoryPath(profilesRootDirectoryPath, profileDefinition) {
  return join(profilesRootDirectoryPath, profileDefinition.directoryName);
}

/**
 * @param {string} profileKey
 * @param {unknown} maybeProfile
 * @returns {ProfileDefinition}
 */
function validateProfileDefinition(profileKey, maybeProfile) {
  if (!isPlainObject(maybeProfile)) {
    throw new Error(`profile ${profileKey} must be an object`);
  }
  const profileId = requireNonEmptyString(maybeProfile.id, `${profileKey}.id`);
  if (profileId !== profileKey) {
    throw new Error(`profile key ${profileKey} must match id ${profileId}`);
  }
  const migrationMode = requireNonEmptyString(maybeProfile.migrationMode, `${profileKey}.migrationMode`);
  if (!ALL_ALLOWED_MIGRATION_MODES.has(migrationMode)) {
    throw new Error(`profile ${profileKey} has unsupported migrationMode: ${migrationMode}`);
  }
  const mcpBundle = requireNonEmptyString(maybeProfile.mcpBundle, `${profileKey}.mcpBundle`);
  if (!ALL_ALLOWED_MCP_BUNDLES.has(mcpBundle)) {
    throw new Error(`profile ${profileKey} has unsupported mcpBundle: ${mcpBundle}`);
  }
  return {
    id: profileId,
    aliases: requireStringArray(maybeProfile.aliases, `${profileKey}.aliases`),
    directoryName: requireNonEmptyString(maybeProfile.directoryName, `${profileKey}.directoryName`),
    launcherNames: requireStringArray(maybeProfile.launcherNames, `${profileKey}.launcherNames`),
    fullLauncherNames: requireStringArray(
      maybeProfile.fullLauncherNames,
      `${profileKey}.fullLauncherNames`,
    ),
    migrationMode,
    mcpBundle,
  };
}

/**
 * @param {unknown} candidate
 * @returns {candidate is Record<string, unknown>}
 */
function isPlainObject(candidate) {
  return typeof candidate === 'object' && candidate !== null && !Array.isArray(candidate);
}

/**
 * @param {unknown} candidate
 * @param {string} fieldName
 * @returns {string}
 */
function requireNonEmptyString(candidate, fieldName) {
  if (typeof candidate !== 'string' || candidate.trim() === '') {
    throw new Error(`${fieldName} must be a non-empty string`);
  }
  return candidate;
}

/**
 * @param {unknown} candidate
 * @param {string} fieldName
 * @returns {string[]}
 */
function requireStringArray(candidate, fieldName) {
  if (!Array.isArray(candidate) || candidate.some((eachEntry) => typeof eachEntry !== 'string')) {
    throw new Error(`${fieldName} must be an array of strings`);
  }
  return candidate.map(String);
}
