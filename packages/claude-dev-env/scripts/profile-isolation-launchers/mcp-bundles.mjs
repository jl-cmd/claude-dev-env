/**
 * Profile MCP bundle validation and materialization.
 *
 * Bundles map to server inventories written through the supported activation
 * interface (profile CLAUDE_CONFIG_DIR mcp.json).
 */

import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  loadProfilesManifestDocument,
  MCP_BUNDLE_FULL,
  MCP_BUNDLE_LEAN,
} from './config/profile-isolation-constants.mjs';
import {
  resolveProfileDefinition,
  validateProfilesManifest,
} from './lib/profile-manifest.mjs';

const MODULE_DIRECTORY = dirname(fileURLToPath(import.meta.url));
const MCP_BUNDLES_CONFIG_PATH = join(MODULE_DIRECTORY, 'config', 'mcp-bundles.json');
const SUPPORTED_ACTIVATION_INTERFACE = 'claude-config-dir-mcp-json';
const DEFAULT_MCP_CONFIG_FILE_NAME = 'mcp.json';

/**
 * @typedef {{
 *   schemaVersion: number,
 *   supportedActivationInterface: string,
 *   mcpConfigFileName: string,
 *   bundles: Record<string, {id: string, allServerNames: string[]}>,
 *   serverByName: Record<string, {command: string, args: string[]}>,
 * }} McpBundlesDocument
 */

/**
 * @returns {McpBundlesDocument}
 */
export function loadMcpBundlesDocument() {
  const raw = JSON.parse(readFileSync(MCP_BUNDLES_CONFIG_PATH, 'utf8'));
  return validateMcpBundlesDocument(raw);
}

/**
 * @param {unknown} maybeDocument
 * @returns {McpBundlesDocument}
 */
export function validateMcpBundlesDocument(maybeDocument) {
  if (!maybeDocument || typeof maybeDocument !== 'object' || Array.isArray(maybeDocument)) {
    throw new Error('mcp bundles document must be a JSON object');
  }
  const document = /** @type {Record<string, unknown>} */ (maybeDocument);
  if (document.schemaVersion !== 1) {
    throw new Error('mcp bundles schemaVersion must be 1');
  }
  if (document.supportedActivationInterface !== SUPPORTED_ACTIVATION_INTERFACE) {
    throw new Error(
      `supportedActivationInterface must be ${SUPPORTED_ACTIVATION_INTERFACE}`,
    );
  }
  const mcpConfigFileName = document.mcpConfigFileName;
  if (typeof mcpConfigFileName !== 'string' || mcpConfigFileName.length === 0) {
    throw new Error('mcpConfigFileName must be a non-empty string');
  }
  if (
    !document.bundles
    || typeof document.bundles !== 'object'
    || Array.isArray(document.bundles)
  ) {
    throw new Error('bundles must be an object');
  }
  if (
    !document.serverByName
    || typeof document.serverByName !== 'object'
    || Array.isArray(document.serverByName)
  ) {
    throw new Error('serverByName must be an object');
  }
  /** @type {Record<string, {id: string, allServerNames: string[]}>} */
  const bundles = {};
  for (const [eachBundleId, eachBundleValue] of Object.entries(
    /** @type {Record<string, unknown>} */ (document.bundles),
  )) {
    if (
      !eachBundleValue
      || typeof eachBundleValue !== 'object'
      || Array.isArray(eachBundleValue)
    ) {
      throw new Error(`bundle ${eachBundleId} must be an object`);
    }
    const bundle = /** @type {Record<string, unknown>} */ (eachBundleValue);
    if (bundle.id !== eachBundleId) {
      throw new Error(`bundle id mismatch for ${eachBundleId}`);
    }
    if (!Array.isArray(bundle.allServerNames) || bundle.allServerNames.length === 0) {
      throw new Error(`bundle ${eachBundleId} requires allServerNames`);
    }
    bundles[eachBundleId] = {
      id: eachBundleId,
      allServerNames: bundle.allServerNames.map(String),
    };
  }
  if (!(MCP_BUNDLE_LEAN in bundles) || !(MCP_BUNDLE_FULL in bundles)) {
    throw new Error('bundles must define lean and full');
  }
  const leanServerNames = new Set(bundles[MCP_BUNDLE_LEAN].allServerNames);
  for (const eachLeanServerName of leanServerNames) {
    if (!bundles[MCP_BUNDLE_FULL].allServerNames.includes(eachLeanServerName)) {
      throw new Error(
        `lean server ${eachLeanServerName} must also appear in full`,
      );
    }
  }
  /** @type {Record<string, {command: string, args: string[]}>} */
  const serverByName = {};
  for (const [eachServerName, eachServerValue] of Object.entries(
    /** @type {Record<string, unknown>} */ (document.serverByName),
  )) {
    if (
      !eachServerValue
      || typeof eachServerValue !== 'object'
      || Array.isArray(eachServerValue)
    ) {
      throw new Error(`server ${eachServerName} must be an object`);
    }
    const server = /** @type {Record<string, unknown>} */ (eachServerValue);
    if (typeof server.command !== 'string' || server.command.length === 0) {
      throw new Error(`server ${eachServerName} requires command`);
    }
    if (!Array.isArray(server.args)) {
      throw new Error(`server ${eachServerName} requires args array`);
    }
    serverByName[eachServerName] = {
      command: server.command,
      args: server.args.map(String),
    };
  }
  for (const eachBundle of Object.values(bundles)) {
    for (const eachServerName of eachBundle.allServerNames) {
      if (!(eachServerName in serverByName)) {
        throw new Error(
          `bundle ${eachBundle.id} references unknown server ${eachServerName}`,
        );
      }
    }
  }
  return {
    schemaVersion: 1,
    supportedActivationInterface: SUPPORTED_ACTIVATION_INTERFACE,
    mcpConfigFileName: String(mcpConfigFileName),
    bundles,
    serverByName,
  };
}

/**
 * Resolve the mcp bundle id for a profile from the profiles manifest.
 *
 * @param {string} profileId
 * @returns {string}
 */
export function resolveProfileMcpBundleId(profileId) {
  const manifest = validateProfilesManifest(loadProfilesManifestDocument());
  try {
    return resolveProfileDefinition(manifest, profileId).mcpBundle;
  } catch (errorValue) {
    if (
      errorValue instanceof Error
      && errorValue.message.startsWith('Unknown profile id or alias:')
    ) {
      throw new Error(`unknown profile id for mcp bundle: ${profileId}`);
    }
    throw errorValue;
  }
}

/**
 * Build the effective MCP server inventory for a bundle id.
 *
 * @param {string} bundleId
 * @param {McpBundlesDocument} [bundlesDocument]
 * @returns {string[]}
 */
export function listServerNamesForBundle(bundleId, bundlesDocument = loadMcpBundlesDocument()) {
  const bundle = bundlesDocument.bundles[bundleId];
  if (!bundle) {
    throw new Error(`unknown mcp bundle id: ${bundleId}`);
  }
  return [...bundle.allServerNames];
}

/**
 * Materialize mcp.json for a profile under CLAUDE_CONFIG_DIR.
 *
 * @param {{
 *   profileId: string,
 *   claudeConfigDir: string,
 *   profileRootPlaceholderValue?: string,
 *   bundlesDocument?: McpBundlesDocument,
 * }} parameters
 * @returns {{
 *   activationInterface: string,
 *   mcpConfigPath: string,
 *   bundleId: string,
 *   allServerNames: string[],
 * }}
 */
export function materializeProfileMcpConfig(parameters) {
  const bundlesDocument = parameters.bundlesDocument ?? loadMcpBundlesDocument();
  if (!parameters.claudeConfigDir || typeof parameters.claudeConfigDir !== 'string') {
    throw new Error('claudeConfigDir is required');
  }
  if (!existsSync(parameters.claudeConfigDir)) {
    mkdirSync(parameters.claudeConfigDir, { recursive: true });
  }
  const bundleId = resolveProfileMcpBundleId(parameters.profileId);
  const allServerNames = listServerNamesForBundle(bundleId, bundlesDocument);
  const profileRootValue = parameters.profileRootPlaceholderValue ?? parameters.claudeConfigDir;
  /** @type {Record<string, {command: string, args: string[]}>} */
  const mcpServers = {};
  for (const eachServerName of allServerNames) {
    const definition = bundlesDocument.serverByName[eachServerName];
    mcpServers[eachServerName] = {
      command: definition.command,
      args: definition.args.map((eachArg) => eachArg.replaceAll('${PROFILE_ROOT}', profileRootValue)),
    };
  }
  const mcpConfigPath = join(parameters.claudeConfigDir, bundlesDocument.mcpConfigFileName);
  writeFileSync(
    mcpConfigPath,
    `${JSON.stringify({ mcpServers }, null, 2)}\n`,
    'utf8',
  );
  return {
    activationInterface: bundlesDocument.supportedActivationInterface,
    mcpConfigPath,
    bundleId,
    allServerNames,
  };
}

/**
 * Read back the effective server inventory from a materialized mcp.json.
 *
 * @param {string} mcpConfigPath
 * @returns {string[]}
 */
export function readEffectiveMcpServerInventory(mcpConfigPath) {
  if (!existsSync(mcpConfigPath)) {
    throw new Error(`mcp config missing: ${mcpConfigPath}`);
  }
  let document;
  try {
    document = JSON.parse(readFileSync(mcpConfigPath, 'utf8'));
  } catch {
    throw new Error(`mcp config malformed: ${mcpConfigPath}`);
  }
  if (
    !document
    || typeof document !== 'object'
    || Array.isArray(document)
    || !document.mcpServers
    || typeof document.mcpServers !== 'object'
    || Array.isArray(document.mcpServers)
  ) {
    throw new Error(`mcp config malformed: ${mcpConfigPath}`);
  }
  return Object.keys(document.mcpServers).sort();
}

export {
  SUPPORTED_ACTIVATION_INTERFACE,
  DEFAULT_MCP_CONFIG_FILE_NAME,
  MCP_BUNDLES_CONFIG_PATH,
};
