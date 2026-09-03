Use positive, present-focused prose.

State what should be done, what something does, what was done, or what needs to be done.

Include only information directly relevant to the immediate task or remaining work.

Use direct outcome-focused wording. Omit filler, failed attempts, alternatives considered, and process narration.

Do not add code comments. Preserve existing comments. Docstrings remain allowed.
When a change touches code that an existing comment describes or is attached to, remove that comment in the same change and carry its meaning through clear names and structure. Leave comments tied to untouched code unchanged. Keep comment cleanup inside the requested task.
Production and tests follow one rule. Changed directive, TODO, FIXME, HACK, XXX, and type-ignore comments are removed rather than added or justified.
