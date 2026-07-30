import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { execFileSync } from 'node:child_process';
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  CLAUDE_CONFIG_DIR_ENVIRONMENT_VARIABLE,
  CLAUDE_HOME_ENVIRONMENT_VARIABLE,
  INSTALL_DESTINATION_ROOT_RELATIVE_PATH,
  LAUNCHER_SCHEMA_VERSION,
  LIVE_DEPLOYMENT_RESERVED_FOR,
  loadProfilesManifestDocument,
  loadSharedAllowlistDocument,
  PACKAGE_FILES_WHITELIST_SCRIPTS_ENTRY,
  PROFILE_ISOLATION_CONTRACT_OWNER,
} from './config/profile-isolation-constants.mjs';
import {
  loadAndValidateProfilesManifest,
  loadAndValidateSharedAllowlist,
  resolveProfileDefinition,
  resolveProfileRootDirectoryPath,
  validateProfilesManifest,
  validateSharedAllowlist,
} from './lib/profile-manifest.mjs';

const CONTRACT_ROOT_DIRECTORY_PATH = dirname(fileURLToPath(import.meta.url));
const PACKAGE_ROOT_DIRECTORY_PATH = join(CONTRACT_ROOT_DIRECTORY_PATH, '..', '..');
const REPOSITORY_ROOT_DIRECTORY_PATH = join(PACKAGE_ROOT_DIRECTORY_PATH, '..', '..');

const ALL_REQUIRED_CONTRACT_SOURCE_RELATIVE_PATHS = Object.freeze([
  'config/profile-isolation-constants.mjs',
  'config/profiles.manifest.json',
  'config/shared-allowlist.json',
  'lib/profile-manifest.mjs',
]);

/** J1 MCP activation sources allowed beside the A1a contract surface. */
const ALL_ALLOWED_MCP_ACTIVATION_RELATIVE_PATHS = Object.freeze([
  'config/mcp-bundles.json',
  'mcp-bundles.mjs',
  'launcher-runtime.mjs',
  'tests/mcp-bundles.test.mjs',
  'tests/launcher-runtime.test.mjs',
]);

test('profiles manifest schemaVersion is 1 and every migrationOrder id resolves', () => {
  const validatedManifest = loadAndValidateProfilesManifest();
  assert.equal(validatedManifest.schemaVersion, 1);
  assert.equal(LAUNCHER_SCHEMA_VERSION, 1);
  for (const eachProfileId of validatedManifest.migrationOrder) {
    assert.equal(resolveProfileDefinition(validatedManifest, eachProfileId).id, eachProfileId);
  }
});

test('resolveProfileDefinition accepts id, alias, and launcher names', () => {
  const validatedManifest = loadAndValidateProfilesManifest();
  assert.equal(resolveProfileDefinition(validatedManifest, 'master').id, 'master');
  assert.equal(resolveProfileDefinition(validatedManifest, 'default').id, 'master');
  assert.equal(resolveProfileDefinition(validatedManifest, 'claude').id, 'master');
  assert.equal(resolveProfileDefinition(validatedManifest, 'claude-full').id, 'master');
  assert.equal(resolveProfileDefinition(validatedManifest, 'profile-c').id, 'profile-c');
  assert.equal(resolveProfileDefinition(validatedManifest, 'claude-profile-c').id, 'profile-c');
  assert.equal(resolveProfileDefinition(validatedManifest, 'claude-profile-b-full').id, 'profile-b');
  assert.equal(resolveProfileDefinition(validatedManifest, 'Master').id, 'master');
  assert.equal(resolveProfileDefinition(validatedManifest, ' CLAUDE-PROFILE-C ').id, 'profile-c');
  assert.throws(
    () => resolveProfileDefinition(validatedManifest, 'not-a-profile'),
    /Unknown profile id or alias/,
  );
  assert.throws(
    () => resolveProfileDefinition(validatedManifest, /** @type {string} */ (/** @type {unknown} */ (42))),
    /Unknown profile id or alias/,
  );
});

test('shared allowlist names shared paths, always-local paths, and desktop exclusions', () => {
  const validatedAllowlist = loadAndValidateSharedAllowlist();
  assert.equal(validatedAllowlist.schemaVersion, 1);
  assert.ok(validatedAllowlist.allSharedRelativePaths.includes('scripts'));
  assert.ok(validatedAllowlist.allSharedRelativePaths.includes('hooks'));
  assert.ok(validatedAllowlist.allAlwaysLocalRelativePaths.includes('settings.json'));
  assert.ok(validatedAllowlist.allAlwaysLocalRelativePaths.includes('credentials'));
  assert.ok(
    validatedAllowlist.allDesktopExcludedPathFragments.some((eachFragment) =>
      eachFragment.toLowerCase().includes('desktop'),
    ),
  );
});

test('validators reject bad schemaVersion and non-object allowlist', () => {
  const rawManifest = loadProfilesManifestDocument();
  assert.throws(
    () => validateProfilesManifest({ ...rawManifest, schemaVersion: 0 }),
    /schemaVersion must be 1/,
  );
  assert.throws(() => validateSharedAllowlist(null), /shared allowlist must be a JSON object/);
  assert.equal(typeof loadSharedAllowlistDocument(), 'object');
});

test('validators reject duplicate launcher identities across profiles', () => {
  const rawManifest = loadProfilesManifestDocument();
  const profiles = {
    .../** @type {Record<string, object>} */ (rawManifest.profiles),
  };
  const masterProfile = { ...profiles.master, launcherNames: ['claude', 'claude-profile-c'] };
  const profileCDefinition = { ...profiles["profile-c"] };
  assert.throws(
    () =>
      validateProfilesManifest({
        ...rawManifest,
        profiles: { ...profiles, master: masterProfile, 'profile-c': profileCDefinition },
      }),
    /duplicate profile identity/,
  );
});

test('CLAUDE_CONFIG_DIR is the sole authoritative profile-root variable name', () => {
  assert.equal(CLAUDE_CONFIG_DIR_ENVIRONMENT_VARIABLE, 'CLAUDE_CONFIG_DIR');
  assert.equal(CLAUDE_HOME_ENVIRONMENT_VARIABLE, 'CLAUDE_HOME');
  assert.notEqual(CLAUDE_CONFIG_DIR_ENVIRONMENT_VARIABLE, CLAUDE_HOME_ENVIRONMENT_VARIABLE);
  const constantsSource = readFileSync(
    join(CONTRACT_ROOT_DIRECTORY_PATH, 'config', 'profile-isolation-constants.mjs'),
    'utf8',
  );
  assert.match(constantsSource, /Sole authoritative profile-root environment variable/);
  assert.match(constantsSource, /CLAUDE_HOME is never honored as a profile root/);
});

test('resolveProfileRootDirectoryPath joins profiles root with directoryName', () => {
  const validatedManifest = loadAndValidateProfilesManifest();
  const profileCDefinition = resolveProfileDefinition(validatedManifest, 'profile-c');
  assert.equal(
    resolveProfileRootDirectoryPath('/profiles', profileCDefinition),
    join('/profiles', 'profile-c'),
  );
});

test('package ships contract under scripts/, reserves live deploy for L1, and holds only A1a files', () => {
  const packageJson = JSON.parse(
    readFileSync(join(PACKAGE_ROOT_DIRECTORY_PATH, 'package.json'), 'utf8'),
  );
  assert.ok(packageJson.files.includes(PACKAGE_FILES_WHITELIST_SCRIPTS_ENTRY));
  assert.equal(INSTALL_DESTINATION_ROOT_RELATIVE_PATH, 'scripts/profile-isolation-launchers');
  assert.equal(LIVE_DEPLOYMENT_RESERVED_FOR, 'L1');
  assert.equal(PROFILE_ISOLATION_CONTRACT_OWNER, 'profile-isolation-contract');

  /** @type {string[]} */
  const allRelativePaths = [];
  /**
   * @param {string} currentDirectoryPath
   */
  function walk(currentDirectoryPath) {
    for (const eachEntry of readdirSync(currentDirectoryPath, { withFileTypes: true })) {
      const eachAbsolutePath = join(currentDirectoryPath, eachEntry.name);
      if (eachEntry.isDirectory()) {
        walk(eachAbsolutePath);
        continue;
      }
      if (eachEntry.isFile()) {
        allRelativePaths.push(
          relative(CONTRACT_ROOT_DIRECTORY_PATH, eachAbsolutePath).split(sep).join('/'),
        );
      }
    }
  }
  walk(CONTRACT_ROOT_DIRECTORY_PATH);
  const allExpectedPaths = new Set([
    ...ALL_REQUIRED_CONTRACT_SOURCE_RELATIVE_PATHS,
    ...ALL_ALLOWED_MCP_ACTIVATION_RELATIVE_PATHS,
    'profile-isolation-contract.test.mjs',
  ]);
  for (const eachRelativePath of allRelativePaths) {
    assert.ok(allExpectedPaths.has(eachRelativePath), `unexpected A1a file: ${eachRelativePath}`);
  }
  for (const eachRequiredPath of ALL_REQUIRED_CONTRACT_SOURCE_RELATIVE_PATHS) {
    const absolutePath = join(CONTRACT_ROOT_DIRECTORY_PATH, ...eachRequiredPath.split('/'));
    assert.ok(existsSync(absolutePath) && statSync(absolutePath).isFile());
  }
});

test('committed contract sources are tracked by git (not dirty-worktree-only)', () => {
  for (const eachRelativePath of ALL_REQUIRED_CONTRACT_SOURCE_RELATIVE_PATHS) {
    const repositoryRelativePath =
      `packages/claude-dev-env/scripts/profile-isolation-launchers/${eachRelativePath}`;
    const lsFilesOutput = execFileSync(
      'git',
      ['ls-files', '--', repositoryRelativePath],
      { cwd: REPOSITORY_ROOT_DIRECTORY_PATH, encoding: 'utf8' },
    ).trim();
    assert.ok(lsFilesOutput.length > 0, `expected git-tracked source for ${eachRelativePath}`);
    const porcelain = execFileSync(
      'git',
      ['status', '--porcelain', '--', repositoryRelativePath],
      { cwd: REPOSITORY_ROOT_DIRECTORY_PATH, encoding: 'utf8' },
    ).trim();
    assert.equal(
      porcelain,
      '',
      `launcher file must be clean committed source: ${eachRelativePath} status=${porcelain}`,
    );
  }
});
