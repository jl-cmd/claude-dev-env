"""Segment-splitting and command-name constants for the destructive command blocker compound rm guard."""

ALL_SHELL_CONTROL_OPERATOR_TOKENS: frozenset[str] = frozenset({"&&", "||", ";", "|&", "|", "&", "\n", "\r"})
ALL_COMMAND_LAUNCHER_WRAPPER_COMMANDS: frozenset[str] = frozenset(
    {
        "timeout",
        "nohup",
        "nice",
        "ionice",
        "stdbuf",
        "time",
        "setsid",
        "chrt",
        "taskset",
    }
)
ALL_LAUNCHERS_REQUIRING_A_POSITIONAL_VALUE: frozenset[str] = frozenset(
    {
        "timeout",
        "chrt",
        "taskset",
    }
)
ALL_INTERPRETER_AND_WRAPPER_COMMANDS: frozenset[str] = frozenset(
    {
        "sh",
        "bash",
        "zsh",
        "dash",
        "ksh",
        "tcsh",
        "csh",
        "fish",
        "pwsh",
        "powershell",
        "cmd",
        "eval",
        "exec",
        "source",
        "sudo",
        "su",
        "env",
        "xargs",
        "parallel",
        "awk",
        "gawk",
        "mawk",
        "nawk",
        "make",
        "tclsh",
        "expect",
        "lua",
    }
)
ALL_REMOTE_AND_PROGRAM_STRING_EXECUTORS: frozenset[str] = frozenset(
    {
        "ssh",
        "python",
        "python2",
        "python3",
        "perl",
        "ruby",
        "node",
        "deno",
        "bun",
        "php",
    }
)
ALL_STRING_ARGUMENT_EXECUTION_FLAGS: frozenset[str] = frozenset({"-c", "-e"})
FIND_PROGRAM_NAME: str = "find"
ALL_FIND_EXEC_ACTION_FLAGS: frozenset[str] = frozenset({"-exec", "-execdir"})
ALL_FIND_EXEC_ACTION_TERMINATORS: frozenset[str] = frozenset({";", "+"})
ALL_FIND_GLOBAL_OPTION_FLAGS_WITHOUT_VALUE: frozenset[str] = frozenset({"-H", "-L", "-P"})
ALL_FIND_GLOBAL_OPTION_FLAGS_TAKING_A_VALUE: frozenset[str] = frozenset({"-D"})
FIND_OPTIMIZATION_LEVEL_OPTION_PREFIX: str = "-O"
ALL_BENIGN_COMPOUND_SEGMENT_COMMANDS: frozenset[str] = frozenset(
    {
        "echo",
        "printf",
        "gh",
        "head",
        "tail",
        "cat",
        "ls",
        "grep",
        "wc",
        "sort",
        "uniq",
        "true",
        "git",
    }
)
OUTPUT_REDIRECTION_OPERATOR_PATTERN: str = r"(?:\d+|&)?>>?\|?(?!&[\d-])"
ALL_FILE_WRITING_OUTPUT_FLAGS_BY_BENIGN_PROGRAM: dict[str, frozenset[str]] = {
    "sort": frozenset({"-o", "--output"}),
}
ALL_GIT_CONFIG_READ_ONLY_FLAGS: frozenset[str] = frozenset(
    {"--get", "--get-all", "--get-regexp", "--list", "-l", "--get-urlmatch"}
)
ALL_GIT_REMOTE_READ_ONLY_VERBS: frozenset[str] = frozenset({"show", "get-url"})
ALL_GIT_FETCH_FORCE_FLAGS: frozenset[str] = frozenset({"-f", "--force"})
ALL_GH_HTTP_WRITE_METHOD_FLAGS: frozenset[str] = frozenset({"-X", "--method"})
ALL_GH_HTTP_WRITE_METHODS: frozenset[str] = frozenset({"POST", "PUT", "PATCH", "DELETE"})
GH_HTTP_READ_ONLY_METHOD: str = "GET"
GH_SHORT_METHOD_FLAG_PREFIX: str = "-X"
GH_LONG_METHOD_FLAG_EQUALS_PREFIX: str = "--method="
ALL_GH_API_REQUEST_BODY_FIELD_FLAGS: frozenset[str] = frozenset(
    {"-f", "--raw-field", "-F", "--field", "--input"}
)
ALL_GH_API_GLUED_REQUEST_BODY_FIELD_FLAG_PREFIXES: tuple[str, ...] = (
    "-f",
    "-F",
    "--raw-field=",
    "--field=",
    "--input=",
)
ALL_READ_ONLY_GIT_SUBCOMMANDS: frozenset[str] = frozenset(
    {
        "status",
        "log",
        "show",
        "diff",
        "rev-parse",
        "rev-list",
        "describe",
        "config",
        "remote",
        "fetch",
        "ls-files",
        "ls-remote",
        "ls-tree",
        "cat-file",
        "blame",
        "shortlog",
        "name-rev",
        "for-each-ref",
        "symbolic-ref",
        "merge-base",
        "count-objects",
        "version",
        "help",
    }
)
ALL_READ_ONLY_GH_SUBCOMMANDS: frozenset[str] = frozenset(
    {
        "view",
        "list",
        "status",
        "checks",
        "diff",
        "search",
        "browse",
        "api",
    }
)
ALL_READ_ONLY_SUBCOMMANDS_BY_DISPATCHING_PROGRAM: dict[str, frozenset[str]] = {
    "git": ALL_READ_ONLY_GIT_SUBCOMMANDS,
    "gh": ALL_READ_ONLY_GH_SUBCOMMANDS,
}
ALL_READ_ONLY_SUBCOMMAND_POSITION_DEPTHS_BY_DISPATCHING_PROGRAM: dict[str, int] = {
    "git": 1,
    "gh": 2,
}
LAUNCHER_POSITIONAL_VALUE_SHAPE_PATTERN: str = (
    r"^(?:0x[0-9A-Fa-f]+"
    r"|[0-9]+(?:[.,][0-9]+)?[smhd]?"
    r"|[0-9]+(?:-[0-9]+)?(?:,[0-9]+(?:-[0-9]+)?)*)$"
)
ALL_LAUNCHER_OPTIONS_TAKING_SEPARATE_VALUE: frozenset[str] = frozenset(
    {
        "-s",
        "--signal",
        "-k",
        "--kill-after",
        "-n",
        "-o",
        "--output",
        "-e",
        "--error",
        "-i",
        "--input",
        "--classdata",
    }
)
ALL_SUBSHELL_GROUPING_CHARACTERS: str = "({"
ALL_KNOWN_TEMPORARY_ENVIRONMENT_VARIABLE_NAMES: frozenset[str] = frozenset(
    {
        "TEMP",
        "TMP",
        "TMPDIR",
        "CLAUDE_JOB_DIR",
    }
)
