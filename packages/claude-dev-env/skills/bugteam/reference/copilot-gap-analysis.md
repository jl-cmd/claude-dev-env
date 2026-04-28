# Copilot gap analysis

This file is the reference record produced by the read-only investigation of why the `/bugteam` audit/fix loop and `bugteam_code_rules_gate.py` repeatedly miss the classes of code-quality violations that the GitHub Copilot reviewer raises on follow-up review rounds. It is written so future bugteam runs can skim the inventory, the rubric/validator coverage diffs, and the patch plan without re-deriving them.

Sources of truth cited below: `~/.claude/docs/CODE_RULES.md`, `~/.claude/CLAUDE.md`, `~/.claude/rules/file-global-constants.md`, `~/.claude/skills/bugteam/SKILL.md`, `~/.claude/skills/bugteam/PROMPTS.md`, `~/.claude/skills/bugteam/CONSTRAINTS.md`, `~/.claude/skills/bugteam/scripts/bugteam_code_rules_gate.py`, `~/.claude/skills/bugteam/scripts/bugteam_preflight.py`, `~/.claude/hooks/blocking/code_rules_enforcer.py`, plus `gh api repos/JonEcho/python-automation/pulls/{70,73}/comments` filtered to author `Copilot`.

---

## Investigation report

### Copilot finding inventory

Copilot review comments fetched with:

```
gh api repos/JonEcho/python-automation/pulls/70/comments --paginate --jq '.[] | select(.user.login == "Copilot")'
gh api repos/JonEcho/python-automation/pulls/73/comments --paginate --jq '.[] | select(.user.login == "Copilot")'
```

PR #70 head SHA `29117309cf4ec1e83883160d8c819e0843f9c3ac` (merged). PR #73 head SHA `c9c935a96cc59d39d623dc7eddda3d341007607c` (merged); Copilot reviewed at original commit `e4abf52c3a6c724b4e64bfed0d979cd60a2c8bf0`.

| finding_id | pr_number | file:line | rule_cited | severity | mapped_bugteam_category_letter | layer_that_should_have_caught_it |
|---|---|---|---|---|---|---|
| 3153098661 | 70 | `shared_utils/theme_db/writer.py:158` | Magic values — column-name string literals (`"theme_name"`, `"content_id"`, …) hardcoded inside SQL builder bodies (CODE_RULES.md §⚡ Magic values; J) | P1 | J | bugteam pre-flight gate (`bugteam_code_rules_gate.py`) — string literals are masked by `_mask_string_literals_preserving_length`, so the number-only magic-value detector never sees them; bugteam audit rubric (J) names the rule but the regex passes |
| 3153098689 | 70 | `shared_utils/theme_db/writer.py:361` | File-length / function-length / SRP smell (`write_outcome` >30 lines, module 446 lines exceeds the 400-line advisory) | P2 | none | initial+final standards-review phases bracketing the loop — no rubric letter exists; the existing 400/1000-line advisory in `code_rules_enforcer.advise_file_line_count` is stderr-only and never blocks |
| 3153098727 | 70 | `shared_utils/theme_db/summary.py:267` | Library `print()` calls in non-CLI library code (CODE_RULES.md §Self-Documenting Code; "Make output stream explicit" practice) | P1 | none | harness PreToolUse hook (`code_rules_enforcer.py`) — no detector exists for `print(`/`sys.stdout.write` inside library modules |
| 3153098762 | 70 | `shared_utils/theme_db/summary.py:263` | PR-description spec drift — banner missing column-header rows promised in PR body | P2 | A (loosely) | initial+final standards-review phases — A is signature/async-shaped, not "promised behavior vs implementation" shaped |
| 3153098782 | 70 | `shared_utils/theme_db/writer.py:125` | Naming clarity — `_is_set_column_value` reads like it excludes `None` but does not | P2 | none | bugteam audit rubric addendum — no naming-clarity category in A–J |
| 3153475246 | 73 | `shared_utils/theme_db/config/constants.py:91` | Collection naming — `THEMES_INSERT_REQUIRED_COLUMN_NAMES` is a tuple and must use the `ALL_*` prefix (CODE_RULES.md §5 "Extended naming rules" → Collections: `all_orders`, `all_users`) | P1 | none | harness PreToolUse hook AND bugteam pre-flight gate — no detector for the collection-prefix rule. Reproduced at `e4abf52c`; renamed to `ALL_THEMES_INSERT_REQUIRED_COLUMN_NAMES` in the merged PR head |
| 3153475297 | 73 | `shared_utils/theme_db/writer.py:296` | Collection naming — parameter `column_value_pairs` is a list and must use the `all_*` prefix | P1 | none | harness PreToolUse hook AND bugteam pre-flight gate — same gap as 3153475246 for parameter names |
| 3153475331 | 73 | `shared_utils/theme_db/summary.py:206` (referenced; underlying defect is in `shared_utils/theme_db/tracker.py` `flush()`) | Wrapper plumb-through — public `tracker.flush(*, output_folder)` silently drops `loud_banner_stream` that `ThemeDatabaseWriteSummary.flush(*, output_folder, loud_banner_stream=None)` accepts | P1 | A (loosely) | bugteam audit rubric addendum — A focuses on signatures/return types, not on whether a wrapper preserves the optional kwargs of the function it delegates to |

### Rubric coverage diff

Source: `~/.claude/skills/bugteam/PROMPTS.md` lines 25-38 ("bug_categories"). Each line below names what the category currently asks the bugfind teammate to do, then lists the Copilot finding ids that fell through it.

- **A. API contract verification (signatures, return types, async/await correctness)** — checks signatures and types on the function under audit; does not require the bugfind teammate to compare a public wrapper signature against the inner function it delegates to, and does not cover the human-shaped "the function name is misleading" or "the implementation does not match the PR description" cases. Fell through: 3153098689, 3153098727 (no library-print framing), 3153098762, 3153098782, 3153475331.
- **B. Selector / query / engine compatibility** — none.
- **C. Resource cleanup and lifecycle (file handles, connections, processes, locks)** — none.
- **D. Variable scoping, ordering, and unbound references** — none.
- **E. Dead code: dead parameters, dead locals, dead imports, dead branches, dead returns, and unused imports** — none.
- **F. Silent failures (catch-all excepts, unconditional success returns, missing error propagation)** — none.
- **G. Off-by-one, bounds, and integer overflow** — none.
- **H. Security boundaries (injection, path traversal, auth bypass, secret leakage)** — none.
- **I. Concurrency hazards (race conditions, missing awaits, shared mutable state)** — none.
- **J. Magic values and configuration drift** — names the rule but the bugfind teammate has been observed treating numeric literals as the only magic-value class; string literals that are domain identifiers (column names, status enums, table names) repeatedly slip past. Fell through: 3153098661.

Categories absent from A–J entirely: collection prefix (`ALL_*` / `all_*`), library `print()` / direct `sys.stdout.write` in non-CLI code, file-length/function-length/SRP smell, naming-clarity (misleading positive name), wrapper plumb-through of optional kwargs, and PR-description vs implementation drift.

### Validator coverage diff

Source: every detector inside `~/.claude/hooks/blocking/code_rules_enforcer.py` reused by `~/.claude/skills/bugteam/scripts/bugteam_code_rules_gate.py` via `load_validate_content()` (gate.py:24-40).

- `check_comments_python` / `check_comments_javascript` (enforcer.py:103-184) — flag `#` and `//` comments outside exempt markers. Catches none of the eight Copilot findings.
- `check_comment_changes` (enforcer.py:256-289) — diff-aware comment add/remove. Catches none.
- `check_imports_at_top` (enforcer.py:292-354) — `import` inside function bodies. Catches none.
- `check_logging_fstrings` (enforcer.py:357-376) — `log_*(f"...")` and `logger.*(f"...")`. Catches none.
- `check_windows_api_none` (enforcer.py:402-414) — `win32gui.*(..., None)`. Catches none.
- `check_magic_values` (enforcer.py:444-491) — number literals inside function bodies, with `_mask_string_literals_preserving_length` (enforcer.py:422-441) blanking string content before the regex runs and `0`, `1`, `-1`, `0.0`, `1.0` allowed. Cannot see string-literal magic values such as `"theme_name"` or `"content_id"`. Misses 3153098661.
- `check_fstring_structural_literals` (enforcer.py:551-598) — only flags f-strings whose literal portion looks like a path / URL / Windows drive / regex anchor. Plain `("theme_name", theme_name)` tuple entries are not f-strings and are not "structural" by `_has_structural_shape` (enforcer.py:525-548). Misses 3153098661.
- `check_constants_outside_config` (enforcer.py:735-786) — module-level `UPPER_SNAKE = …` outside `config/`. Files in `config/` are exempt via `is_config_file`, so a constant placed correctly under `config/` is silent. Does not check the `ALL_*` shape on collection-typed constants. Misses 3153475246.
- `check_constants_outside_config_advisory` (enforcer.py:848-859) — function-local UPPER_SNAKE advisory only. Catches none.
- `check_file_global_constants_use_count` (enforcer.py:1338-1390) — file-global UPPER_SNAKE used by exactly one caller. Catches none.
- `check_type_escape_hatches` (enforcer.py:711-726) — `Any` and unjustified `# type: ignore`. Catches none.
- `check_banned_identifiers` (enforcer.py:908-933) — `result`, `data`, `output`, `response`, `value`, `item`, `temp`. Does not name `column_value_pairs` (it is not a banned word) and does not enforce the inverse "must have a prefix" rule for collections. Misses 3153475297.
- `check_boolean_naming` (enforcer.py:1032-1064) — boolean assignments require `is_/has_/should_/can_` prefix. Direct analogue of the rule we need but only for booleans. Misses 3153475246, 3153475297.
- `check_skip_decorators_in_tests` / `check_existence_check_tests` / `check_constant_equality_tests` (enforcer.py:1079-1277) — test-file checks. Catches none.
- `check_unused_optional_parameters` (enforcer.py:1854-1933) — same-file callers must vary an optional parameter. Does not catch the inverse case where a wrapper drops an underlying function's optional kwarg from its own signature. Misses 3153475331.
- `check_incomplete_mocks` / `check_duplicated_format_patterns` (enforcer.py:1746-1851) — advisory-only on test files / repeated f-strings. Catches none.
- `advise_file_line_count` (enforcer.py:379-399) — soft advisory at 400, hard advisory at 1000; never blocking. Triggers on PR #70 `writer.py` (446 lines) but is stderr-only, so the bugteam gate exit code stays 0 and the audit/fix loop never sees the signal as a finding. Misses 3153098689 in practice.

`bugteam_code_rules_gate.py` adds no detectors of its own — `run_gate` (gate.py:379-443) only filters violations to the changed-line set and routes blocking/advisory output. Extending the gate without extending `validate_content` (or adding sibling detectors invoked from `run_gate`) cannot close the gap.

Validators absent entirely:
- Collection-prefix `ALL_*` / `all_*` for tuple/list/set/dict assignments and function parameters.
- Library `print(` / `sys.stdout.write(` / `sys.stderr.write(` outside CLI entry points.
- String-literal magic values inside function bodies (column names, status enums, table names) when they are not f-string structural shapes.
- Wrapper plumb-through detector — public function calling a same-file inner function whose signature has optional kwargs absent from the wrapper.

### Root-cause statement

The bugteam audit rubric (PROMPTS.md §bug_categories A–J) and the deterministic validators (`bugteam_code_rules_gate.py` reusing `code_rules_enforcer.validate_content`) together cover only a narrow slice of `CODE_RULES.md`: number-only magic values, UPPER_SNAKE constants location, boolean naming, banned identifiers, comments, type hints, and a small AST-level f-string check. Three rule classes that `CODE_RULES.md §5 "Extended naming rules"` and the readability rubric explicitly require — the collection prefix `ALL_*` / `all_*`, library `print()` / direct `sys.stdout.write` in non-CLI code, and string-literal magic values that are not structural f-string fragments — have neither a rubric category nor a deterministic detector, so every audit/fix loop converges "0 P0 / 0 P1 / 0 P2 → clean" while leaving them in place; the fourth class — wrapper plumb-through (a public function silently dropping the optional kwargs of an underlying call) — is API-contract-shaped but does not fit category A's signature/async framing. The right enforcement layer is layered: deterministic checks (collection prefix, library print, string-literal magic for known SQL/HTTP keys) belong in `code_rules_enforcer.py` so they block at write time AND in the gate via the existing `validate_content` reuse path; judgment-heavy checks (PR-description drift, naming clarity, SRP/length smells, wrapper plumb-through) belong in a Copilot-derived rubric addendum to `PROMPTS.md`, plus an INITIAL and FINAL standards-review phase bracketing the audit/fix loop so the addendum runs against the cumulative diff with no clean-room context loss.

---

## Patch plan

Each section names exactly one target file, the literal text or regex to add, and a verification step that re-runs the new detection against the PR #70 / PR #73 diffs.

### a. `~/.claude/skills/bugteam/PROMPTS.md`

**Insertion site:** the `<bug_categories>` block inside the AUDIT spawn-prompt XML (PROMPTS.md lines 25-38). Append four new categories K–N and a "Copilot-derived addendum" preamble immediately before the closing `</bug_categories>` tag, leaving A–J unchanged.

**New section header:** `Copilot-derived addendum (K–N)`

**Literal text to add:**

```
  Copilot-derived addendum (K–N) — verify each one explicitly. Return at
  least one finding per category OR a verified-clean entry that names the
  exact files and lines you walked.
  K. Collection naming. Every tuple, list, set, dict, mapping, or sequence
     parameter must follow the CODE_RULES.md §5 "Extended naming rules"
     prefix discipline:
       - module-level constant whose value is a tuple/list/set/dict/frozenset
         literal MUST start with `ALL_` (e.g. `ALL_THEMES_INSERT_REQUIRED_COLUMN_NAMES`)
       - function/method parameter whose annotation is `list[...]`, `tuple[...]`,
         `set[...]`, `dict[...]`, `Iterable[...]`, `Sequence[...]`, `Mapping[...]`,
         or `frozenset[...]` MUST start with `all_` (e.g. `all_column_value_pairs`)
       - exempt: dict/map names that follow the `X_by_Y` pattern (e.g.
         `price_by_product`)
  L. Library print / direct stdout. In any module that is not a CLI entry
     point (`__main__`, `*_cli.py`, `scripts/*.py`), every `print(...)`,
     `sys.stdout.write(...)`, `sys.stderr.write(...)` call is a finding.
     The fix is to route through a `logger` call OR to make the output
     stream an explicit parameter so callers can redirect it.
  M. String-literal magic values. Treat domain-identifier string literals
     (database column names, table names, HTTP header names, status enums,
     environment-variable names) inside a function body as magic values
     even when the existing number-only check would let them pass. The
     fix is to extract them into `config/` and reference the imported
     name. Do not flag plain log messages, error messages, or one-off
     human-readable strings.
  N. Wrapper plumb-through. When a public function delegates to an
     inner function defined in the same package, every optional kwarg
     accepted by the inner function MUST appear in the public wrapper
     unless the wrapper docstring explicitly states the kwarg is fixed
     to a sentinel default. Silently dropping `loud_banner_stream`,
     `timeout`, `dry_run`, or any similar optional kwarg is a finding.
</bug_categories>

<copilot_derived_addendum_source>
  The K–N categories were added after Copilot raised real findings on
  PR #70 (writer.py / summary.py) and PR #73 (constants.py / writer.py /
  tracker.py) that converged "0 P0 / 0 P1 / 0 P2" under the original
  A–J rubric. See ~/.claude/skills/bugteam/reference/copilot-gap-analysis.md
  for the inventory and the validators that now back categories K and L.
</copilot_derived_addendum_source>
```

(Replace the existing closing `</bug_categories>` line with the literal text above so K–N live inside the same block as A–J.)

**Verification step (one line, no `$(...)`):**

```
python C:/Users/jon/.claude/skills/bugteam/scripts/bugteam_code_rules_gate.py /tmp/pr70_writer.py /tmp/pr70_summary.py /tmp/pr73_constants.py /tmp/pr73_writer.py
```

Run after the K and L deterministic detectors land in §c/d below; the categories M and N stay rubric-only and are exercised by replaying PR #70 / PR #73 through `/bugteam` with the new PROMPTS.md and observing that the audit posts findings keyed to lines 158 (M), 125 (rubric N — naming clarity), 263 (rubric N — PR-description drift), 361 (initial/final standards review — file length), and 206 (N — wrapper plumb-through).

### b. `~/.claude/skills/bugteam/SKILL.md`

**Insertion site 1 — progress checklist (SKILL.md lines 72-81).** Add two rows so the checklist reads:

```
[ ] Step 0: project permissions granted
[ ] Step 1: PR scope resolved
[ ] Step 2: agent team created + loop state set
[ ] Step 2.6: INITIAL standards review against cumulative PR diff
[ ] Step 3: cycle complete (converged | cap reached | stuck | error)
[ ] Step 3.5: FINAL standards review against cumulative PR diff
[ ] Step 4: team torn down + working tree clean
[ ] Step 4.5: PR description rewritten (or skip warning logged)
[ ] Step 5: project permissions revoked
[ ] Step 6: final report printed
```

**Insertion site 2 — between the existing Step 2.5 ("PR comments") and Step 3 ("The cycle").** Add a new section:

```
### Step 2.6: INITIAL standards review (once, before Loop 1 audit)

Run BEFORE the first pre-audit gate fires. Spawn a fresh `code-quality-agent`
teammate inside the same team and drive it through the K–N addendum (see
PROMPTS.md `<copilot_derived_addendum_source>`). The teammate audits the
cumulative PR diff (`gh pr diff <N>`) instead of a single loop's incremental
patch; clean-room context is preserved by the same agent-team isolation as
the per-loop bugfind teammate. Findings are posted using the same Step 2.5
review-shape with body `## /bugteam INITIAL standards review against PR #<N>
cumulative diff: <P0>P0 / <P1>P1 / <P2>P2`. Findings advance the audit/fix
cycle exactly as if they had been raised in Loop 1: the lead increments
`loop_count` to 1, sets `last_action = "audited"` with the merged
`last_findings`, and Step 3 begins on the FIX branch. When the INITIAL
review returns zero findings, `loop_count` stays at 0 and Step 3 begins on
the AUDIT branch as before. Failure on this phase logs the error and
proceeds to Step 3 unchanged so the legacy A–J cycle still runs.
```

**Insertion site 3 — between the existing Step 3 cycle exit and Step 4 ("Teardown").** Add a new section:

```
### Step 3.5: FINAL standards review (once, after convergence)

Run AFTER Step 3 exits with `converged`, `cap reached`, or `stuck`, and
BEFORE Step 4 teardown. Spawn one more fresh `code-quality-agent` teammate;
audit the cumulative PR diff against the K–N addendum a second time. Post
the review with body `## /bugteam FINAL standards review against PR #<N>
cumulative diff: <P0>P0 / <P1>P1 / <P2>P2`. When findings remain, the
exit reason is upgraded to `error: final standards review found <P0>+<P1>+<P2>
unresolved finding(s)` and the loop log gains an extra `final-review` line.
A clean FINAL review preserves the existing exit reason. Failure on this
phase logs the error and continues to Step 4 unchanged so teardown,
permission revoke, and the final report still run.
```

**Insertion site 4 — Step 6 final report template (SKILL.md lines 308-320).** Extend the loop log section so both new phases appear:

```
Loop log:
  initial standards review: 1P0 0P1 2P2
  1 audit: 3P0 2P1 0P2
  ...
  final standards review: 0P0 0P1 0P2
```

**Verification step:**

```
gh pr diff 70 -R JonEcho/python-automation > /tmp/pr70.diff && gh pr diff 73 -R JonEcho/python-automation > /tmp/pr73.diff && /bugteam --dry-run --replay 70 73
```

Followed by reading `<team_temp_dir>/pr-70/initial-review.outcomes.xml` and `final-review.outcomes.xml` to confirm Copilot finding ids 3153098661, 3153098689, 3153098727, 3153098762, 3153098782, 3153475246, 3153475297, 3153475331 are surfaced as new entries in either the INITIAL or FINAL review (or both) and that `Step 3.5` upgrades the exit reason when any P0/P1 finding remains.

### c. `~/.claude/skills/bugteam/scripts/bugteam_code_rules_gate.py`

**Insertion site:** new module-level helper functions immediately after `is_code_path` (gate.py:237-239), and a new top-level call inside `run_gate` (gate.py:379-443) that augments `validate_content`'s output. The new detectors live in this file (not in `code_rules_enforcer.py`) when their false-positive rate is too high for write-time blocking but still acceptable for the bugteam gate's coarser granularity. The collection-prefix and library-print detectors below are also added to `code_rules_enforcer.py` (§d) so they reach Write/Edit; the column-name string-literal detector below is bugteam-only.

**Detector 1 — column-name string magic values (rubric M deterministic backstop):**

```python
def check_database_column_string_magic(content: str, file_path: str) -> list[str]:
    """Flag string literals that look like database/HTTP column or key names inside function bodies.

    Triggers when a string literal matches the snake_case shape used by SQL
    column names and table identifiers and appears as a tuple element, list
    element, dict key, dict value, or function-call argument inside a
    function body. Files under ``config/`` and test files are exempt.
    """
    if "/config/" in file_path.replace("\\", "/") or "\\config\\" in file_path:
        return []
    if "/tests/" in file_path.replace("\\", "/") or file_path.endswith(("_test.py", ".spec.py")):
        return []
    issues: list[str] = []
    column_name_shape = re.compile(r'"([a-z][a-z0-9_]{2,})"|\'([a-z][a-z0-9_]{2,})\'')
    inside_function = False
    function_def_pattern = re.compile(r"^\s*(async\s+)?def\s+\w+")
    class_def_pattern = re.compile(r"^\s*class\s+\w+")
    builder_context_pattern = re.compile(r"\b(column|columns|fields|keys|select|insert|update|where|table)\b", re.IGNORECASE)
    for line_number, each_line in enumerate(content.splitlines(), 1):
        if function_def_pattern.match(each_line):
            inside_function = True
            continue
        if class_def_pattern.match(each_line):
            inside_function = False
            continue
        if not inside_function:
            continue
        if not builder_context_pattern.search(each_line):
            continue
        for first_quote_match, second_quote_match in column_name_shape.findall(each_line):
            literal_text = first_quote_match or second_quote_match
            if not literal_text:
                continue
            if literal_text in {"true", "false", "none", "null"}:
                continue
            issues.append(
                f"Line {line_number}: Column-name string magic {literal_text!r} - extract to config"
            )
            if len(issues) >= 3:
                return issues
    return issues
```

Wired into `run_gate` (replace the body of the per-file loop in gate.py:387-414 so the new detector's output joins `issues`):

```python
        issues = validate_content(content, str(relative).replace("\\", "/"), old_content=content)
        issues.extend(check_database_column_string_magic(content, str(relative).replace("\\", "/")))
```

**Detector 2 — wrapper plumb-through (rubric N deterministic backstop, file-local only):**

```python
def check_wrapper_plumb_through(content: str, file_path: str) -> list[str]:
    """Flag public wrappers that drop optional kwargs of a same-file delegate.

    Walks the AST. For every public function (name does not start with '_'),
    if its body contains exactly one direct call to another same-file
    function and that delegate's signature accepts optional kwargs that the
    wrapper does not also accept, emit a finding with both line numbers.
    """
    if file_path.endswith((".js", ".ts", ".tsx", ".jsx")):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    function_signatures: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            optional_kwargs: set[str] = set()
            for each_kwonly, each_default in zip(node.args.kwonlyargs, node.args.kw_defaults):
                if each_default is not None:
                    optional_kwargs.add(each_kwonly.arg)
            function_signatures[node.name] = optional_kwargs
    issues: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("_"):
            continue
        wrapper_kwargs = function_signatures.get(node.name, set())
        for each_call in ast.walk(node):
            if not isinstance(each_call, ast.Call):
                continue
            if not isinstance(each_call.func, ast.Attribute):
                continue
            delegate_name = each_call.func.attr
            delegate_kwargs = function_signatures.get(delegate_name)
            if delegate_kwargs is None:
                continue
            missing = delegate_kwargs - wrapper_kwargs
            if missing:
                issues.append(
                    f"Line {node.lineno}: Wrapper {node.name!r} drops optional kwargs {sorted(missing)!r} of delegate {delegate_name!r}"
                )
                if len(issues) >= 3:
                    return issues
    return issues
```

Wire into `run_gate` the same way as Detector 1, by appending its output to `issues` immediately after the column-magic call.

**Imports:** add `import ast` to the top of `bugteam_code_rules_gate.py` (currently absent).

**Verification step:**

```
python C:/Users/jon/.claude/skills/bugteam/scripts/bugteam_code_rules_gate.py /tmp/pr70_writer.py /tmp/pr70_summary.py /tmp/pr73_constants.py /tmp/pr73_writer.py /tmp/pr73_tracker.py
```

Expected output after the patch lands: at minimum one `Column-name string magic 'theme_name' - extract to config` line on `pr70_writer.py` (Copilot id 3153098661) and one `Wrapper 'flush' drops optional kwargs ['loud_banner_stream'] of delegate 'flush'` line on `pr73_tracker.py` (Copilot id 3153475331).

### d. `~/.claude/hooks/blocking/code_rules_enforcer.py`

The root-cause statement names write-time enforcement as the right layer for the collection-prefix and library-print rules, because both have a low false-positive rate and produce concrete, mechanical fixes. Both detectors plug into `validate_content` (enforcer.py:1936-1978) so they reach Write/Edit (the harness PreToolUse path) and the bugteam gate (which reuses `validate_content` via `load_validate_content`).

**Detector 1 — collection-prefix (rubric K deterministic backstop):**

```python
COLLECTION_TYPE_NAMES: frozenset[str] = frozenset({
    "list", "tuple", "set", "frozenset", "dict",
    "Iterable", "Sequence", "Mapping", "MutableMapping", "FrozenSet",
})
COLLECTION_BY_NAME_PATTERN: re.Pattern[str] = re.compile(r"^[a-z][a-z0-9]*_by_[a-z][a-z0-9_]*$")


def _annotation_names_collection(annotation_node: ast.expr | None) -> bool:
    if annotation_node is None:
        return False
    if isinstance(annotation_node, ast.Name):
        return annotation_node.id in COLLECTION_TYPE_NAMES
    if isinstance(annotation_node, ast.Subscript):
        return _annotation_names_collection(annotation_node.value)
    if isinstance(annotation_node, ast.Attribute):
        return annotation_node.attr in COLLECTION_TYPE_NAMES
    return False


def check_collection_prefix(content: str, file_path: str) -> list[str]:
    if is_test_file(file_path):
        return []
    if is_workflow_registry_file(file_path) or is_migration_file(file_path):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    issues: list[str] = []
    for node in tree.body:
        target_name: str | None = None
        target_line = 0
        is_collection_value = False
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target_name = node.target.id
            target_line = node.lineno
            is_collection_value = _annotation_names_collection(node.annotation)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            target_name = node.targets[0].id
            target_line = node.lineno
            is_collection_value = isinstance(node.value, (ast.Tuple, ast.List, ast.Set, ast.Dict))
        if target_name is None or not is_collection_value:
            continue
        if not UPPER_SNAKE_CONSTANT_PATTERN.match(target_name):
            continue
        if target_name.startswith("ALL_") or COLLECTION_BY_NAME_PATTERN.match(target_name.lower()):
            continue
        issues.append(
            f"Line {target_line}: Collection constant {target_name} - prefix with ALL_ (CODE_RULES §5)"
        )
        if len(issues) >= MAX_ISSUES_PER_CHECK:
            break
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for each_arg in _collect_annotated_arguments(node):
            if not _annotation_names_collection(each_arg.annotation):
                continue
            if each_arg.arg in {"self", "cls"}:
                continue
            if each_arg.arg.startswith("all_") or COLLECTION_BY_NAME_PATTERN.match(each_arg.arg):
                continue
            issues.append(
                f"Line {each_arg.lineno}: Collection parameter {each_arg.arg} - prefix with all_ (CODE_RULES §5)"
            )
            if len(issues) >= MAX_ISSUES_PER_CHECK:
                return issues
    return issues
```

**File-path filter:** Python files only (`extension in PYTHON_EXTENSIONS`); `is_test_file` / `is_config_file` / `is_workflow_registry_file` / `is_migration_file` exempt families.

**Corrective error message:** `Line N: Collection constant FOO - prefix with ALL_ (CODE_RULES §5)` and `Line N: Collection parameter foo - prefix with all_ (CODE_RULES §5)`.

**Detector 2 — library print (rubric L deterministic backstop):**

```python
CLI_FILE_PATH_MARKERS: tuple[str, ...] = ("/scripts/", "\\scripts\\", "_cli.py", "/cli.py", "\\cli.py")


def _is_cli_entry_point(file_path: str) -> bool:
    path_lower = file_path.lower().replace("\\", "/")
    return any(marker.replace("\\", "/") in path_lower for marker in CLI_FILE_PATH_MARKERS)


def check_library_print(content: str, file_path: str) -> list[str]:
    if is_test_file(file_path) or is_config_file(file_path) or is_hook_infrastructure(file_path):
        return []
    if _is_cli_entry_point(file_path):
        return []
    if get_file_extension(file_path) not in PYTHON_EXTENSIONS:
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    issues: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function_reference = node.func
        if isinstance(function_reference, ast.Name) and function_reference.id == "print":
            issues.append(
                f"Line {node.lineno}: Library print() - route through logger or accept an explicit stream parameter"
            )
        elif isinstance(function_reference, ast.Attribute) and function_reference.attr == "write":
            value_node = function_reference.value
            if isinstance(value_node, ast.Attribute) and isinstance(value_node.value, ast.Name):
                if value_node.value.id == "sys" and value_node.attr in {"stdout", "stderr"}:
                    issues.append(
                        f"Line {node.lineno}: sys.{value_node.attr}.write - route through logger"
                    )
        if len(issues) >= MAX_ISSUES_PER_CHECK:
            break
    return issues
```

**File-path filter:** Python only; CLI entry points (`/scripts/`, `*_cli.py`, `cli.py`), hook infrastructure, config files, and test files exempt.

**Corrective error message:** `Line N: Library print() - route through logger or accept an explicit stream parameter` (and the parallel `sys.stdout.write` / `sys.stderr.write` form).

**Wire-up in `validate_content`** — append two new lines inside the `if extension in PYTHON_EXTENSIONS:` block of `validate_content` (enforcer.py:1948-1968), immediately after `check_unused_optional_parameters`:

```python
        all_issues.extend(check_collection_prefix(content, file_path))
        all_issues.extend(check_library_print(content, file_path))
```

**Verification step:**

```
python -c "import importlib.util, sys; spec=importlib.util.spec_from_file_location('e','C:/Users/jon/.claude/hooks/blocking/code_rules_enforcer.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); content=open('/tmp/pr73_constants.py').read(); print(m.check_collection_prefix(content,'shared_utils/theme_db/config/constants.py'))"
```

Expected output after the patch lands: a list containing `Line 91: Collection constant THEMES_INSERT_REQUIRED_COLUMN_NAMES - prefix with ALL_ (CODE_RULES §5)`. The same command against `/tmp/pr73_writer.py` (Copilot id 3153475297) emits `Line 296: Collection parameter column_value_pairs - prefix with all_ (CODE_RULES §5)`. Replacing the call with `m.check_library_print` against `/tmp/pr70_summary.py` (Copilot id 3153098727) emits at minimum one `Line 256: Library print() - …` line.

**Justification for touching `code_rules_enforcer.py`:** the root-cause statement names write-time enforcement as the right layer for collection-prefix and library-print, because both rules in `CODE_RULES.md §5` are mechanical (no judgment), produce concrete fixes, and were the dominant source of follow-up Copilot findings (3 of 8 inventory rows). The bugteam pre-flight gate alone is insufficient — it only fires before each AUDIT, so a clean-coder fix pass that introduces a new violation lives unblocked until the next gate run; write-time enforcement closes that window.

---

## Cross-references

- Inventory data sources: live `gh api repos/JonEcho/python-automation/pulls/{70,73}/comments` filtered to `Copilot`; verbatim bodies preserved in the inventory table above.
- Original-commit content used to confirm violations: PR #70 head `29117309cf4ec1e83883160d8c819e0843f9c3ac`; PR #73 review-time commit `e4abf52c3a6c724b4e64bfed0d979cd60a2c8bf0`; PR #73 merged head `c9c935a96cc59d39d623dc7eddda3d341007607c`.
- CODE_RULES.md sections invoked by the patch plan: §⚡ Magic values; §5 Extended naming rules (collections `all_orders`, `all_users`); §6.5 File length guidance; §7 Right-Sized Engineering; §10 No redundant data fetches (used as analogue for wrapper plumb-through).
- Constraints honored: `gh-body-file` (no `gh ... --body` calls in the new code paths), `no-shell-substitution` (no `$(...)` in the verification commands above; multi-step shell flows are written as separate Bash invocations or `&&`-chained literal strings).
