# Category N — Test-name scenario verifier

**What this category audits:** tests whose names assert a specific scenario (`test_*_when_*`, `test_*_at_*`, `test_*_under_*`, `test_*_with_*`) must demonstrate via fixture inspection, monkeypatch state, or environment setup that the named condition is in effect when the system under test runs. Common failure: a test named `test_resolves_under_unc_prefix` constructs a regular drive-letter path, asserts the function returns a non-empty result, and passes — but the UNC-prefix branch was never exercised. The test is a load-bearing witness that the named scenario works, but it actually only exercises the no-op default path.

**Why this category is its own bucket:** Categories A–K catch defects in the production code. Category N catches defects in the *test corpus's claim to coverage*. A green test suite is only meaningful when each test's name accurately describes what was exercised. When a test passes "for the wrong reason" — e.g., the assertion matches a substring that appears in both the scenario-named branch AND the default branch — the suite reports coverage of a scenario it never actually ran.

**Examples of Category N findings:**
- Cross-platform tests named `test_*_on_windows` / `test_*_on_linux` that don't gate on `sys.platform` or `monkeypatch.setattr(os, "name", ...)` and run unchanged on every platform. (ccc#476 F5, F21, F23, F26, F27)
- String-shape tests that exercise only the no-op branch (`assert result == ""` after constructing an input that hits the early-return path, not the named scenario). (pa#135 F11, F15)
- Integration tests with assertions like `<substring> not in executed_sql` where the substring shape never matches the SQL fragment shape — the assertion cannot fail by construction. (pa#136 F50)
- Path-decision tests for `is_test_file` / `is_hook_infrastructure` / `_resolve_*_path` without a parametric matrix of canonical edge cases (empty string, tilde-prefix, UNC, drive-letter, symlinked, `..`-containing, trailing slash).
- A test resolves `Path(__file__).parents[3]` expecting the `claude-dev-env/` package root, but the parents chain actually stops at `skills/` — the test cannot fail for the right reason and the asserted directory wiring is broken by construction.
- A test imports the same function twice under two names (`from path_utils import is_config_file` plus `from path_utils import is_config_file as path_utils_is_config_file`) and asserts the two bound names produce the same result — the assertion cannot fail because both names are the same function object; the appearance of two parallel implementations is fake.

**Companion reference:** see `../source-material-section-types.md`.

---

## Sub-bucket decomposition (Category N)

Decomposition is by the **kind of scenario claim** the test name makes vs the evidence in its body.

| ID | Axis name | Concrete checks |
|---|---|---|
| N1 | Scenario-named tests demonstrate the scenario | A test whose name contains `_when_`, `_at_`, `_under_`, `_with_`, `_on_`, `_after_`, `_during_` proves via monkeypatch / fixture / environment setup that the named condition holds during the act phase |
| N2 | Path-decision parametric matrices | Tests for `is_*_path` / `_resolve_*_path` / `*_path_exemptions` modules ship a parametrized matrix covering: empty string, single filename, tilde-prefix, UNC path, drive-letter path, symlinked path, `..`-containing path, trailing-slash path |
| N3 | Tests that pass "for the wrong reason" | The assertion's substring matches both the scenario-named branch and the default branch — the test cannot distinguish which branch executed |
| N4 | No-op branch exercised by scenario name | The constructed input hits an early-return / guard / no-feature-installed branch BEFORE the scenario-named code runs; the assertion succeeds against the no-op output |
| N5 | Assertion shape mismatch | The assertion shape (`<substring> not in result`, `result == ""`, `len(result) > 0`) cannot fail by construction against the actual return type / value space |
| N6 | Cross-platform scenario gating | Tests named `_on_<platform>` MUST gate on `sys.platform`, `monkeypatch.setattr(os, ...)`, or `@pytest.mark.skipif(sys.platform != "<platform>")` — bare scenario names that run unchanged across platforms claim more than they prove |
| N7 | Time / clock scenario gating | Tests named `_after_<duration>` / `_at_midnight` / `_during_business_hours` MUST inject a frozen clock (`freezegun.freeze_time`, `monkeypatch.setattr(time, "time", ...)`) — wall-clock tests are non-deterministic and may pass against the wrong scenario |
| N8 | Concurrent / load scenario gating | Tests named `_under_load` / `_with_concurrent_writers` MUST spawn the concurrent workers and `wait()` on them — single-threaded tests cannot claim concurrent-scenario coverage |
| N9 | Neutral-named tests (out of scope) | Tests named `test_returns_empty_list_for_unknown_key` / `test_handles_y` (no scenario claim in the name) are NOT subject to N1–N8; flag them only for assertion-shape mismatches under N5 |
| N10 | Test fixture wiring correctness | The test's fixture / path / import wiring resolves to the artifact the test name claims. Path arithmetic (`Path(__file__).parents[k]`) reaches the directory the assertion expects — verify by walking the parents chain symbolically. Same-symbol dual imports (`from m import f` plus `from m import f as f_alias`) bind two names to the same function object, so any parity assertion between them is true by construction. Fixture file lookups (`open(Path(__file__).parent / 'fixture.txt')`) reach a file that actually exists. |

Customize per-artifact: a pure-function test corpus with no scenario claims reduces N1–N4 to "verified clean — no scenario-named tests in scope"; a path-classifier PR may need N2 exhausted across 8+ canonical inputs.

---

## Write-time advisory for the flag-gated N1 slice

`check_flag_gated_scenario_test_naming` in `code_rules_test_assertions.py` (wired into `code_rules_enforcer.py`) catches the deterministic N1 slice at Write/Edit time. When two or more sibling tests in a file `monkeypatch.setattr` the same module-level UPPER_SNAKE flag, that flag governs which branch the code under test runs. A `test_*` whose name carries a scenario clause (`_when_`, `_passes`, `_succeeds`, `_on_clean`) but never patches that flag runs under the flag's default value, so its named condition may not be in effect. The check prints an advisory to stderr and never blocks the write — the breadth of the sibling-pattern heuristic suits a judgment lane, where the author decides whether to patch the flag (and assert the gated path runs) or rename the test. The audit still owns the full N1–N10 surface; the advisory only surfaces this one mechanically-detectable shape early.

---

## Sample prompt

The reusable Variant C template for Category N is in [`../prompts/category-n-test-name-scenario-verifier.md`](../prompts/category-n-test-name-scenario-verifier.md). Inline every changed test function under `## Source material` along with the production function it claims to cover, so the audit can compare the named scenario against the body's act phase.

## Why Category N matters as its own bucket

Categories A–K each examine production code. Category N examines whether the test corpus's name claims match its body evidence. A green suite without N coverage gives a false sense of confidence: scenario-named tests that pass against the no-op branch report success for code that was never run.

The ccc#476 cases (F5, F21, F23, F26, F27) demonstrate the cost of not running N: tests named `_on_windows` and `_on_linux` ran unchanged on every CI runner. The Windows-specific test passed on Linux because the production function's Windows branch was guarded by `sys.platform == "win32"` and short-circuited — the assertion succeeded against the Linux fallback. The test name claimed Windows coverage; the body never exercised it. Only an N6-style gating audit (require `monkeypatch.setattr(sys, "platform", "win32")` inside any `_on_windows`-named test, or `@pytest.mark.skipif`) would have caught this in review.
