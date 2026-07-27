"""Decomposed modules that make up the code-rules gate entry point.

Each module owns one concern of the gate: enforcer loading, git file-set
resolution, added-line maps, violation scoping, wrapper plumb-through
detection, gate execution, and staged-test running. The ``code_rules_gate``
entry module in the parent directory wires them together.
"""
