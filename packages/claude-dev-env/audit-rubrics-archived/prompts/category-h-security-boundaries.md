Audit [REPO/ARTIFACT] [TARGET_ID] for **Category H only** (security boundaries). Skip A–G, I–P. Sub-bucket forced-exhaustion mode: Category H is decomposed into 10 sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

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
- Shape B probes (when no traversal surface exists): (1) `os.walk` / equivalent does not follow symlinks (`followlinks=False` in Python; `-NoFollowSymlink` semantics in PowerShell). (2) UNC / drive-letter / reparse-point handling — document whether the artifact honors them as given (operator authority) or rejects them. (3) Path normalization — does the code call `realpath`/`normpath` before filesystem ops? (4) TOCTOU between any pre-flight check (`isdir`, `Test-Path`) and the filesystem op. (5) Pre-flight gate identification — what is the only validation between attacker input and the filesystem syscall?

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
- Shape A pattern: state-changing handler with no CSRF token validation; SameSite-cookie assumption used as the sole CSRF defense without verifying the framework sets it; pre-flight CORS check trusted as authentication; same-origin assumed without enforcement.
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
Q3: Which input is most fragile to a future API addition — i.e., where would a future change most likely turn an operator-trust assumption into an attacker-reachable surface? Name the line(s) most likely to break.

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket H1-H10, produce Shape A or Shape B (with at least 3 probes). Cross-bucket Q1-Q3 answers after the per-sub-bucket walk. Report every finding you reach, including uncertain ones and P2 ones, and give each finding a confidence level (high, medium, or low) beside its severity so a later pass can rank and filter them. Open Questions section for ambiguities. Read-only. No edits, no commits.

Note: Category H findings tend toward P0/P1 because they are security-relevant. Rate each finding against the trust model named in the metadata block. When that trust model caps realistic findings below P1 (e.g., operator-only invocation with no remote attacker surface), record each hazard at the severity the trust model supports and add an Open Question asking what changes if this code is ever invoked from an untrusted context: a CI runner, a different user's session, a remote-management tool, or a future HTTP wrapper.
