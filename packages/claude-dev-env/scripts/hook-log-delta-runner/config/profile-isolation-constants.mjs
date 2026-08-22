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

export const PUBLIC_PIN = /** @type {{
  repositoryLabel: string,
  commitSha: string,
  localWorktreePath: string,
  stopProducerRelativePath: string,
  deltaUpdaterRelativePath: string,
  eventIdMigrationRelativePath: string,
}} */ (readJsonConfigFile('public-pin.json'));

export const PUBLIC_PIN_COMMIT_SHA = PUBLIC_PIN.commitSha;

export const PROFILES_MANIFEST_FILE_NAME = 'profiles.manifest.json';
export const SHARED_ALLOWLIST_FILE_NAME = 'shared-allowlist.json';
export const MCP_BUNDLES_FILE_NAME = 'mcp-bundles.json';
export const PUBLIC_PIN_FILE_NAME = 'public-pin.json';

export const PROFILES_ROOT_ENVIRONMENT_VARIABLE = 'LLM_SETTINGS_PROFILES_ROOT';
export const SHARED_SOURCE_ROOT_ENVIRONMENT_VARIABLE = 'LLM_SETTINGS_SHARED_SOURCE_ROOT';
export const PLUGIN_SEED_ROOT_ENVIRONMENT_VARIABLE = 'LLM_SETTINGS_PLUGIN_SEED_ROOT';
export const CLAUDE_CLI_BINARY_ENVIRONMENT_VARIABLE = 'LLM_SETTINGS_CLAUDE_CLI_PATH';

export const CLAUDE_CONFIG_DIR_ENVIRONMENT_VARIABLE = 'CLAUDE_CONFIG_DIR';
export const CLAUDE_HOME_ENVIRONMENT_VARIABLE = 'CLAUDE_HOME';
export const CLAUDE_CODE_TMPDIR_ENVIRONMENT_VARIABLE = 'CLAUDE_CODE_TMPDIR';
export const CLAUDE_CODE_PLUGIN_SEED_DIR_ENVIRONMENT_VARIABLE = 'CLAUDE_CODE_PLUGIN_SEED_DIR';

export const DEFAULT_PROFILES_ROOT_DIRECTORY_NAME = '.claude-profiles';
export const DEFAULT_SHARED_SOURCE_DIRECTORY_NAME = 'shared-source';
export const DEFAULT_PLUGIN_SEED_DIRECTORY_NAME = 'plugin-seed';
export const DEFAULT_CLAUDE_DIRECTORY_NAME = '.claude';

export const LEASE_FILE_NAME = 'launcher.lease.json';
export const PENDING_MIGRATION_MARKER_FILE_NAME = 'pending-migration.marker';
export const MIGRATION_INVENTORY_FILE_NAME = 'migration-inventory.json';
export const ROLLBACK_METADATA_FILE_NAME = 'rollback-metadata.json';
export const PROFILE_STATE_DIRECTORY_NAME = '.profile-isolation';
export const TELEMETRY_QUEUE_RELATIVE_DIRECTORY = join('logs', 'hooks', '.queue');
export const TELEMETRY_STATE_RELATIVE_DIRECTORY = join('logs', 'hooks', '.state');
export const PROFILE_UUID_FILE_NAME = 'profile_uuid';
export const SETTINGS_FILE_NAME = 'settings.json';
export const SETTINGS_LOCAL_FILE_NAME = 'settings.local.json';
export const CLAUDE_JSON_FILE_NAME = '.claude.json';
export const MASTER_SETTINGS_OVERLAY_FILE_NAME = 'master-settings-overlay.json';
export const UPDATER_MANIFEST_FILE_NAME = 'hook-log-delta-updater-manifest.json';

export const DELTA_UPDATER_MUTEX_NAME = 'claude-dev-env-hook-log-delta-updater';
export const DELTA_UPDATER_GLOBAL_MUTEX_NAMESPACE = `Global\\${DELTA_UPDATER_MUTEX_NAME}`;
export const DELTA_UPDATER_LOCAL_MUTEX_NAMESPACE_DOCUMENTATION_ONLY = `Local\\${DELTA_UPDATER_MUTEX_NAME}`;
export const DELTA_UPDATER_INTERVAL_MINUTES = 30;
export const DELTA_UPDATER_TASK_NAME = 'claude-dev-env-hook-log-delta-updater';
export const DELTA_UPDATER_OVERLAP_POLICY = 'IgnoreNew';
export const DELTA_UPDATER_LOGON_TRIGGER_ENABLED = true;

export const STOP_HOOK_TIMEOUT_SECONDS = 30;
export const STOP_HOOK_COMMAND_TEMPLATE =
  'python "{stopProducerAbsolutePath}"';

export const ACTIVE_GUARD_PROCESS_NAME_PATTERN = /claude/i;
export const ACTIVE_GUARD_DESKTOP_PROCESS_NAME_PATTERN = /claude[- ]?desktop/i;
export const ACTIVE_GUARD_PROCESS_LIST_MAX_BUFFER_BYTES = 20 * 1024 * 1024;

export const LINK_KIND_JUNCTION = 'junction';
export const LINK_KIND_SYMBOLIC = 'symlink';
export const LINK_KIND_NONE = 'none';

export const INVENTORY_ACTION_SHARED_LINK = 'shared-link';
export const INVENTORY_ACTION_SHARED_COPY_FALLBACK = 'shared-copy-fallback';
export const INVENTORY_ACTION_LOCAL_MATERIALIZE = 'local-materialize';
export const INVENTORY_ACTION_LOCAL_EMPTY = 'local-empty';
export const INVENTORY_ACTION_SKIPPED_CREDENTIALS = 'skipped-credentials';
export const INVENTORY_ACTION_SKIPPED_EXISTING_LINK_CONTENTS =
  'skipped-existing-link-contents';

export const SHARED_PATH_MATERIALIZATION_LINK = INVENTORY_ACTION_SHARED_LINK;
export const SHARED_PATH_MATERIALIZATION_COPY_FALLBACK =
  INVENTORY_ACTION_SHARED_COPY_FALLBACK;
export const SHARED_PATH_COPY_FALLBACK_LOG_PREFIX =
  'shared-path-link-fallback:';

export const DELTA_UPDATER_HEALTH_FILE_NAME = 'delta-updater-singleton-health.json';
export const DELTA_UPDATER_HEALTH_CLASSIFICATION_SINGLETON_NON_ZERO =
  'singleton-class-non-zero';
export const DELTA_UPDATER_HEALTH_HONESTY_NOTE =
  'Public pin returns the same exit surface for mutex-busy and Global create-failure; Stage 4 candidate: exit-surface discrimination';

export const DELTA_UPDATER_CLI_MANIFEST_FLAG = '--manifest';
export const DELTA_UPDATER_CLI_UPDATER_FLAG = '--updater';
export const DELTA_UPDATER_CLI_PYTHON_FLAG = '--python';
export const DELTA_UPDATER_CLI_PROFILE_ROOT_FLAG = '--profile-root';
export const DELTA_UPDATER_MANIFEST_PROFILES_FIELD_NAME = 'profiles';
export const DELTA_UPDATER_MANIFEST_PROFILE_ROOT_FIELD_NAME = 'profile_root';

export const MIGRATION_MODE_CLEAN_LOCAL_RUNTIME = 'clean-local-runtime';
export const MIGRATION_MODE_MATERIALIZE_FROM_LEGACY = 'materialize-from-legacy';

export const APPLY_STATUS_APPLIED = 'applied';
export const APPLY_STATUS_DEFERRED = 'deferred';
export const APPLY_STATUS_ALREADY_APPLIED = 'already-applied';
export const APPLY_STATUS_ROLLED_BACK = 'rolled-back';

export const MCP_BUNDLE_LEAN = 'lean';
export const MCP_BUNDLE_FULL = 'full';

export const HONOR_PROBE_MARKER_FILE_NAME = 'honor-probe-marker.txt';
export const HONOR_PROBE_MARKER_CONTENTS = 'profile-isolation-honor-probe';

export const ISOLATION_CRITICAL_RELATIVE_PATHS = Object.freeze([
  '.claude.json',
  'sessions',
  'history',
  'settings.json',
  'plugins',
  'tmp',
]);

/**
 * @returns {typeof import('./profiles.manifest.json')}
 */
export function loadProfilesManifestDocument() {
  return /** @type {any} */ (readJsonConfigFile(PROFILES_MANIFEST_FILE_NAME));
}

/**
 * @returns {typeof import('./shared-allowlist.json')}
 */
export function loadSharedAllowlistDocument() {
  return /** @type {any} */ (readJsonConfigFile(SHARED_ALLOWLIST_FILE_NAME));
}

/**
 * @returns {typeof import('./mcp-bundles.json')}
 */
export function loadMcpBundlesDocument() {
  return /** @type {any} */ (readJsonConfigFile(MCP_BUNDLES_FILE_NAME));
}

/**
 * @returns {string}
 */
export function resolvePinnedStopProducerAbsolutePath() {
  return join(PUBLIC_PIN.localWorktreePath, PUBLIC_PIN.stopProducerRelativePath);
}

/**
 * @returns {string}
 */
export function resolvePinnedDeltaUpdaterAbsolutePath() {
  return join(PUBLIC_PIN.localWorktreePath, PUBLIC_PIN.deltaUpdaterRelativePath);
}

/**
 * @returns {string}
 */
export function resolvePinnedEventIdMigrationAbsolutePath() {
  return join(PUBLIC_PIN.localWorktreePath, PUBLIC_PIN.eventIdMigrationRelativePath);
}
