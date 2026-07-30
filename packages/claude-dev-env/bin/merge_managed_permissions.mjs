/**
 * Merge package-owned permission defaults into a settings object.
 *
 * Ownership is the stable deny-entry string published in the package
 * settings.json. Install ensures each package deny appears once. Uninstall
 * removes only those package-owned identity strings and leaves every other
 * allow/ask/deny entry unchanged.
 */

/**
 * @typedef {{
 *   allow?: string[],
 *   ask?: string[],
 *   deny?: string[],
 * }} PermissionLists
 */

/**
 * @typedef {{
 *   permissions?: PermissionLists,
 *   [key: string]: unknown,
 * }} SettingsObject
 */

/**
 * Read the managed deny list from a package settings source object.
 *
 * @param {SettingsObject | null | undefined} packageSettings
 * @returns {string[]}
 */
export function managedDenyEntriesFromPackageSettings(packageSettings) {
    const denyList = packageSettings?.permissions?.deny;
    if (!Array.isArray(denyList)) {
        return [];
    }
    return denyList.filter((eachEntry) => typeof eachEntry === 'string' && eachEntry.length > 0);
}

/**
 * Merge package-owned deny entries into target settings in place.
 *
 * Existing allow/ask entries and non-package deny entries stay as written.
 * Package deny strings already present are not duplicated.
 *
 * @param {SettingsObject} targetSettings
 * @param {string[]} managedDenyEntries
 * @returns {{addedCount: number, alreadyPresentCount: number, managedDenyEntries: string[]}}
 */
export function mergeManagedPermissionsIntoSettings(targetSettings, managedDenyEntries) {
    if (!targetSettings || typeof targetSettings !== 'object' || Array.isArray(targetSettings)) {
        throw new TypeError('targetSettings must be a plain object');
    }
    if (!Array.isArray(managedDenyEntries)) {
        throw new TypeError('managedDenyEntries must be an array');
    }

    if (
        !targetSettings.permissions
        || typeof targetSettings.permissions !== 'object'
        || Array.isArray(targetSettings.permissions)
    ) {
        targetSettings.permissions = {};
    }
    const permissions = targetSettings.permissions;
    if (!Array.isArray(permissions.deny)) {
        permissions.deny = [];
    }

    let addedCount = 0;
    let alreadyPresentCount = 0;
    for (const eachEntry of managedDenyEntries) {
        if (typeof eachEntry !== 'string' || eachEntry.length === 0) {
            continue;
        }
        if (permissions.deny.includes(eachEntry)) {
            alreadyPresentCount += 1;
            continue;
        }
        permissions.deny.push(eachEntry);
        addedCount += 1;
    }

    return {
        addedCount,
        alreadyPresentCount,
        managedDenyEntries: [...managedDenyEntries],
    };
}

/**
 * Remove package-owned deny entries from target settings in place.
 *
 * User allow, ask, and non-package deny entries remain. Empty permission
 * lists are dropped so uninstall leaves a clean settings object.
 *
 * @param {SettingsObject} targetSettings
 * @param {string[]} managedDenyEntries
 * @returns {{removedCount: number}}
 */
export function pruneManagedPermissionsFromSettings(targetSettings, managedDenyEntries) {
    if (!targetSettings?.permissions || typeof targetSettings.permissions !== 'object') {
        return { removedCount: 0 };
    }
    const permissions = targetSettings.permissions;
    if (!Array.isArray(permissions.deny) || permissions.deny.length === 0) {
        return { removedCount: 0 };
    }

    const managedSet = new Set(
        managedDenyEntries.filter((eachEntry) => typeof eachEntry === 'string'),
    );
    const denyCountBefore = permissions.deny.length;
    permissions.deny = permissions.deny.filter((eachEntry) => !managedSet.has(eachEntry));
    const removedCount = denyCountBefore - permissions.deny.length;

    if (permissions.deny.length === 0) {
        delete permissions.deny;
    }
    if (Array.isArray(permissions.allow) && permissions.allow.length === 0) {
        delete permissions.allow;
    }
    if (Array.isArray(permissions.ask) && permissions.ask.length === 0) {
        delete permissions.ask;
    }
    if (Object.keys(permissions).length === 0) {
        delete targetSettings.permissions;
    }

    return { removedCount };
}
