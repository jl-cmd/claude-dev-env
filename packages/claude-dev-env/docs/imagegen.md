# Image generation

The canonical image-generation entrypoint lives in the
`python-automation` repository at `shared_utils.imagegen`.

Resolve `python_automation_root` and `python_exe` from the repository's
`run/tooling.json`, set `PYTHONPATH` to the resolved root, and run:

```powershell
$tooling = Get-Content '<REPO>\\run\\tooling.json' | ConvertFrom-Json
$python_automation_root = $tooling.python_automation_root
$python_executable = $tooling.python_exe
$env:PYTHONPATH = $python_automation_root

& $python_executable -m shared_utils.imagegen `
  --prompt-file <PROMPT.txt> `
  --size 2880x2880 `
  --out <IMAGE.png>
```

Repeat `--reference-image <IMAGE.png>` for up to two visual references.
The command verifies the decoded PNG dimensions before reporting success.
