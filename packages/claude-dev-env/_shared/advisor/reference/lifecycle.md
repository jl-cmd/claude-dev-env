# Lifecycle detail

Detail behind the **Lifecycle ownership** section of [`advisor-protocol.md`](../advisor-protocol.md).
Open this when the advisor drifts, dies, or the task pivots.

## Claude host

The session that spawns the shared advisor owns its whole lifecycle — spawn, drift-respawn, and shutdown.
Every other consumer (executors, or any other consulting session) reaches it by message alone; spawn, respawn, and shutdown belong to the owning session.
One shared advisor exists per orchestrated session, owned by the session that spawned it.

**Re-spawn on drift.** If a reply shows the agent working from a stale picture, or the session pivots to an unrelated task, the owning session ends that agent and spawns a fresh one with a new charter.
A **Fable**-tier re-spawn carries the exact token `FABLE-SPAWN-AUTHORIZED` in that fresh prompt, as a Fable-tier warm-up try does.

## Third-party host

The orchestrating session owns the Claude CLI advisor bind for the whole run — first bind, re-bind on drift or lost `session_id`, and fail-closed report when the chain cannot serve.

**Re-bind on drift.** If a reply shows a stale picture, the task pivots, or `--resume` fails after a usage-limit failover (session stores are per binary/account), re-bind through `claude_chain_runner.py` with the charter plus a compact recap of consults so far.
Capture the new `session_id`, and log a fresh Fable→Opus walk with `result: "cli"` on success.
Executors keep reporting to the orchestrating session; advisor binding stays with that session alone.
