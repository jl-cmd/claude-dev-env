#!/usr/bin/env python3
"""Cross-platform clipboard writes for prompt-workflow XML artifacts."""

from __future__ import annotations

import os


def _clipboard_disabled_by_env() -> bool:
    flag = os.environ.get("PROMPT_WORKFLOW_SKIP_CLIPBOARD", "").strip().lower()
    return flag in {"1", "true", "yes", "on"}


def copy_text_to_system_clipboard(text: str) -> bool:
    """Write ``text`` to the OS clipboard using Python-only backends.

    Tries :mod:`tkinter` (stdlib) first, then optional ``pyperclip`` if installed.
    Returns ``True`` when a backend reports success, ``False`` otherwise
    (missing dependency, headless display, empty payload, or env opt-out).
    """
    if not text.strip():
        return False
    if _clipboard_disabled_by_env():
        return False
    if _copy_via_tkinter(text):
        return True
    return _copy_via_pyperclip(text)


def _copy_via_tkinter(text: str) -> bool:
    try:
        import tkinter as tk
    except ImportError:
        return False
    root: tk.Tk | None = None
    try:
        root = tk.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update_idletasks()
        root.update()
        return True
    except Exception:
        return False
    finally:
        if root is not None:
            try:
                root.destroy()
            except Exception:
                pass


def _copy_via_pyperclip(text: str) -> bool:
    try:
        import pyperclip
    except ImportError:
        return False
    try:
        pyperclip.copy(text)
        return True
    except Exception:
        return False
