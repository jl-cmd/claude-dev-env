import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { mkdtempSync, readFileSync, rmSync, writeFileSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import {
  listServerNamesForBundle,
  loadMcpBundlesDocument,
  materializeProfileMcpConfig,
  readEffectiveMcpServerInventory,
  resolveProfileMcpBundleId,
  SUPPORTED_ACTIVATION_INTERFACE,
  validateMcpBundlesDocument,
} from '../mcp-bundles.mjs';

test('mcp bundles document loads with lean and full inventories', () => {
  const document = loadMcpBundlesDocument();
  assert.equal(document.supportedActivationInterface, SUPPORTED_ACTIVATION_INTERFACE);
  assert.ok(document.bundles.lean.allServerNames.length >= 1);
  assert.ok(document.bundles.full.allServerNames.length >= document.bundles.lean.allServerNames.length);
});

test('editor and mel resolve to lean mcp bundles from the profiles manifest', () => {
  assert.equal(resolveProfileMcpBundleId('editor'), 'lean');
  assert.equal(resolveProfileMcpBundleId('mel'), 'lean');
});

test('materializeProfileMcpConfig writes mcp.json inventory for editor', () => {
  const claudeConfigDir = mkdtempSync(join(tmpdir(), 'mcp-editor-'));
  try {
    const result = materializeProfileMcpConfig({
      profileId: 'editor',
      claudeConfigDir,
    });
    assert.equal(result.activationInterface, SUPPORTED_ACTIVATION_INTERFACE);
    assert.equal(result.bundleId, 'lean');
    const inventory = readEffectiveMcpServerInventory(result.mcpConfigPath);
    assert.deepEqual(inventory, [...result.allServerNames].sort());
    const document = JSON.parse(readFileSync(result.mcpConfigPath, 'utf8'));
    assert.ok(document.mcpServers['filesystem-readonly']);
  } finally {
    rmSync(claudeConfigDir, { recursive: true, force: true });
  }
});

test('materializeProfileMcpConfig writes mcp.json inventory for mel', () => {
  const claudeConfigDir = mkdtempSync(join(tmpdir(), 'mcp-mel-'));
  try {
    const result = materializeProfileMcpConfig({
      profileId: 'mel',
      claudeConfigDir,
    });
    assert.equal(result.bundleId, 'lean');
    const inventory = readEffectiveMcpServerInventory(result.mcpConfigPath);
    assert.deepEqual(inventory, listServerNamesForBundle('lean').sort());
  } finally {
    rmSync(claudeConfigDir, { recursive: true, force: true });
  }
});

test('unknown profile id fails with an actionable message', () => {
  assert.throws(
    () => resolveProfileMcpBundleId('not-a-profile'),
    /unknown profile id/,
  );
});

test('malformed bundles document is rejected', () => {
  assert.throws(
    () => validateMcpBundlesDocument({ schemaVersion: 2 }),
    /schemaVersion must be 1/,
  );
});

test('missing mcp config readback fails closed', () => {
  const claudeConfigDir = mkdtempSync(join(tmpdir(), 'mcp-missing-'));
  try {
    assert.throws(
      () => readEffectiveMcpServerInventory(join(claudeConfigDir, 'mcp.json')),
      /mcp config missing/,
    );
  } finally {
    rmSync(claudeConfigDir, { recursive: true, force: true });
  }
});

test('malformed mcp config readback fails closed', () => {
  const claudeConfigDir = mkdtempSync(join(tmpdir(), 'mcp-bad-'));
  try {
    mkdirSync(claudeConfigDir, { recursive: true });
    const path = join(claudeConfigDir, 'mcp.json');
    writeFileSync(path, '{"notServers":true}\n', 'utf8');
    assert.throws(
      () => readEffectiveMcpServerInventory(path),
      /malformed/,
    );
  } finally {
    rmSync(claudeConfigDir, { recursive: true, force: true });
  }
});
