def fetch_since(cursor: str) -> tuple[list[dict], str]:
    return [], cursor or "0"
