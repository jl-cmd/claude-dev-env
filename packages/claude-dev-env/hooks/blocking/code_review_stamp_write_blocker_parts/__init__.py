"""Concern modules of the code-review stamp write blocker, wired by the entry hook.

The entry hook ``code_review_stamp_directory_write_blocker.py`` imports two
public matchers from this package to keep its own file short: a split
directory-change matcher and an obfuscated-path-write matcher. Each mirrors the
sibling verdict-directory guard's logic against the code-review stamp segments.
"""
