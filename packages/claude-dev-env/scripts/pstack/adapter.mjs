import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';

export function putFile(path, text) {
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, text);
}

export function skillNames(pluginRoot) {
    return readdirSync(join(pluginRoot, 'skills'), { withFileTypes: true })
        .filter(entry => entry.isDirectory())
        .filter(entry => existsSync(join(pluginRoot, 'skills', entry.name, 'SKILL.md')))
        .map(entry => entry.name).sort();
}

function metadata(source, name) {
    if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(name)) throw new Error(`Invalid skill name: ${name}`);
    const match = source.match(/^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/);
    if (!match || !/^description:\s*\S/m.test(match[1])) {
        throw new Error(`Missing skill frontmatter or description: ${name}`);
    }
    const lines = match[1].split(/\r?\n/);
    const start = lines.findIndex(line => line.startsWith('description:'));
    let end = start + 1;
    while (end < lines.length && (/^[ \t]/.test(lines[end]) || lines[end] === '')) end += 1;
    const flags = lines.filter(line => /^(disable-model-invocation|user-invocable):[ \t]*(true|false)[ \t]*$/.test(line));
    return [`name: ${name}`, lines.slice(start, end).join('\n').trimEnd(), ...flags].join('\n');
}

export function buildPublication(stage, release, packageRoot) {
    const skills = [];
    const names = new Set();
    for (const plugin of ['pstack', 'cursor-team-kit']) {
        const root = join(stage, 'upstream', plugin);
        const paths = [];
        for (const name of skillNames(root)) {
            if (names.has(name)) throw new Error(`Conflicting upstream skill: ${name}`);
            names.add(name);
            const source = readFileSync(join(root, 'skills', name, 'SKILL.md'), 'utf8');
            const sourcePath = join(release, 'upstream', plugin, 'skills', name, 'SKILL.md');
            const text = `---\n${metadata(source, name)}\n---\n\n`
                + `PSTACK_RELEASE: ${release}\n\n`
                + `Read ${JSON.stringify(join(release, 'compatibility.md'))} and `
                + `${JSON.stringify(join(release, 'rules', 'pstack-models.md'))} first.\n`
                + `Then read and follow ${JSON.stringify(sourcePath)} in full. Resolve relative `
                + `paths from that upstream file. Carry PSTACK_RELEASE and these compatibility `
                + `instructions into every child prompt.\n`;
            putFile(join(stage, 'published', plugin, name, 'SKILL.md'), text);
            paths.push(`./${name}`);
            skills.push({ plugin, name });
        }
        if (plugin === 'pstack') {
            if (names.has('create-skill')) throw new Error('Upstream now provides create-skill; review its adapter');
            putFile(join(stage, 'published', plugin, 'create-skill', 'SKILL.md'),
                '---\nname: create-skill\ndescription: Author portable agent skills with verified local references.\n---\n\n'
                + 'Name the outcome and invocation. Read one working skill on the active host. '
                + 'Create a lowercase hyphenated folder under .claude/skills with SKILL.md, '
                + 'name and description frontmatter, clear steps and completion checks. '
                + 'Keep scripts and references beside it. Link it into .agents/skills for Codex. '
                + 'Resolve every referenced file and run every supplied test. Invoke the skill '
                + 'in its intended host and show the result. Record a missing live-host test explicitly.\n');
            paths.push('./create-skill');
            names.add('create-skill');
            skills.push({ plugin, name: 'create-skill' });
        }
        const manifestPath = join(root, '.cursor-plugin', 'plugin.json');
        const upstream = existsSync(manifestPath) ? JSON.parse(readFileSync(manifestPath, 'utf8')) : {};
        putFile(join(stage, 'published', plugin, '.claude-plugin', 'plugin.json'), JSON.stringify({
            name: plugin,
            version: upstream.version ?? '0.0.0',
            description: upstream.description ?? `${plugin} host-compatible workflows`,
            skills: paths,
        }, null, 2) + '\n');
    }
    for (const [plugin, required] of [
        ['pstack', ['poteto-mode']],
        ['cursor-team-kit', ['deslop', 'control-cli', 'control-ui']],
    ]) {
        for (const name of required) {
            if (!skills.some(skill => skill.plugin === plugin && skill.name === name)) {
                throw new Error(`Missing dependency: ${plugin}:${name}`);
            }
        }
    }
    for (const path of ['playbooks/feature.md', 'playbooks/bug-fix.md']) {
        if (!existsSync(join(stage, 'upstream', 'pstack', 'skills', 'poteto-mode', path))) {
            throw new Error(`Missing Poteto Mode reference: ${path}`);
        }
    }
    for (const name of ['poteto-agent', 'comment-sicko']) {
        if (!existsSync(join(stage, 'upstream', 'pstack', 'agents', `${name}.md`))) {
            throw new Error(`Missing agent definition: ${name}`);
        }
    }
    for (const name of ['pstack-models.md', 'pstack-host-mapping.md']) {
        putFile(join(stage, 'rules', name), readFileSync(join(packageRoot, 'rules', name)));
    }
    putFile(join(stage, 'scripts', 'select_pstack_models.mjs'),
        readFileSync(join(packageRoot, 'scripts', 'select_pstack_models.mjs')));
    putFile(join(stage, 'compatibility.md'),
        readFileSync(join(packageRoot, 'scripts', 'pstack', 'compatibility.md')));
    return skills;
}

export function nativeAgentFiles(root) {
    const files = [];
    for (const name of ['poteto-agent', 'comment-sicko']) {
        const instructions = `The parent supplies PSTACK_RELEASE, an absolute immutable release directory. `
            + `If absent, read ${JSON.stringify(join(root, '.claude', 'pstack', 'state.json'))} `
            + `and resolve its generation under the sibling releases directory. `
            + `Read compatibility.md and rules/pstack-models.md in that release, then `
            + `upstream/pstack/agents/${name}.md. Resolve relative paths from the upstream file. `
            + `Carry the same release into each child prompt. Return complete findings, checks and evidence `
            + `in the final message. Use only the tools and models available in this session.`;
        const description = `Pstack ${name} with active-host tools and model policy.`;
        for (const host of ['claude', 'cursor']) {
            files.push({
                path: join(root, `.${host}`, 'agents', `pstack-${name}.md`),
                content: `---\nname: ${name}\ndescription: ${description}\n---\n\n${instructions}\n`,
            });
        }
        files.push({
            path: join(root, '.codex', 'agents', `pstack-${name}.toml`),
            content: `name = ${JSON.stringify(name)}\ndescription = ${JSON.stringify(description)}\n`
                + `developer_instructions = ${JSON.stringify(instructions)}\n`,
        });
    }
    return files;
}
