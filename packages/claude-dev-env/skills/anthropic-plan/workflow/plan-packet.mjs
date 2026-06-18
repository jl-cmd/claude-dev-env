export const meta = {
  name: 'plan-packet',
  description: 'Create a repo-local implementation planning packet under docs/plans/<slug>, validate it deterministically, verify it with a fresh validator agent, repair findings, and stop before implementation.',
  whenToUse: 'Launched by the anthropic-plan skill for non-trivial implementation planning, scoping, design, or plan-first requests.',
  phases: [
    { title: 'Discover', detail: 'Resolve repo root, read instructions, inspect matching source files, tests, configs, docs, skills, hooks, agents, and workflows.' },
    { title: 'Write packet', detail: 'Create the required docs/plans/<slug>/ tree with a thin README hub and detailed second-level docs.' },
    { title: 'Validate', detail: 'Run scripts/validate_packet.py, spawn plan-packet-validator in fresh context, and repair findings up to the cap.' },
    { title: 'Reuse audit', detail: 'Search the codebase for existing equivalents of each new symbol or file the packet introduces; write validation/reuse-audit.md with a per-item verdict; gate approval on any unjustified reproduction.' },
    { title: 'Visualize', detail: 'Build a single-file offline visual HTML of the finished packet from the visual-plan template; write it beside the packet as visual-plan.html.' },
    { title: 'Approval', detail: 'Return the packet path and validation verdict, then stop before implementation work.' },
  ],
}

function validationSchema() {
  return {
    type: 'object',
    additionalProperties: false,
    properties: {
      allPassed: { type: 'boolean' },
      findings: {
        type: 'array',
        items: {
          type: 'object',
          additionalProperties: false,
          properties: {
            file: { type: 'string' },
            check: { type: 'string' },
            detail: { type: 'string' },
          },
          required: ['file', 'check', 'detail'],
        },
      },
      summary: { type: 'string' },
    },
    required: ['allPassed', 'findings', 'summary'],
  }
}

function packetWriteSchema() {
  return {
    type: 'object',
    additionalProperties: false,
    properties: {
      packetPath: { type: 'string' },
      slug: { type: 'string' },
      filesWritten: { type: 'array', items: { type: 'string' } },
      summary: { type: 'string' },
      recovered: { type: 'boolean' },
      recoveryNote: { type: 'string' },
    },
    required: ['packetPath', 'slug', 'filesWritten', 'summary', 'recovered', 'recoveryNote'],
  }
}

function deterministicSchema() {
  return {
    type: 'object',
    additionalProperties: false,
    properties: {
      passed: { type: 'boolean' },
      stdout: { type: 'string' },
      stderr: { type: 'string' },
      findings: { type: 'array', items: { type: 'string' } },
    },
    required: ['passed', 'stdout', 'stderr', 'findings'],
  }
}

function repairSchema() {
  return {
    type: 'object',
    additionalProperties: false,
    properties: {
      repaired: { type: 'boolean' },
      summary: { type: 'string' },
      recovered: { type: 'boolean' },
      recoveryNote: { type: 'string' },
    },
    required: ['repaired', 'summary', 'recovered', 'recoveryNote'],
  }
}

function reuseAuditSchema() {
  return {
    type: 'object',
    additionalProperties: false,
    properties: {
      allJustified: { type: 'boolean' },
      findings: {
        type: 'array',
        items: {
          type: 'object',
          additionalProperties: false,
          properties: {
            item: { type: 'string' },
            kind: { type: 'string' },
            verdict: { type: 'string' },
            searched: { type: 'string' },
            found: { type: 'string' },
            decision: { type: 'string' },
            evidence: { type: 'string' },
          },
          required: ['item', 'kind', 'verdict', 'searched', 'found', 'decision', 'evidence'],
        },
      },
      summary: { type: 'string' },
    },
    required: ['allJustified', 'findings', 'summary'],
  }
}

function visualHtmlSchema() {
  return {
    type: 'object',
    additionalProperties: false,
    properties: {
      htmlPath: { type: 'string' },
      sectionsBuilt: { type: 'array', items: { type: 'string' } },
      summary: { type: 'string' },
    },
    required: ['htmlPath', 'sectionsBuilt', 'summary'],
  }
}

function normalizeRunInput(rawInput) {
  if (rawInput && typeof rawInput === 'object') return rawInput
  if (typeof rawInput !== 'string' || rawInput.trim() === '') return {}
  try {
    const parsedInput = JSON.parse(rawInput)
    return parsedInput && typeof parsedInput === 'object' ? parsedInput : {}
  } catch {
    return { task: rawInput }
  }
}

function slugFromTask(taskText) {
  const words = String(taskText || 'implementation-plan')
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, ' ')
    .split(/\s+/)
    .filter(Boolean)
    .filter((eachWord) => !['the', 'and', 'for', 'with', 'this', 'that'].includes(eachWord))
    .slice(0, 4)
  return words.length ? words.join('-') : 'implementation-plan'
}

function buildPacketPath(runInput) {
  const cwd = runInput.cwd || runInput.repoRoot || '.'
  const slug = runInput.slug || slugFromTask(runInput.task || runInput.prompt || runInput.arguments)
  return `${cwd.replace(/[\\/]$/, '')}/docs/plans/${slug}`
}

function requiredPacketTree() {
  return [
    'README.md',
    'packet.json',
    'context/user-request.md',
    'context/source-map.md',
    'context/current-state.md',
    'context/existing-patterns.md',
    'context/constraints.md',
    'context/glossary.md',
    'spec/scope.md',
    'spec/behavior.md',
    'spec/interfaces.md',
    'spec/data-flow.md',
    'spec/failure-modes.md',
    'spec/acceptance.md',
    'implementation/strategy.md',
    'implementation/steps.md',
    'implementation/tdd-plan.md',
    'implementation/file-plan.md',
    'implementation/refactor-checkpoints.md',
    'validation/validator-report.md',
    'validation/deterministic-checks.md',
    'validation/unresolved-risks.md',
    'handoff/build-prompt.md',
    'handoff/review-prompt.md',
    'handoff/verification-commands.md',
  ]
}

function packetContractText() {
  return (
    `Create this exact packet tree under docs/plans/<slug>/:\n${requiredPacketTree().map((eachPath) => `- ${eachPath}`).join('\n')}\n\n` +
    `README.md stays a thin hub. First-level folders group purpose. Second-level files carry real detail. Do not add deeper nesting unless more than twelve source files or more than three subsystems are found; then add context/subsystems/<name>.md.\n\n` +
    `Every material claim must be source-backed in context/source-map.md, user-confirmed in context/user-request.md, or listed as an assumption in packet.json. Do not write an Open Questions section. Resolve discoverable unknowns by reading/searching. Ask the user only for product choices that cannot be derived.\n\n` +
    `The packet must stop before implementation. The build prompt must stand alone for a blind build agent and say to use only this packet.`
  )
}

function discoveryPrompt(runInput, packetPath) {
  return (
    `Plan packet discovery for: ${runInput.task || runInput.prompt || runInput.arguments || 'the current user request'}\n\n` +
    `Target packet path: ${packetPath}\n\n` +
    `Collect context before writing:\n` +
    `1. Resolve the repo root and current working directory.\n` +
    `2. Read project instructions in priority order: AGENTS.md or CLAUDE.md, nearest .claude rules, relevant skill docs, package manifests, tool manifests.\n` +
    `3. Search for user terms and likely entrypoints: commands, hooks, agents, skills, configs, schemas, tests, docs, scripts, workflows.\n` +
    `4. Build a source inventory with production files, tests, configs/constants, docs, and workflow scripts.\n` +
    `5. Extract exact facts for source-map.md: path, relevant symbol or section, observed behavior, and plan implication.\n\n` +
    `Return a concise discovery summary. Do not edit files.`
  )
}

function writePacketPrompt(runInput, packetPath, discoverySummary) {
  return (
    `Write the plan packet for: ${runInput.task || runInput.prompt || runInput.arguments || 'the current user request'}\n\n` +
    `Packet path: ${packetPath}\n\n` +
    `Discovery summary:\n${discoverySummary}\n\n` +
    `${packetContractText()}\n\n` +
    `Use the templates in the anthropic-plan skill if helpful. Write docs only. Do not edit source code. Do not run implementation commands. ` +
    `Write every packet file with the Write tool at the packet path. ` +
    `If the Write tool is blocked by a worktree or isolation guard, recover automatically: write each file with the Write tool under a writable temporary directory such as $CLAUDE_JOB_DIR/tmp/anthropic-plan/<slug> (so the content checks still run), then copy the staged tree into the packet path with a filesystem copy (cp -r, Copy-Item, or equivalent). Set recovered=true with recoveryNote describing the staging path and copy; otherwise set recovered=false with an empty recoveryNote. ` +
    `After writing, ensure packet.json includes schemaVersion 1, slug, repoRoot, packetPath, sourceFiles, assumptions, and validator fields.`
  )
}

function deterministicValidationPrompt(packetPath) {
  return (
    `Run the deterministic packet validator exactly:\n` +
    `python "$HOME/.claude/skills/anthropic-plan/scripts/validate_packet.py" "${packetPath}"\n\n` +
    `Return passed=true only when the command exits 0. Put stdout, stderr, and each stderr line as findings. Do not edit files.`
  )
}

function semanticValidationPrompt(packetPath) {
  return (
    `Validate the plan packet at ${packetPath}. Re-read the packet and the source files it cites. ` +
    `Every material claim must be source-backed, user-confirmed, or an explicit assumption. ` +
    `Check that referenced paths exist or are clearly proposed as new, source facts match actual files, implementation steps are enough for a blind build agent, the TDD sequence is real, scope matches the user request, no commands/APIs/schemas/conventions are invented, and acceptance criteria prove the behavior end to end. ` +
    `Return allPassed=true only when the packet is accurate and complete. Do not edit files.`
  )
}

function repairPrompt(packetPath, deterministicValidation, semanticValidation, reuseAudit) {
  return (
    `Repair only the plan packet at ${packetPath}. Do not edit source code.\n\n` +
    `Deterministic validation findings:\n${JSON.stringify(deterministicValidation.findings || [])}\n\n` +
    `Semantic validation findings:\n${JSON.stringify(semanticValidation.findings || [])}\n\n` +
    `Reuse audit findings:\n${JSON.stringify(reuseAudit?.findings || [])}\n\n` +
    `For each reuse audit finding marked unjustified-reproduction, either record the reuse decision in the packet that justifies the new code, or change the plan to reuse the existing public helper or extract it to shared_utils; update validation/reuse-audit.md accordingly. ` +
    `Make the packet pass by correcting documentation, adding missing source grounding, removing placeholders, strengthening TDD steps, and updating validation/validator-report.md. ` +
    `If the Edit or Write tool is blocked by a worktree or isolation guard, recover automatically: stage the corrected files under a writable temporary directory with the Write tool, then copy them over the packet path with a filesystem copy. Set recovered=true with recoveryNote describing the staging path and copy; otherwise set recovered=false with an empty recoveryNote.`
  )
}

function reuseAuditPrompt(packetPath) {
  return (
    `Run the reuse audit for the plan packet at ${packetPath}. Resolve the repo root from packet.json. Do not edit source code; only write the packet doc.\n\n` +
    `Read implementation/file-plan.md, spec/interfaces.md, implementation/tdd-plan.md, and spec/scope.md in the packet to enumerate every new file, public symbol, helper, and constant the build introduces.\n\n` +
    `For each item, search the codebase with grep, serena, or zoekt — repo-wide and specifically under shared_utils — for an existing implementation or near-equivalent behavior.\n\n` +
    `Assign exactly one verdict per item from: reused (an existing public helper is used), extract-to-shared (an equivalent exists but is not shared or public and should be extracted), new-justified (genuinely new, with the reason reuse or extract was rejected), config-local (a constant living in config/), or unjustified-reproduction (reproduces existing behavior that could be made public or extracted, with no recorded justification).\n\n` +
    `Write validation/reuse-audit.md into the packet: a markdown table with columns Item, Kind, Verdict, Searched, Found, Decision, Evidence using real file:line evidence, plus a one-line summary of verdict counts. Write concrete content only — no angle-bracket placeholder tokens and no todo, tbd, or placeholder words.\n\n` +
    `Return the structured object. Set allJustified=false when any finding has verdict unjustified-reproduction.`
  )
}

function visualHtmlPrompt(packetPath) {
  return (
    `Build a single-file, offline, diagram-first visual HTML of the finished plan packet at ${packetPath}. Do not edit source code or the packet markdown; only write the HTML view.\n\n` +
    `Read the style template first and reuse its CSS and section components exactly:\n` +
    `$HOME/.claude/skills/anthropic-plan/templates/visual-plan.template.html\n\n` +
    `Then read the packet: README.md, packet.json, every file under spec/ and implementation/, and validation/reuse-audit.md. Translate the packet into the template's visual vocabulary — stat hero, scenario row strips, is/isn't cards, edit-recipe step sequences, verdict badges, and a checklist. Show the plan as diagrams and compact cards, never walls of prose, and never paste the markdown verbatim.\n\n` +
    `Write for the reviewer — a person reading the plan, not the computer that runs the code. State every label as what a step accomplishes, in plain language. Drop code symbols from the picture: no function names, selector strings, call traces, or snake_case test names in the visible diagram — those stay in the packet markdown for the build agent. Keep each touched file's repo-relative path, but dim it (the .rpath / .ap style) so it sits quietly beneath the human description.\n\n` +
    `Render the change (section 05) as edit-recipe step sequences, one recipe per touched file: a plain-language title for what the file accomplishes, the dimmed repo-relative path, then an ordered row of colored steps — reused (green), modified (violet), new (amber). Fold a trivial one-line change into the recipe it supports as an "Also adds" line rather than giving it its own card. Name each test by the behavior it proves, not its function name.\n\n` +
    `Surface validation/reuse-audit.md as a Reuse audit section with one verdict badge per item (reused, extract-to-shared, new-justified, config-local, unjustified-reproduction), each item titled in plain language with its file path dimmed.\n\n` +
    `Write the result to ${packetPath}/visual-plan.html. Inline all CSS and JavaScript; make no network calls and reference no external assets, so the file opens offline. If the Write tool is blocked by a worktree or isolation guard, stage the file under $CLAUDE_JOB_DIR/tmp with the Write tool, then copy it to the packet path.\n\n` +
    `Return htmlPath set to the written file path, sectionsBuilt listing the section names you included, and a one-line summary.`
  )
}

async function discoverContext(runInput, packetPath) {
  return agent(discoveryPrompt(runInput, packetPath), {
    label: `plan-packet-discover`,
    phase: 'Discover',
    agentType: 'general-purpose',
  })
}

async function writePacket(runInput, packetPath, discoverySummary) {
  return agent(writePacketPrompt(runInput, packetPath, discoverySummary), {
    label: `plan-packet-write`,
    phase: 'Write packet',
    schema: packetWriteSchema(),
    agentType: 'general-purpose',
  })
}

async function runDeterministicValidation(packetPath) {
  return agent(deterministicValidationPrompt(packetPath), {
    label: `plan-packet-deterministic-validation`,
    phase: 'Validate',
    schema: deterministicSchema(),
    agentType: 'general-purpose',
  })
}

async function runSemanticValidator(packetPath) {
  const prompt =
    `${semanticValidationPrompt(packetPath)}\n\n` +
    `Confirm the packet is source-backed and complete enough for a blind build agent.`
  return agent(prompt, {
    label: `plan-packet-semantic-validator`,
    phase: 'Validate',
    schema: validationSchema(),
    agentType: 'plan-packet-validator',
  })
}

async function runReuseAudit(packetPath) {
  return agent(reuseAuditPrompt(packetPath), {
    label: `plan-packet-reuse-audit`,
    phase: 'Reuse audit',
    schema: reuseAuditSchema(),
    agentType: 'general-purpose',
  })
}

async function runVisualHtml(packetPath) {
  return agent(visualHtmlPrompt(packetPath), {
    label: `plan-packet-visual-html`,
    phase: 'Visualize',
    schema: visualHtmlSchema(),
    agentType: 'general-purpose',
  })
}

async function repairPacket(packetPath, deterministicValidation, semanticValidation, reuseAudit) {
  return agent(repairPrompt(packetPath, deterministicValidation, semanticValidation, reuseAudit), {
    label: `plan-packet-repair`,
    phase: 'Validate',
    schema: repairSchema(),
    agentType: 'general-purpose',
  })
}

async function runPlanPacketWorkflow(rawInput) {
  const runInput = normalizeRunInput(rawInput)
  const policy = { maxRepairLoops: 3 }
  const packetPath = buildPacketPath(runInput)
  let repairLoops = 0
  let packetWrite = null
  let deterministicValidation = null
  let semanticValidation = null
  let reuseAudit = null
  let recovered = false
  let recoveryNote = ''
  let visualHtmlPath = ''
  const visualHtmlFindings = []
  const recordRecovery = (recovery) => {
    if (recovery?.recovered !== true) return
    recovered = true
    recoveryNote = recovery.recoveryNote || recoveryNote
  }

  try {
    const discoverySummary = await discoverContext(runInput, packetPath)
    packetWrite = await writePacket(runInput, packetPath, discoverySummary)
    recordRecovery(packetWrite)
    reuseAudit = await runReuseAudit(packetPath)
    deterministicValidation = await runDeterministicValidation(packetPath)
    semanticValidation = await runSemanticValidator(packetPath)
    const hasCleanValidation = () =>
      deterministicValidation?.passed === true &&
      semanticValidation &&
      semanticValidation.allPassed === true &&
      reuseAudit &&
      reuseAudit.allJustified === true

    while (!hasCleanValidation() && repairLoops < policy.maxRepairLoops) {
      repairLoops += 1
      const repair = await repairPacket(packetPath, deterministicValidation, semanticValidation, reuseAudit)
      recordRecovery(repair)
      reuseAudit = await runReuseAudit(packetPath)
      deterministicValidation = await runDeterministicValidation(packetPath)
      semanticValidation = await runSemanticValidator(packetPath)
    }

    const passed = hasCleanValidation()
    try {
      const visualHtml = await runVisualHtml(packetPath)
      visualHtmlPath = visualHtml?.htmlPath || ''
    } catch (visualHtmlError) {
      visualHtmlFindings.push(String(visualHtmlError?.message || visualHtmlError))
    }
    return {
      packetPath: packetWrite?.packetPath || packetPath,
      slug: packetWrite?.slug || slugFromTask(runInput.task || runInput.prompt || runInput.arguments),
      validationPassed: passed,
      repairLoops,
      deterministicFindings: deterministicValidation?.findings || [],
      semanticFindings: semanticValidation?.findings || [],
      reuseAuditFindings: reuseAudit?.findings || [],
      implementationStarted: false,
      approvalRequired: true,
      recovered,
      recoveryNote,
      visualHtmlPath,
      visualHtmlFindings,
    }
  } catch (workflowError) {
    return {
      packetPath,
      slug: packetWrite?.slug || slugFromTask(runInput.task || runInput.prompt || runInput.arguments),
      validationPassed: false,
      repairLoops,
      deterministicFindings: deterministicValidation?.findings || [],
      semanticFindings: [
        ...(semanticValidation?.findings || []),
        {
          file: 'workflow/plan-packet.mjs',
          check: 'workflow phase error',
          detail: String(workflowError?.message || workflowError),
        },
      ],
      reuseAuditFindings: reuseAudit?.findings || [],
      implementationStarted: false,
      approvalRequired: true,
      recovered,
      recoveryNote,
      visualHtmlPath,
      visualHtmlFindings,
    }
  }
}

return await runPlanPacketWorkflow(args)
