Audit [REPO/ARTIFACT] [TARGET_ID] for **Category N only** (test-name scenario verifier). Skip A–M. Sub-bucket forced-exhaustion mode: Category N is decomposed into 9 sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

[ARTIFACT METADATA — include every changed test alongside the production code path it claims to cover]

- Title / one-line summary: [TITLE]
- Head ref / SHA at audit time: [HEAD_SHA]
- Changed test functions (file + line range + test name + first-line assertion): [CHANGED_TESTS]
- Production functions the tests claim to cover (file + line range + symbol name + branch structure): [PRODUCTION_TARGETS]
- Scenario fixtures / monkeypatches in scope (`monkeypatch.setattr`, `pytest.mark.skipif`, `freezegun.freeze_time`, `mock.patch`): [SCENARIO_GATES]
- Stated intent of each scenario-named test (what condition the test name claims to exercise): [INTENT]

ID prefix: `find`.

[ONE-PARAGRAPH FRAME: enumerate every test whose name includes a scenario claim (`_when_*`, `_at_*`, `_under_*`, `_with_*`, `_on_*`, `_after_*`, `_during_*`). State the audit goal: for each scenario-named test, verify the body sets up the named condition via fixture / monkeypatch / environment gate so the production code's scenario-named branch actually runs during the act phase.]

## Source material ([N] files/sections, all lines in scope)

[INLINE every changed test function alongside the production function it claims to cover. Include the production function's branch structure so the audit can identify the no-op / early-return / default branches that scenario-named tests must NOT silently pass against.]

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**N1. Scenario-named tests demonstrate the scenario** ⭐ canonical N case
- For every test whose name contains `_when_X` / `_at_X` / `_under_X` / `_with_X` / `_on_X` / `_after_X` / `_during_X`, verify the body sets up condition X via fixture, monkeypatch, or environment gate before calling the system under test.
- Adversarial probes: (a) construct an input that satisfies the test's assertion but does NOT trigger the scenario-named code path — does the test still pass; (b) trace the production function's code path under the test's input — which branch executes during the act phase; (c) inspect the test's setup-phase for monkeypatch / fixture calls that gate the scenario.

**N2. Path-decision parametric matrices**
- For tests of `is_*_path` / `_resolve_*_path` / `*_path_exemptions` modules, verify the test corpus ships a parametric matrix covering: empty string, single filename, tilde-prefix, UNC path, drive-letter path, symlinked path, `..`-containing path, trailing-slash path.
- Adversarial probes: (a) walk the production function's path-classification branches — which branch does each input class hit; (b) check the test corpus for input shapes that hit only the default / no-classification branch; (c) for each input class missing from the matrix, construct a probe input and trace which branch executes.

**N3. Tests that pass "for the wrong reason"**
- For every assertion of the shape `assert <substring> in result`, verify the substring shape is unique to the scenario-named branch's output.
- Adversarial probe: walk the production function's branches; for each branch, build the output and test the substring against it. If the substring matches more than one branch's output, the assertion cannot discriminate which branch ran.

**N4. No-op branch exercised by scenario name**
- For every scenario-named test, identify the production function's no-op / early-return / no-feature-installed branch. Verify the test's constructed input does NOT hit that branch.
- Adversarial probes: (a) any test whose input fails the production function's first guard returns the no-op default and the assertion checks the default; (b) any test whose input is empty / None / missing returns early; (c) any test whose fixture is not installed at the test runtime hits the "feature missing" branch.

**N5. Assertion shape mismatch**
- For every assertion, verify the assertion's shape can fail by construction. `assert <substring> not in result` where the substring is misspelled relative to the production output, or `assert result == ""` when the production function returns `None` on the negative case, or `len(result) > 0` when the production function returns an empty list on the no-feature path.
- Adversarial probes: (a) inspect each assertion's shape against the production function's actual return-value space; (b) check for assertions where the substring shape never appears in the production output by construction; (c) check for `assert x is True` where the production function returns truthy non-bool values.

**N6. Cross-platform scenario gating**
- For every test named `_on_windows` / `_on_linux` / `_on_macos`, verify the body gates on `sys.platform`, `monkeypatch.setattr(os, "name", ...)`, or `@pytest.mark.skipif`.
- Bare scenario names that run unchanged across platforms claim more than they prove.
- Adversarial probes: (a) does the production function's platform-specific branch get skipped on the CI runner's actual platform; (b) does the test pass against the platform fallback rather than the platform-specific code; (c) is the platform fixture installed and respected by the test runner.

**N7. Time / clock scenario gating**
- For every test named `_after_<duration>` / `_at_midnight` / `_during_business_hours`, verify the body injects a frozen clock (`freezegun.freeze_time`, `monkeypatch.setattr(time, "time", ...)`, `unittest.mock.patch("datetime.now")`).
- Wall-clock tests are non-deterministic and may pass against the wrong scenario.
- Adversarial probes: (a) does the test's act phase depend on the system clock being at a specific value; (b) does any timezone shift cause the test to flake; (c) does the production function read the clock during the act phase.

**N8. Concurrent / load scenario gating**
- For every test named `_under_load` / `_with_concurrent_writers` / `_under_contention`, verify the body spawns the concurrent workers and `wait()`s on them.
- Single-threaded tests cannot claim concurrent-scenario coverage.
- Adversarial probes: (a) does the test spawn `threading.Thread` / `multiprocessing.Process` / `asyncio.gather` / `concurrent.futures.ThreadPoolExecutor`; (b) does the test's act phase exercise the concurrency primitive the production function relies on; (c) does the test introduce a race window the production function's lock should serialize.

**N9. Neutral-named tests (out of scope)**
- Tests named `test_returns_empty_list_for_unknown_key` / `test_handles_y` / `test_raises_value_error` (no scenario claim in the name) are NOT subject to N1–N8.
- For neutral-named tests, only N5 (assertion shape mismatch) applies.

## Cross-bucket questions to answer at the end

Q1: Across all 9 sub-buckets, is there a scenario-named test that does not exercise the named scenario? Cite the test's file:line and the production function's scenario-named branch that should have been exercised.

Q2: What's the worst false-coverage signal introduced by the diff? Evaluate by (a) whether the test's name is load-bearing in the suite's coverage report, (b) whether the named scenario has any other coverage; (c) whether removing the test would change the coverage percentage.

Q3: Which scenario-named test most likely will start passing for the wrong reason in a future refactor? Identify tests whose assertions match substrings that could appear in multiple branches — these are time bombs.

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket N1-N9, produce Shape A or Shape B (with ≥3 probes). Each Shape A finding must cite the test's file:line AND the production function's branch the test's name claims to cover. Cross-bucket Q1-Q3 answers after the per-sub-bucket walk. Adversarial second pass: "assume your first pass missed at least 3 scenario-named tests that exercise the no-op branch — find them." Open Questions section for ambiguities. Read-only. No edits, no commits.

---

# Worked example: jl-cmd/claude-code-config PR #476

Audit jl-cmd/claude-code-config PR #476 for **Category N only** (test-name scenario verifier). Skip A–M. Sub-bucket forced-exhaustion mode: Category N is decomposed into 9 sub-buckets below.

PR: refactor(hooks): cross-platform path resolution for windows-rmtree-blocker
Head SHA: (the commit that landed the platform-conditional logic)
ID prefix: `find`.

The PR adds platform-conditional path-resolution logic to `windows_rmtree_blocker.py` and ships 5 new tests named `test_*_on_windows` and `test_*_on_linux` across `test_windows_rmtree_blocker.py`. The audit goal: verify each scenario-named test sets up the named platform via monkeypatch or skipif gate so the production function's platform-specific branch actually runs during the act phase.

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**N1. Scenario-named tests demonstrate the scenario** ⭐ canonical N case — Shape A findings F5, F21, F23, F26, F27
- `test_resolves_path_on_windows` calls `windows_rmtree_blocker.resolve_path("C:/Users/test")` and asserts the result equals `Path("C:/Users/test")`. The body does NOT call `monkeypatch.setattr(sys, "platform", "win32")` or `@pytest.mark.skipif(sys.platform != "win32")`. On a Linux CI runner, `sys.platform == "linux"` is in effect when the test runs; the production function's `if sys.platform == "win32":` branch is skipped, and the assertion succeeds against the Linux fallback branch's output (which happens to match `Path("C:/Users/test")` because `pathlib.PurePath` accepts Windows-style strings on Linux without normalization).
- The test's NAME claims Windows-branch coverage; the test's BODY exercises the Linux fallback. This is the canonical N1 finding shape.
- Adversarial probe (a): construct an input that the Windows branch would handle differently from the Linux branch — does the test catch the divergence? In F5's case, no: the assertion uses a string that both branches happen to produce, so the test cannot discriminate.
- Adversarial probe (b): the production function's `sys.platform == "win32"` branch performs UNC-prefix stripping; the Linux fallback does not. Inputs containing `\\?\` would yield different outputs on the two branches. The test does not use such inputs.
- Adversarial probe (c): the test runtime's `sys.platform` is `"linux"` on the CI runner. The act phase hits the fallback, full stop.
- **Severity P1** for each of F5, F21, F23, F26, F27: scenario-named tests claim platform-specific coverage they do not provide.
- **Fix**: wrap each `_on_windows`-named test in `@pytest.mark.skipif(sys.platform != "win32", reason="windows-specific path resolution")` AND duplicate as `_on_linux` for the Linux fallback branch; OR use `monkeypatch.setattr(sys, "platform", "win32")` to force the named platform during the act phase.

**N2. Path-decision parametric matrices**
- The production function `resolve_path` is a path-classifier — it qualifies for N2 coverage. The PR ships 5 inputs: drive-letter, UNC-prefix, tilde-prefix, `..`-containing, and trailing-slash. Missing: empty string, single filename, symlinked path. These three input classes have no test in the diff.
- Adversarial probes: (a) construct an empty-string input — does any branch handle it; (b) construct a single-filename input (no directory component) — does the function return as-is or attempt to resolve against cwd; (c) construct a symlinked path — does the function resolve through the symlink or preserve it.

**N3. Tests that pass "for the wrong reason"**
- See N1 findings F5, F21, F23, F26, F27 — each passes because the assertion's substring matches both the Windows-branch output and the Linux-fallback output. The assertion shape cannot discriminate which branch ran.

**N4. No-op branch exercised by scenario name**
- F5 finding above: the scenario-named test exercises the Linux-fallback no-op branch on the CI runner.

**N5. Assertion shape mismatch**
- All five tests use `assert result == Path(<expected>)`. The shape can fail by construction (Path equality is strict). N5 verified clean.

**N6. Cross-platform scenario gating** ⭐
- Five `_on_windows`-named tests have zero platform gating. Five `_on_linux`-named tests have zero platform gating. N6 is the structural lens on the N1 findings — every test's NAME claims platform coverage, every test's BODY ignores the platform gate.
- See N1 F5 / F21 / F23 / F26 / F27.

**N7. Time / clock scenario gating**
- No time-named tests in scope. N7 verified clean.

**N8. Concurrent / load scenario gating**
- No concurrency-named tests in scope. N8 verified clean.

**N9. Neutral-named tests (out of scope)**
- One test in the diff is neutrally named (`test_returns_path_unchanged_when_already_absolute`). N9 marks it out of scope for N1-N4 / N6-N8; only N5 applies. The assertion is `assert result == input_path` — shape clean. Verified clean.

## Cross-bucket questions to answer at the end

Q1: Five scenario-named tests (F5, F21, F23, F26, F27) do not gate on `sys.platform` and pass against the Linux-fallback branch on the CI runner. The Windows-specific code path has zero actual coverage despite the test names claiming it. Cite `test_windows_rmtree_blocker.py:42` (F5 first test) and `windows_rmtree_blocker.py:67` (the `if sys.platform == "win32":` branch) as the misclaim pair.

Q2: Worst false-coverage signal: F5 — the test's name `test_resolves_path_on_windows` reads as Windows-branch coverage in the PR review, but the act phase exercises the Linux fallback. A reviewer reading the test name during PR review would assume Windows coverage exists; it does not.

Q3: Once the Windows branch and the Linux branch diverge in their output for the same input — for example, a future PR that adds normalization to the Windows branch only — these five tests will start failing on Windows CI, exposing the false coverage retroactively.

## Output

Lead: `Total: 5 (P0=0, P1=5, P2=0)`. F5, F21, F23, F26, F27 are the N1+N6 scenario-gate-missing findings. N2 has one finding (parametric matrix incomplete) at P2. N3 / N4 are subsumed by N1. N5 / N7 / N8 / N9 verified clean. Adversarial second pass: scan for any non-`_on_<platform>`-named test that exercises the platform-conditional branch — verified none in this diff. Open Questions: whether the PR author intended any of the `_on_<platform>` tests to be platform-gated; resolve via reply on the audit thread. Read-only. No edits, no commits.
