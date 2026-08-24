/**
 * Package-source layout: skills and agents live under `.agents`, and
 * `.claude/skills` / `.claude/agents` are directory pointers to that home.
 */

import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import {
    existsSync,
    lstatSync,
    mkdirSync,
    mkdtempSync,
    realpathSync,
    rmSync,
    writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
    MANAGED_AGENTS_DIRECTORY_NAME,
    MANAGED_SKILLS_DIRECTORY_NAME,
    PACKAGE_AGENTS_HOME_DIRECTORY_NAME,
} from './install-constants.mjs';
import { resolvePackageManagedDirectory } from './resolve-package-managed-directory.mjs';

const PACKAGE_ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const CANONICAL_SKILL_NAME = 'privacy-hygiene';
const CANONICAL_AGENT_FILE_NAME = 'clean-coder.md';

test('prefers the .agents tree when both layouts exist', () => {
    const sourceRoot = mkdtempSync(join(tmpdir(), 'cdev-src-agents-'));
    try {
        const agentsHomeSkills = join(
            sourceRoot, PACKAGE_AGENTS_HOME_DIRECTORY_NAME, MANAGED_SKILLS_DIRECTORY_NAME,
        );
        const packageRootSkills = join(sourceRoot, MANAGED_SKILLS_DIRECTORY_NAME);
        mkdirSync(agentsHomeSkills, { recursive: true });
        mkdirSync(packageRootSkills, { recursive: true });
        writeFileSync(join(agentsHomeSkills, 'marker.txt'), 'canonical\n');
        writeFileSync(join(packageRootSkills, 'marker.txt'), 'legacy\n');
        assert.equal(
            resolvePackageManagedDirectory(sourceRoot, MANAGED_SKILLS_DIRECTORY_NAME),
            agentsHomeSkills,
        );
    } finally {
        rmSync(sourceRoot, { recursive: true, force: true });
    }
});

test('falls back to the package-root tree when .agents does not carry it', () => {
    const sourceRoot = mkdtempSync(join(tmpdir(), 'cdev-src-legacy-'));
    try {
        const packageRootSkills = join(sourceRoot, MANAGED_SKILLS_DIRECTORY_NAME);
        mkdirSync(packageRootSkills, { recursive: true });
        assert.equal(
            resolvePackageManagedDirectory(sourceRoot, MANAGED_SKILLS_DIRECTORY_NAME),
            packageRootSkills,
        );
    } finally {
        rmSync(sourceRoot, { recursive: true, force: true });
    }
});

test('live package source keeps skills and agents under .agents with .claude pointers', () => {
    const canonicalSkills = join(
        PACKAGE_ROOT, PACKAGE_AGENTS_HOME_DIRECTORY_NAME, MANAGED_SKILLS_DIRECTORY_NAME,
    );
    const canonicalAgents = join(
        PACKAGE_ROOT, PACKAGE_AGENTS_HOME_DIRECTORY_NAME, MANAGED_AGENTS_DIRECTORY_NAME,
    );
    const lookupSkills = join(PACKAGE_ROOT, '.claude', MANAGED_SKILLS_DIRECTORY_NAME);
    const lookupAgents = join(PACKAGE_ROOT, '.claude', MANAGED_AGENTS_DIRECTORY_NAME);

    assert.equal(
        resolvePackageManagedDirectory(PACKAGE_ROOT, MANAGED_SKILLS_DIRECTORY_NAME),
        canonicalSkills,
    );
    assert.equal(
        resolvePackageManagedDirectory(PACKAGE_ROOT, MANAGED_AGENTS_DIRECTORY_NAME),
        canonicalAgents,
    );
    assert.equal(
        existsSync(join(canonicalSkills, CANONICAL_SKILL_NAME, 'SKILL.md')),
        true,
    );
    assert.equal(
        existsSync(join(canonicalAgents, CANONICAL_AGENT_FILE_NAME)),
        true,
    );
    assert.equal(existsSync(join(PACKAGE_ROOT, MANAGED_SKILLS_DIRECTORY_NAME)), false);
    assert.equal(existsSync(join(PACKAGE_ROOT, MANAGED_AGENTS_DIRECTORY_NAME)), false);
    assert.equal(lstatSync(lookupSkills).isSymbolicLink(), true);
    assert.equal(lstatSync(lookupAgents).isSymbolicLink(), true);
    assert.equal(realpathSync(lookupSkills), realpathSync(canonicalSkills));
    assert.equal(realpathSync(lookupAgents), realpathSync(canonicalAgents));
});
