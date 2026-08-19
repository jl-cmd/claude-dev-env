"""Copy and verify canonical docs under .cursor/docs/."""

import shutil
from pathlib import Path

from sync_to_cursor.config import ALL_CANONICAL_DOC_FILES
from sync_to_cursor.hashing import sha256_bytes


def sync_canonical_docs(
    claude: Path,
    cursor: Path,
    dry_run: bool,
    quiet: bool,
) -> dict:
    docs_out = cursor / "docs"
    if not dry_run:
        docs_out.mkdir(parents=True, exist_ok=True)
    new_docs: dict = {}
    for each_name in ALL_CANONICAL_DOC_FILES:
        src = claude / "docs" / each_name
        dst = docs_out / each_name
        if not src.is_file():
            if dst.is_file():
                if not dry_run:
                    dst.unlink()
                if not quiet:
                    print(f"WARN     docs/{each_name} (source removed — deleted stale copy at {dst})")
            elif not quiet:
                print(f"WARN     docs/{each_name} (missing source: {src})")
            continue
        key = f"docs/{each_name}"
        src_hash = sha256_bytes(src.read_bytes())
        if dry_run:
            if dst.is_file():
                out_hash = sha256_bytes(dst.read_bytes())
            else:
                out_hash = ""
        else:
            shutil.copy2(src, dst)
            out_hash = sha256_bytes(dst.read_bytes())
        new_docs[key] = {"sources_hash": src_hash, "output_hash": out_hash}
    return new_docs


def check_canonical_docs(claude: Path, cursor: Path, docs_entries: dict) -> bool:
    for each_name in ALL_CANONICAL_DOC_FILES:
        key = f"docs/{each_name}"
        src = claude / "docs" / each_name
        dst = cursor / "docs" / each_name
        if not src.is_file():
            if key in docs_entries:
                return False
            continue
        if not dst.is_file():
            return False
        src_hash = sha256_bytes(src.read_bytes())
        dst_hash = sha256_bytes(dst.read_bytes())
        prev = docs_entries.get(key)
        if not prev:
            return False
        if prev.get("sources_hash") != src_hash:
            return False
        if prev.get("output_hash") != dst_hash:
            return False
    return True
