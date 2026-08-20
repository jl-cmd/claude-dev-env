"""Shared XML utilities for pr-loop scripts."""

from __future__ import annotations

from xml.dom import minidom
from xml.etree.ElementTree import Element, tostring


def emit_pretty_xml(root: Element) -> str:
    """Serialize an ElementTree to a pretty-printed XML string.

    Args:
        root: Root XML element.

    Returns:
        Pretty-printed XML string.
    """
    raw_text = tostring(root, encoding="unicode")
    reparsed_dom = minidom.parseString(raw_text)
    return reparsed_dom.toprettyxml(indent="  ")
