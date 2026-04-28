---
name: rebase
description: Rebase a branch onto its base ref with the verification gates needed to catch logically broken results before pushing. Use when the user invokes `/rebase`, says "rebase this branch", "PR has merge conflicts", "rebase onto main", or asks for a force-push to update a remote branch's history. Critical for stacked PRs where the base merged via squash, and for any rebase that includes deletions or renames.
---

# /rebase

Rebase the current branch (or a named branch's worktree) onto its correct base ref. Resolve conflicts. Verify the result is **logically correct**, not just textually clean. Push only after explicit authorization.

The default failure mode is shipping a rebase that compiled but doesn't run. This skill exists to prevent that.

## When to rebase vs. merge

**Default to rebase** when:

- Solo branch (you are the only author of the commits being rebased).
- 1–5 commits ahead of base.
- Stacked PR whose base just merged via squash.

**Default to merge** when:

- Branch has multiple authors (force-push would clobber their state).
- More than ~5 commits or more than ~2 weeks of divergence (rebase complexity grows non-linearly).
- The user said "merge", not "rebase".
- Open PR with approving reviews already on the current SHA (force-push invalidates them).

When in doubt, ask. Both work; the choice affects history shape, not correctness.

## Phase 1 — Pre-rebase analysis

1. **Resolve the canonical base.** Stacked-PR base refs change when the base PR merges. Always re-resolve:

   ```
   gh pr view <N> --json baseRefName,mergeable,mergeStateStatus
   ```

   Trust GitHub's `baseRefName`, not whatever the local branch was originally based on.

2. **Identify the rebase scenario.** Three playbooks:

   | Scenario | Signal | Approach |
   |---|---|---|
   | Stacked PR, base merged via squash | base PR `state: MERGED`, base ref redirected to main | Rebase onto main; expect to `--skip` the squash-absorbed commit |
   | Stacked PR, base still open | base PR `state: OPEN` | Rebase onto base PR's tip, not main |
   | Long-lived feature branch | many commits, no stacking | Straight `rebase origin/main` |

3. **Fetch fresh.** `git fetch origin <base-ref> <head-ref>` before starting. Stale local refs cause false conflicts.

4. **Read every rebased commit's message.** Author intent lives in commit messages ("removes orphan constants X, Y, Z"). For every named symbol mentioned as deleted or renamed, scan `origin/main` for new consumers — if main has new uses of those symbols, the rebase will produce broken state without conflicting at the textual level.

   **Tool preference for symbol scans** (in order):

   | Tool | Use when | Example |
   |---|---|---|
   | `mcp__serena__find_symbol` / `find_referencing_symbols` | Symbol-aware language server is available — definition vs. reference distinction matters, and you want call-site context | `find_referencing_symbols(symbol_name)` returns every caller with file/line and surrounding code |
   | `mcp__zoekt__search_symbols` / `search` | Cross-repo or large codebase indexed in zoekt; faster than grep on big trees | `search(query)` returns ranked matches with snippets |
   | `Grep` tool (ripgrep) | Local single-repo plain-text scan; no symbol awareness needed | `Grep(pattern, type="py")` — much faster than shell `grep` and respects `.gitignore` |
   | `grep -rn` | Last resort; only when the above are unavailable | — |

   The Grep tool is the default for plain-text scans (faster than shell grep, respects gitignore). Reach for serena when you need to distinguish "this name is defined here" from "this name is referenced here," which catches false positives from comments, docstrings, and string literals. Reach for zoekt for cross-repo scans.

   This is the bug that hides best. Don't skip it.

## Phase 2 — During rebase

5. **`--skip` only after verifying content overlap.** When a commit fails to apply because main already has its content (squash-merge case), confirm the content is actually equivalent:

   ```
   git diff <skipped-commit> origin/<base> -- <files-touched-by-skipped-commit>
   ```

   Skip only after that diff shows the equivalent content lives in main. Don't skip on the heuristic "main is downstream."

6. **Audit auto-merged files.** Files that git merged without conflict markers are not automatically correct. After each commit applies, run:

   ```
   git diff --name-only --diff-filter=M HEAD@{1}
   ```

   For each modified file with no conflict markers, eyeball the changes — auto-merge can produce duplicate blocks (when both sides added similar content) or silently drop content (when both sides removed adjacent lines). Pay extra attention to `config/`, `constants.*`, and `__init__.py` files where additions often sit near each other.

7. **At every conflict, take both sides' intent seriously.** Read both, then decide based on the post-rebase logical state. Do not reflex-pick HEAD or `origin/main`. Document the resolution reasoning in the commit message if it is non-obvious.

## Phase 3 — Verification gates (mandatory before push)

`py_compile`, `tsc --noEmit`, `cargo check`, etc. validate **syntax and types**, not **import resolution and runtime correctness**. Run real checks:

8. **Real import check.** For Python:

   ```
   python -c "import <every_top_level_module_in_changed_packages>"
   ```

   This catches the most common rebase failure: an import that survived the rebase pointing at a name the rebased commits removed or renamed.

9. **Test collection.** `pytest --collect-only -q` on the changed packages catches NameError, AttributeError, and ImportError surfaces beyond plain imports.

10. **Targeted test run.** Run the test suite for every package the rebase touched. Do not push a rebase that dropped or broke test coverage that was passing pre-rebase.

11. **Reference scan for removals/renames.** For every symbol the rebase deleted or renamed (per the commit messages from step 4), scan the post-rebase tree using the same tool-preference order as step 4:

    - **Preferred:** `mcp__serena__find_referencing_symbols` (symbol-aware; ignores false matches in comments and string literals).
    - **Fallback:** `mcp__zoekt__search` for cross-repo or large trees.
    - **Then:** the `Grep` tool (e.g., `Grep(pattern="<symbol>", type="py")`) for fast in-repo scans.
    - **Last resort:** `grep -rn "<symbol>" --include='*.py' --include='*.ts' --include='*.json' .`

    Any reference outside the rebased commits' own changes is a stale reference. Either update it (with user authorization) or surface it and refuse to push.

12. **"Unchanged" files are not safe.** A rebase can break files it never textually modified if their imports depend on something the rebase removed or renamed. List `git diff --name-only origin/<base>..HEAD`, then for every file NOT in that list but that imports from a file IN that list, manually verify the imports still resolve.

## Phase 4 — Push

13. **Force-push requires explicit authorization.** Auto mode does not bypass this. Before any `git push --force` or `--force-with-lease`:

    - State the rewrite scope: "this rewrites N commits of remote history on branch `<name>`".
    - State the branch's PR state: "PR #M is OPEN with K approving reviews on the current SHA" (force-push invalidates approvals).
    - Ask for explicit authorization.
    - If denied: leave the rebase result locally, report merge-instead as the alternative, stop.

14. **Refuse to force-push** `main`, `master`, `release/*`, `production`, or any branch with more than one author in `git log --format='%ae' origin/<branch> | sort -u`. Surface the refusal; do not ask for authorization on these.

15. **Always `--force-with-lease=<branch>:<sha>`**, never bare `--force`. Pin the lease to the SHA you started from so concurrent pushes are detected as a lease mismatch instead of clobbered.

16. **Confirm mergeability** post-push:

    ```
    gh pr view <N> --json mergeable,mergeStateStatus,headRefOid
    ```

    Expect `mergeable: MERGEABLE`, `mergeStateStatus: CLEAN`. Anything else means the rebase didn't actually unblock the PR — investigate before declaring done.

## Anti-patterns (the failure modes this skill prevents)

- **`py_compile` exit 0 → "verified"**. Wrong. Syntax-clean is not import-clean. Always run a real `import` check.
- **Skipping squash-absorbed commits without diff verification.** Heuristically usually right, occasionally wrong, never confirmed without the diff.
- **Auditing only `git diff --name-only`.** Files unchanged by the rebase can still break if their imports depended on what the rebase removed.
- **Force-pushing under "the user asked me to fix the conflicts" interpretation.** Force-push is a separate authorization from "fix this." Ask.
- **Bare `--force` instead of `--force-with-lease=<branch>:<sha>`.** Loses the safety net against concurrent pushes.

## Quick decision flowchart

```
Branch shared with others?  ──► merge instead
Stacked PR, base merged?    ──► rebase onto main, expect --skip
Stacked PR, base open?      ──► rebase onto base PR tip
Solo, ≤5 commits ahead?     ──► straight rebase

After rebase, BEFORE push:
  python -c "import …"      ──► must succeed
  pytest --collect-only     ──► must succeed
  targeted pytest run       ──► must pass
  symbol scan (serena → zoekt → Grep) ──► no stale references

Push:
  not main/master/release   ──► force-with-lease, ask first
  main/master/release       ──► refuse
```
