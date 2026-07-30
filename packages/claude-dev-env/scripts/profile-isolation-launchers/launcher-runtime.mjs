/**
 * Launcher runtime helpers for MCP activation through a supported interface.
 */

import { join } from 'node:path';
import {
  CLAUDE_CONFIG_DIR_ENVIRONMENT_VARIABLE,
  loadProfilesManifestDocument,
  MCP_BUNDLE_FULL,
  MCP_BUNDLE_LEAN,
} from './config/profile-isolation-constants.mjs';
import {
  resolveProfileDefinition,
  validateProfilesManifest,
} from './lib/profile-manifest.mjs';
import {
  listServerNamesForBundle,
  loadMcpBundlesDocument,
  materializeProfileMcpConfig,
  resolveProfileMcpBundleId,
  SUPPORTED_ACTIVATION_INTERFACE,
} from './mcp-bundles.mjs';

/**
 * Resolve a launcher name to a profile id from the profiles manifest.
 *
 * @param {string} launcherName
 * @returns {string}
 */
export function resolveProfileIdForLauncherName(launcherName) {
  const manifest = validateProfilesManifest(loadProfilesManifestDocument());
  try {
    return resolveProfileDefinition(manifest, launcherName).id;
  } catch {
    throw new Error(`no profile owns launcher name: ${launcherName}`);
  }
}

/**
 * Assemble activation for one profile into a disposable CLAUDE_CONFIG_DIR.
 *
 * @param {{
 *   profileId: string,
 *   claudeConfigDir: string,
 * }} parameters
 * @returns {{
 *   profileId: string,
 *   environment: Record<string, string>,
 *   activationInterface: string,
 *   mcpConfigPath: string,
 *   bundleId: string,
 *   allServerNames: string[],
 *   expectedInventory: string[],
 * }}
 */
export function activateProfileMcpBundle(parameters) {
  const bundlesDocument = loadMcpBundlesDocument();
  const materialization = materializeProfileMcpConfig({
    profileId: parameters.profileId,
    claudeConfigDir: parameters.claudeConfigDir,
    bundlesDocument,
  });
  const expectedInventory = [...materialization.allServerNames].sort();
  return {
    profileId: parameters.profileId,
    environment: {
      [CLAUDE_CONFIG_DIR_ENVIRONMENT_VARIABLE]: parameters.claudeConfigDir,
    },
    activationInterface: materialization.activationInterface,
    mcpConfigPath: materialization.mcpConfigPath,
    bundleId: materialization.bundleId,
    allServerNames: materialization.allServerNames,
    expectedInventory,
  };
}

/**
 * Activate MCP for a launcher name (claude-editor / claude-mel).
 *
 * @param {{
 *   launcherName: string,
 *   claudeConfigDir: string,
 * }} parameters
 * @returns {ReturnType<typeof activateProfileMcpBundle>}
 */
export function activateLauncherMcpBundle(parameters) {
  const profileId = resolveProfileIdForLauncherName(parameters.launcherName);
  return activateProfileMcpBundle({
    profileId,
    claudeConfigDir: parameters.claudeConfigDir,
  });
}

/**
 * Lean-boundary check: lean inventory is a subset of full and excludes full-only servers.
 *
 * @returns {{leanServers: string[], fullServers: string[], fullOnlyServers: string[]}}
 */
export function describeLeanServerBoundary() {
  const bundlesDocument = loadMcpBundlesDocument();
  const leanServers = listServerNamesForBundle(MCP_BUNDLE_LEAN, bundlesDocument).sort();
  const fullServers = listServerNamesForBundle(MCP_BUNDLE_FULL, bundlesDocument).sort();
  const leanSet = new Set(leanServers);
  const fullOnlyServers = fullServers.filter((eachName) => !leanSet.has(eachName));
  return { leanServers, fullServers, fullOnlyServers };
}

/**
 * Build a diagnostic when a required bundle or profile is invalid.
 *
 * @param {string} profileId
 * @param {unknown} errorValue
 * @returns {string}
 */
export function formatProfileMcpActivationFailure(profileId, errorValue) {
  const message = errorValue instanceof Error ? errorValue.message : String(errorValue);
  return `profile ${profileId} mcp activation failed: ${message}`;
}

/**
 * Path helpers for tests and pack verification.
 *
 * @param {string} packageRoot
 * @returns {string[]}
 */
export function listMcpActivationPackageRelativePaths(packageRoot) {
  return [
    join(packageRoot, 'scripts/profile-isolation-launchers/mcp-bundles.mjs'),
    join(packageRoot, 'scripts/profile-isolation-launchers/launcher-runtime.mjs'),
    join(packageRoot, 'scripts/profile-isolation-launchers/config/mcp-bundles.json'),
    join(packageRoot, 'scripts/profile-isolation-launchers/config/profiles.manifest.json'),
    join(packageRoot, 'scripts/profile-isolation-launchers/tests/mcp-bundles.test.mjs'),
    join(packageRoot, 'scripts/profile-isolation-launchers/tests/launcher-runtime.test.mjs'),
  ];
}

export {
  SUPPORTED_ACTIVATION_INTERFACE,
  resolveProfileMcpBundleId,
};
