#!/usr/bin/env node
import { cpSync, existsSync, lstatSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, readlinkSync, realpathSync, renameSync, rmSync, symlinkSync, unlinkSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { execFileSync, spawnSync } from 'node:child_process';
import { homedir } from 'node:os';
import { basename, dirname, isAbsolute, join, relative, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const packageRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const bundledLockPath = join(packageRoot, 'scripts', 'pstack.lock.json');
const hosts = ['claude', 'codex', 'cursor'];
const digest = value => createHash('sha256').update(value).digest('hex');
const readJson = path => JSON.parse(readFileSync(path, 'utf8'));
const json = value => JSON.stringify(value, null, 2) + '\n';
const entryExists = path => { try { lstatSync(path); return true; } catch (error) { if (error.code === 'ENOENT') return false; throw error; } };

export function validateLock(lock) {
    if (lock?.schemaVersion !== 1 || lock?.adapterVersion !== 1
        || lock.repository !== 'https://github.com/cursor/plugins.git'
        || !/^[0-9a-f]{40}$/.test(lock.commit ?? '')
        || JSON.stringify(lock.components) !== JSON.stringify(['pstack', 'cursor-team-kit'])) {
        throw new Error('Unsupported pstack lock. Update claude-dev-env for a newer adapter.');
    }
    const required = { pstack: ['poteto-mode'], 'cursor-team-kit': ['deslop', 'control-cli', 'control-ui'] };
    for (const [component, names] of Object.entries(required)) {
        const declared = lock.requiredSkills?.[component];
        if (!Array.isArray(declared) || declared.some(name => !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(name))
            || names.some(name => !declared.includes(name))) throw new Error(`Invalid ${component} dependencies`);
    }
    return lock;
}

function filesUnder(root) {
    return readdirSync(root, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name)).flatMap(entry => {
        const path = join(root, entry.name);
        if (entry.isSymbolicLink()) throw new Error(`Upstream symlinks require review: ${path}`);
        if (entry.isDirectory()) return filesUnder(path);
        if (!entry.isFile()) throw new Error(`Unsupported upstream file: ${path}`);
        return [path];
    });
}

function runGit(args, cwd) {
    return execFileSync('git', args, {
        cwd, encoding: 'utf8', timeout: 40000, maxBuffer: 16 * 1024 * 1024,
        env: { ...process.env, GIT_TERMINAL_PROMPT: '0' },
        stdio: ['ignore', 'pipe', 'pipe'],
    }).trim();
}

export function fetchUpstream(lock, destination) {
    mkdirSync(destination, { recursive: true });
    runGit(['init', '--quiet'], destination);
    runGit(['config', 'core.autocrlf', 'false'], destination);
    runGit(['config', 'core.hooksPath', join(destination, '.disabled-hooks')], destination);
    runGit(['remote', 'add', 'origin', lock.repository], destination);
    runGit(['config', 'core.sparseCheckout', 'true'], destination);
    writeFileSync(join(destination, '.git', 'info', 'sparse-checkout'), '/pstack/\n/cursor-team-kit/\n/LICENSE\n');
    runGit(['fetch', '--quiet', '--depth=1', '--filter=blob:none', 'origin', lock.commit], destination);
    if (runGit(['rev-parse', 'FETCH_HEAD'], destination) !== lock.commit) throw new Error('Upstream commit mismatch');
    runGit(['checkout', '--quiet', '--detach', 'FETCH_HEAD'], destination);
}

function adapterFiles(root) {
    const adapters = join(root, 'scripts', 'pstack-adapters');
    return Object.fromEntries([
        ...['common.md', ...hosts.map(host => `host-${host}.md`), 'create-skill.md'].map(name => [name, join(adapters, name)]),
        ...['pstack-host-mapping.md', 'pstack-models.md'].map(name => [name, join(root, 'rules', name)]),
        ['select_pstack_models.mjs', join(root, 'scripts', 'select_pstack_models.mjs')],
    ].map(([name, path]) => [name, readFileSync(path, 'utf8')]));
}

function adaptSkill(text, name, releaseRoot, skillRoot) {
    const match = text.match(/^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)([\s\S]*)$/);
    if (!match || !/^description:\s*\S/m.test(match[1])) throw new Error(`Missing skill metadata: ${name}`);
    const frontmatter = match[1].replace(/^name:.*$/m, `name: ${name}`);
    if (!/^name:/m.test(frontmatter)) throw new Error(`Missing skill name: ${name}`);
    const safeFrontmatter = frontmatter.replace(/^(?:context|agent|model):.*\r?\n?/gm, '');
    const fork = /^context:\s*fork\s*$/m.test(frontmatter)
        ? 'The upstream entry requests a fork. Delegate through the native host after reading the compatibility mapping.\n' : '';
    return `---\n${safeFrontmatter}\n---\n\n## Host compatibility\n\n`
        + `Read ${JSON.stringify(join(releaseRoot, 'compat', 'common.md'))} and the matching host file before following this workflow.\n`
        + `Resolve this skill's relative paths from ${JSON.stringify(skillRoot)}. Read ${JSON.stringify(join(releaseRoot, 'release.json'))} for skill and agent paths.\n`
        + fork + '\n' + match[2].trimStart();
}

function writePstackPluginManifest(checkout, stage, skills) {
    const upstream = readJson(join(checkout, 'pstack', '.cursor-plugin', 'plugin.json'));
    const manifest = {
        $schema: 'https://anthropic.com/claude-code/plugin.schema.json',
        name: 'pstack',
        version: upstream.version,
        description: upstream.description,
        author: upstream.author,
        homepage: upstream.homepage,
        repository: upstream.repository,
        license: upstream.license,
        skills: skills.filter(skill => skill.component === 'pstack').map(skill => `./${skill.slug}`),
    };
    const pluginRoot = join(stage, 'runtime', 'pstack', 'skills');
    mkdirSync(join(pluginRoot, '.claude-plugin'), { recursive: true });
    writeFileSync(join(pluginRoot, '.claude-plugin', 'plugin.json'), json(manifest));
}

export function prepareRelease(checkout, stage, finalRoot, lock, adapters) {
    const skills = [];
    const agents = [];
    mkdirSync(join(stage, 'compat'), { recursive: true });
    for (const [name, content] of Object.entries(adapters)) writeFileSync(join(stage, 'compat', name), content);
    for (const component of lock.components) {
        const source = join(checkout, component);
        filesUnder(source);
        cpSync(source, join(stage, 'upstream', component), { recursive: true });
        cpSync(source, join(stage, 'runtime', component), { recursive: true });
        rmSync(join(stage, 'runtime', component, '.cursor-plugin', 'plugin.json'), { force: true });
        const skillHome = join(source, 'skills');
        const names = readdirSync(skillHome).filter(name => existsSync(join(skillHome, name, 'SKILL.md'))).sort();
        for (const name of lock.requiredSkills[component]) {
            if (!names.includes(name)) throw new Error(`Missing dependency: ${component}:${name}`);
        }
        for (const slug of names) {
            if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)) throw new Error(`Invalid skill directory: ${slug}`);
            const name = `${component}-${slug}`;
            const path = join('runtime', component, 'skills', slug);
            const text = readFileSync(join(source, 'skills', slug, 'SKILL.md'), 'utf8');
            writeFileSync(join(stage, path, 'SKILL.md'), adaptSkill(text, name, finalRoot, join(finalRoot, path)));
            skills.push({ name, component, slug, path });
        }
        const agentHome = join(source, 'agents');
        if (existsSync(agentHome)) {
            for (const path of filesUnder(agentHome)) agents.push({ component, path: join('runtime', component, 'agents', relative(agentHome, path)) });
        }
    }
    if (existsSync(join(checkout, 'LICENSE'))) cpSync(join(checkout, 'LICENSE'), join(stage, 'upstream', 'LICENSE'));
    const creatorPath = join('runtime', 'cde-create-skill');
    mkdirSync(join(stage, creatorPath), { recursive: true });
    writeFileSync(join(stage, creatorPath, 'SKILL.md'), adapters['create-skill.md']);
    skills.push({ name: 'cde-create-skill', component: 'cde', slug: 'create-skill', path: creatorPath });
    writePstackPluginManifest(checkout, stage, skills);
    const knownNames = new Set(skills.map(skill => `${skill.component}:${skill.slug}`));
    for (const path of filesUnder(join(stage, 'upstream')).filter(path => path.endsWith('.md') && (path.includes(sep + 'skills' + sep) || path.includes(sep + 'agents' + sep)))) {
        const references = readFileSync(path, 'utf8').matchAll(/\b(pstack|cursor-team-kit):([a-z][a-z0-9-]*)/g);
        for (const [, component, slug] of references) {
            if (!knownNames.has(`${component}:${slug}`)) throw new Error(`Unresolved skill dependency: ${component}:${slug}`);
        }
    }
    const fileDigests = Object.fromEntries(filesUnder(stage).map(path => [relative(stage, path), digest(readFileSync(path))]));
    const managedRoot = dirname(dirname(dirname(finalRoot)));
    const agentsRoot = basename(managedRoot) === '.claude' ? join(dirname(managedRoot), '.agents') : managedRoot + '.agents';
    const release = { preferencesDirectory: join(agentsRoot, 'rules'), selectorPath: join(finalRoot, 'compat', 'select_pstack_models.mjs'), schemaVersion: 1, commit: lock.commit, adapterVersion: lock.adapterVersion, skills, agents, fileDigests, verification: 'filesystem-only' };
    writeFileSync(join(stage, 'release.json'), json(release));
    return release;
}

function assertContained(root, path) {
    const rel = relative(root, resolve(root, path));
    if (isAbsolute(rel) || rel === '..' || rel.startsWith('..' + sep) || resolve(root, path) === resolve(root)) throw new Error('Invalid release path');
    return resolve(root, path);
}

export function verifyRelease(root) {
    const release = readJson(join(root, 'release.json'));
    if (release.schemaVersion !== 1 || !Array.isArray(release.skills) || !release.skills.length || !release.fileDigests) throw new Error('Invalid release manifest');
    for (const [path, hash] of Object.entries(release.fileDigests)) {
        if (digest(readFileSync(assertContained(root, path))) !== hash) throw new Error(`Changed installed file: ${path}`);
    }
    for (const skill of release.skills) {
        if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(skill.name)) throw new Error('Invalid installed skill name');
        const path = join(assertContained(root, skill.path), 'SKILL.md');
        if (!Object.hasOwn(release.fileDigests, relative(root, path)) || !existsSync(path)) throw new Error(`Missing entry: ${skill.name}`);
    }
    return release;
}

function layout(options) {
    const root = resolve(options.root ?? (options.project ? join(options.project, '.claude') : process.env.CLAUDE_CONFIG_DIR || join(homedir(), '.claude')));
    const agents = basename(root) === '.claude' ? join(dirname(root), '.agents') : root + '.agents';
    return { root, store: join(root, 'pstack'), skillHomes: [join(root, 'skills'), join(agents, 'skills')] };
}

function loadState(store) {
    const path = join(store, 'installed.json');
    return existsSync(path) ? readJson(path) : null;
}

export function verifyInstallation(options = {}) {
    const { store } = layout(options);
    const state = loadState(store);
    if (!state) throw new Error('Pstack is not installed');
    const release = verifyRelease(assertContained(join(store, 'releases'), state.release));
    for (const [path, target] of Object.entries(state.links)) {
        if (!lstatSync(path).isSymbolicLink() || realpathSync(path) !== realpathSync(target)) throw new Error(`Changed skill pointer: ${path}`);
    }
    return { ...state, skillCount: release.skills.length, verification: release.verification };
}

function publish(releaseRoot, release, homes, prior) {
    const uniqueHomes = [...new Set(homes.map(home => { mkdirSync(home, { recursive: true }); return realpathSync(home); }))];
    const pstackSkill = release.skills.find(skill => skill.component === 'pstack');
    const directSkills = release.skills.filter(skill => skill.component !== 'pstack');
    const links = Object.fromEntries(uniqueHomes.flatMap(home => [
        ...(pstackSkill ? [[join(home, 'pstack'), join(releaseRoot, dirname(pstackSkill.path))]] : []),
        ...directSkills.map(skill => [join(home, skill.name), join(releaseRoot, skill.path)]),
    ]));
    const paths = new Set([...Object.keys(prior?.links ?? {}), ...Object.keys(links)]);
    const before = new Map();
    for (const path of paths) {
        if (entryExists(path)) {
            if (!lstatSync(path).isSymbolicLink() || !prior?.links[path]
                || resolve(dirname(path), readlinkSync(path)) !== resolve(prior.links[path])) {
                throw new Error(`Keep existing unmanaged path: ${path}`);
            }
            before.set(path, readlinkSync(path));
        } else before.set(path, null);
    }
    const restore = () => {
        for (const [path, target] of before) {
            if (entryExists(path)) unlinkSync(path);
            if (target !== null) symlinkSync(target, path, process.platform === 'win32' ? 'junction' : 'dir');
        }
    };
    try {
        for (const path of paths) {
            if (entryExists(path)) unlinkSync(path);
            if (links[path]) symlinkSync(links[path], path, process.platform === 'win32' ? 'junction' : 'dir');
        }
    } catch (error) { restore(); throw error; }
    return { links, restore };
}

function liveLeases(store) {
    const root = join(store, 'sessions');
    if (!existsSync(root)) return false;
    return readdirSync(root).some(name => {
        const pid = Number(name);
        if (!Number.isSafeInteger(pid) || pid < 1) throw new Error('Invalid session lease');
        try { process.kill(pid, 0); return true; } catch (error) {
            if (error.code !== 'ESRCH') return true;
            unlinkSync(join(root, name));
            return false;
        }
    });
}

function readCentralLock(temporaryRoot) {
    const repository = join(temporaryRoot, 'record');
    mkdirSync(repository);
    runGit(['init', '--quiet'], repository);
    runGit(['fetch', '--quiet', '--depth=1', '--filter=blob:none', 'https://github.com/jl-cmd/claude-dev-env.git', 'main'], repository);
    return JSON.parse(runGit(['show', 'FETCH_HEAD:packages/claude-dev-env/scripts/pstack.lock.json'], repository));
}

export function installPstack(options = {}, dependencies = {}) {
    const { store, skillHomes } = layout(options);
    mkdirSync(store, { recursive: true });
    const lockDirectory = join(store, '.install-lock');
    mkdirSync(lockDirectory);
    let temporaryRoot;
    const finish = installation => {
        if (options.reserveSession) {
            const sessions = join(store, 'sessions');
            mkdirSync(sessions, { recursive: true });
            writeFileSync(join(sessions, String(process.pid)), installation.release);
        }
        return installation;
    };
    try {
        const prior = loadState(store);
        if ((options.offline || liveLeases(store)) && prior) return finish({ ...verifyInstallation(options), status: 'retained' });
        if (options.offline) throw new Error('Offline install needs an existing verified release');
        temporaryRoot = mkdtempSync(join(store, '.prepare-'));
        const now = dependencies.now ?? Date.now();
        const interval = options.intervalMs ?? 3600000;
        if (!Number.isFinite(interval) || interval < 0) throw new Error('Invalid update interval');
        const bundled = options.lock ?? prior?.lock ?? readJson(bundledLockPath);
        let lock = bundled;
        let checkedAt = prior?.checkedAt ?? 0;
        if (options.refresh && (options.force || now - checkedAt >= interval)) {
            lock = (dependencies.readCentralLock ?? readCentralLock)(temporaryRoot);
            checkedAt = now;
        } else if (options.refresh && prior?.lock) lock = prior.lock;
        validateLock(lock);
        const adapters = adapterFiles(options.packageRoot ?? packageRoot);
        const installerSource = readFileSync(fileURLToPath(import.meta.url), 'utf8').replace(/\r\n/g, '\n');
        const adapterDigest = digest(json(adapters) + installerSource);
        const id = `${lock.commit}-${adapterDigest.slice(0, 16)}`;
        const releaseRoot = join(store, 'releases', id);
        mkdirSync(dirname(releaseRoot), { recursive: true });
        if (!existsSync(releaseRoot)) {
            const checkout = join(temporaryRoot, 'source');
            (dependencies.fetchSource ?? fetchUpstream)(lock, checkout);
            const stage = join(temporaryRoot, 'release');
            prepareRelease(checkout, stage, releaseRoot, lock, adapters);
            verifyRelease(stage);
            renameSync(stage, releaseRoot);
        }
        const release = verifyRelease(releaseRoot);
        const publication = publish(releaseRoot, release, skillHomes, prior);
        const state = { release: id, commit: lock.commit, adapterVersion: lock.adapterVersion, adapterDigest, checkedAt, lock, links: publication.links };
        try {
            writeFileSync(join(store, 'installed.next.json'), json(state));
            renameSync(join(store, 'installed.next.json'), join(store, 'installed.json'));
        } catch (error) { publication.restore(); throw error; }
        return finish({ ...verifyInstallation(options), status: prior?.release === id ? 'unchanged' : 'installed' });
    } catch (error) {
        if (!options.strict) {
            try { return finish({ ...verifyInstallation(options), status: 'retained', warning: error.message }); } catch { }
        }
        throw error;
    } finally {
        if (temporaryRoot) rmSync(temporaryRoot, { recursive: true, force: true });
        rmSync(lockDirectory, { recursive: true, force: true });
    }
}

function parseArguments(args) {
    const options = {};
    const tailIndex = args.indexOf('--');
    const tokens = tailIndex < 0 ? args : args.slice(0, tailIndex);
    const forwarded = tailIndex < 0 ? [] : args.slice(tailIndex + 1);
    for (let index = 0; index < tokens.length; index++) {
        const flag = tokens[index];
        if (['--offline', '--refresh', '--force', '--strict'].includes(flag)) options[flag.slice(2)] = true;
        else if (['--root', '--project', '--host', '--lock', '--interval-ms'].includes(flag)) {
            const argument = tokens[++index];
            if (!argument || argument.startsWith('--')) throw new Error(`${flag} requires a value`);
            if (flag === '--lock') options.lock = readJson(resolve(argument));
            else if (flag === '--interval-ms') options.intervalMs = Number(argument);
            else options[flag.slice(2)] = argument;
        } else throw new Error(`Unknown option: ${flag}`);
    }
    if (options.host && !hosts.includes(options.host)) throw new Error('Host must be claude, codex, or cursor');
    if (options.root && options.project) throw new Error('Choose --root or --project');
    return { options, forwarded };
}

export function main(args = process.argv.slice(2)) {
    try {
        const [command = 'help', ...rest] = args;
        if (['help', '--help', '-h'].includes(command)) {
            console.log('Usage: cde-pstack <install|verify|launch|hook> [--root PATH|--project PATH] [--refresh] [--offline] [--strict] [--lock PATH] [--host claude|codex|cursor] [-- agent arguments]');
            return 0;
        }
        const { options, forwarded } = parseArguments(rest);
        if (!['install', 'verify', 'launch', 'hook'].includes(command)) throw new Error(`Unknown command: ${command}`);
        let hookInput;
        if (command === 'hook') {
            hookInput = JSON.parse(readFileSync(0, 'utf8') || '{}');
            options.project ??= process.env.CLAUDE_PROJECT_DIR || process.cwd();
            options.offline = hookInput.source !== 'startup';
            options.refresh = !options.offline && loadState(layout(options).store) !== null;
        }
        if (command === 'launch' && !options.host) throw new Error('launch requires --host');
        if (command === 'launch') { options.refresh = !options.offline && !options.lock; options.reserveSession = true; }
        const installation = command === 'verify' ? verifyInstallation(options) : installPstack(options);
        if (installation.warning) console.error(`Pstack update failed; keeping ${installation.commit}: ${installation.warning}`);
        if (command === 'hook') {
            const { store } = layout(options);
            const release = join(store, 'releases', installation.release);
            console.log(json({ hookSpecificOutput: { hookEventName: 'SessionStart', additionalContext: `Pstack ${installation.commit} is installed. Use the immutable release recorded by session-continuity or the loaded skill entry for this session. Read common.md and host-claude.md in that release's compat directory. New sessions can use the installed inventory at ${join(release, 'release.json')}. ${installation.warning ?? ''}` } }));
        } else if (command === 'launch') {
            const sessions = join(layout(options).store, 'sessions');
            const lease = join(sessions, String(process.pid));
            try {
                const child = spawnSync(options.host, forwarded, { stdio: 'inherit', shell: false, env: { ...process.env, CDE_PSTACK_RELEASE: join(layout(options).store, 'releases', installation.release) } });
                if (child.error) throw child.error;
                return child.status ?? 1;
            } finally { unlinkSync(lease); }
        } else console.log(json(installation));
        return 0;
    } catch (error) { console.error(`Pstack: ${error.message}`); return 1; }
}

if (process.argv[1] && realpathSync(process.argv[1]) === fileURLToPath(import.meta.url)) process.exitCode = main();
