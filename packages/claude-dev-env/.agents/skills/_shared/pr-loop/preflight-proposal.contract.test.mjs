import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const THIS_DIRECTORY = dirname(fileURLToPath(import.meta.url))
const canonicalContractSource = readFileSync(
  resolve(THIS_DIRECTORY, '../../../../_shared/pr-loop/preflight-proposal.md'),
  'utf8',
)
const sharedSkillSource = readFileSync(
  resolve(THIS_DIRECTORY, '../../pr-shared-extraction/SKILL.md'),
  'utf8',
)
const capabilitySkillSource = readFileSync(
  resolve(THIS_DIRECTORY, '../../pr-name-by-capability/SKILL.md'),
  'utf8',
)
const capabilityTaskSeedsSource = readFileSync(
  resolve(THIS_DIRECTORY, '../../pr-name-by-capability/reference/task-seeds.md'),
  'utf8',
)

const allSkillContracts = [
  {
    name: 'shared extraction audit',
    skillSource: sharedSkillSource,
    invocationPattern: /pr-shared-extraction preflight-proposal/,
    classificationPattern: /priority and target/,
    expectedDefaultBehavior: 'applies the prioritized fix band by default',
  },
  {
    name: 'name by capability audit',
    skillSource: capabilitySkillSource,
    invocationPattern: /pr-name-by-capability preflight-proposal/,
    classificationPattern: /violation or OK-driver classification/,
    expectedDefaultBehavior: 'applies the suggested rename direction by default',
  },
]

function assertProposalAdapter(skillContract) {
  const preflightRoutingOffset = skillContract.skillSource.indexOf('`preflight-proposal`')
  const reportOnlyRoutingOffset = skillContract.skillSource.indexOf('`audit-only`')

  assert.ok(preflightRoutingOffset >= 0, `${skillContract.name} selects proposal mode`)
  assert.ok(preflightRoutingOffset < reportOnlyRoutingOffset, `${skillContract.name} routes proposal mode first`)
  assert.match(skillContract.skillSource, skillContract.invocationPattern)
  assert.match(skillContract.skillSource, skillContract.classificationPattern)
  assert.match(skillContract.skillSource, new RegExp(skillContract.expectedDefaultBehavior))
}

function assertTaskRoutingAndNormalMode() {
  assert.match(sharedSkillSource, /Register this checklist with `update_plan`/)
  assert.match(capabilitySkillSource, /Register every bullet from `reference\/task-seeds\.md` with `update_plan`/)
  assert.match(capabilityTaskSeedsSource, /Register each item with `update_plan`/)
  assert.doesNotMatch(sharedSkillSource, /TodoWrite|TaskCreate/)
  assert.doesNotMatch(capabilitySkillSource, /TodoWrite|TaskCreate/)
  assert.doesNotMatch(capabilityTaskSeedsSource, /TodoWrite|TaskCreate/)
  assert.match(sharedSkillSource, /audit-only` is report-only/)
  assert.match(capabilitySkillSource, /audit-only` is report-only/)
}

function assertSharedProposalContract(contractSource) {
  assert.match(contractSource, /caller-supplied isolated worktree/)
  assert.match(contractSource, /resolved PR number/)
  assert.match(contractSource, /immutable base SHA/)
  assert.match(contractSource, /immutable head SHA/)
  assert.match(contractSource, /exact `base_sha\.\.\.head_sha` range/)
  assert.match(contractSource, /require exact equality with the head SHA/)
  assert.match(contractSource, /immutable proposal identity/)
  assert.match(contractSource, /deterministic diff hash/)
  assert.match(contractSource, /changed paths/)
  assert.match(contractSource, /exact tests and outcomes/)
  assert.match(contractSource, /selected-candidate-ready proposal evidence/)
  assert.match(contractSource, /selected or dispositioned proposal collection/)
  assert.match(contractSource, /Reapplication uses exactly the selected records/)
}

test('audit modes retain their normal routing behavior', () => {
  assertTaskRoutingAndNormalMode()
})

test('one shared contract defines proposal evidence for both audit skills', () => {
  for (const eachSkillContract of allSkillContracts) {
    assertProposalAdapter(eachSkillContract)
  }
  assertSharedProposalContract(canonicalContractSource)
})
