from pathlib import Path

from syncer.store import keys
from syncer.store.backend import read_document, write_document


def reset_owner(path: Path, owner: str) -> None:
    document = read_document(path)
    document[keys.FIELD_OWNER] = owner
    write_document(path, document)
