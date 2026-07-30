import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const CONFIG_DIRECTORY_PATH = dirname(fileURLToPath(import.meta.url));

/**
 * @param {string} fileName
 * @returns {unknown}
 */
function readJsonConfigFile(fileName) {
  const absolutePath = join(CONFIG_DIRECTORY_PATH, fileName);
  return JSON.parse(readFileSync(absolutePath, 'utf8'));
}

export const PROFILES_MANIFEST_FILE_NAME = 'profiles.manifest.json';
export const SHARED_ALLOWLIST_FILE_NAME = 'shared-allowlist.json';

/**
 * Sole authoritative profile-root environment variable for CLI isolation.
 * CLAUDE_HOME is never honored as a profile root by this contract.
 */
export const CLAUDE_CONFIG_DIR_ENVIRONMENT_VARIABLE = 'CLAUDE_CONFIG_DIR';
export const CLAUDE_HOME_ENVIRONMENT_VARIABLE = 'CLAUDE_HOME';
export const CLAUDE_CODE_TMPDIR_ENVIRONMENT_VARIABLE = 'CLAUDE_CODE_TMPDIR';
export const CLAUDE_CODE_PLUGIN_SEED_DIR_ENVIRONMENT_VARIABLE = 'CLAUDE_CODE_PLUGIN_SEED_DIR';

export const PROFILES_ROOT_ENVIRONMENT_VARIABLE = 'LLM_SETTINGS_PROFILES_ROOT';
export const SHARED_SOURCE_ROOT_ENVIRONMENT_VARIABLE = 'LLM_SETTINGS_SHARED_SOURCE_ROOT';
export const PLUGIN_SEED_ROOT_ENVIRONMENT_VARIABLE = 'LLM_SETTINGS_PLUGIN_SEED_ROOT';

export const DEFAULT_PROFILES_ROOT_DIRECTORY_NAME = '.claude-profiles';
export const DEFAULT_SHARED_SOURCE_DIRECTORY_NAME = 'shared-source';
export const DEFAULT_PLUGIN_SEED_DIRECTORY_NAME = 'plugin-seed';

export const MIGRATION_MODE_CLEAN_LOCAL_RUNTIME = 'clean-local-runtime';
export const MIGRATION_MODE_MATERIALIZE_FROM_LEGACY = 'materialize-from-legacy';

export const MCP_BUNDLE_LEAN = 'lean';
export const MCP_BUNDLE_FULL = 'full';

export const LAUNCHER_SCHEMA_VERSION = 1;
export const PROFILE_ISOLATION_CONTRACT_OWNER = 'profile-isolation-contract';
export const PACKAGE_FILES_WHITELIST_SCRIPTS_ENTRY = 'scripts/';
export const LIVE_DEPLOYMENT_RESERVED_FOR = 'L1';
export const INSTALL_DESTINATION_ROOT_RELATIVE_PATH = 'scripts/profile-isolation-launchers';

/**
 * @returns {Record<string, unknown>}
 */
export function loadProfilesManifestDocument() {
  return /** @type {Record<string, unknown>} */ (readJsonConfigFile(PROFILES_MANIFEST_FILE_NAME));
}

/**
 * @returns {Record<string, unknown>}
 */
export function loadSharedAllowlistDocument() {
  return /** @type {Record<string, unknown>} */ (readJsonConfigFile(SHARED_ALLOWLIST_FILE_NAME));
}
