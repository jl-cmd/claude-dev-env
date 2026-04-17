"""Shared gh body-arg parsing utilities for blocking hooks."""

body_file_flag: str = "--body-file"
body_file_flag_prefix: str = "--body-file="

all_body_flags: frozenset[str] = frozenset({"--body", "-b"})
all_body_flag_prefixes: tuple[str, ...] = ("--body=", "-b=")
all_value_flags: frozenset[str] = frozenset(
    {
        "--title",
        "-t",
        "--reviewer",
        "-r",
        "--assignee",
        "-a",
        "--label",
        "-l",
        "--milestone",
        "-m",
        "--project",
        "-p",
        "--base",
        "-B",
        "--head",
        "-H",
        "--repo",
        "-R",
        body_file_flag,
    }
)


def get_logical_first_line(command: str) -> str:
    logical = ""
    for each_line in command.splitlines():
        stripped_line = each_line.rstrip()
        is_backslash_continuation = (
            stripped_line.endswith("\\") and stripped_line.count("\\") % 2 == 1
        )
        is_powershell_backtick_continuation = (
            stripped_line.endswith("`") and stripped_line.count("`") % 2 == 1
        )
        if is_backslash_continuation or is_powershell_backtick_continuation:
            logical += stripped_line[:-1].rstrip() + " "
        else:
            logical += each_line
            break
    return logical.strip()
