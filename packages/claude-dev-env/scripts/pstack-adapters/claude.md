# Claude Code

Use Claude Code's native Skill mechanism to load installed skills. Use Agent for Task requests, with only arguments the session exposes. For an upstream poteto-agent or another unavailable agent type, use an available general-purpose agent and include the upstream definition and compatibility files in its prompt. A file on disk does not register a native agent type.

Use AskUserQuestion for a required human choice. Use Read, Glob, Grep, Edit, Write, Bash, and the available browser tools for their corresponding work. Read native tool schemas rather than forwarding Cursor-only arguments. Use background execution only when the current tool supports it.

Choose model aliases accepted by this session. Omit the model argument for permitted parent inheritance. Keep host preferences in the profile's agents-home rules/pstack-model-preferences.claude.json. Use the current session's transcript location, or state that transcripts are unavailable.
