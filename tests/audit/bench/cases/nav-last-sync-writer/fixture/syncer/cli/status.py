from pathlib import Path

from syncer.store import keys
from syncer.store.backend import read_document


def describe(path: Path) -> str:
    document = read_document(path)
    return f"last sync: {document.get(keys.FIELD_LAST_SYNC, 'never')}"
