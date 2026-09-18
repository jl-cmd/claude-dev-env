import { dirname, join } from 'node:path';

export const CONTINUITY_SCRIPT_MARKER = '/session-continuity/continuity.mjs';

/**
 * True when a hook command calls the retired session-continuity companion.
 *
 * @param {unknown} command The `command` field of one host hook entry.
 * @returns {boolean} True when this entry calls the retired companion.
 */
export function isContinuityHookCommand(command) {
    return typeof command === 'string' && command.includes(CONTINUITY_SCRIPT_MARKER);
}

/**
 * Locate the hook configuration file each host keeps its registrations in.
 *
 * @param {object} roots An `InstallRootResolution`.
 * @returns {Record<string, string>} One configuration path per host.
 */
export function continuityHostConfigurationPaths(roots) {
    return {
        claude: join(roots.managedRoot, 'settings.json'),
        codex: join(dirname(roots.codexRulesInstallDirectory), 'hooks.json'),
        cursor: join(roots.cursorInstallDirectory, 'hooks.json'),
    };
}

/**
 * Strip every retired session-continuity registration from one host
 * configuration, in place, and drop an event left with no entries.
 *
 * An earlier claude-dev-env registered this companion in each host. The pstack
 * plugin now carries the SessionStart context the companion supplied, so a
 * registration left behind points every session at a deleted script.
 *
 * @param {object} configuration A parsed host hook configuration.
 * @returns {number} How many registrations this call removed.
 */
export function removeContinuityHooks(configuration) {
    let removedCount = 0;
    for (const [event, entries] of Object.entries(configuration.hooks || {})) {
        const kept = entries.flatMap(entry => {
            if (!entry.hooks) {
                if (!isContinuityHookCommand(entry.command)) return [entry];
                removedCount += 1;
                return [];
            }
            const hooks = entry.hooks.filter(hook => !isContinuityHookCommand(hook.command));
            removedCount += entry.hooks.length - hooks.length;
            return hooks.length ? [{ ...entry, hooks }] : [];
        });
        if (kept.length) configuration.hooks[event] = kept;
        else delete configuration.hooks[event];
    }
    return removedCount;
}
