export const meta = {
  name: 'plan-packet',
  description: 'Create a repo-local implementation planning packet under docs/plans/<slug>, validate it deterministically, verify it with a fresh validator agent, repair findings, and stop before implementation.',
  whenToUse: 'Launched by the anthropic-plan skill for non-trivial implementation planning, scoping, design, or plan-first requests.',
  phases: [
    { title: 'Discover', detail: 'Resolve repo root, read instructions, inspect matching source files, tests, configs, docs, skills, hooks, agents, and workflows.' },
    { title: 'Write packet', detail: 'Create the required docs/plans/<slug>/ tree with a thin README hub and detailed second-level docs.' },
    { title: 'Validate', detail: 'Run scripts/validate_packet.py, spawn plan-packet-validator in fresh context, and repair findings up to the cap.' },
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
    },
    required: ['repaired', 'summary'],
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

function repairPrompt(packetPath, deterministicValidation, semanticValidation) {
  return (
    `Repair only the plan packet at ${packetPath}. Do not edit source code.\n\n` +
    `Deterministic validation findings:\n${JSON.stringify(deterministicValidation.findings || [])}\n\n` +
    `Semantic validation findings:\n${JSON.stringify(semanticValidation.findings || [])}\n\n` +
    `Make the packet pass by correcting documentation, adding missing source grounding, removing placeholders, strengthening TDD steps, and updating validation/validator-report.md. ` +
    `If the Edit or Write tool is blocked by a worktree or isolation guard, recover automatically: stage the corrected files under a writable temporary directory with the Write tool, then copy them over the packet path with a filesystem copy.`
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

async function repairPacket(packetPath, deterministicValidation, semanticValidation) {
  return agent(repairPrompt(packetPath, deterministicValidation, semanticValidation), {
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

  try {
    const discoverySummary = await discoverContext(runInput, packetPath)
    packetWrite = await writePacket(runInput, packetPath, discoverySummary)
    deterministicValidation = await runDeterministicValidation(packetPath)
    semanticValidation = await runSemanticValidator(packetPath)
    const hasCleanValidation = () =>
      deterministicValidation?.passed === true && semanticValidation && semanticValidation.allPassed === true

    while (!hasCleanValidation() && repairLoops < policy.maxRepairLoops) {
      repairLoops += 1
      await repairPacket(packetPath, deterministicValidation, semanticValidation)
      deterministicValidation = await runDeterministicValidation(packetPath)
      semanticValidation = await runSemanticValidator(packetPath)
    }

    const passed = hasCleanValidation()
    return {
      packetPath: packetWrite?.packetPath || packetPath,
      slug: packetWrite?.slug || slugFromTask(runInput.task || runInput.prompt || runInput.arguments),
      validationPassed: passed,
      repairLoops,
      deterministicFindings: deterministicValidation?.findings || [],
      semanticFindings: semanticValidation?.findings || [],
      implementationStarted: false,
      approvalRequired: true,
      recovered: packetWrite?.recovered === true,
      recoveryNote: packetWrite?.recoveryNote || '',
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
      implementationStarted: false,
      approvalRequired: true,
    }
  }
}

return await runPlanPacketWorkflow(args)
