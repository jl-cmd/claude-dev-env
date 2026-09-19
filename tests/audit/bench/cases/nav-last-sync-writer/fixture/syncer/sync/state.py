from datetime import datetime, timezone
from pathlib import Path

from syncer.store import keys
from syncer.store.backend import read_document, write_document


def read_cursor(path: Path) -> str:
    return str(read_document(path).get(keys.FIELD_CURSOR, ""))


def record_completion(path: Path, cursor: str) -> None:
    document = read_document(path)
    document[keys.FIELD_CURSOR] = cursor
    document[keys.FIELD_LAST_SYNC] = datetime.now(timezone.utc).isoformat()
    write_document(path, document)
