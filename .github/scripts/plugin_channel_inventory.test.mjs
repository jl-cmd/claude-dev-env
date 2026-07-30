/**
 * R2A plugin-channel inventory tests.
 *
 * Stated mutation: gut parsePluginManifest to always return version "" —
 * kills plugin-manifest and journal version assertions; README and profile
 * probe cases still pass.
 */
import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  CHANNEL_VALUES,
  CLASSIFICATION_VALUES,
  PROBE_RESULT_VALUES,
  buildInventoryJournal,
  computeSelectedLiveConsumerCollision,
  extractReadmePluginEntry,
  parseMarketplaceManifest,
  parsePluginManifest,
  packageVersionFromPackageJson,
  profileRegistersPackage,
  validateInventoryJournal,
} from './plugin_channel_inventory.mjs';

const REPOSITORY_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');

const PLUGIN_JSON = JSON.stringify({
  name: 'claude-dev-env',
  version: '1.0.0',
});
const MARKETPLACE_JSON = JSON.stringify({
  name: 'claude-dev-env',
  plugins: [{ name: 'config', version: '1.0.0' }],
});
const README_BOTH = [
  'npx claude-dev-env',
  'claude plugin install jl-cmd/claude-dev-env',
].join('\n');
const INSTALLED_ABSENT = JSON.stringify({
  version: 1,
  plugins: { 'github@claude-plugins-official': {} },
});
const INSTALLED_PRESENT = JSON.stringify({
  version: 1,
  plugins: { 'claude-dev-env@some-marketplace': {} },
});

test('parsePluginManifest returns name and version', () => {
  const parsed = parsePluginManifest(PLUGIN_JSON);
  assert.equal(parsed.name, 'claude-dev-env');
  assert.equal(parsed.version, '1.0.0');
});

test('parseMarketplaceManifest returns entry version', () => {
  const parsed = parseMarketplaceManifest(MARKETPLACE_JSON);
  assert.equal(parsed.entry_version, '1.0.0');
  assert.equal(parsed.entry_count, 1);
});

test('extractReadmePluginEntry detects npx and plugin install lines', () => {
  const entry = extractReadmePluginEntry(README_BOTH);
  assert.equal(entry.has_plugin_install_instruction, true);
  assert.equal(entry.has_npx_install_instruction, true);
});

test('profile and collision probes distinguish absent from present registration', () => {
  assert.equal(profileRegistersPackage(INSTALLED_ABSENT, 'claude-dev-env'), false);
  assert.equal(profileRegistersPackage(INSTALLED_PRESENT, 'claude-dev-env'), true);
  assert.equal(
    computeSelectedLiveConsumerCollision([
      { profile: 'main', is_registered: false },
      { profile: 'editor', is_registered: false },
    ]),
    false,
  );
  assert.equal(
    computeSelectedLiveConsumerCollision([
      { profile: 'main', is_registered: false },
      { profile: 'editor', is_registered: true },
    ]),
    true,
  );
});

test('buildInventoryJournal emits boolean collision and valid consumers', () => {
  const journal = buildInventoryJournal({
    generated_from_ref: 'abc123',
    package_version: '2.8.0',
    plugin_manifest: parsePluginManifest(PLUGIN_JSON),
    marketplace_manifest: parseMarketplaceManifest(MARKETPLACE_JSON),
    readme_entry: extractReadmePluginEntry(README_BOTH),
    selected_profiles: [
      {
        profile: 'main',
        is_registered: false,
        probe_path: 'profile:main/plugins/installed_plugins.json',
        plugin_count: 16,
      },
    ],
    release: {
      tag: 'claude-dev-env-v2.8.0',
      target_commitish: 'b74fab73849601b828342399a0d47d54554d22d1',
      classification: 'active',
    },
    external_marketplace_registration: {
      classification: 'unresolved',
      owner: 'R2C',
      blocker: 'External marketplace registration remains unverified.',
    },
  });
  assert.equal(journal.selected_live_consumer_collision, false);
  assert.equal(typeof journal.selected_live_consumer_collision, 'boolean');
  assert.equal(journal.plugin_manifest_version, '1.0.0');
  assert.equal(journal.package_version, '2.8.0');
  for (const eachConsumer of journal.consumers) {
    assert.ok(CLASSIFICATION_VALUES.includes(eachConsumer.classification));
    assert.ok(CHANNEL_VALUES.includes(eachConsumer.channel));
    assert.ok(PROBE_RESULT_VALUES.includes(eachConsumer.probe_result));
  }
  const validation = validateInventoryJournal(journal);
  assert.equal(validation.is_valid, true);
  assert.deepEqual(validation.errors, []);
});

function journalWith(overrides) {
  return buildInventoryJournal({
    generated_from_ref: 'abc123',
    package_version: '2.8.0',
    plugin_manifest: parsePluginManifest(PLUGIN_JSON),
    marketplace_manifest: parseMarketplaceManifest(MARKETPLACE_JSON),
    readme_entry: extractReadmePluginEntry(README_BOTH),
    selected_profiles: [],
    ...overrides,
  });
}

function consumerById(journal, consumerId) {
  return journal.consumers.find((eachConsumer) => eachConsumer.id === consumerId);
}

test('an unprobed release records unreadable rather than registered', () => {
  const journal = journalWith({});
  const release = consumerById(journal, 'github-release-package');
  assert.equal(release.probe_result, 'unreadable');
  assert.equal(release.classification, 'unresolved');
  assert.equal(release.owner, 'R2A');
  assert.ok(release.blocker);
  assert.equal(validateInventoryJournal(journal).is_valid, true);
});

test('a release input carrying no tag counts as unprobed', () => {
  const release = consumerById(
    journalWith({ release: { classification: 'active' } }),
    'github-release-package',
  );
  assert.equal(release.probe_result, 'unreadable');
  assert.equal(release.probe_path, 'release:unknown');
});

test('a probed unresolved release keeps the owner and blocker it was given', () => {
  const journal = journalWith({
    release: {
      tag: 'claude-dev-env-v2.8.0',
      classification: 'unresolved',
      owner: 'R2A',
      blocker: 'GitHub release API rate-limited during probe',
    },
  });
  const release = consumerById(journal, 'github-release-package');
  assert.equal(release.blocker, 'GitHub release API rate-limited during probe');
  assert.equal(validateInventoryJournal(journal).is_valid, true);
});

test('a resolved consumer carries no owner or blocker key', () => {
  const external = consumerById(
    journalWith({
      external_marketplace_registration: {
        classification: 'retained-external',
        notes: 'Listed in an external marketplace',
      },
    }),
    'external-marketplace-registration',
  );
  assert.equal(external.classification, 'retained-external');
  assert.equal('blocker' in external, false);
  assert.equal('owner' in external, false);
});

test('a README missing the npx line yields an owned unresolved consumer', () => {
  const journal = journalWith({
    readme_entry: extractReadmePluginEntry('claude plugin install jl-cmd/claude-dev-env'),
  });
  const npxEntry = consumerById(journal, 'readme-npx-entry');
  assert.equal(npxEntry.classification, 'unresolved');
  assert.ok(npxEntry.owner);
  assert.ok(npxEntry.blocker);
  assert.equal(validateInventoryJournal(journal).is_valid, true);
});

test('validateInventoryJournal rejects a missing package_name and a wrong schema_version', () => {
  const journal = journalWith({});
  assert.ok(
    validateInventoryJournal({ ...journal, package_name: '' }).errors.some(
      (eachError) => eachError.includes('package_name'),
    ),
  );
  assert.ok(
    validateInventoryJournal({ ...journal, schema_version: 99 }).errors.some(
      (eachError) => eachError.includes('schema_version'),
    ),
  );
});

test('a non-boolean is_registered counts as absent everywhere in the journal', () => {
  const journal = journalWith({
    selected_profiles: [
      { profile: 'main', is_registered: 'yes', probe_path: 'profile:main', plugin_count: 3 },
    ],
  });
  assert.equal(journal.selected_live_consumer_collision, false);
  assert.equal(consumerById(journal, 'selected-profile-main').probe_result, 'absent');
  assert.equal(
    journal.evidence.find(
      (eachItem) => eachItem.claim === 'selected_live_consumer_collision',
    ).verbatim,
    'main:absent',
  );
});

test('validateInventoryJournal rejects missing collision boolean', () => {
  const validation = validateInventoryJournal({
    schema_version: 1,
    generated_from_ref: 'abc',
    package_version: '2.8.0',
    plugin_manifest_version: '1.0.0',
    marketplace_entry_version: '1.0.0',
    consumers: [],
    evidence: [],
  });
  assert.equal(validation.is_valid, false);
  assert.ok(
    validation.errors.some((eachError) =>
      eachError.includes('selected_live_consumer_collision'),
    ),
  );
});

test('committed journal validates and records collision false', () => {
  const journalPath = join(
    REPOSITORY_ROOT,
    'docs',
    'references',
    'plugin-channel-inventory.json',
  );
  const journal = JSON.parse(readFileSync(journalPath, 'utf8'));
  const validation = validateInventoryJournal(journal);
  assert.equal(validation.is_valid, true, validation.errors.join('; '));
  assert.equal(journal.selected_live_consumer_collision, false);
  const collisionEvidence = journal.evidence.find(
    (eachItem) => eachItem.claim === 'selected_live_consumer_collision',
  );
  assert.ok(collisionEvidence);
  assert.ok(collisionEvidence.verbatim.includes('main:absent'));
});

test('repository HEAD metadata still shows version drift', () => {
  const plugin = parsePluginManifest(
    readFileSync(join(REPOSITORY_ROOT, '.claude-plugin', 'plugin.json'), 'utf8'),
  );
  const marketplace = parseMarketplaceManifest(
    readFileSync(
      join(REPOSITORY_ROOT, '.claude-plugin', 'marketplace.json'),
      'utf8',
    ),
  );
  const packageVersion = packageVersionFromPackageJson(
    readFileSync(
      join(REPOSITORY_ROOT, 'packages', 'claude-dev-env', 'package.json'),
      'utf8',
    ),
  );
  const readmeEntry = extractReadmePluginEntry(
    readFileSync(join(REPOSITORY_ROOT, 'README.md'), 'utf8'),
  );
  assert.equal(plugin.version, '1.0.0');
  assert.equal(marketplace.entry_version, '1.0.0');
  assert.equal(packageVersion, '2.8.0');
  assert.equal(readmeEntry.has_plugin_install_instruction, true);
  assert.equal(readmeEntry.has_npx_install_instruction, true);
  assert.notEqual(packageVersion, plugin.version);
});
