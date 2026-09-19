import argparse
import sys
from collections import Counter
from pathlib import Path


def main(all_arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="toptokens")
    parser.add_argument("file")
    parser.add_argument("--top", type=int, default=10, help="how many tokens to show")
    parser.add_argument("--ignore-case", action="store_true", help="fold tokens to lower case")
    parser.add_argument("--min-length", type=int, default=1, help="skip shorter tokens")
    arguments = parser.parse_args(all_arguments)
    text = Path(arguments.file).read_text(encoding="utf-8")
    if arguments.ignore_case:
        text = text.lower()
    all_tokens = [each_token for each_token in text.split() if len(each_token) >= arguments.min_length]
    for each_token, each_count in Counter(all_tokens).most_common(arguments.top):
        print(f"{each_count} {each_token}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
