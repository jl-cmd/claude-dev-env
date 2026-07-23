import { strict as assert } from 'node:assert';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';

const binDirectory = dirname(fileURLToPath(import.meta.url));
const packageRoot = join(binDirectory, '..');
const sourceSkillsRoot = join(packageRoot, 'skills');
const installEntryPoint = join(binDirectory, 'install.mjs');
const skillNames = ['e-simplify', 'review-tier', 'review-router'];

function collectFiles(directory, relativeRoot = directory) {
    const files = [];
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
        const entryPath = join(directory, entry.name);
        if (entry.isDirectory() && entry.name === '__pycache__') continue;
        if (entry.isDirectory()) files.push(...collectFiles(entryPath, relativeRoot));
        else if (!entry.name.endsWith('.pyc')) files.push(relative(relativeRoot, entryPath).replaceAll('\\', '/'));
    }
    return files.sort();
}

function collectCacheArtifacts(directory, relativeRoot = directory) {
    const artifacts = [];
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
        const entryPath = join(directory, entry.name);
        const relativePath = relative(relativeRoot, entryPath).replaceAll('\\', '/');
        if (entry.isDirectory()) {
            if (entry.name === '__pycache__') artifacts.push(relativePath);
            artifacts.push(...collectCacheArtifacts(entryPath, relativeRoot));
        } else if (entry.name.endsWith('.pyc')) {
            artifacts.push(relativePath);
        }
    }
    return artifacts.sort();
}

function fileDigest(filePath) {
    return createHash('sha256').update(readFileSync(filePath)).digest('hex');
}

function assertSkillParity(installedSkillsRoot, skillName) {
    const sourceRoot = join(sourceSkillsRoot, skillName);
    const installedRoot = join(installedSkillsRoot, skillName);
    const sourceFiles = collectFiles(sourceRoot);
    const installedFiles = collectFiles(installedRoot);
    assert.deepEqual(installedFiles, sourceFiles, skillName);
    for (const relativePath of sourceFiles) {
        assert.equal(
            fileDigest(join(installedRoot, relativePath)),
            fileDigest(join(sourceRoot, relativePath)),
            `${skillName}/${relativePath}`,
        );
    }
}

test('cache inspection detects Python cache directories and bytecode files', () => {
    const temporaryRoot = mkdtempSync(join(tmpdir(), 'cdev-review-cache-fixture-'));
    try {
        mkdirSync(join(temporaryRoot, 'nested', '__pycache__'), { recursive: true });
        writeFileSync(join(temporaryRoot, 'nested', '__pycache__', 'module.pyc'), Buffer.from([0]));
        assert.deepEqual(collectCacheArtifacts(temporaryRoot), ['nested/__pycache__', 'nested/__pycache__/module.pyc']);
    } finally {
        if (statSync(temporaryRoot, { throwIfNoEntry: false })) rmSync(temporaryRoot, { recursive: true, force: true });
    }
});

test('real installer preserves exact review skill parity without Python cache artifacts', () => {
    const temporaryHome = mkdtempSync(join(tmpdir(), 'cdev-review-skill-install-'));
    try {
        execFileSync(process.execPath, [installEntryPoint, '--only', 'core'], {
            cwd: packageRoot,
            env: { ...process.env, HOME: temporaryHome, USERPROFILE: temporaryHome },
            stdio: 'pipe',
        });
        const installedSkillsRoot = join(temporaryHome, '.claude', 'skills');
        for (const skillName of skillNames) assertSkillParity(installedSkillsRoot, skillName);
        assert.deepEqual(collectCacheArtifacts(installedSkillsRoot), []);
    } finally {
        if (statSync(temporaryHome, { throwIfNoEntry: false })) rmSync(temporaryHome, { recursive: true, force: true });
    }
});
