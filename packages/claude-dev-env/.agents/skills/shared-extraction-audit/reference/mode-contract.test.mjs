import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const sharedSkillSource = readFileSync(new URL('../SKILL.md', import.meta.url), 'utf8')
const sharedContractSource = readFileSync(new URL('./preflight-proposal.md', import.meta.url), 'utf8')
const capabilitySkillSource = readFileSync(
  new URL('../../name-by-capability-audit/SKILL.md', import.meta.url),
  'utf8',
)
const capabilityContractSource = readFileSync(
  new URL('../../name-by-capability-audit/reference/preflight-proposal.md', import.meta.url),
  'utf8',
)
const capabilityTaskSeedsSource = readFileSync(
  new URL('../../name-by-capability-audit/reference/task-seeds.md', import.meta.url),
  'utf8',
)

const skillContracts = [
  {
    name: 'shared extraction audit',
    skillSource: sharedSkillSource,
    contractSource: sharedContractSource,
    expectedDefaultBehavior: 'applies the prioritized fix band by default',
  },
  {
    name: 'name by capability audit',
    skillSource: capabilitySkillSource,
    contractSource: capabilityContractSource,
    expectedDefaultBehavior: 'applies the suggested rename direction by default',
  },
]

function assertProposalContract(skillContract) {
  const combinedSource = `${skillContract.skillSource}\n${skillContract.contractSource}`
  const preflightRoutingOffset = skillContract.skillSource.indexOf('`preflight-proposal`')
  const reportOnlyRoutingOffset = skillContract.skillSource.indexOf('`audit-only`')

  assert.ok(preflightRoutingOffset >= 0, `${skillContract.name} selects proposal mode`)
  assert.ok(preflightRoutingOffset < reportOnlyRoutingOffset, `${skillContract.name} routes proposal mode first`)
  assert.match(combinedSource, /caller-supplied isolated worktree/)
  assert.match(combinedSource, /resolved PR number/)
  assert.match(combinedSource, /immutable base SHA/)
  assert.match(combinedSource, /immutable head SHA/)
  assert.match(combinedSource, /exact `base_sha\.\.\.head_sha` range/)
  assert.match(combinedSource, /require exact equality with the head SHA/)
  assert.match(combinedSource, /immutable proposal identity/)
  assert.match(combinedSource, /deterministic diff hash/)
  assert.match(combinedSource, /changed paths/)
  assert.match(combinedSource, /exact tests and outcomes/)
  assert.match(combinedSource, /selected-candidate-ready proposal evidence/)
  assert.match(combinedSource, /selected or dispositioned proposal collection/)
  assert.match(combinedSource, /Reapplication uses exactly the selected records/)
  assert.match(combinedSource, /new proposal ID and new evidence/)
  assert.match(combinedSource, /commit, push, pull-request body, pull-request comment, pull-request review, pull-request update, merge, rebase, and Ready-state mutations/)
  assert.match(skillContract.skillSource, /audit-only` is report-only/)
  assert.match(skillContract.skillSource, new RegExp(skillContract.expectedDefaultBehavior))
  assert.match(skillContract.skillSource, /preflight-proposal.*reference\/preflight-proposal\.md/s)
}

function assertTaskRoutingAndNormalMode() {
  assert.match(sharedSkillSource, /Register this checklist with `update_plan`/)
  assert.match(capabilitySkillSource, /Register every bullet from `reference\/task-seeds\.md` with `update_plan`/)
  assert.match(capabilityTaskSeedsSource, /Register each item with `update_plan`/)
  assert.doesNotMatch(sharedSkillSource, /TodoWrite|TaskCreate/)
  assert.doesNotMatch(capabilitySkillSource, /TodoWrite|TaskCreate/)
  assert.doesNotMatch(capabilityTaskSeedsSource, /TodoWrite|TaskCreate/)
  assert.match(
    capabilitySkillSource,
    /A user-supplied rename or fix direction follows the existing normal fix workflow\./,
  )
  assert.doesNotMatch(
    capabilitySkillSource,
    /A user-supplied rename or fix direction applies inside the isolated worktree/,
  )
  assert.match(
    sharedSkillSource,
    /Run scoped pytest in every mode\. Normal mode may then commit, push, and update the PR; preflight-proposal keeps those actions suppressed\./,
  )
}

test('proposal mode preserves local mutation boundaries and immutable evidence for both audits', () => {
  for (const skillContract of skillContracts) {
    assertProposalContract(skillContract)
  }

  assertTaskRoutingAndNormalMode()
  assert.match(capabilityTaskSeedsSource, /preflight-proposal/)
  assert.match(capabilityTaskSeedsSource, /reference\/preflight-proposal\.md/)
  assert.match(capabilityTaskSeedsSource, /resolved PR number and immutable base and head SHAs/)
  assert.match(capabilityTaskSeedsSource, /selected or dispositioned proposal collection/)
})
