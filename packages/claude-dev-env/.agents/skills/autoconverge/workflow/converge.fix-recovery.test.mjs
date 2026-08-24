import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const workflowSource = readFileSync(new URL('./converge.mjs', import.meta.url), 'utf8')

test('review results gate recovery commits', () => {
  const recoveryStart = workflowSource.indexOf('async function commitWithRecovery')
  const recoveryEnd = workflowSource.indexOf('async function verifyWithRecovery', recoveryStart)
  const recoverySource = workflowSource.slice(recoveryStart, recoveryEnd)
  assert.match(recoverySource, /commitNeedsCodeRecovery/)
  assert.match(recoverySource, /runRecoverEdit/)
  assert.match(recoverySource, /reviewPassed\(verifyTranscript\)/)
  assert.match(recoverySource, /rebindReviewedSurface/)
  assert.match(recoverySource, /captureReviewedSurface/)
})

test('failed review findings route back to the bounded repair loop', () => {
  const recoveryStart = workflowSource.indexOf('async function verifyWithRecovery')
  const recoveryEnd = workflowSource.indexOf('async function applyFixes', recoveryStart)
  const recoverySource = workflowSource.slice(recoveryStart, recoveryEnd)
  assert.match(recoverySource, /FIX_RECOVERY_MAX_ATTEMPTS/)
  assert.match(recoverySource, /extractVerifyObjection/)
  assert.match(recoverySource, /reviewPassed\(verifyTranscript\)/)
})

test('commit paths bind a deterministic reviewed working-tree surface', () => {
  assert.match(workflowSource, /function runWorkingTreeSurfaceTask\(context\)/)
  assert.match(workflowSource, /git diff --no-ext-diff --binary HEAD/)
  assert.match(workflowSource, /git ls-files --others --exclude-standard -z/)
  assert.match(workflowSource, /async function rebindReviewedSurface/)
  assert.match(workflowSource, /stableReviewedSurfaceHash/)
})
