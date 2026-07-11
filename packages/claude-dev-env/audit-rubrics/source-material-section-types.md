# What "section" means in the source-material block

Audit prompt templates ask you to inline the artifact under audit, broken into "sections." A section is **the natural chunk you'd quote and reference back to when reporting a finding.** The right chunk size depends on what you're auditing.

## Lookup table

| If you're auditing… | A "section" is… | What you put in the code fence |
|---|---|---|
| A code PR | One file in the diff | Filename as header, full file content |
| A long Python module by itself | One function or class | Function name as header, just that function's body |
| A design doc / RFC | One named heading (e.g. "## Authentication") | The heading + all paragraphs under it |
| An essay or article | One section break or chapter | Section title + the paragraphs |
| A contract or terms-of-service | One clause | Clause number + clause text |
| A meeting transcript | One topic or speaker block | Topic name + the dialogue |
| An email thread | One message | Sender + timestamp + message body |
| A spreadsheet | One sheet or one logical table | Sheet name + the rows |
| A SQL schema | One table definition | Table name + the CREATE TABLE statement |
| A config file | One stanza | Stanza name + the keys/values |
| A test suite | One test file | Filename + all the test functions |

## Picking the right size

The rule: **pick the chunk size that lets the agent cite a finding with `[section name]:[line/paragraph N]` and have the user know exactly where to look.**

- **Too small** (one sentence per section): the agent runs out of context per chunk and findings can't reference cross-chunk patterns.
- **Too big** (the whole document as one section): the agent can't anchor findings to a specific spot, and the `failure_mode` text becomes vague.
- **Sweet spot in the May 2026 audit experiment on PR #394**: 4 files, 11–102 lines each. Each finding cited `<filename>:<line>` and was easy to verify. Results were better than the same audit run with the diff fetched on demand instead of inlined.

## Header format inside the source-material block

Use one `###` header per section so the agent can reference each one by name:

````
## Source material (4 files, all lines in scope)

### packages/foo/bar.py
```python
[content]
```

### packages/foo/baz.py
```python
[content]
```
````

The header text becomes the anchor the agent quotes back when reporting findings — keep it stable, unambiguous, and copy-pasteable into a citation.

## When the artifact has no natural section breaks

If you're auditing something monolithic (a single long function, a contract with no clauses, a stream of dialogue), impose your own breaks at logical hinge points and label them: `### lines 1–40 (parameter parsing)`, `### lines 41–120 (main loop)`, `### lines 121–200 (cleanup)`. Don't hand the agent a wall of text — without anchors, findings degrade to "somewhere in this file."
