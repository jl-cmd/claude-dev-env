import json
from pathlib import Path

CACHE_PATH = Path(__file__).resolve().parent.parent / "build" / "cache.json"


def greeting(name: str) -> str:
    if CACHE_PATH.exists():
        cached = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        if name in cached:
            return str(cached[name])
    return f"Hello, {name}!"
