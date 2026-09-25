/**
 * Merge package-owned permission defaults into a settings object.
 *
 * Ownership is the stable rule string published in the package settings.json
 * `permissions.allow` and `permissions.deny` lists. Install ensures each
 * package rule appears once in its list. Uninstall removes only those
 * package-owned rule strings and leaves every other allow/ask/deny entry
 * unchanged.
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
 * @typedef {{
 *   allow: string[],
 *   deny: string[],
 * }} ManagedPermissions
 */

export const MANAGED_PERMISSION_LIST_NAMES = Object.freeze(['allow', 'deny']);

/**
 * Build an empty managed-permissions record.
 *
 * @returns {ManagedPermissions}
 */
export function emptyManagedPermissions() {
    return { allow: [], deny: [] };
}

/**
 * Read the managed allow and deny lists from a package settings source object
 * or a manifest record of the same shape.
 *
 * @param {SettingsObject | null | undefined} packageSettings
 * @returns {ManagedPermissions}
 */
export function managedPermissionsFromPackageSettings(packageSettings) {
    const managedPermissions = emptyManagedPermissions();
    for (const eachListName of MANAGED_PERMISSION_LIST_NAMES) {
        const sourceList = packageSettings?.permissions?.[eachListName];
        if (!Array.isArray(sourceList)) {
            continue;
        }
        managedPermissions[eachListName] = sourceList.filter(
            (eachEntry) => typeof eachEntry === 'string' && eachEntry.trim().length > 0,
        );
    }
    return managedPermissions;
}

/**
 * Count the rules a managed-permissions record holds across every list.
 *
 * @param {ManagedPermissions} managedPermissions
 * @returns {number}
 */
export function countManagedPermissions(managedPermissions) {
    return MANAGED_PERMISSION_LIST_NAMES.reduce(
        (runningCount, eachListName) => runningCount + managedPermissions[eachListName].length,
        0,
    );
}

/**
 * List the rules a prior record owned that the current record no longer owns.
 *
 * @param {ManagedPermissions} priorPermissions
 * @param {ManagedPermissions} currentPermissions
 * @returns {ManagedPermissions}
 */
export function retiredManagedPermissions(priorPermissions, currentPermissions) {
    const retiredPermissions = emptyManagedPermissions();
    for (const eachListName of MANAGED_PERMISSION_LIST_NAMES) {
        const currentSet = new Set(currentPermissions[eachListName]);
        retiredPermissions[eachListName] = priorPermissions[eachListName].filter(
            (eachEntry) => !currentSet.has(eachEntry),
        );
    }
    return retiredPermissions;
}

/**
 * Merge package-owned allow and deny rules into target settings in place.
 *
 * Existing user entries stay as written. Package rules already present are
 * not duplicated.
 *
 * @param {SettingsObject} targetSettings
 * @param {ManagedPermissions} managedPermissions
 * @returns {{addedCount: number, alreadyPresentCount: number, managedPermissions: ManagedPermissions}}
 */
export function mergeManagedPermissionsIntoSettings(targetSettings, managedPermissions) {
    if (!targetSettings || typeof targetSettings !== 'object' || Array.isArray(targetSettings)) {
        throw new TypeError('targetSettings must be a plain object');
    }
    if (!managedPermissions || typeof managedPermissions !== 'object') {
        throw new TypeError('managedPermissions must be an object of allow and deny lists');
    }

    if (
        !targetSettings.permissions
        || typeof targetSettings.permissions !== 'object'
        || Array.isArray(targetSettings.permissions)
    ) {
        targetSettings.permissions = {};
    }
    const permissions = targetSettings.permissions;

    let addedCount = 0;
    let alreadyPresentCount = 0;
    for (const eachListName of MANAGED_PERMISSION_LIST_NAMES) {
        const managedEntries = managedPermissions[eachListName] ?? [];
        if (managedEntries.length === 0) {
            continue;
        }
        if (!Array.isArray(permissions[eachListName])) {
            permissions[eachListName] = [];
        }
        for (const eachEntry of managedEntries) {
            if (typeof eachEntry !== 'string' || eachEntry.length === 0) {
                continue;
            }
            if (permissions[eachListName].includes(eachEntry)) {
                alreadyPresentCount += 1;
                continue;
            }
            permissions[eachListName].push(eachEntry);
            addedCount += 1;
        }
    }

    return {
        addedCount,
        alreadyPresentCount,
        managedPermissions: {
            allow: [...(managedPermissions.allow ?? [])],
            deny: [...(managedPermissions.deny ?? [])],
        },
    };
}

/**
 * Remove package-owned allow and deny rules from target settings in place.
 *
 * User allow, ask, and deny entries the package does not own remain. Empty
 * permission lists are dropped so uninstall leaves a clean settings object.
 *
 * @param {SettingsObject} targetSettings
 * @param {ManagedPermissions} managedPermissions
 * @returns {{removedCount: number}}
 */
export function pruneManagedPermissionsFromSettings(targetSettings, managedPermissions) {
    if (!targetSettings?.permissions || typeof targetSettings.permissions !== 'object') {
        return { removedCount: 0 };
    }
    const permissions = targetSettings.permissions;

    let removedCount = 0;
    for (const eachListName of MANAGED_PERMISSION_LIST_NAMES) {
        if (!Array.isArray(permissions[eachListName])) {
            continue;
        }
        const managedSet = new Set(
            (managedPermissions?.[eachListName] ?? []).filter((eachEntry) => typeof eachEntry === 'string'),
        );
        const countBefore = permissions[eachListName].length;
        permissions[eachListName] = permissions[eachListName].filter(
            (eachEntry) => !managedSet.has(eachEntry),
        );
        removedCount += countBefore - permissions[eachListName].length;
    }
    if (removedCount === 0) {
        return { removedCount };
    }

    for (const eachListName of ['allow', 'ask', 'deny']) {
        if (Array.isArray(permissions[eachListName]) && permissions[eachListName].length === 0) {
            delete permissions[eachListName];
        }
    }
    if (Object.keys(permissions).length === 0) {
        delete targetSettings.permissions;
    }

    return { removedCount };
}
