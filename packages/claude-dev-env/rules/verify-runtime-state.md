# Verify Runtime State

**When this applies:** Before stating that a component is fine, healthy, not at fault, or working — during debugging, triage, or any judgment about whether something runs.

## Rule

A verdict that a component is fine or not the cause rests on live evidence gathered this session: a process list, a port probe, a log tail, an HTTP status code, or a fresh repro. Reading the code, recalling how the component behaved earlier, or trusting a prior session's finding does not settle whether it runs right now. Code shows what should happen; only a live probe shows what does.

Gather the probe before you write the verdict. When the probe contradicts the code (the code looks right but the port refuses the connection), report the live result and treat the component as suspect.

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

Only after a live signal backs the claim do you state it.

## Examples

**Wrong:** "The search server code looks correct, so it is not the problem."
**Right:** Probe port 54321; report "connection refused — the server is down."

**Wrong:** "This function handles the retry, so the request must be going through."
**Right:** Tail the request log and confirm the retry fired, or report that no retry line appears.

**Wrong:** "The config sets the timeout to 30 seconds, so the timeout is fine."
**Right:** Print the loaded config at runtime and report the value the process actually holds.

## Relationship to other rules

- **`verify-before-asking`** answers questions with a tool before asking the user. This rule extends that to runtime verdicts: gather the live probe before you conclude, not just before you ask.
- **`long-horizon-autonomy`** requires every progress claim to rest on a tool result from this session. A runtime verdict is a progress claim; this rule names the probes that back it.
