import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const proposalSource = readFileSync(new URL('./preflight-proposal.md', import.meta.url), 'utf8')
const fixSource = readFileSync(new URL('./fix.md', import.meta.url), 'utf8')
const loopSource = readFileSync(new URL('./loop.md', import.meta.url), 'utf8')

function sourceBetweenHeadings(source, fromHeading, toHeading) {
  const fromOffset = source.indexOf(fromHeading)
  const toOffset = source.indexOf(toHeading, fromOffset)

  assert.ok(fromOffset >= 0)
  assert.ok(toOffset > fromOffset)

  return source.slice(fromOffset, toOffset)
}

function assertReviewLevelExtension() {
  assert.match(proposalSource, /<review_level> --fix loop/)
  const allReviewLevelMappings = [
    ['Omitted override', 'low'],
    ['`low`', 'low'],
    ['`medium`', 'medium'],
    ['`xhigh`', 'xhigh'],
  ]

  for (const [eachCallerSelection, eachLevel] of allReviewLevelMappings) {
    const expectedRow = `| ${eachCallerSelection} | \`${eachLevel}\` |`
    assert.match(proposalSource, new RegExp(expectedRow.replaceAll('|', '\\|')))
  }
  assert.match(proposalSource, /`review_level` evidence mirrors the resolved `--level` value/)
}

function assertProposalHandoffs() {
  assert.match(proposalSource, /canonical contract owns the immutable range/)
  const fixModeSource = sourceBetweenHeadings(
    fixSource,
    '## Preflight-proposal mode',
    '## Resume the finding agent',
  )
  assert.match(fixModeSource, /consume the established proposal context/)
  assert.doesNotMatch(fixModeSource, /follow \[preflight-proposal.md\]/)
  const proposalModeSource = sourceBetweenHeadings(
    loopSource,
    '## Preflight-proposal mode',
    '## Act',
  )
  assert.match(proposalModeSource, /continue the review loop with the established proposal context/)
  assert.doesNotMatch(proposalModeSource, /follow \[preflight-proposal.md\]/)
  assert.match(proposalModeSource, /Proposal mode ends with proposal evidence/)
  assert.doesNotMatch(proposalModeSource, /proof-of-work PR comment|gh pr ready/)
  assert.doesNotMatch(proposalSource, /proof-of-work PR comment|gh pr ready/)
}

function assertNormalTerminationContract() {
  const normalTerminalSource = loopSource.slice(loopSource.indexOf('## Terminal outcomes'))
  assert.match(normalTerminalSource, /proof-of-work PR comment/)
  assert.match(normalTerminalSource, /gh pr ready/)
}

test('preflight proposal mode isolates review loops and preserves normal termination behavior', () => {
  assertReviewLevelExtension()
  assertProposalHandoffs()
  assertNormalTerminationContract()
})
