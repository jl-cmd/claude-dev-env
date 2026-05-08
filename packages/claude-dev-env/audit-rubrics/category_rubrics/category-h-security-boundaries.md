# Category H — Security boundaries

**What this category audits:** injection (SQL / command / template), path traversal, authentication and authorization bypass, secret and credential leakage, SSRF, CSRF, deserialization gadgets, file-upload validation — anything where untrusted input crosses a privilege boundary without proper sanitization.

**Examples of Category H findings:**
- User input concatenated into SQL rather than parameterized.
- File path joined from untrusted input without normalization or root containment.
- Token, password, or API key written to a log line.
- A `pickle.loads` call against attacker-controllable bytes.
- An HTTP redirect to a URL derived from a query parameter without an allowlist.

**Companion reference:** see `../source-material-section-types.md`.

---

## Sub-bucket decomposition (Category H)

| ID | Axis name | Concrete checks |
|---|---|---|
| H1 | SQL injection | Parameterization vs string concatenation; ORM `raw()` usage; dynamic table/column names. |
| H2 | Command injection | `shell=True`, `os.system`, f-string into shell, PowerShell `-Command` with interpolated input. |
| H3 | Path traversal | User input joined to a base path without `realpath` + root containment check. |
| H4 | Authentication bypass | Missing auth checks; role checks bypassed via direct API; cookie / token validation gaps. |
| H5 | Authorization checks | Vertical (admin vs user) and horizontal (user A vs user B) access controls; IDOR vulnerabilities. |
| H6 | Secret / credential leakage | API keys / tokens / passwords in logs, errors, traces, env-dump endpoints, telemetry. |
| H7 | SSRF / external request validation | URL parameters not validated against allowlist; cloud metadata endpoint blocked? |
| H8 | CSRF / state-changing without token | POST/PUT/DELETE handlers without CSRF protection; same-origin assumptions. |
| H9 | Deserialization | `pickle.loads`, `yaml.load` (without SafeLoader), `eval` / `exec` against external input. |
| H10 | File upload / MIME validation | Trusted Content-Type from client; no extension allowlist; no magic-byte verification. |

---

## Sample prompt

The reusable Variant C template for Category H is in [`../prompts/category-h-security-boundaries.md`](../prompts/category-h-security-boundaries.md). Inline your artifact under `## Source material` and adapt the sub-bucket bullets to your project's threat model.

For a literal worked example using PR #394, see [`category-a-api-contracts.md`](category-a-api-contracts.md). Category H walks for that diff:
- H2: the test helper builds `f"(Get-Item '{path}').CreationTimeUtc = [DateTime]'{date_str}'"` and passes to `subprocess.run(["powershell", "-Command", ...])`. The `path` is from `tempfile.TemporaryDirectory` (locally trusted) but the f-string into a single-quoted PowerShell literal is fragile; if an attacker controlled the path they could break out of the literal with a single quote. Severity P2 in this context (test code, locally bounded).
- H3: `arguments.root` from CLI is passed to `os.walk` and `os.rmdir`. Path traversal isn't applicable since the script *is* the privileged process — it walks whatever is given. The trust assumption is "operator provides correct root."
- H6: no secrets / credentials handled.
