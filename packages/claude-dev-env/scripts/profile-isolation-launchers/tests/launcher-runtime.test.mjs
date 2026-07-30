import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { mkdtempSync, rmSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import { dirname } from 'node:path';
import {
  activateLauncherMcpBundle,
  activateProfileMcpBundle,
  describeLeanServerBoundary,
  formatProfileMcpActivationFailure,
  listMcpActivationPackageRelativePaths,
  resolveProfileIdForLauncherName,
  SUPPORTED_ACTIVATION_INTERFACE,
} from '../launcher-runtime.mjs';
import { readEffectiveMcpServerInventory } from '../mcp-bundles.mjs';
import { CLAUDE_CONFIG_DIR_ENVIRONMENT_VARIABLE } from '../config/profile-isolation-constants.mjs';

const PACKAGE_ROOT = join(
  dirname(fileURLToPath(import.meta.url)),
  '..',
  '..',
  '..',
);

test('claude-profile-a and claude-profile-b resolve to profile-a and profile-b profiles', () => {
  assert.equal(resolveProfileIdForLauncherName('claude-profile-a'), 'profile-a');
  assert.equal(resolveProfileIdForLauncherName('claude-profile-b'), 'profile-b');
});

test('activateLauncherMcpBundle materializes lean inventory for profile-a and profile-b', () => {
  const profileADir = mkdtempSync(join(tmpdir(), 'launcher-profile-a-'));
  const profileBDir = mkdtempSync(join(tmpdir(), 'launcher-profile-b-'));
  try {
    const profileA = activateLauncherMcpBundle({
      launcherName: 'claude-profile-a',
      claudeConfigDir: profileADir,
    });
    const profileB = activateLauncherMcpBundle({
      launcherName: 'claude-profile-b',
      claudeConfigDir: profileBDir,
    });
    assert.equal(profileA.activationInterface, SUPPORTED_ACTIVATION_INTERFACE);
    assert.equal(profileB.activationInterface, SUPPORTED_ACTIVATION_INTERFACE);
    assert.equal(profileA.bundleId, 'lean');
    assert.equal(profileB.bundleId, 'lean');
    assert.equal(
      profileA.environment[CLAUDE_CONFIG_DIR_ENVIRONMENT_VARIABLE],
      profileADir,
    );
    assert.deepEqual(
      readEffectiveMcpServerInventory(profileA.mcpConfigPath),
      profileA.expectedInventory,
    );
    assert.deepEqual(
      readEffectiveMcpServerInventory(profileB.mcpConfigPath),
      profileB.expectedInventory,
    );
  } finally {
    rmSync(profileADir, { recursive: true, force: true });
    rmSync(profileBDir, { recursive: true, force: true });
  }
});

test('lean aliases expose only lean servers', () => {
  const boundary = describeLeanServerBoundary();
  assert.ok(boundary.leanServers.length >= 1);
  assert.ok(boundary.fullServers.length >= boundary.leanServers.length);
  for (const eachLeanServer of boundary.leanServers) {
    assert.ok(boundary.fullServers.includes(eachLeanServer));
  }
  assert.ok(boundary.fullOnlyServers.every((eachName) => !boundary.leanServers.includes(eachName)));

  const claudeConfigDir = mkdtempSync(join(tmpdir(), 'launcher-lean-'));
  try {
    const activation = activateProfileMcpBundle({
      profileId: 'profile-a',
      claudeConfigDir,
    });
    assert.deepEqual(activation.expectedInventory, boundary.leanServers);
    for (const eachFullOnly of boundary.fullOnlyServers) {
      assert.ok(!activation.expectedInventory.includes(eachFullOnly));
    }
  } finally {
    rmSync(claudeConfigDir, { recursive: true, force: true });
  }
});

test('unknown launcher name fails with an actionable message', () => {
  assert.throws(
    () => resolveProfileIdForLauncherName('claude-does-not-exist'),
    /no profile owns launcher name/,
  );
  const message = formatProfileMcpActivationFailure(
    'profile-a',
    new Error('bundle missing'),
  );
  assert.match(message, /profile profile-a mcp activation failed/);
  assert.match(message, /bundle missing/);
});

test('package-relative MCP activation paths exist for pack verification', () => {
  const allPaths = listMcpActivationPackageRelativePaths(PACKAGE_ROOT);
  for (const eachPath of allPaths) {
    assert.ok(existsSync(eachPath), `missing pack path: ${eachPath}`);
  }
});
