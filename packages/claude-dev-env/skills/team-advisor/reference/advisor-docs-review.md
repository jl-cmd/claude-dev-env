# Advisor-Tool Documentation Review

Distilled facts from the Anthropic advisor-tool documentation, for the
Sonnet-executor advisor path and the hand-rolled `/team-advisor` bind. Every
claim below cites its source page.

Consult timing, the hard rule before a first write, and how to weigh the
advice live in [`docs/references/advisor-tool.md`](../../../docs/references/advisor-tool.md).
The consult cadence lives in [`SKILL.md`](../SKILL.md). This file carries the
source facts those two omit: measured effects, Sonnet steering, cost levers,
failure modes, and what transfers to a hand-rolled bind.

## Sources

| # | Page |
|---|---|
| 1 | [Advisor tool — platform docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/advisor-tool) |
| 2 | [Escalate hard decisions with the advisor tool — Claude Code](https://code.claude.com/docs/en/advisor) |
| 3 | [The advisor strategy — blog](https://claude.com/blog/the-advisor-strategy) |
| 4 | [Best practices for computer and browser use — blog](https://claude.com/blog/best-practices-for-computer-and-browser-use-with-claude) |
| 5 | [Claude models explained — blog](https://claude.com/blog/claude-models-explained-choosing-the-best-model-for-your-use-case) |
| 6 | [Messages API — beta](https://platform.claude.com/docs/en/api/beta/messages) |
| 7 | [Claude Code changelog](https://code.claude.com/docs/en/changelog) |

## A. Consult timing the canonical rules omit

Planner funnel, page 1:

```text
If your agent exposes other planner-like tools (for example, a todo list
tool), prompt the model to call the advisor before those tools so the
advisor's plan funnels into them.
```

Consult moments for long agent runs, page 4: "choosing which tab to open,
recovering from an unexpected modal, deciding whether to abandon a strategy".

Frequency control stays prompt-only, page 2:

```text
There is no setting to cap or force advisor calls; if you want Claude to
consult more or less often during a task, say so in your instructions.
```

## B. Measured effect of the hard rule

Page 1 reports: the Haiku coding block raises pass rates by roughly 7.5
points on an internal coding benchmark. On Opus the same checkpoint raises
under-calling tasks 7–10 points and holds roughly flat on a mixed workload
where plan-free tasks over-call.

## C. Sonnet-executor facts

Page 1 marks the startup nudge as dead weight on Sonnet:

```text
On Sonnet executors, the plain-text nudge had no measurable effect in
Anthropic's testing.
```

Steering for a Sonnet executor belongs in the system prompt, prepended
"before any other sentences that mention the advisor" (page 1).

Page 4 names a long-session gap: the executor does not always remember the
advisor exists on long-horizon tasks; the tested pattern is a one-line
reminder after roughly 20 advisor-free turns.

Named pairing, page 1:

```text
You currently use Sonnet on complex tasks: Add a higher-tier advisor. Opus
keeps total cost similar or lower; Claude Fable 5 maximizes the quality lift.
```

Effort pairing, page 1:

```text
For coding tasks, pairing a Sonnet executor at medium effort with an Opus
advisor achieves intelligence comparable to Sonnet at default effort, at
lower cost. For maximum intelligence, keep the executor at default effort.
```

Page 3 footnotes the benchmark condition: the Sonnet-plus-advisor SWE-bench
Multilingual run uses the suggested system prompt "with thinking turned
off" — a consult substitutes for extended thinking in that run.

## D. Benchmarks

Page 3 and page 5 report these results:

- Sonnet 4.6 with an Opus 4.6 advisor: +2.7 points on SWE-bench Multilingual
  over Sonnet solo, cost per agentic task down 11.9%.
- Haiku 4.5 with an Opus advisor on BrowseComp: 41.2% versus 19.7% solo;
  trails Sonnet solo by 29% in score at 85% lower cost per task.
- Sonnet 5 with a Fable 5 advisor (page 5): within 10% of Fable 5's own score
  at 63% of the price of running Fable 5 for the whole task, on SWE-bench
  Pro.

Advisor reply shape, page 3:

```text
Opus accesses the shared context and returns a plan, a correction, or a stop
signal, and the executor resumes. The advisor never calls tools or produces
user-facing output.
```

## E. Cost levers

Output size is the advisor's largest cost driver; the top-level `max_tokens`
parameter does not bound it (pages 1, 4, 6). A tool-definition
`max_tokens: 2048` cuts mean advisor output roughly 7x with near-zero
truncation; `1024` cuts roughly 10x and truncates about 10% of calls. The
server passes the advisor its remaining budget, so the advisor self-shapes
its reply length.

The brevity line belongs in the user message and addresses the advisor
directly; the wording lives under **Brevity cue** in
[`advisor-tool.md`](../../../docs/references/advisor-tool.md).

Direct address works because the advisor reads the executor's prompt as
quoted context: "instructions that address the advisor directly are followed
much more reliably than third-person descriptions." A brief that asks for
roughly 80 percent of the true ceiling raises consult frequency while
lowering total cost.

Typical advisor output runs 400–700 text tokens, or 1,400–1,800 with
thinking included.

Advisor-side caching breaks even at roughly three consults per conversation;
set it once and leave it. A `clear_thinking` setting with `keep` other than
`"all"` shifts the advisor's quoted transcript and causes advisor-side cache
misses.

`max_uses` caps consults per request; Anthropic's launch example sets
`max_uses: 3`. Conversation-level caps count client-side; dropping the tool
requires stripping every `advisor_tool_result` block from history, or the API
returns 400.

## F. Failure modes and API mechanics

Error codes the advisor call surfaces (pages 1, 6): `max_uses_exceeded`,
`too_many_requests`, `overloaded`, `prompt_too_long`,
`execution_time_exceeded`, `unavailable`, `model_not_found`.

```text
The executor sees the error and continues without further advice. The
request itself does not fail.
```

The advisor runs without tools and without context management; thinking
blocks are dropped, and only advice text returns. On the server side,
nothing the executor puts in `input` reaches the advisor — the server
forwards the full transcript itself.

Fable, Opus 5, and Mythos advisors return `advisor_redacted_result`
(encrypted, round-trips verbatim). Opus 4.8 and below return plaintext
`advisor_result`. A native Fable-class advisor's encrypted block carries no
guidance the client can read; when logging or auditing the guidance matters,
pick a plaintext-returning advisor — the hand-rolled CLI and warm-agent
paths always yield a readable transcript.

Pairing invariant: "The advisor must be at least as capable as the
executor." Claude Code enforces the same check per subagent — subagents
inherit the configured advisor and apply the same pairing check against
their own model.

The native advisor is a server tool with no name a permission rule or hook
matcher can reference, so it bypasses hooks. The bind this skill uses lives
in [`SKILL.md`](../SKILL.md) **Bind**.

Consults run slow enough to look like stalls: changelog 2.1.214 (page 7)
fixes a spurious "check your network" warning that appeared while the
advisor was thinking.

Usage accounting: each consult is an `advisor_message` entry in
`usage.iterations[]` with its own model and token counts, billed at advisor
rates.

## G. What transfers to the hand-rolled advisor path

The claude-dev-env advisor is a warm agent or CLI session. Three inversions
apply against the native server tool:

1. **Context forwarding is manual.** The native tool auto-forwards the full
   transcript. Everything a hand-rolled advisor sees arrives in the consult.
   Build the first packet with
   [`_shared/advisor/reference/consult-format.md`](../../../_shared/advisor/reference/consult-format.md);
   later consults carry only the delta.
2. **Caching becomes prefix stability.** The charter and role text stay
   byte-stable at the top of the consult stream; volatile detail goes last.
3. **Hooks apply.** Consult payloads travel through ordinary tools, so each
   payload stays hook-safe and the bind log is mechanically validated.

## H. Measuring the advisor's lift

Repository practice, sourced to no page: benchmark three routes on one
representative workload — the executor alone, the executor plus advisor, and
the strongest model throughout. Route future work by measured cost per
successful task.

Track, per route: completion rate, regression rate, tool calls, tokens by
tier, and latency.
