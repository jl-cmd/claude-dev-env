# doc-gist/scripts/doc_gist_scripts_constants

Named constants for `gist_upload.py`. Importing from this package keeps all URL templates, default filenames, and timeout values out of the script body.

## Modules

| File | Constants |
|---|---|
| `gist_upload_constants.py` | `GIST_HOST_PREFIX` — base URL for parsing gist output; `PREVIEW_URL_TEMPLATE` — htmlpreview.github.io URL shape; `GIST_DEFAULT_FILENAME` — filename when input is stdin; `MINIMUM_GIST_URL_PARTS` — fewest path segments in a valid gist URL; `UPLOAD_TIMEOUT_SECONDS` — subprocess timeout for `gh gist create`. |
| `__init__.py` | Empty package marker. |
