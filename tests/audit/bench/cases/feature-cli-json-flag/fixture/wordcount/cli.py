import argparse
import sys
from pathlib import Path


def count(text: str) -> tuple[int, int, int]:
    return len(text.splitlines()), len(text.split()), len(text)


def main(all_arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wordcount")
    parser.add_argument("file")
    arguments = parser.parse_args(all_arguments)
    lines, words, characters = count(Path(arguments.file).read_text(encoding="utf-8"))
    print(f"{lines} {words} {characters}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
