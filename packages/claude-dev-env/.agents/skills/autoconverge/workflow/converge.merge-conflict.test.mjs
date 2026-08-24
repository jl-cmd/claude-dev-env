import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const workflowSource = readFileSync(new URL('./converge.mjs', import.meta.url), 'utf8')

test('merge-conflict repair keeps the rebase, review, and force-push sequence', () => {
  const conflictStart = workflowSource.indexOf('async function resolveMergeConflicts')
  const conflictEnd = workflowSource.indexOf('function isStandardsOnlyRound', conflictStart)
  const conflictSource = workflowSource.slice(conflictStart, conflictEnd)
  assert.match(conflictSource, /runCodeEditorTask\('conflict-edit'/)
  assert.match(conflictSource, /runReviewTask\('repair-verify'/)
  assert.match(conflictSource, /reviewPassed\(verifyTranscript\)/)
  assert.match(conflictSource, /commitWithRecovery/)
})
