/**
 * Pure parse and classify helpers for the plugin-channel consumer inventory.
 *
 * Measures committed metadata, README entry text, release tags, and selected
 * profile registration results without mutating repository or live state.
 */

export const SCHEMA_VERSION = 1;
export const CLASSIFICATION_VALUES = Object.freeze([
  'active',
  'migrated',
  'retained-external',
  'retired',
  'unresolved',
]);
export const CHANNEL_VALUES = Object.freeze(['npx', 'plugin', 'manual']);
export const PROBE_RESULT_VALUES = Object.freeze([
  'registered',
  'absent',
  'unreadable',
]);

const PACKAGE_NAME = 'claude-dev-env';
const PLUGIN_INSTALL_COMMAND = 'claude plugin install jl-cmd/claude-dev-env';
const NPX_INSTALL_COMMAND = 'npx claude-dev-env';

/**
 * Parse plugin.json text into name and version.
 *
 * ::
 *
 *     parsePluginManifest('{"name":"claude-dev-env","version":"1.0.0"}')
 *     // -> { name: 'claude-dev-env', version: '1.0.0' }
 */
export function parsePluginManifest(pluginJsonText) {
  const parsed = JSON.parse(pluginJsonText);
  return {
    name: String(parsed.name ?? ''),
    version: String(parsed.version ?? ''),
  };
}

/**
 * Parse marketplace.json text into listing identity fields.
 *
 * ::
 *
 *     parseMarketplaceManifest('{"plugins":[{"version":"1.0.0"}]}')
 *     // -> { entry_version: '1.0.0', entry_count: 1 }
 */
export function parseMarketplaceManifest(marketplaceJsonText) {
  const parsed = JSON.parse(marketplaceJsonText);
  const allPlugins = Array.isArray(parsed.plugins) ? parsed.plugins : [];
  const firstEntry = allPlugins[0] ?? {};
  return {
    name: String(parsed.name ?? ''),
    entry_version: String(firstEntry.version ?? ''),
    entry_count: allPlugins.length,
  };
}

/** Read package version from package.json text. */
export function packageVersionFromPackageJson(packageJsonText) {
  return String(JSON.parse(packageJsonText).version ?? '');
}

/** Detect README-advertised npx and plugin install instructions. */
export function extractReadmePluginEntry(readmeText) {
  const hasNpx = readmeText.includes(NPX_INSTALL_COMMAND);
  const hasPlugin = readmeText.includes(PLUGIN_INSTALL_COMMAND);
  return {
    has_npx_install_instruction: hasNpx,
    has_plugin_install_instruction: hasPlugin,
    plugin_install_command: hasPlugin ? PLUGIN_INSTALL_COMMAND : '',
    npx_install_command: hasNpx ? NPX_INSTALL_COMMAND : '',
  };
}

/**
 * Return whether installed_plugins.json registers the package name.
 *
 * ::
 *
 *     profileRegistersPackage('{"plugins":{"github@x":{}}}', 'claude-dev-env')
 *     // -> false
 */
export function profileRegistersPackage(installedPluginsJsonText, packageName) {
  const pluginsValue = JSON.parse(installedPluginsJsonText).plugins;
  if (pluginsValue == null) {
    return false;
  }
  if (Array.isArray(pluginsValue)) {
    return pluginsValue.some((eachPlugin) => {
      const pluginName = String(eachPlugin?.name ?? eachPlugin ?? '');
      return (
        pluginName === packageName || pluginName.startsWith(`${packageName}@`)
      );
    });
  }
  return Object.keys(pluginsValue).some(
    (eachKey) =>
      eachKey === packageName || eachKey.startsWith(`${packageName}@`),
  );
}

/** True when any selected profile still registers the package as a plugin. */
export function computeSelectedLiveConsumerCollision(profileProbeResults) {
  return profileProbeResults.some(
    (eachProfile) => eachProfile.is_registered === true,
  );
}

/** Build the inventory journal from already-parsed probe inputs. */
export function buildInventoryJournal(inputs) {
  const selectedProfiles = inputs.selected_profiles ?? [];
  const collision = computeSelectedLiveConsumerCollision(selectedProfiles);
  const external = inputs.external_marketplace_registration ?? {};
  const readme = inputs.readme_entry;

  const consumers = [
    {
      id: 'committed-plugin-manifest',
      channel: 'plugin',
      classification: 'active',
      probe_path: '.claude-plugin/plugin.json',
      probe_result: 'registered',
      observed_at: 'source',
      notes: `Committed plugin version ${inputs.plugin_manifest.version}`,
    },
    {
      id: 'committed-marketplace-manifest',
      channel: 'plugin',
      classification: 'active',
      probe_path: '.claude-plugin/marketplace.json',
      probe_result: 'registered',
      observed_at: 'source',
      notes: `Marketplace entry version ${inputs.marketplace_manifest.entry_version}`,
    },
    {
      id: 'readme-plugin-entry',
      channel: 'plugin',
      classification: readme.has_plugin_install_instruction ? 'active' : 'retired',
      probe_path: 'README.md',
      probe_result: readme.has_plugin_install_instruction ? 'registered' : 'absent',
      observed_at: 'source',
      notes: readme.plugin_install_command,
    },
    {
      id: 'readme-npx-entry',
      channel: 'npx',
      classification: readme.has_npx_install_instruction ? 'active' : 'unresolved',
      probe_path: 'README.md',
      probe_result: readme.has_npx_install_instruction ? 'registered' : 'absent',
      observed_at: 'source',
      notes: readme.npx_install_command,
    },
    {
      id: 'github-release-package',
      channel: 'npx',
      classification: inputs.release?.classification ?? 'active',
      probe_path: `release:${inputs.release?.tag ?? 'unknown'}`,
      probe_result: 'registered',
      observed_at: 'github',
      notes: `target_commitish=${inputs.release?.target_commitish ?? ''}`,
    },
    {
      id: 'external-marketplace-registration',
      channel: 'plugin',
      classification: external.classification ?? 'unresolved',
      probe_path: 'external:marketplace',
      probe_result: 'unreadable',
      observed_at: 'external',
      notes: external.blocker ?? 'External marketplace registration unverified',
      owner: external.owner ?? 'R2C',
      blocker: external.blocker ?? '',
    },
  ];

  for (const eachProfile of selectedProfiles) {
    consumers.push({
      id: `selected-profile-${eachProfile.profile}`,
      channel: 'plugin',
      classification: eachProfile.is_registered ? 'active' : 'migrated',
      probe_path: eachProfile.probe_path,
      probe_result: eachProfile.is_registered ? 'registered' : 'absent',
      observed_at: 'selected-profile',
      notes: `plugin_count=${eachProfile.plugin_count ?? 0}`,
    });
  }

  return {
    schema_version: SCHEMA_VERSION,
    generated_from_ref: inputs.generated_from_ref,
    package_name: PACKAGE_NAME,
    package_version: inputs.package_version,
    plugin_manifest_version: inputs.plugin_manifest.version,
    marketplace_entry_version: inputs.marketplace_manifest.entry_version,
    selected_live_consumer_collision: collision,
    consumers,
    evidence: [
      {
        claim: 'selected_live_consumer_collision',
        source_path: 'selected-profiles',
        source_line: 0,
        verbatim: selectedProfiles
          .map(
            (eachProfile) =>
              `${eachProfile.profile}:${eachProfile.is_registered ? 'registered' : 'absent'}`,
          )
          .join('; '),
      },
      {
        claim: 'plugin_manifest_version',
        source_path: '.claude-plugin/plugin.json',
        source_line: 0,
        verbatim: inputs.plugin_manifest.version,
      },
      {
        claim: 'package_version',
        source_path: 'packages/claude-dev-env/package.json',
        source_line: 0,
        verbatim: inputs.package_version,
      },
      {
        claim: 'version_channel_drift',
        source_path: '.claude-plugin/plugin.json',
        source_line: 0,
        verbatim: `plugin=${inputs.plugin_manifest.version}; package=${inputs.package_version}`,
      },
    ],
  };
}

function requireNonEmptyString(value, fieldName, allErrors) {
  if (typeof value !== 'string' || !value) {
    allErrors.push(`${fieldName} must be a non-empty string`);
  }
}

/** Validate inventory journal shape and vocabulary. */
export function validateInventoryJournal(journal) {
  const allErrors = [];
  if (journal == null || typeof journal !== 'object') {
    return { is_valid: false, errors: ['journal must be an object'] };
  }
  if (typeof journal.schema_version !== 'number') {
    allErrors.push('schema_version must be a number');
  }
  requireNonEmptyString(journal.generated_from_ref, 'generated_from_ref', allErrors);
  requireNonEmptyString(journal.package_version, 'package_version', allErrors);
  requireNonEmptyString(
    journal.plugin_manifest_version,
    'plugin_manifest_version',
    allErrors,
  );
  requireNonEmptyString(
    journal.marketplace_entry_version,
    'marketplace_entry_version',
    allErrors,
  );
  if (typeof journal.selected_live_consumer_collision !== 'boolean') {
    allErrors.push('selected_live_consumer_collision must be a boolean');
  }
  if (!Array.isArray(journal.consumers)) {
    allErrors.push('consumers must be an array');
  } else {
    for (const eachConsumer of journal.consumers) {
      if (!eachConsumer?.id) {
        allErrors.push('consumer missing id');
      }
      if (!CHANNEL_VALUES.includes(eachConsumer?.channel)) {
        allErrors.push(`consumer ${eachConsumer?.id} has invalid channel`);
      }
      if (!CLASSIFICATION_VALUES.includes(eachConsumer?.classification)) {
        allErrors.push(`consumer ${eachConsumer?.id} has invalid classification`);
      }
      if (!PROBE_RESULT_VALUES.includes(eachConsumer?.probe_result)) {
        allErrors.push(`consumer ${eachConsumer?.id} has invalid probe_result`);
      }
      if (
        eachConsumer?.classification === 'unresolved' &&
        (!eachConsumer.owner || !eachConsumer.blocker)
      ) {
        allErrors.push(
          `unresolved consumer ${eachConsumer?.id} requires owner and blocker`,
        );
      }
    }
  }
  if (!Array.isArray(journal.evidence)) {
    allErrors.push('evidence must be an array');
  } else if (
    !journal.evidence.some(
      (eachItem) => eachItem?.claim === 'selected_live_consumer_collision',
    )
  ) {
    allErrors.push('evidence must include claim selected_live_consumer_collision');
  }
  return { is_valid: allErrors.length === 0, errors: allErrors };
}
