import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import {
    existsSync,
    lstatSync,
    mkdirSync,
    mkdtempSync,
    rmSync,
    symlinkSync,
    writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import {
    removeRetiredPstackInstallation,
    retiredPstackStoreRoot,
} from './prune-retired-pstack-store.mjs';

function retiredInstallationFixture(t) {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-retired-pstack-'));
    t.after(() => rmSync(homeDirectory, { recursive: true, force: true }));
    const managedRoot = join(homeDirectory, '.claude');
    const agentsHome = join(homeDirectory, '.agents');
    const releaseRoot = join(managedRoot, 'pstack', 'releases', 'abc123', 'runtime');
    mkdirSync(join(releaseRoot, 'pstack', 'skills', 'poteto-mode'), { recursive: true });
    mkdirSync(join(releaseRoot, 'cursor-team-kit', 'skills', 'deslop'), { recursive: true });
    writeFileSync(join(managedRoot, 'pstack', 'installed.json'), '{}\n');
    const managedSkillsRoot = join(managedRoot, 'skills');
    const agentsSkillsRoot = join(agentsHome, 'skills');
    mkdirSync(managedSkillsRoot, { recursive: true });
    mkdirSync(agentsSkillsRoot, { recursive: true });
    const pointers = [
        [join(managedSkillsRoot, 'pstack'), join(releaseRoot, 'pstack', 'skills')],
        [join(agentsSkillsRoot, 'pstack'), join(releaseRoot, 'pstack', 'skills')],
        [
            join(agentsSkillsRoot, 'cursor-team-kit-deslop'),
            join(releaseRoot, 'cursor-team-kit', 'skills', 'deslop'),
        ],
    ];
    for (const [pointerPath, targetPath] of pointers) {
        symlinkSync(targetPath, pointerPath, 'dir');
    }
    return {
        roots: { managedRoot, agentsHome, skillsLookupDirectory: managedSkillsRoot, skillsInstallDirectory: agentsSkillsRoot },
        managedSkillsRoot,
        agentsSkillsRoot,
        pointerPaths: pointers.map(([pointerPath]) => pointerPath),
    };
}

test('the store root sits under the managed root', () => {
    assert.equal(
        retiredPstackStoreRoot(join('/managed', '.claude')),
        join('/managed', '.claude', 'pstack'),
    );
});

test('every pointer into the retired store is removed along with the store', t => {
    const fixture = retiredInstallationFixture(t);

    const outcome = removeRetiredPstackInstallation(fixture.roots);

    assert.deepEqual(outcome.removedPointerPaths.sort(), fixture.pointerPaths.sort());
    assert.equal(outcome.removedStorePath, retiredPstackStoreRoot(fixture.roots.managedRoot));
    for (const pointerPath of fixture.pointerPaths) {
        assert.equal(existsSync(pointerPath), false);
    }
    assert.equal(existsSync(retiredPstackStoreRoot(fixture.roots.managedRoot)), false);
});

test('a skill that is not a pointer into the store stays in place', t => {
    const fixture = retiredInstallationFixture(t);
    const ownSkillDirectory = join(fixture.agentsSkillsRoot, 'pull-request');
    mkdirSync(ownSkillDirectory, { recursive: true });
    writeFileSync(join(ownSkillDirectory, 'SKILL.md'), '---\nname: pull-request\n---\n');
    const unrelatedTarget = join(fixture.roots.managedRoot, 'elsewhere', 'pstack');
    mkdirSync(unrelatedTarget, { recursive: true });
    const unrelatedPointer = join(fixture.agentsSkillsRoot, 'pstack-of-my-own');
    symlinkSync(unrelatedTarget, unrelatedPointer, 'dir');

    removeRetiredPstackInstallation(fixture.roots);

    assert.equal(existsSync(join(ownSkillDirectory, 'SKILL.md')), true);
    assert.equal(lstatSync(unrelatedPointer).isSymbolicLink(), true);
});

test('a home with no retired installation reports nothing removed', t => {
    const fixture = retiredInstallationFixture(t);
    removeRetiredPstackInstallation(fixture.roots);

    const secondOutcome = removeRetiredPstackInstallation(fixture.roots);

    assert.deepEqual(secondOutcome.removedPointerPaths, []);
    assert.equal(secondOutcome.removedStorePath, null);
});

test('a dangling pointer into the store is removed after the store is gone', t => {
    const fixture = retiredInstallationFixture(t);
    rmSync(retiredPstackStoreRoot(fixture.roots.managedRoot), { recursive: true, force: true });

    const outcome = removeRetiredPstackInstallation(fixture.roots);

    assert.deepEqual(outcome.removedPointerPaths.sort(), fixture.pointerPaths.sort());
    assert.equal(outcome.removedStorePath, null);
});
