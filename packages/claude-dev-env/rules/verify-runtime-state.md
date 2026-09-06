# Verify Runtime State

**When this applies:** Before stating that a component is fine, healthy, not at fault, or working — during debugging, triage, or any judgment about whether something runs.

## Rule

A verdict that a component is fine or not the cause rests on live evidence gathered this session: a process list, a port probe, a log tail, an HTTP status code, or a fresh repro. Reading the code, recalling how the component behaved earlier, or trusting a prior session's finding does not settle whether it runs right now. Code shows what should happen; only a live probe shows what does.

Gather the probe before you write the verdict. When the probe contradicts the code (the code looks right but the port refuses the connection), report the live result and treat the component as suspect.

A status field is a report, not the effect. An exit code, a green pipeline run, and a task result all say the work finished. They do not say the work happened. Read the thing the work was meant to make.

Some evidence lasts only a moment. When a user shows you a failure, read the source they already hold: the terminal itself, and any log file the error names. A fresh probe minutes later measures a different moment, and a system that healed in between hides the failure you were asked about.

## Grounding checklist

Before stating a runtime claim, gather the matching live signal:

| Claim | Grounding probe |
|---|---|
| The service is healthy | Hit its health endpoint and read the status code. |
| The config is in effect | Print the loaded config at runtime and read the value. |
| The server is up | Probe the port; a refused connection means it is down. |
| The process is running | List processes and match the name or PID. |
| The change took effect | Drive the flow and watch the new behavior. |
| The dependency is reachable | Send one real request and read the response. |
| The release or deploy shipped | Read what it makes: the tag, the published version, the file on disk. |
| The pipeline did the work | Read each job's own result. A run reports success while a job inside it is skipped. |
| The automation works | Drive the branch that matters. A green run of the do-nothing branch proves nothing. |

Only after a live signal backs the claim do you state it.

## Examples

**Wrong:** "The search server code looks correct, so it is not the problem."
**Right:** Probe port 54321; report "connection refused — the server is down."

**Wrong:** "This function handles the retry, so the request must be going through."
**Right:** Tail the request log and confirm the retry fired, or report that no retry line appears.

**Wrong:** "The config sets the timeout to 30 seconds, so the timeout is fine."
**Right:** Print the loaded config at runtime and report the value the process actually holds.
