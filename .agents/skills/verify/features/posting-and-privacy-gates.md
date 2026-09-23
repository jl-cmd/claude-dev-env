# Posting and privacy gates

Every GitHub post passes a local linter before it leaves the machine. CI scans each pull request, issue, comment, review, and release for a private organization name. The committed tree fails when a file names one. A PNG shrinks with oxipng before any upload. The pull requests that built this path are #1427, #1428, #1465, #1467, #1468, #1470, and #1471.

## Sub-features

- `packages/claude-dev-env/scripts/durable_post_lint.py` checks one post before publication. It checks the Conventional Commit title, the `## Why` and `## Verification` headings on a pull request description, contrast framing, volatile local paths, private organization names, and a rewritten release body.
- `packages/claude-dev-env/.agents/skills/pull-request/scripts/pull_request.py` runs that linter first and calls `gh` only on a clean result. It creates every pull request as a draft.
- `packages/claude-dev-env/scripts/private_term_scan.py` runs in `.github/workflows/private-terms.yml`. It scans the event text and, on a pull request, every commit message and author identity in `base..head`.
- `packages/claude-dev-env/scripts/private_terms.py` holds the matcher. It compares SHA-256 digests of normalized text windows, so no file stores the names.
- `packages/claude-dev-env/scripts/repository_policy.py` runs the `tracked-private-terms` and `tracked-secrets` checks. Both are breaking. A repository whose github.com origin owner is itself a private organization passes `tracked-private-terms`, because that organization may name itself.
- `config/repository-policy.json` in a consumer repository owns its `email_exemptions` and `private_ip_exemptions`. Each entry holds `path`, `sha256` of the matched text, and `reason`.
- `packages/claude-dev-env/scripts/gh_artifact_upload.py` uploads a file to the `artifacts` prerelease and prints its download URL. A PNG passes through `oxipng --opt 4 --strip none --nb --nc` on a staged copy first.
- `.github/workflows/binary-optimization.yml` fails a pull request whose changed PNG files still shrink under that oxipng pass.
- `.gitleaks.toml` adds the personal-data rules. The `committed-tree` job in `.github/workflows/ci-tests.yml` runs gitleaks 8.30.1 on the added commits.

## How to get to it (user POV)

An agent opens a pull request through the `pull-request` skill, posts a comment through a GitHub MCP tool, or attaches a screenshot. The linter reports the first bad line before the post reaches GitHub. When a post bypasses the linter, the `Private terms` check reports the line number of the private name and never prints the name.

## Driving it with the package

Run each command from the repository root. Write each body file under the scratchpad directory.

```
python packages/claude-dev-env/scripts/durable_post_lint.py --action pr-create --title "docs(skills): add a map" --body-file <body>
python packages/claude-dev-env/scripts/durable_post_lint.py --action issue-comment --body-file <body> --repository <owner>/<name>
python packages/claude-dev-env/scripts/private_term_scan.py --event-path <event.json> --commit-range origin/main~5..origin/main
python packages/claude-dev-env/.agents/skills/pull-request/scripts/pull_request.py create --repo <owner>/<name> --base main --head <branch> --title "<title>" --body-file <body>
python packages/claude-dev-env/scripts/repository_policy.py
```

Expected results:

| Input | Output | Exit |
|---|---|---|
| Conventional title, body with `## Why` and `## Verification` | nothing | 0 |
| Title `Add a map` | `pull request title does not use the repository Conventional Commit form` | 1 |
| `pr-create` body with neither heading | `body is missing required heading: Why`, then `Verification` | 1 |
| Body naming `/tmp/run/log.txt` | `body contains a volatile local artifact path` | 1 |
| Body line `We park it rather than fix it.` | `Contrast framing (substitution-rather-than): ...` | 1 |
| `--head-branch release-please--branches--main` with a rewritten body | `release automation reads this body back ...` | 1 |
| `--action pr-post`, a `pr-create` without `--title`, or a missing body file | a usage message | 2 |
| Event JSON with clean title and body | nothing | 0 |
| `pull_request.py` with title `Add a map` | the linter message, and no `gh` call | 1 |
| `repository_policy.py` on a clean checkout | nothing | 0 |

The test suites cover the private-name, private-address, and oxipng paths with their own fixtures:

```
python -m pytest packages/claude-dev-env/scripts/test_durable_post_lint.py packages/claude-dev-env/scripts/tests/test_private_term_scan.py packages/claude-dev-env/scripts/tests/test_private_terms.py packages/claude-dev-env/scripts/tests/test_tracked_private_terms.py packages/claude-dev-env/scripts/tests/test_match_exemptions.py packages/claude-dev-env/scripts/tests/test_tracked_secrets.py packages/claude-dev-env/scripts/tests/test_gh_artifact_upload.py packages/claude-dev-env/.agents/skills/pull-request/scripts/test_pull_request.py -q
```

## Gotchas

- This repository is public. A positive private-name drive stays in the test fixtures, which patch `ALL_PRIVATE_TERM_DIGESTS`. Never type a private name into a file, a commit, a body, or a log here.
- `--repository <owner>/<name>` lets a post name the organization that owns the target repository. A post with no `--repository` may name no private organization.
- `pr-edit` takes a title, a body file, or both. `pr-create` requires a title. Only those two actions accept a title.
- A release-please head branch skips the heading and contrast checks. Its body must keep both generated marker lines whole.
- `gh_artifact_upload.py` creates the `artifacts` prerelease before it looks for oxipng. A PNG upload on a machine with no oxipng fails after the release exists.
- `test_timestamped_asset_name_prefixes_basename` passes a Windows path. It fails on Linux and runs in the `windows-semantics` job, which reads `.github/ci/windows-semantics-node-ids.txt`.
- A PNG whose exact bytes a test pins takes `binary-optimizer=keep` in `.gitattributes`, and the binary optimization check skips it.
- A duplicate exemption entry in `config/repository-policy.json` stops the policy run. An entry clears one address at one path, and the same address at another path still reports.
