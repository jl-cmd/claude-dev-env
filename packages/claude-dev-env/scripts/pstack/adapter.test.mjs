import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { buildPublication, putFile, skillNames } from './adapter.mjs';

test('skill enumeration includes only directories with a skill entry point', t => {
    const directory = mkdtempSync(join(tmpdir(), 'pstack enumeration '));
    t.after(() => rmSync(directory, { recursive: true, force: true }));
    putFile(join(directory, 'skills/zebra/SKILL.md'), 'Zebra workflow.');
    putFile(join(directory, 'skills/alpha/SKILL.md'), 'Alpha workflow.');
    putFile(join(directory, 'skills/references/guide.md'), 'Supporting file.');
    putFile(join(directory, 'skills/README.md'), 'Skill index.');
    assert.deepEqual(skillNames(directory), ['alpha', 'zebra']);
});

test('publication rejects skill names outside the portable naming rules', t => {
    const directory = mkdtempSync(join(tmpdir(), 'pstack invalid name '));
    t.after(() => rmSync(directory, { recursive: true, force: true }));
    putFile(join(directory, 'upstream/pstack/skills/Invalid Name/SKILL.md'),
        '---\nname: Invalid Name\ndescription: A fixture workflow.\n---\nRead evidence.\n');
    assert.throws(() => buildPublication(directory, join(directory, 'release'), directory),
        /Invalid skill name: Invalid Name/);
});
