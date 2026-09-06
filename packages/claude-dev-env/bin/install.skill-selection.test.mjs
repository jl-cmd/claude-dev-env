import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';
import test from 'node:test';
import { CORE_SKILLS, INSTALL_GROUPS } from './install.mjs';
import { EVER_SHIPPED_SKILL_NAMES } from './ever-shipped-skills.mjs';
import { resolvePackageManagedDirectory } from './resolve-package-managed-directory.mjs';

const PACKAGE_ROOT = fileURLToPath(new URL('../', import.meta.url));
const RETIRED_SKILLS = ['pr-small-cl', 'session-log', 'session-tidy'];

test('each core skill has a shipped entry point', () => {
    const skillsRoot = resolvePackageManagedDirectory(PACKAGE_ROOT, 'skills');
    for (const skillName of CORE_SKILLS) {
        assert.ok(existsSync(join(skillsRoot, skillName, 'SKILL.md')), skillName);
    }
});

test('retired skills leave install groups and stay in the cleanup registry', () => {
    const selectedSkills = Object.values(INSTALL_GROUPS).flatMap(group => group.skills ?? []);
    assert.equal(Object.hasOwn(INSTALL_GROUPS, 'journal'), false);
    for (const skillName of RETIRED_SKILLS) {
        assert.equal(selectedSkills.includes(skillName), false, skillName);
        assert.ok(EVER_SHIPPED_SKILL_NAMES.has(skillName), skillName);
    }
});

test('README and vault guidance use current session tools', () => {
    const readme = readFileSync(new URL('../../../README.md', import.meta.url), 'utf8');
    const vaultRule = readFileSync(new URL('../rules/vault-context.md', import.meta.url), 'utf8');
    assert.doesNotMatch(readme, /--only journal|session-log|session-tidy/);
    assert.doesNotMatch(vaultRule, /`session-log`|`recall`/);
    assert.match(vaultRule, /obsidian MCP tools/);
    assert.match(vaultRule, /project.*frontmatter/);
});
