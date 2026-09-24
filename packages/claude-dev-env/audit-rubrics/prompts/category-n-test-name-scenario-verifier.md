Audit [REPO/ARTIFACT] [TARGET_ID] for **Category N only** (test-name scenario verifier). Skip A–M, O, P. Sub-bucket forced-exhaustion mode: Category N is decomposed into 10 sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

[ARTIFACT METADATA — include every changed test alongside the production code path it claims to cover]

- Title / one-line summary: [TITLE]
- Head ref / SHA at audit time: [HEAD_SHA]
- Changed test functions (file + line range + test name + first-line assertion): [CHANGED_TESTS]
- Production functions the tests claim to cover (file + line range + symbol name + branch structure): [PRODUCTION_TARGETS]
- Scenario fixtures / monkeypatches in scope (`monkeypatch.setattr`, `pytest.mark.skipif`, `freezegun.freeze_time`, `mock.patch`): [SCENARIO_GATES]
- Stated intent of each scenario-named test (what condition the test name claims to exercise): [INTENT]

ID prefix: `find`.

[ONE-PARAGRAPH FRAME: enumerate every test whose name includes a scenario claim (`_when_*`, `_at_*`, `_under_*`, `_with_*`, `_on_*`, `_after_*`, `_during_*`). State the audit goal: for each scenario-named test, verify the body sets up the named condition via fixture / monkeypatch / environment gate so the production code's scenario-named branch runs during the act phase.]

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
- Adversarial probes: (a) inspect each assertion's shape against the production function's return-value space; (b) check for assertions where the substring shape never appears in the production output by construction; (c) check for `assert x is True` where the production function returns truthy non-bool values.

**N6. Cross-platform scenario gating**
- For every test named `_on_windows` / `_on_linux` / `_on_macos`, verify the body gates on `sys.platform`, `monkeypatch.setattr(os, "name", ...)`, or `@pytest.mark.skipif`.
- Bare scenario names that run unchanged across platforms claim more than they prove.
- Adversarial probes: (a) does the production function's platform-specific branch get skipped on the CI runner's platform; (b) does the test pass against the platform fallback rather than the platform-specific code; (c) is the platform fixture installed and respected by the test runner.

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

**N10. Test fixture wiring correctness**
- For every test, verify the fixture / path / import wiring resolves to the artifact the test name claims.
- Path arithmetic: walk every `Path(__file__).parents[k]` chain symbolically and confirm it reaches the directory the assertion expects — a `parents[3]` that stops at `skills/` while the test expects the package root cannot fail for the right reason.
- Same-symbol dual imports: `from module import helper` plus `from module import helper as helper_alias` bind two names to the same function object, so any parity assertion between the two bound names is true by construction and proves nothing.
- Fixture file lookups: confirm every `open(Path(__file__).parent / "fixture.txt")` (or equivalent) reaches a file that exists in the repo.
- Adversarial probes: (a) re-derive each `parents[k]` index against the directory depth and flag any off-by-k; (b) check whether two imports in the test resolve to the same object before trusting a cross-name comparison; (c) confirm each referenced fixture path exists on disk at the depth the arithmetic produces.

## Cross-bucket questions to answer at the end

Q1: Across all 10 sub-buckets, is there a scenario-named test that does not exercise the named scenario? Cite the test's file:line and the production function's scenario-named branch that should have been exercised.

Q2: What's the worst false-coverage signal introduced by the diff? Evaluate by (a) whether the test's name is load-bearing in the suite's coverage report, (b) whether the named scenario has any other coverage; (c) whether removing the test would change the coverage percentage.

Q3: Which scenario-named test most likely will start passing for the wrong reason in a future refactor? Identify tests whose assertions match substrings that could appear in multiple branches — these are time bombs.

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket N1-N10, produce Shape A or Shape B (with at least 3 probes). Each Shape A finding must cite the test's file:line AND the production function's branch the test's name claims to cover. Cross-bucket Q1-Q3 answers after the per-sub-bucket walk. Report every finding you reach, including uncertain ones and P2 ones, and give each finding a confidence level (high, medium, or low) beside its severity so a later pass can rank and filter them. Open Questions section for ambiguities. Read-only. No edits, no commits.
