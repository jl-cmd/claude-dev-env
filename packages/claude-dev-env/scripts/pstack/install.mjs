import {
    cpSync, existsSync, lstatSync, mkdirSync, mkdtempSync, readFileSync, readdirSync,
    readlinkSync, renameSync, rmSync, symlinkSync,
} from 'node:fs';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { buildPublication, nativeAgentFiles, putFile } from './adapter.mjs';

const packageRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const upstreamUrl = 'https://github.com/cursor/plugins.git';
const channelUrl = 'https://raw.githubusercontent.com/jl-cmd/claude-dev-env/pstack-verified/pstack.lock.json';

function readJson(path) {
    return JSON.parse(readFileSync(path, 'utf8'));
}

function atomicJson(path, jsonValue) {
    const pending = `${path}.${process.pid}.tmp`;
    putFile(pending, JSON.stringify(jsonValue, null, 2) + '\n');
    renameSync(pending, path);
}

function present(path) {
    try { lstatSync(path); return true; } catch (error) {
        if (error.code === 'ENOENT') return false;
        throw error;
    }
}

function hash(content) {
    return createHash('sha256').update(content).digest('hex');
}

function inventory(root, prefix = '') {
    const files = {};
    for (const entry of readdirSync(join(root, prefix), { withFileTypes: true })) {
        const name = join(prefix, entry.name);
        if (entry.isSymbolicLink()) throw new Error(`Symlink in source or release: ${name}`);
        if (entry.isDirectory()) Object.assign(files, inventory(root, name));
        else if (entry.isFile()) files[name] = hash(readFileSync(join(root, name)));
        else throw new Error(`Unsupported source entry: ${name}`);
    }
    return files;
}

export function validateLock(lock) {
    if (lock?.schemaVersion !== 1 || lock.adapterVersion !== 1
        || !/^[a-f0-9]{40}$/.test(lock.upstreamCommit ?? '')
        || !/^[a-f0-9]{64}$/.test(lock.adapterDigest ?? '')
        || lock.verification !== 'install-contract') {
        throw new Error('Invalid pstack lock or unsupported adapter version');
    }
    return lock;
}

function git(args, cwd) {
    return execFileSync('git', ['-c', 'core.hooksPath=/dev/null', '-c', 'core.autocrlf=false', ...args], {
        cwd, encoding: 'utf8', timeout: 120000,
        env: { ...process.env, GIT_TERMINAL_PROMPT: '0' },
        stdio: ['ignore', 'pipe', 'pipe'],
    }).trim();
}

function sourceCheckout(lock, explicitSource, work) {
    const source = explicitSource ? resolve(explicitSource) : upstreamUrl;
    if (explicitSource) {
        if (git(['rev-parse', 'HEAD'], source) !== lock.upstreamCommit) {
            throw new Error('Source checkout does not match the pinned commit');
        }
        if (git(['status', '--porcelain', '--untracked-files=all', '--', 'pstack', 'cursor-team-kit'], source)) {
            throw new Error('Source plugin directories have uncommitted changes');
        }
    }
    git(['init', '--quiet', work]);
    git(['fetch', '--quiet', '--depth=1', source, lock.upstreamCommit], work);
    if (git(['rev-parse', 'FETCH_HEAD'], work) !== lock.upstreamCommit) {
        throw new Error('Fetched commit differs from the verified record');
    }
    git(['checkout', '--quiet', '--detach', 'FETCH_HEAD'], work);
    return work;
}

export function adapterDigest(packageDirectory) {
    const paths = [
        'bin/pstack.mjs', 'scripts/pstack/install.mjs', 'scripts/pstack/adapter.mjs',
        'scripts/pstack/compatibility.md', 'rules/pstack-models.md',
        'rules/pstack-host-mapping.md', 'scripts/select_pstack_models.mjs',
    ];
    return hash(paths.map(path => readFileSync(join(packageDirectory, path), 'utf8').replace(/\r\n/g, '\n')).join('\0'));
}

function releasePath(root, generation) {
    if (!/^[a-f0-9]{40}-[a-f0-9]{16}$/.test(generation ?? '')) {
        throw new Error('Invalid installed generation');
    }
    return join(root, '.claude', 'pstack', 'releases', generation);
}

export function verifyRelease(root, generation) {
    const release = releasePath(root, generation);
    const record = readJson(join(release, 'release.json'));
    validateLock(record.lock);
    if (record.generation !== generation) throw new Error('Release identity mismatch');
    const actual = inventory(release);
    delete actual['release.json'];
    if (JSON.stringify(Object.keys(actual).sort()) !== JSON.stringify(Object.keys(record.files).sort())) {
        throw new Error('Installed file set differs from the release record');
    }
    for (const [path, digest] of Object.entries(record.files)) {
        if (actual[path] !== digest) throw new Error(`Installed file changed: ${path}`);
    }
    return record;
}

function aliases(root, skills) {
    const links = [
        ...['pstack', 'cursor-team-kit'].map(plugin => ({
            path: join(root, '.claude', 'skills', plugin),
            target: join(root, '.claude', 'pstack', 'current', 'published', plugin),
        })),
        ...skills.map(({ plugin, name }) => ({
            path: join(root, '.agents', 'skills', name),
            target: join(root, '.claude', 'skills', plugin, name),
        })),
    ];
    return links;
}

function sameLink(path, target) {
    return present(path) && lstatSync(path).isSymbolicLink()
        && resolve(dirname(path), readlinkSync(path)) === resolve(target);
}

function directoryLink(path, target) {
    mkdirSync(dirname(path), { recursive: true });
    symlinkSync(resolve(target), path, process.platform === 'win32' ? 'junction' : 'dir');
}

function setCurrent(home, release) {
    const current = join(home, 'current');
    const pending = join(home, `current-${process.pid}`);
    const previous = join(home, 'previous-link');
    rmSync(pending, { force: true });
    directoryLink(pending, release);
    try {
        renameSync(pending, current);
    } catch (error) {
        if (process.platform !== 'win32' || !present(current)) {
            rmSync(pending, { force: true });
            throw error;
        }
        renameSync(current, previous);
        try { renameSync(pending, current); } catch (replacementError) {
            renameSync(previous, current);
            throw replacementError;
        }
        rmSync(previous, { force: true });
    }
}

export function verifyInstallation(root) {
    root = resolve(root);
    const home = join(root, '.claude', 'pstack');
    const state = readJson(join(home, 'state.json'));
    const record = verifyRelease(root, state.generation);
    if (!sameLink(join(home, 'current'), releasePath(root, state.generation))) {
        throw new Error('Current release pointer does not match the installation record');
    }
    for (const { path, target } of aliases(root, record.skills)) {
        if (!sameLink(path, target)) throw new Error(`Skill discovery link changed: ${path}`);
    }
    for (const { path, content } of nativeAgentFiles(root)) {
        if (!present(path) || readFileSync(path, 'utf8') !== content) {
            throw new Error(`Native agent file changed: ${path}`);
        }
    }
    return { ...state, release: releasePath(root, state.generation), skills: record.skills };
}

function processLives(pid) {
    if (!Number.isInteger(pid) || pid < 1) return false;
    try { process.kill(pid, 0); return true; } catch (error) { return error.code === 'EPERM'; }
}

function activeLeases(home) {
    const leases = join(home, 'leases');
    if (!existsSync(leases)) return [];
    return readdirSync(leases).filter(name => {
        const pid = Number(name.replace(/\.json$/, ''));
        if (processLives(pid)) return true;
        rmSync(join(leases, name), { force: true });
        return false;
    });
}

function acquireLock(home) {
    const lock = join(home, 'install-lock');
    try { mkdirSync(lock); } catch (error) {
        if (error.code !== 'EEXIST') throw error;
        const owner = join(lock, 'owner.json');
        if (!existsSync(owner) || processLives(readJson(owner).pid)) {
            throw new Error('Another pstack installation is in progress');
        }
        rmSync(lock, { recursive: true });
        mkdirSync(lock);
    }
    atomicJson(join(lock, 'owner.json'), { pid: process.pid });
    return () => rmSync(lock, { recursive: true, force: true });
}

async function remoteLock() {
    const channelResponse = await fetch(channelUrl, { signal: AbortSignal.timeout(15000), redirect: 'error' });
    if (!channelResponse.ok) throw new Error(`Verified pstack channel returned HTTP ${channelResponse.status}`);
    return validateLock(await channelResponse.json());
}

function publish(root, record, previous) {
    const home = join(root, '.claude', 'pstack');
    const links = aliases(root, record.skills);
    const oldLinks = previous ? aliases(root, previous.skills) : [];
    const files = nativeAgentFiles(root);
    for (const { path, target } of [...oldLinks, ...links]) {
        if (present(path) && !sameLink(path, target)) throw new Error(`Unmanaged discovery path: ${path}`);
    }
    for (const { path, content } of files) {
        if (present(path) && (lstatSync(path).isSymbolicLink() || readFileSync(path, 'utf8') !== content)) {
            throw new Error(`Unmanaged agent file: ${path}`);
        }
    }
    const created = [];
    const removed = [];
    let hasSwitched = false;
    try {
        for (const { path, target } of links) {
            if (!present(path)) { directoryLink(path, target); created.push(path); }
        }
        for (const { path, content } of files) {
            if (!present(path)) { putFile(path, content); created.push(path); }
        }
        setCurrent(home, releasePath(root, record.generation));
        hasSwitched = true;
        for (const link of oldLinks) {
            if (!links.some(next => next.path === link.path)) {
                rmSync(link.path); removed.push(link);
            }
        }
        const state = {
            schemaVersion: 1, generation: record.generation, upstreamCommit: record.lock.upstreamCommit,
            adapterVersion: record.lock.adapterVersion, adapterDigest: record.adapterDigest,
            checkedAt: new Date().toISOString(), hosts: ['claude', 'codex', 'cursor'],
            verification: 'install-contract',
        };
        atomicJson(join(home, 'state.json'), state);
        return { ...state, release: releasePath(root, state.generation), skills: record.skills };
    } catch (error) {
        if (hasSwitched) {
            if (previous) setCurrent(home, previous.release);
            else rmSync(join(home, 'current'), { force: true });
        }
        for (const path of created.reverse()) rmSync(path, { force: true });
        for (const { path, target } of removed) directoryLink(path, target);
        throw error;
    }
}

function prepare(root, lock, source, packageDirectory) {
    const digest = adapterDigest(packageDirectory);
    if (lock.adapterDigest !== digest) throw new Error('Verified adapter differs from this package; update claude-dev-env first');
    const generation = `${lock.upstreamCommit}-${digest.slice(0, 16)}`;
    const release = releasePath(root, generation);
    if (existsSync(release)) return verifyRelease(root, generation);
    mkdirSync(dirname(release), { recursive: true });
    const stage = mkdtempSync(join(dirname(release), '.building-'));
    const work = mkdtempSync(join(tmpdir(), 'cde-pstack-source-'));
    try {
        const checkout = sourceCheckout(lock, source, work);
        for (const plugin of ['pstack', 'cursor-team-kit']) {
            inventory(join(checkout, plugin));
            cpSync(join(checkout, plugin), join(stage, 'upstream', plugin), { recursive: true });
        }
        for (const file of ['LICENSE', 'NOTICE']) {
            if (existsSync(join(checkout, file))) {
                cpSync(join(checkout, file), join(stage, 'upstream', file));
            }
        }
        const skills = buildPublication(stage, release, packageDirectory);
        const record = { generation, adapterDigest: digest, lock, skills, files: inventory(stage) };
        atomicJson(join(stage, 'release.json'), record);
        renameSync(stage, release);
        return verifyRelease(root, generation);
    } finally {
        rmSync(stage, { recursive: true, force: true });
        rmSync(work, { recursive: true, force: true });
    }
}

export async function installPstack(options = {}) {
    const root = resolve(options.root ?? process.cwd());
    if (!['claude', 'codex', 'cursor'].includes(options.host)) throw new Error('Choose --host claude, codex or cursor');
    const home = join(root, '.claude', 'pstack');
    mkdirSync(home, { recursive: true });
    const unlock = acquireLock(home);
    try {
        if (!present(join(home, 'current')) && present(join(home, 'previous-link'))) {
            renameSync(join(home, 'previous-link'), join(home, 'current'));
        }
        const previous = existsSync(join(home, 'state.json')) ? verifyInstallation(root) : null;
        if (!previous && present(join(home, 'current'))) throw new Error('Unmanaged current release pointer');
        const finish = outcome => {
            if (options.leasePid) {
                if (!processLives(options.leasePid)) throw new Error('Launch lease owner is not running');
                atomicJson(join(home, 'leases', `${options.leasePid}.json`), { generation: outcome.generation });
            }
            return outcome;
        };
        if (previous && activeLeases(home).length) {
            return finish({ ...previous, deferred: true, warning: 'Update deferred while a launched agent is running.' });
        }
        const interval = options.checkIntervalMs ?? 6 * 60 * 60 * 1000;
        if (previous && !options.lock && !options.source
            && (options.offline || Date.now() - Date.parse(previous.checkedAt) < interval)) {
            return finish(previous);
        }
        let lock = options.lock ? validateLock(options.lock) : null;
        let warning;
        if (!lock && !options.offline && !options.source) {
            try { lock = await (options.fetchLock ?? remoteLock)(); validateLock(lock); } catch (error) {
                warning = `Update check failed: ${error.message}`;
                if (previous) return finish({ ...previous, warning });
            }
        }
        lock ??= validateLock(readJson(join(options.packageRoot ?? packageRoot, 'scripts', 'pstack', 'verified.json')));
        if (options.offline && !options.source && !previous) {
            throw new Error('A fresh offline installation needs --source and --lock');
        }
        try {
            const record = prepare(root, lock, options.source, options.packageRoot ?? packageRoot);
            if (previous?.generation === record.generation) {
                const state = readJson(join(home, 'state.json'));
                state.checkedAt = new Date().toISOString();
                atomicJson(join(home, 'state.json'), state);
                return finish({ ...previous, checkedAt: state.checkedAt, warning });
            }
            return finish({ ...publish(root, record, previous), warning });
        } catch (error) {
            if (!previous) throw error;
            return finish({ ...verifyInstallation(root), warning: `Update failed; kept working release: ${error.message}` });
        }
    } finally { unlock(); }
}

export function releaseLease(root, pid = process.pid) {
    rmSync(join(resolve(root), '.claude', 'pstack', 'leases', `${pid}.json`), { force: true });
}
