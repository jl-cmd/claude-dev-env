# Parallel Tool Calls

Source: [Anthropic - Parallel Tool Calling](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices#optimize-parallel-tool-calling)

<use_parallel_tool_calls>
When multiple tool calls have no dependencies between them, make all independent calls in a single response. Only sequence calls when a later call needs an earlier call's result.
</use_parallel_tool_calls>

## Examples

- Reading 3 files: call all 3 Read operations at once.
- Running independent searches: launch all Grep/Glob calls simultaneously.
- Checking git status + reading a config file: both in one response.
- Reading a file, then editing based on its content: sequential (edit depends on read result).

## Guard rails

- Use real parameter values only. Do not guess or use placeholders to force parallelism.
- If you are unsure whether calls are independent, run them sequentially.

## Why

Explicit reinforcement of parallel calling boosts compliance to near 100%. Sequential calls for independent operations waste time and round-trips for the user.
