import sys
from pathlib import Path

_BENCH_DIRECTORY = str(Path(__file__).resolve().parent)

if _BENCH_DIRECTORY not in sys.path:
    sys.path.insert(0, _BENCH_DIRECTORY)

collect_ignore = ["cases"]
