import { execFileSync } from 'node:child_process';
import { mkdirSync, readFileSync, realpathSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { adapterDigest, validateVerifiedLock } from '../packages/claude-dev-env/bin/pstack.mjs';

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const packageRoot = join(repositoryRoot, 'packages', 'claude-dev-env');
const channelRef = 'refs/heads/pstack-verified';

export function createPstackCandidate(outputPath, dependencies = {}) {
    const bundled = JSON.parse(readFileSync(join(packageRoot, 'scripts', 'pstack.lock.json'), 'utf8'));
    const readCommit = dependencies.readCommit ?? (repository => execFileSync('git', ['ls-remote', repository, 'HEAD'], {
        encoding: 'utf8', timeout: 30000, env: { ...process.env, GIT_TERMINAL_PROMPT: '0' },
    }).trim().split(/\s+/)[0]);
    const candidate = validateVerifiedLock({ ...bundled, commit: readCommit(bundled.repository),
        adapterDigest: adapterDigest(), verification: 'install-contract' });
    mkdirSync(dirname(resolve(outputPath)), { recursive: true });
    writeFileSync(outputPath, JSON.stringify(candidate, null, 2) + '\n');
    return candidate;
}

export function publishPstackChannel(lockPath, options = {}) {
    const record = validateVerifiedLock(JSON.parse(readFileSync(lockPath, 'utf8')));
    if (record.adapterDigest !== adapterDigest()) throw new Error('Candidate adapter differs from the checked source');
    const content = JSON.stringify(record, null, 2) + '\n';
    const remote = options.remote ?? 'origin';
    const git = (args, input) => execFileSync('git', args, {
        cwd: options.repositoryRoot ?? repositoryRoot, input, encoding: 'utf8', timeout: 40000,
        env: { ...process.env, GIT_TERMINAL_PROMPT: '0' }, stdio: ['pipe', 'pipe', 'pipe'],
    }).trim();
    let parent;
    const remoteHead = git(['ls-remote', remote, channelRef]);
    if (remoteHead) {
        git(['fetch', '--quiet', remote, channelRef]);
        parent = git(['rev-parse', 'FETCH_HEAD']);
        if (git(['show', `${parent}:pstack.lock.json`]) === content.trim()) {
            return { status: 'unchanged', commit: record.commit };
        }
    }
    const blob = git(['hash-object', '-w', '--stdin'], content);
    const tree = git(['mktree'], `100644 blob ${blob}\tpstack.lock.json\n`);
    const commit = git(['-c', 'user.name=github-actions[bot]',
        '-c', 'user.email=41898282+github-actions[bot]@users.noreply.github.com',
        'commit-tree', tree, ...(parent ? ['-p', parent] : []), '-m', `Verify pstack ${record.commit}`]);
    git(['push', remote, `${commit}:${channelRef}`]);
    return { status: 'published', commit: record.commit };
}

if (process.argv[1] && realpathSync(process.argv[1]) === fileURLToPath(import.meta.url)) {
    try {
        const [command, lockPath] = process.argv.slice(2);
        if (!lockPath || !['candidate', 'publish'].includes(command)) {
            throw new Error('Use pstack-channel.mjs <candidate|publish> LOCK_PATH');
        }
        const record = command === 'candidate' ? createPstackCandidate(lockPath) : publishPstackChannel(lockPath);
        console.log(JSON.stringify(record, null, 2));
    } catch (error) { console.error(error.message); process.exitCode = 1; }
}
