# ntfy Message Body

Fill this template, then pass the title as `--title` and the filled body as
`--message` to `scripts/notify_ntfy.py`. Pass the review URL as `--click-url` so
tapping the page opens the Copilot review.

## Title line

```
Copilot code concern on PR {pr_number}: {short_pr_title}
```

## Body

```
{finding_count} code concern(s) need your call on PR {pr_number} ({head_sha}):

- {file_1}:{line_1} — {severity_1} — {one_sentence_concern_1}
- {file_2}:{line_2} — {severity_2} — {one_sentence_concern_2}

Review: {review_url}
Reply within 45 minutes or the run tears down and reports these findings unreviewed.
```

## Field notes

- `{finding_count}` counts the CODE CONCERN findings on this HEAD, not the
  self-healing ones.
- Each bullet holds one finding: its `file:line`, its severity, and one sentence
  naming the concern.
- `{review_url}` is the same URL passed as `--click-url`, so the reader sees it
  in the body and reaches it by tapping the message.
- The 45-minute clock starts when the page reaches the user, which is the moment
  `scripts/notify_ntfy.py` exits zero.
