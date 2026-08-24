import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'

const sourcePath = new URL('./converge.mjs', import.meta.url)
const workflowSource = readFileSync(sourcePath, 'utf8')

function loadReviewResultParser() {
  const passMarker = workflowSource.match(/const REVIEW_RESULT_PASS_MARKER = .+/)[0]
  const findingsMarker = workflowSource.match(/const REVIEW_RESULT_FINDINGS_MARKER = .+/)[0]
  const parserStart = workflowSource.indexOf('function parseReviewResult')
  const parserEnd = workflowSource.indexOf('\n}\n', parserStart) + 2
  const parserSource = `${passMarker}\n${findingsMarker}\n${workflowSource.slice(parserStart, parserEnd)}`
  const parserContext = {}
  vm.runInNewContext(`${parserSource}\nglobalThis.parseReviewResult = parseReviewResult`, parserContext)
  return parserContext.parseReviewResult
}

test('review tasks apply the canonical review guide and return a review result', () => {
  assert.match(workflowSource, /function runReviewTask\(task, context\)/)
  assert.match(workflowSource, /_shared\/pr-loop\/precatch-rubric\.md/)
  assert.match(workflowSource, /REVIEW_RESULT: PASS/)
  assert.match(workflowSource, /REVIEW_RESULT: FINDINGS/)
})

test('review tasks use code-quality-agent and keep the working tree read-only', () => {
  const reviewTaskStart = workflowSource.indexOf('function runReviewTask')
  const reviewTaskEnd = workflowSource.indexOf('function serializeOneLineJson', reviewTaskStart)
  const reviewTaskSource = workflowSource.slice(reviewTaskStart, reviewTaskEnd)
  assert.match(reviewTaskSource, /agentType: 'code-quality-agent'/)
  assert.match(reviewTaskSource, /Make no edit to the tree under verification/)
})

test('review result parser accepts one standalone terminal disposition only', () => {
  const parseReviewResult = loadReviewResultParser()

  assert.equal(parseReviewResult('review complete\nREVIEW_RESULT: PASS'), 'PASS')
  assert.equal(parseReviewResult('finding: missing test\nREVIEW_RESULT: FINDINGS'), 'FINDINGS')
  assert.equal(parseReviewResult('REVIEW_RESULT: PASSING'), null)
  assert.equal(parseReviewResult('REVIEW_RESULT: PASS\nREVIEW_RESULT: FINDINGS'), null)
  assert.equal(parseReviewResult('REVIEW_RESULT: PASS\n> REVIEW_RESULT: FINDINGS'), null)
  assert.equal(parseReviewResult('review complete'), null)
})

test('the fix flow keeps edit, review, and commit as distinct operational steps', () => {
  const fixerStart = workflowSource.indexOf('async function fixerWithRecovery')
  const fixerEnd = workflowSource.indexOf('function runCodeEditorTask', fixerStart)
  const fixerSource = workflowSource.slice(fixerStart, fixerEnd)
  assert.match(fixerSource, /runReviewTask\('fix-verify'/)
  assert.match(fixerSource, /runFixerTask\('commit'/)
  assert.match(fixerSource, /reviewPassed\(verifyTranscript\)/)
})
