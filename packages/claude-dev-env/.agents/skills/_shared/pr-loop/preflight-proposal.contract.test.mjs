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
const reviewSkillSource = readFileSync(
  resolve(THIS_DIRECTORY, '../../e-code-review/SKILL.md'),
  'utf8',
)
const reviewProposalSource = readFileSync(
  resolve(THIS_DIRECTORY, '../../e-code-review/reference/preflight-proposal.md'),
  'utf8',
)

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

function assertReviewProposalAdapter() {
  const preflightRoutingOffset = reviewSkillSource.indexOf('`preflight-proposal`')
  const refusalRoutingOffset = reviewSkillSource.indexOf('**Refusal — first match wins:**')
  const allProposalEntryMatches = reviewSkillSource.match(
    /Route the selected mode through \[reference\/preflight-proposal.md\]\(reference\/preflight-proposal.md\) to establish proposal context/g,
  ) ?? []

  assert.ok(preflightRoutingOffset >= 0)
  assert.ok(preflightRoutingOffset < refusalRoutingOffset)
  assert.equal(allProposalEntryMatches.length, 1)
  assert.match(reviewSkillSource, /e-code-review preflight-proposal/)
  assert.match(reviewSkillSource, /`--level <low\|medium\|xhigh>`/)
  assert.match(reviewSkillSource, /@~\/.claude\/_shared\/pr-loop\/preflight-proposal.md/)
  assert.match(reviewSkillSource, /Normal mode follows the current level/)
  assert.match(reviewProposalSource, /Keep Gate 1, Gate 2, the bare code-rules gate, and exact required tests/)
  assert.match(reviewProposalSource, /review_level: low \| medium \| xhigh/)
  assert.match(reviewProposalSource, /severity: blocker \| high \| medium \| low \| nit/)
  assert.match(reviewProposalSource, /verdict: CONFIRMED \| PLAUSIBLE/)
  assert.match(reviewProposalSource, /outcome: fixed \| no_change_needed \| skipped/)
}

test('the shared contract defines proposal evidence for the active review skill', () => {
  assertReviewProposalAdapter()
  assertSharedProposalContract(canonicalContractSource)
})
