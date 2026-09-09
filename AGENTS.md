Do not add code comments. Preserve existing comments. Docstrings remain allowed.
When a change touches code that an existing comment describes or is attached to, remove that comment in the same change and carry its meaning through clear names and structure. Leave comments tied to untouched code unchanged. Keep comment cleanup inside the requested task.
Production and tests follow one rule. Changed directive, TODO, FIXME, HACK, XXX, and type-ignore comments are removed rather than added or justified.

Banned word: real

Never write real, really, or real-world. Not in chat, not in a commit message, not in a pull request body, not in a comment, not in documentation, not in a heading, not in a variable name. This ban has no exception. Emphasis is not an exception. Contrast with a test, a mock, a fixture, or a hypothetical is not an exception. Insisting that something is genuine is not an exception.

Every sentence carrying real says the same thing without it. "One real failure" is "one failure". "The real cause" is "the cause". "Really fast" is "fast", or the measured number. "Real users" is "users". "A real bug, not a flake" is "a bug", followed by the evidence that rules out a flake.

Delete the word, then read the sentence. When it still says what you meant, you are done. When something is missing, the missing part is evidence, so name the evidence. The failing check. The log line. The measured number. The file and the line.

Swapping in actual, actually, genuine, or true is the same move, and each is banned with it. So is the invented contrast that invites the word back, such as "not a hypothetical problem but a problem".
