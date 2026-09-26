import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import {
    emptyManagedPermissions,
    managedPermissionsFromPackageSettings,
    countManagedPermissions,
    retiredManagedPermissions,
    mergeManagedPermissionsIntoSettings,
    pruneManagedPermissionsFromSettings,
} from './merge_managed_permissions.mjs';

test('emptyManagedPermissions returns separate empty records', () => {
    const first = emptyManagedPermissions();
    const second = emptyManagedPermissions();
    assert.deepEqual(first, { allow: [], deny: [] });
    first.allow.push('Read(./managed/**)');
    assert.deepEqual(second, { allow: [], deny: [] });
});

test('managedPermissionsFromPackageSettings keeps nonblank string rules', () => {
    const settings = {
        permissions: {
            allow: ['Read(./managed/**)', '', '   ', 4],
            deny: ['Write(./managed/**)', null],
            ask: ['Write(./user/**)'],
        },
    };
    assert.deepEqual(managedPermissionsFromPackageSettings(settings), {
        allow: ['Read(./managed/**)'],
        deny: ['Write(./managed/**)'],
    });
    assert.deepEqual(managedPermissionsFromPackageSettings(null), {
        allow: [],
        deny: [],
    });
});

test('countManagedPermissions counts both owned lists', () => {
    assert.equal(countManagedPermissions({ allow: ['read-a', 'read-b'], deny: ['write-a'] }), 3);
});

test('retiredManagedPermissions keeps only rules absent from the same current list', () => {
    const prior = {
        allow: ['Read(./old/**)', 'Read(./keep/**)'],
        deny: ['Write(./keep/**)', 'Write(./old/**)'],
    };
    const current = {
        allow: ['Read(./keep/**)'],
        deny: ['Write(./keep/**)'],
    };
    assert.deepEqual(retiredManagedPermissions(prior, current), {
        allow: ['Read(./old/**)'],
        deny: ['Write(./old/**)'],
    });
    assert.equal(prior.allow.length, 2);
    assert.equal(prior.deny.length, 2);
});

test('mergeManagedPermissionsIntoSettings adds owned rules once and keeps user rules', () => {
    const settings = { permissions: { allow: ['Read(./user/**)'], ask: ['Write(./user/**)'] } };
    const managed = { allow: ['Read(./managed/**)'], deny: ['Write(./managed/**)'] };
    const first = mergeManagedPermissionsIntoSettings(settings, managed);
    const second = mergeManagedPermissionsIntoSettings(settings, managed);
    assert.deepEqual([first.addedCount, first.alreadyPresentCount], [2, 0]);
    assert.deepEqual([second.addedCount, second.alreadyPresentCount], [0, 2]);
    assert.deepEqual(settings.permissions, {
        allow: ['Read(./user/**)', 'Read(./managed/**)'],
        ask: ['Write(./user/**)'],
        deny: ['Write(./managed/**)'],
    });
});

test('pruneManagedPermissionsFromSettings removes owned rules and keeps user rules', () => {
    const settings = {
        permissions: {
            allow: ['Read(./user/**)', 'Read(./managed/**)'],
            ask: ['Write(./user/**)'],
            deny: ['Write(./managed/**)'],
        },
    };
    const managed = { allow: ['Read(./managed/**)'], deny: ['Write(./managed/**)'] };
    assert.deepEqual(pruneManagedPermissionsFromSettings(settings, managed), { removedCount: 2 });
    assert.deepEqual(settings.permissions, {
        allow: ['Read(./user/**)'],
        ask: ['Write(./user/**)'],
    });
});
