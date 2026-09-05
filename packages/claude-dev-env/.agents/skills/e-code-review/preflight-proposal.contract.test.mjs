import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const skill = readFileSync(resolve(here, 'SKILL.md'), 'utf8')
const contract = readFileSync(resolve(here, 'reference/preflight-proposal.md'), 'utf8')

test('e-code-review owns its preflight proposal contract', () => {
  assert.match(skill, /reference\/preflight-proposal\.md/)
  assert.doesNotMatch(skill, /_shared\/pr-loop/)
  assert.match(contract, /caller-supplied isolated worktree/)
  assert.match(contract, /exact `base_sha\.\.\.head_sha` range/)
  assert.match(contract, /immutable proposal identity/)
  assert.match(contract, /selected or dispositioned proposal collection/)
  assert.match(contract, /review_level: low \| medium \| xhigh/)
  assert.match(contract, /outcome: fixed \| no_change_needed \| skipped/)
})
