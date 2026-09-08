import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { installPstack, validateLock } from '../packages/claude-dev-env/bin/pstack.mjs';

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const lockPath = join(repositoryRoot, 'packages', 'claude-dev-env', 'scripts', 'pstack.lock.json');
const lock = JSON.parse(readFileSync(lockPath, 'utf8'));
const commit = execFileSync('git', ['ls-remote', lock.repository, 'HEAD'], { encoding: 'utf8', timeout: 30000 }).trim().split(/\s+/)[0];
validateLock({ ...lock, commit });
if (commit !== lock.commit) {
    const temporary = mkdtempSync(join(tmpdir(), 'pstack-candidate-'));
    try {
        const candidate = { ...lock, commit };
        const result = installPstack({ root: join(temporary, '.claude'), lock: candidate, strict: true });
        console.log(`Candidate ${result.commit}: ${result.skillCount} skill entries. Native host acceptance remains a review gate.`);
        writeFileSync(lockPath, JSON.stringify(candidate, null, 2) + '\n');
    } finally { rmSync(temporary, { recursive: true, force: true }); }
}
