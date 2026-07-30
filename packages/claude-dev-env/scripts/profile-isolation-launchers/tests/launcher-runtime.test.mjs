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

test('claude-editor and claude-mel resolve to editor and mel profiles', () => {
  assert.equal(resolveProfileIdForLauncherName('claude-editor'), 'editor');
  assert.equal(resolveProfileIdForLauncherName('claude-mel'), 'mel');
});

test('activateLauncherMcpBundle materializes lean inventory for editor and mel', () => {
  const editorDir = mkdtempSync(join(tmpdir(), 'launcher-editor-'));
  const melDir = mkdtempSync(join(tmpdir(), 'launcher-mel-'));
  try {
    const editor = activateLauncherMcpBundle({
      launcherName: 'claude-editor',
      claudeConfigDir: editorDir,
    });
    const mel = activateLauncherMcpBundle({
      launcherName: 'claude-mel',
      claudeConfigDir: melDir,
    });
    assert.equal(editor.activationInterface, SUPPORTED_ACTIVATION_INTERFACE);
    assert.equal(mel.activationInterface, SUPPORTED_ACTIVATION_INTERFACE);
    assert.equal(editor.bundleId, 'lean');
    assert.equal(mel.bundleId, 'lean');
    assert.equal(
      editor.environment[CLAUDE_CONFIG_DIR_ENVIRONMENT_VARIABLE],
      editorDir,
    );
    assert.deepEqual(
      readEffectiveMcpServerInventory(editor.mcpConfigPath),
      editor.expectedInventory,
    );
    assert.deepEqual(
      readEffectiveMcpServerInventory(mel.mcpConfigPath),
      mel.expectedInventory,
    );
  } finally {
    rmSync(editorDir, { recursive: true, force: true });
    rmSync(melDir, { recursive: true, force: true });
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
      profileId: 'editor',
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
    'editor',
    new Error('bundle missing'),
  );
  assert.match(message, /profile editor mcp activation failed/);
  assert.match(message, /bundle missing/);
});

test('package-relative MCP activation paths exist for pack verification', () => {
  const allPaths = listMcpActivationPackageRelativePaths(PACKAGE_ROOT);
  for (const eachPath of allPaths) {
    assert.ok(existsSync(eachPath), `missing pack path: ${eachPath}`);
  }
});
