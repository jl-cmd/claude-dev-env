# doc-gist/scripts

Transport script and supporting constants for the `doc-gist` skill.

## Files

| File | Purpose |
|---|---|
| `gist_upload.py` | Core transport: reads HTML from a file path or stdin, runs `gh gist create`, prints `Gist:` and `Preview:` URLs to stderr, prints the preview URL to stdout, and opens it in the default browser (unless `--no-open`). |
| `test_gist_upload.py` | Tests for `gist_upload.py`. |

## Subdirectories

| Directory | Role |
|---|---|
| `doc_gist_scripts_constants/` | Named constants imported by `gist_upload.py` (URL prefixes, default filename, timeout). |

## CLI usage

```
python gist_upload.py --input <path-or-stdin>
                      [--filename gist-file.html]
                      [--description "short label"]
                      [--no-open]
```

Pass `--input -` to read from stdin. The auto-publish hook calls this script with the written file's path; the skill body documents when to call it manually.
