import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, realpathSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { installPstack, validateLock } from '../packages/claude-dev-env/bin/pstack.mjs';

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const defaultLockPath = join(repositoryRoot, 'packages', 'claude-dev-env', 'scripts', 'pstack.lock.json');

export function proposePstackUpdate(lockPath = defaultLockPath, dependencies = {}) {
    const lock = validateLock(JSON.parse(readFileSync(lockPath, 'utf8')));
    const readCommit = dependencies.readCommit ?? (repository => execFileSync('git', ['ls-remote', repository, 'HEAD'], {
        encoding: 'utf8', timeout: 30000, env: { ...process.env, GIT_TERMINAL_PROMPT: '0' },
    }).trim().split(/\s+/)[0]);
    const candidate = validateLock({ ...lock, commit: readCommit(lock.repository) });
    if (candidate.commit === lock.commit) return { status: 'unchanged', commit: lock.commit };
    const temporary = mkdtempSync(join(tmpdir(), 'pstack-candidate-'));
    try {
        const installation = (dependencies.install ?? installPstack)({ root: join(temporary, '.claude'), lock: candidate, strict: true });
        writeFileSync(lockPath, JSON.stringify(candidate, null, 2) + '\n');
        return { status: 'proposed', commit: installation.commit, skillCount: installation.skillCount };
    } finally { rmSync(temporary, { recursive: true, force: true }); }
}

if (process.argv[1] && realpathSync(process.argv[1]) === fileURLToPath(import.meta.url)) {
    const proposal = proposePstackUpdate();
    console.log(`Pstack ${proposal.commit}: ${proposal.status}. Native host acceptance remains a review gate.`);
}
