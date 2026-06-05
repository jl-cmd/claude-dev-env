Audit [REPO/ARTIFACT] [TARGET_ID] for **Category H only** (security boundaries). Skip A–G, I–N. Sub-bucket forced-exhaustion mode: Category H is decomposed into 10 sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

## ARTIFACT METADATA — trust model

[Describe the artifact under audit: what it is, how it is invoked, who invokes it, and what privilege it runs with. Then explicitly name the **trust model**:]

- **Who is the attacker?** [remote unauthenticated caller / authenticated tenant / co-located process / operator-only / no attacker surface — pick one and justify]
- **What input do they control?** [enumerate every attacker-reachable input: HTTP params, headers, request body, file uploads, CLI args, env vars, config files, message-queue payloads, RPC arguments, filenames, database rows, etc.]
- **Privilege boundary being crossed:** [what does the attacker gain by compromising this surface — code execution, data exfiltration, lateral movement, denial of service, privilege escalation?]
- **What is NOT in scope:** [explicitly name behaviors that look like H findings but are operator-authority-by-design rather than privilege-boundary violations.]

ID prefix: `find`.

## Source material

[Inline the artifact under audit here — diff, file contents, or both. Follow the chunking guide at `../source-material-section-types.md` for how to structure long artifacts. Each line cited in a finding must be reachable from the inlined material.]

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**H1. SQL injection**
- Surface check: any SQL driver, ORM, or query-builder reachable from attacker-controlled input?
- Shape A pattern: string concatenation / f-string / `%`-formatting building a query that includes attacker input; ORM `raw()` / `execute()` with interpolated text; dynamic table or column names from request input.
- Shape B probes (when no SQL surface exists): (1) full-text scan for `SELECT`, `INSERT`, `UPDATE`, `DELETE`, `execute(`, `executemany(`, `.raw(`, ORM imports. (2) Scan for any string built with `+`, `%`, or f-string that could later flow into a SQL driver via an imported helper. (3) Verify no template-string construction in scope flows into a SQL pathway through indirect imports or dynamic dispatch.

**H2. Command injection**
- Surface check: any `subprocess`, `os.system`, `os.popen`, `shell=True`, backticks, `Invoke-Expression`, PowerShell `-Command` with interpolated input, `eval`-on-shell-string, or template-into-shell pattern reachable from attacker input?
- Shape A pattern: f-string / format / concat building a shell command line that includes attacker-influenced text; `subprocess.run(..., shell=True)` with composed argv; PowerShell `-Command "…$var…"` with interpolated variables; argv-shape drift where the command line is parsed twice (once by the shell, once by the C runtime / `CommandLineToArgvW`).
- Shape B probes (when no shell surface exists): (1) grep for `subprocess.`, `os.system`, `os.popen`, `shell=True`, `Invoke-Expression`, `-Command`, `pty.spawn`, `commands.getoutput`. (2) Verify no library import indirectly invokes a shell (e.g., `git.Repo(..., shell=True)`-style wrappers). (3) Confirm any process-launch site uses argv-list form with no string interpolation into argv[0] or argv[1].

**H3. Path traversal**
- Surface check: any filesystem operation (`open`, `os.walk`, `os.rmdir`, `Path(…).read_text`, `shutil.copy`, `Get-Content`, `Test-Path`, `Remove-Item`) whose path is built from attacker-controlled input?
- Shape A pattern: user input joined to a base path without `realpath`/`normpath` and without a containment check verifying the resolved path stays under the intended root; symlink-following enabled where it shouldn't be; UNC / device-namespace paths (`\\?\`, `\\.\`) accepted without filtering; trailing-dot or trailing-space Windows pathname tricks.
- Shape B probes (when no traversal surface exists): (1) `os.walk` / equivalent does not follow symlinks (`followlinks=False` in Python; `-NoFollowSymlink` semantics in PowerShell). (2) UNC / drive-letter / reparse-point handling — document whether the artifact honors them as given (operator authority) or rejects them. (3) Path normalization — does the code call `realpath`/`normpath` before filesystem ops? (4) TOCTOU between any pre-flight check (`isdir`, `Test-Path`) and the actual filesystem op. (5) Pre-flight gate identification — what is the only validation between attacker input and the filesystem syscall?

**H4. Authentication bypass**
- Surface check: any HTTP / RPC / IPC entry point that should require authentication?
- Shape A pattern: missing auth decorator on a sensitive route; auth check that compares to a constant short-circuit; cookie or token validation that trusts a client-supplied claim without verification; session fixation; auth gated only by client-side state.
- Shape B probes (when no auth surface exists): (1) grep for `auth`, `token`, `session`, `cookie`, `bearer`, `Authorization`, `password`, `credential`, `@login_required`, equivalent decorators. (2) Confirm no network listener is opened by the artifact (`socket.bind`, `http.server`, `Flask`, `FastAPI`, `aiohttp`, `Express`, `grpc.server`). (3) Confirm any privileged action (`-User`, `-RunLevel Highest`, `setuid`, sudo wrappers) is invoked with a static principal, not from attacker input.

**H5. Authorization checks**
- Surface check: vertical (admin vs user) and horizontal (user A vs user B) access controls on every state-changing or data-reading operation reachable by an authenticated caller.
- Shape A pattern: missing `is_admin` / role check; ownership lookup that trusts a caller-supplied `user_id` without comparing to the session principal; IDOR — incrementing-id resource access with no per-resource ownership check; tenant-isolation gap where one tenant's request reaches another tenant's row.
- Shape B probes (when no authorization surface exists): (1) grep for `is_admin`, `role`, `permission`, `owner_id`, `tenant`, `IDOR`, `current_user`, framework-specific role decorators. (2) Confirm state-changing operations are not gated only by URL knowledge or session membership without per-resource ownership. (3) Confirm no privilege escalates between caller principal and operation principal (e.g., a process registered to run as a different user than the registering caller).

**H6. Secret / credential leakage**
- Surface check: any code path that handles API keys, tokens, passwords, signing keys, database credentials, OAuth refresh tokens, JWTs, or other secrets?
- Shape A pattern: secret written to a log line, error message, stack trace, env-dump endpoint, telemetry payload, crash report, or test fixture; secret committed to source; secret exposed via verbose error in a non-debug build; secret returned in an HTTP response body to an unauthenticated caller.
- Shape B probes (when no secret surface exists): (1) grep for `key`, `token`, `secret`, `password`, `credential`, `bearer`, `private_key`, `client_secret`, `api_key`. (2) Verify error paths and exception handlers do not log environment, headers, or full request state. (3) Verify no `Get-Credential`, `ConvertFrom-SecureString`, `keyring.*`, secret-manager SDK call persists secrets to disk in plaintext.

**H7. SSRF / external request validation**
- Surface check: any outbound HTTP / network call (`requests.*`, `urllib.*`, `httpx.*`, `Invoke-WebRequest`, `Invoke-RestMethod`, `WebClient`, `HttpClient`, `fetch`, `axios`, `socket.connect`) whose URL or host is built from attacker input?
- Shape A pattern: URL parameter from request flowing into an outbound `requests.get` without an allowlist; protocol smuggling (`file://`, `gopher://`, `ftp://`); host parsing that diverges from the eventual connect (e.g., `urlparse` vs DNS resolution); cloud-metadata endpoint (`169.254.169.254`, `fd00:ec2::254`) reachable; redirect-following past the validated URL.
- Shape B probes (when no outbound network surface exists): (1) grep for `requests.`, `urllib`, `http.client`, `Invoke-WebRequest`, `Invoke-RestMethod`, `WebClient`, `HttpClient`, `fetch(`, `axios.`. (2) Verify any auxiliary network-adjacent call (`Get-Command`, `which`, `nslookup`) does not perform an attacker-influenced HTTP request. (3) Verify cloud-metadata endpoints (`169.254.169.254`, `metadata.google.internal`) are not mentioned and not reachable from any code path in scope.

**H8. CSRF / state-changing without token**
- Surface check: any state-changing HTTP handler (POST, PUT, DELETE, PATCH) reachable by an authenticated browser session?
- Shape A pattern: state-changing handler with no CSRF token validation; SameSite-cookie assumption used as the sole CSRF defense without verifying the framework actually sets it; pre-flight CORS check trusted as authentication; same-origin assumed without enforcement.
- Shape B probes (when no CSRF surface exists): (1) confirm no `@app.route`-style POST handler, no `@router.post`, no `flask.Flask`, no `fastapi.FastAPI`, no `aiohttp.web.RouteTableDef`, no Express `app.post`. (2) Confirm any local trigger surface (named pipe, Unix socket, COM endpoint, scheduled task) is local-only and not reachable by a remote unauthenticated caller. (3) Confirm no inter-process listener exists that an unprivileged caller could poke to trigger the state change.

**H9. Deserialization**
- Surface check: any code path that deserializes attacker-controllable bytes via a format that supports arbitrary code execution or object instantiation?
- Shape A pattern: `pickle.loads`, `marshal.loads`, `yaml.load` (without `SafeLoader`), `eval`, `exec`, `Import-Clixml`, `BinaryFormatter`, `ObjectInputStream`, `JsonConvert.DeserializeObject` with `TypeNameHandling.All`, against attacker-controllable bytes.
- Shape B probes (when no deserialization surface exists): (1) grep for `pickle`, `yaml.load`, `marshal`, `eval(`, `exec(`, `Import-Clixml`, `Deserialize-PSObject`, `BinaryFormatter`, `ObjectInputStream`. (2) Verify any JSON parser is invoked safely (`json.loads` without `object_hook` from attacker input; `JsonConvert` without `TypeNameHandling`). (3) Verify CLI / config parsing (`argparse.parse_args`, `configparser`, `tomllib`) does not deserialize beyond string typing.

**H10. File upload / MIME validation**
- Surface check: any code path that accepts a file from an attacker (multipart upload, paste-from-URL, stream-to-disk)?
- Shape A pattern: trusted Content-Type from client; missing extension allowlist; missing magic-byte verification; filename used directly as on-disk path; MIME-sniffing differences between server and downstream renderer; archive extraction without zip-slip protection.
- Shape B probes (when no upload surface exists): (1) grep for `multipart`, `UploadFile`, `request.files`, `werkzeug.FileStorage`, `fastapi.UploadFile`, `Content-Type`, `magic` (libmagic), `zipfile.extractall`. (2) Confirm the only filesystem-write operations in scope target paths the artifact controls, not paths derived from attacker input. (3) Confirm no archive (zip / tar / 7z) is extracted with attacker-supplied member paths.

## Cross-bucket questions to answer at the end

Q1: Are there any inputs that cross two H sub-buckets? (e.g., a path that flows through H3-style filesystem handling AND becomes an interpolated argument in an H2 shell command — are the two trust assumptions consistent across both sites?)
Q2: What's the worst injection / leakage hazard introduced by this artifact? Cite `<file>:<line>` for the specific construction.
Q3: Which input is most fragile to a future API addition — i.e., where would a future change most likely turn an operator-trust assumption into an actual attacker-reachable surface? Name the line(s) most likely to break.

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket H1-H10, produce Shape A or Shape B (with ≥3 probes). Cross-bucket Q1-Q3 answers after the per-sub-bucket walk. Adversarial second pass: "assume your first pass missed at least 3 P0/P1 vulnerabilities across these 10 sub-buckets — find them." Open Questions section for ambiguities. Read-only. No edits, no commits.

Note: Category H findings tend toward P0/P1 since they're security-relevant — adjust the adversarial-pass quota severity accordingly. If the artifact's trust model caps realistic findings below P1 (e.g., operator-only invocation with no remote attacker surface), the adversarial pass should still hunt P0/P1 by asking "what changes if this code is ever invoked from an untrusted context — a CI runner, a different user's session, a remote-management tool, a future HTTP wrapper?"

---

# Worked example: jl-cmd/claude-code-config PR #394

Audit jl-cmd/claude-code-config PR #394 for **Category H only** (security boundaries). Skip A–G, I–N. Sub-bucket forced-exhaustion mode: Category H is decomposed into 10 sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

PR: feat(scripts): add sweep-empty-dirs utility and scheduled-task installer
Head SHA: 62c9c169ee7a44824e5da25c4cf8b74fdca08a53
ID prefix: `find`.

## ARTIFACT METADATA — trust model

This PR adds a directory-sweeping utility plus a Windows scheduled-task installer that registers it. The script is invoked locally by an operator as a scheduled task; there is no network listener, no inbound HTTP, no external callers.

- **Operator-controlled inputs** (the only inputs that exist):
  - `arguments.root` — CLI positional, free-form path string.
  - `arguments.age` — CLI int (`--age`), feeds `time.time()` arithmetic and `min_age_seconds` comparison.
  - `arguments.interval` — CLI int (`--interval`), feeds `time.sleep`.
  - `--once` — CLI switch (bool).
  - PowerShell installer parameters: `$Target` (path string), `$IntervalMinutes` (int), `$AgeSeconds` (int), `$Remove` / `$Status` switches.
- **Privilege:** the script runs as whatever user the scheduled task is registered under (typically the operator's own account; potentially SYSTEM if `Register-ScheduledTask` is invoked from an elevated session).
- **Attacker model:** there is no remote attacker surface. The interesting H surfaces in this PR are (a) operator-error blast radius — does the script honor or silently expand the path the operator gave? — and (b) shell-injection-via-test-helper, where a future test author could pass a path containing a single quote into a PowerShell single-quoted literal and break the string. Authentication, authorization, SSRF, CSRF, deserialization, and file-upload sub-buckets are Shape B (no surface) for this artifact.
- **What's NOT in scope here:** the operator deliberately providing `--age 0` against `C:\` to wipe their own machine. That is operator authority being used as designed, not a privilege-boundary violation.

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**H1. SQL injection**
- The PR introduces no SQL, no ORM, no database driver, no `sqlite3` / `psycopg2` / `sqlalchemy` import.
- Shape B probes: (1) full-text scan all 4 inlined files for `SELECT`, `INSERT`, `UPDATE`, `DELETE`, `execute(`, `executemany(`, `.raw(`. (2) Scan for any string built with `+`, `%`, or f-string that could later be passed to a SQL driver. (3) Verify the only string-template construction in the diff (PowerShell command at the test helper, `New-ScheduledTaskAction -Argument` at the installer) does not flow into a SQL pathway via any imported helper.

**H2. Command injection** ⭐ canonical H surface for this PR
This sub-bucket has TWO distinct command-string-build sites in the diff, both with operator-trust assumptions worth naming explicitly.

- **Site 1 — test helper f-string into a PowerShell single-quoted literal.** `test_sweep_empty_dirs.py:25` builds `f"(Get-Item '{path}').CreationTimeUtc = [DateTime]'{date_str}'"` and passes it as the argument to `subprocess.run(["powershell", "-Command", ...], check=True, capture_output=True)`.
  - PowerShell single-quoted strings DO NOT honor backslash escapes, so `\` in `path` is fine. They DO terminate at the first unescaped single quote (`'`), and PowerShell's escape inside a single-quoted literal is a doubled single quote (`''`), which f-string interpolation does not produce.
  - NTFS legitimately permits `'` in directory names. A directory like `O'Brien-temp` would terminate the literal early, leave `).CreationTimeUtc = [DateTime]'…` as live PowerShell to execute, and break the test (or, in the wrong hands, execute injected commands under the operator's identity).
  - Trust assumption that defends this: `tempfile.TemporaryDirectory()` produces a system-temp path and a generated 8-char random suffix. The system-temp ancestor (`C:\Users\<user>\AppData\Local\Temp`) is operator-controlled but stable; the generated suffix uses `string.ascii_letters + string.digits + "_"` (CPython `tempfile._RandomNameSequence`) — no single quotes. So under normal operation no quote ever appears.
  - Severity P2 in this context: it's test-only code, locally bounded, and an operator who renames `Temp` to a path with a single quote has bigger problems. But the bullet is a Shape A finding because the f-string-into-single-quoted-PowerShell pattern itself is fragile and a future caller (e.g., a parametrized test that takes a path argument) could break it.
  - Alternative fix shape worth naming in the report: invoke via the cmdlet's named-argument argv — `subprocess.run(["powershell", "-NoProfile", "-Command", "param([string]$Path,[string]$Date) (Get-Item -LiteralPath $Path).CreationTimeUtc = [DateTime]$Date", "-Path", path, "-Date", date_str], ...)` — moves `path` and `date_str` out of the source string and into argv slots PowerShell parses safely.

- **Site 2 — installer PowerShell argument-string for the registered scheduled task.** `Install-SweepEmptyDirs.ps1:69` builds `$Action = New-ScheduledTaskAction -Execute $PythonPath -Argument "$ScriptPath --once --age $AgeSeconds ""$Target"""`.
  - PowerShell double-quoted strings expand `$` variables and use doubled `"` (`""`) as the embedded-quote escape, which is what's used here for `$Target`.
  - The operator-supplied `$Target` is interpolated INTO that double-quoted PowerShell string AND the resulting string is later parsed as Windows process argv by the C runtime when the scheduled task launches `python.exe …`. Two parsers, two escape contexts.
  - **Trailing-backslash hazard (Microsoft C-runtime argv parser):** if `$Target` ends with `\` (which is allowed; the operator typed `Y:\Some Folder\`), the `\"` sequence at the end of the string can be interpreted by `CommandLineToArgvW` as an escaped quote rather than a closing quote, merging the trailing `"` into the path token. The downstream `arguments.root` string would then contain a literal `"`. Severity P2 — the resulting `os.path.isdir(arguments.root)` check at sweep_empty_dirs.py main() rejects nonexistent paths and exits non-zero; failure mode is "task runs and immediately fails with a clear error" rather than silent compromise.
  - **Embedded-quote hazard:** if `$Target` itself contains a `"` (NTFS forbids `"` in names, so this is not reachable on Windows-native filesystems; reachable if a SMB share maps in a UNC path that originated on a non-Windows server). Document as "guarded by NTFS naming rules; not a current vulnerability."
  - **Embedded-`$` hazard:** PowerShell expands `$` inside double-quoted strings at the time `New-ScheduledTaskAction -Argument "…"` is evaluated. If `$Target` contains a literal `$Foo` substring, `$Foo` is expanded against the installer's variable scope at registration time — empty string by default, so the registered task gets a corrupted path. Cite as a Shape A finding; the safer pattern is to build the argument with `[string]::Join` and a backtick-escape, or to register the task with separate `-Execute` and `-Argument` slots that quote the path via `'`-delimited single-quoted PowerShell literal at install time.
  - **Argv-shape drift:** `--once --age $AgeSeconds "$Target"` puts `--once` and `--age` BEFORE the positional `root`. The argparse parser at sweep_empty_dirs.py (`_build_parser`) accepts this ordering, so it works today. A future argparse refactor that adds `parser.add_argument("root", nargs=argparse.OPTIONAL)` or makes `root` a sub-command name would silently reorder requirements; the installer's argv would still validate at PowerShell-string time but would mis-route at Python-time.

- Cross-shape probe for both sites: search the full diff for ANY other f-string, `Format-Operator -f`, `[string]::Format`, or string-concat pattern that builds shell-bound text. Confirm sites 1 and 2 are the only two.

**H3. Path traversal**
- `arguments.root` (CLI positional) flows directly into `os.walk(arguments.root, onerror=_log_walk_error, topdown=False)` and from there each `each_directory_path` flows into `os.rmdir(each_directory_path)`.
- Path traversal as classically defined (a remote attacker submitting `../../etc/passwd` to escape a containment root) is **Shape B not applicable**: the script IS the privileged process — there is no containment root. Whatever path the operator gives is exactly the path that gets walked. The trust assumption is "operator provides correct root."
- Adversarial probes: (1) symlink-following — `os.walk` does NOT follow symlinks by default (`followlinks=False`), so a sibling symlink under `arguments.root` pointing to `C:\Windows\Temp` is not traversed. Confirmed safe. (2) UNC paths — `os.walk(r"\\server\share")` works on Windows and is honored as given; if the operator types a UNC path, the script walks it. Document as operator authority. (3) path normalization — the script does NOT call `os.path.realpath` or `os.path.normpath` before `os.walk`. A path like `Y:\Projects\..\Projects\foo` is honored literally by `os.walk` (Windows resolves it via `GetFullPathName` at syscall time anyway). No additional risk introduced. (4) `os.path.isdir(arguments.root)` is the only pre-flight gate — if the operator provides a file path (not a directory) the script exits 1; if they provide a non-existent path it exits 1; if they provide a directory under a junction or reparse point, it walks it. (5) Race: between the `os.path.isdir` check at main() and the `os.walk` call, the operator could swap the path for a symlink to a different tree (TOCTOU). Operator-only attack surface; not exploitable remotely.
- Severity for the unverified-realpath observation: P3 / accepted-trust. The reviewer should note "no realpath; trusts operator's literal root" and move on; introducing a containment root would constrain the script's stated purpose.

**H4. Authentication bypass**
- This artifact has zero authentication surface. There is no HTTP server, no token check, no session, no cookie, no API key parsing, no `Authorization:` header reading, no credential validation flow.
- Shape B probes: (1) grep all 4 files for `auth`, `token`, `session`, `cookie`, `bearer`, `Authorization`, `password`, `credential`. Expect zero matches. (2) Verify the PowerShell installer does not register the task with `-User` / `-RunLevel Highest` from operator input — confirmed: `Register-ScheduledTask` is called without `-User` or `-Password`, defaulting to the current interactive user at install time. (3) Verify nothing in the diff exposes a network port (`socket.bind`, `http.server`, `Flask`, `FastAPI`, `aiohttp`).

**H5. Authorization checks**
- This artifact has no concept of users, roles, tenants, or per-resource ownership. There is no vertical-privilege check (admin vs user) and no horizontal-privilege check (user A vs user B).
- Shape B probes: (1) full-text grep for `is_admin`, `role`, `permission`, `owner_id`, `tenant`, `IDOR`. Expect zero matches. (2) Verify `os.rmdir` is not gated by an ownership check — confirmed it is not, but this is by design: the script runs with the operator's authority and deletes whatever empty directories that authority can reach. (3) Confirm the registered scheduled task does not run as a more-privileged principal than the installer — `Register-ScheduledTask` without an explicit `-User` runs as the registering user, so privilege does not escalate.

**H6. Secret / credential leakage**
- This PR handles zero secrets. No API keys, no tokens, no passwords, no database credentials, no signing keys, no environment-dump endpoints.
- Shape B probes: (1) grep all 4 files for `key`, `token`, `secret`, `password`, `credential`, `bearer`. Result: two hits in `Install-SweepEmptyDirs.ps1` for `-TaskName` (false-positive — substring match on `name`), zero credential matches. (2) Verify error paths in `sweep_empty_dirs.py` (`_log_walk_error`, the `except OSError: pass` blocks) do not log environment or trace state — confirmed they log only `os_error.filename` and `os_error.strerror`. (3) Verify the PowerShell installer does not call `Get-Credential`, `ConvertFrom-SecureString`, or persist secrets to the task XML — confirmed.

**H7. SSRF / external request validation**
- The artifact makes zero outbound network requests. No `requests.*`, no `urllib.*`, no `httpx.*`, no `Invoke-WebRequest`, no `Invoke-RestMethod`, no `socket.*` connect calls.
- Shape B probes: (1) grep all 4 files for `requests.`, `urllib`, `http.client`, `Invoke-WebRequest`, `Invoke-RestMethod`, `WebClient`, `HttpClient`. Expect zero matches. (2) Verify `Get-Command` (the only network-adjacent PowerShell call) only resolves a binary on PATH — it does not perform DNS or HTTP. (3) Verify the cloud-metadata endpoint (169.254.169.254) is not mentioned and not reachable from any code path in the diff.

**H8. CSRF / state-changing without token**
- Not applicable: there is no HTTP handler, no form, no same-origin assumption, no browser-mediated POST. The script's state-changing operation (`os.rmdir`) is invoked from a local Python process, not from a browser-issued HTTP request.
- Shape B probes: (1) confirm no `@app.route`, no `@router.post`, no `flask.Flask`, no `fastapi.FastAPI`, no `aiohttp.web.RouteTableDef`. (2) Confirm the scheduled-task trigger surface (`Register-ScheduledTask`) is local-only and not reachable by a remote unauthenticated caller. (3) Confirm there's no inter-process listener (named pipe, Unix socket, COM endpoint) that an unprivileged caller could poke to trigger sweeps.

**H9. Deserialization**
- The artifact never deserializes attacker-controllable bytes. No `pickle.loads`, no `yaml.load`, no `marshal.loads`, no `eval`, no `exec`, no `json.loads(..., object_hook=…)`. No `Import-Clixml`, no `Deserialize-PSObject`.
- Shape B probes: (1) grep all 4 files for `pickle`, `yaml`, `marshal`, `eval(`, `exec(`, `Import-Clixml`, `ConvertFrom-Json` (note: `ConvertFrom-Json` is a JSON parser, generally safe; verify it isn't called against operator input). Expect zero matches. (2) Verify the PowerShell installer does not deserialize task XML from operator-controlled paths. (3) Verify `argparse.parse_args()` behavior — it does not deserialize; it only string-types CLI tokens.

**H10. File upload / MIME validation**
- Not applicable: the artifact accepts no file uploads. There is no HTTP multipart handler, no `werkzeug.FileStorage`, no `flask.request.files`, no `fastapi.UploadFile`, no `Save-Item`-from-stream pathway.
- Shape B probes: (1) grep all 4 files for `multipart`, `UploadFile`, `request.files`, `werkzeug`, `Content-Type`, `magic` (libmagic). Expect zero matches. (2) Confirm the only file-system operations in the diff are read (`Test-Path`, `os.walk`, `os.path.getctime`, `os.path.isdir`) and delete-empty (`os.rmdir`) — there is no file-write operation introduced by this PR. (3) Confirm `Path(nonempty_dir, "keepme.txt").write_text("hello")` in the test file at `test_sweep_empty_dirs.py` creates fixture content under `tempfile.TemporaryDirectory`, not under operator-controlled input.

## Cross-bucket questions to answer at the end

Q1: Are there any inputs that cross two H sub-buckets? (For PR #394, the candidate is `arguments.root` flowing through H3-style path-handling code that ALSO becomes the `$Target` interpolated into the H2 PowerShell argument string when an operator re-runs the installer with the same path. Are the two trust assumptions consistent?)
Q2: What's the worst injection / leakage hazard introduced by this PR? Cite `<file>:<line>` for the specific construction. (Candidate: `Install-SweepEmptyDirs.ps1:69` `New-ScheduledTaskAction -Argument` interpolating `$Target` — embedded-`$` and trailing-backslash hazards are both reachable in normal Windows path-naming.)
Q3: Which input is most fragile to a future API addition — i.e., where would a future change most likely turn an operator-trust assumption into an actual attacker-reachable surface? Name the line(s) most likely to break. (Candidate: `test_sweep_empty_dirs.py:25` `_set_creation_time_windows` — if a future test parametrizes `path` from a non-tempfile source, the f-string-into-single-quoted-PowerShell pattern flips from "fragile-but-bounded" to "exploitable.")

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket H1-H10, produce Shape A or Shape B (with ≥3 probes). Cross-bucket Q1-Q3 answers after the per-sub-bucket walk. Adversarial second pass: "assume your first pass missed at least 3 P0/P1 vulnerabilities across these 10 sub-buckets — find them." Open Questions section for ambiguities. Read-only. No edits, no commits.

Note: Category H findings tend toward P0/P1 since they're security-relevant — adjust the adversarial-pass quota severity accordingly. For PR #394 specifically, the trust model (no remote attacker, operator-only invocation) caps most realistic findings at P2; the adversarial pass should still hunt P0/P1 by asking "what changes if this script is ever invoked from an untrusted context — a CI runner, a different user's scheduled task, a remote-management tool?"

## Diff (4 new files, all lines in scope)

### packages/claude-dev-env/scripts/sweep_empty_dirs.py
```python
#!/usr/bin/env python3
"""Delete empty directories older than 2 minutes under a given root."""

import argparse
import os
import sys
import time

from config.sweep_config import DEFAULT_AGE_SECONDS
from config.sweep_config import DEFAULT_POLL_INTERVAL


def _log_walk_error(os_error: OSError) -> None:
    print(f"warning: cannot scan {os_error.filename} — {os_error.strerror}", file=sys.stderr)


def sweep(root: str, min_age_seconds: int) -> list[str]:
    """Remove empty directories under *root* older than *min_age_seconds*."""

    now = time.time()
    removed: list[str] = []

    for each_directory_path, _, _ in os.walk(
        root, onerror=_log_walk_error, topdown=False
    ):
        try:
            created = os.path.getctime(each_directory_path)
        except OSError:
            continue
        if now - created >= min_age_seconds:
            try:
                os.rmdir(each_directory_path)
                print(f"deleted: {each_directory_path}")
                removed.append(each_directory_path)
            except OSError:
                pass

    return removed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Delete empty directories older than a given age.")
    parser.add_argument("root", help="Root directory to scan")
    parser.add_argument("--age", type=int, default=DEFAULT_AGE_SECONDS,
                        help=f"Minimum age in seconds (default: {DEFAULT_AGE_SECONDS} = 2 minutes)")
    parser.add_argument("--once", action="store_true",
                        help="Single pass and exit instead of watching in a loop")
    parser.add_argument("--interval", type=int, default=DEFAULT_POLL_INTERVAL,
                        help=f"Poll interval in seconds when looping (default: {DEFAULT_POLL_INTERVAL})")
    return parser


def main() -> None:
    parser = _build_parser()
    arguments = parser.parse_args()

    if not os.path.isdir(arguments.root):
        print(f"error: not a directory: {arguments.root}", file=sys.stderr)
        sys.exit(1)

    if arguments.once:
        sweep(arguments.root, arguments.age)
        return

    print(f"watching {arguments.root} every {arguments.interval}s (age threshold: {arguments.age}s)")
    try:
        while True:
            sweep(arguments.root, arguments.age)
            time.sleep(arguments.interval)
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
```

### packages/claude-dev-env/scripts/config/sweep_config.py
```python
"""Centralized timing configuration for sweep_empty_dirs."""

DEFAULT_AGE_SECONDS: int = 120
DEFAULT_POLL_INTERVAL: int = 30
```

### packages/claude-dev-env/scripts/tests/test_sweep_empty_dirs.py
```python
"""Tests for sweep_empty_dirs.py"""

from __future__ import annotations

import datetime
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from sweep_empty_dirs import sweep  # noqa: E402


def _set_creation_time_windows(path: str, timestamp: float) -> None:
    dt = datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)
    date_str = dt.strftime("%Y-%m-%d %H:%M:%S")
    subprocess.run(
        ["powershell", "-Command",
         f"(Get-Item '{path}').CreationTimeUtc = [DateTime]'{date_str}'"],
        check=True, capture_output=True,
    )


def test_deletes_empty_dir_older_than_threshold() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        empty_dir = os.path.join(tmp, "old_empty")
        os.mkdir(empty_dir)
        _set_creation_time_windows(empty_dir, time.time() - 300)
        removed = sweep(tmp, min_age_seconds=120)
        assert empty_dir in removed
        assert not os.path.isdir(empty_dir)


def test_skips_empty_dir_newer_than_threshold() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        fresh_dir = os.path.join(tmp, "fresh_empty")
        os.mkdir(fresh_dir)
        removed = sweep(tmp, min_age_seconds=120)
        assert fresh_dir not in removed
        assert os.path.isdir(fresh_dir)


def test_deletes_nested_empty_dirs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        leaf = os.path.join(tmp, "parent", "child", "leaf")
        os.makedirs(leaf)
        _set_creation_time_windows(os.path.join(tmp, "parent"), time.time() - 300)
        _set_creation_time_windows(os.path.join(tmp, "parent", "child"), time.time() - 300)
        _set_creation_time_windows(leaf, time.time() - 300)
        removed = sweep(tmp, min_age_seconds=120)
        assert leaf in removed
        assert os.path.join(tmp, "parent", "child") in removed
        assert os.path.join(tmp, "parent") in removed


def test_empty_root_does_not_crash() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        _set_creation_time_windows(tmp, time.time() - 300)
        sweep(tmp, min_age_seconds=120)


def test_skips_nonempty_dir() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        nonempty_dir = os.path.join(tmp, "has_stuff")
        os.mkdir(nonempty_dir)
        Path(nonempty_dir, "keepme.txt").write_text("hello")
        removed = sweep(tmp, min_age_seconds=0)
        assert nonempty_dir not in removed
        assert os.path.isdir(nonempty_dir)
```

### packages/claude-dev-env/scripts/Install-SweepEmptyDirs.ps1
```powershell
#!/usr/bin/env pwsh
param(
    [Parameter(ParameterSetName = "install")]
    [string]$Target,

    [Parameter(ParameterSetName = "install")]
    [int]$IntervalMinutes = 5,

    [Parameter(ParameterSetName = "install")]
    [int]$AgeSeconds = 120,

    [Parameter(ParameterSetName = "remove")]
    [switch]$Remove,

    [Parameter(ParameterSetName = "status")]
    [switch]$Status
)

$TaskName = "SweepEmptyDirs"

if ($Status) {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if (-not $task) {
        Write-Host "STATUS: $TaskName is not registered."
        return
    }
    Write-Host "STATUS: $TaskName is registered."
    Write-Host "  State: $($task.State)"
    Write-Host "  Actions:"
    foreach ($action in $task.Actions) {
        Write-Host "    $($action.Execute) $($action.Arguments)"
    }
    Write-Host "  Triggers:"
    foreach ($trigger in $task.Triggers) {
        Write-Host "    $($trigger.Repetition.Interval) (starting $($trigger.StartBoundary))"
    }
    return
}

if ($Remove) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "$TaskName removed."
    return
}

$ScriptDir = Split-Path -Parent $PSCommandPath
$ScriptPath = Join-Path $ScriptDir "sweep_empty_dirs.py"

if (-not (Test-Path $ScriptPath)) {
    Write-Error "sweep_empty_dirs.py not found at: $ScriptPath"
    exit 1
}

if (-not $Target) {
    Write-Error "Parameter -Target is required (the directory to watch)."
    exit 1
}

if (-not (Test-Path $Target)) {
    Write-Error "Target directory does not exist: $Target"
    exit 1
}

$_py = Get-Command py -ErrorAction SilentlyContinue
$PythonPath = if ($_py) { $_py.Source } else { (Get-Command python).Source }
if (-not $PythonPath) {
    Write-Error "Cannot find Python (py or python) on PATH."
    exit 1
}
$Action = New-ScheduledTaskAction -Execute $PythonPath -Argument "$ScriptPath --once --age $AgeSeconds ""$Target"""
$Trigger = New-ScheduledTaskTrigger -Daily -At "00:00" -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes)
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Force | Out-Null
Write-Host "$TaskName registered — runs every ${IntervalMinutes}min against '$Target' (age ≥ ${AgeSeconds}s)."
```
