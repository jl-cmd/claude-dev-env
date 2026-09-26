---
name: step-notes
description: Turns the step-notes status-line gate on or off. While on, a hook asks for a short status line naming each tool action, like a progress caption, so the user can follow the session. Use when the user types /step-notes or asks to turn step notes on or off.
argument-hint: "[on | off | status]"
---

# /step-notes

The step-notes gate is a PreToolUse hook (`hooks/blocking/step_note_gate.py`). It is off by default. While it is on, each message that calls a tool starts with a short status line naming the action, such as "Reading hooks.json." or "Running the gate tests." A call with no status line fails with "Status line missing".

## Run the toggle

Pass the user's argument through. With no argument, the toggle flips the current state.

```
python "${CLAUDE_SKILL_DIR}/scripts/toggle_step_notes.py" <on|off|status>
```

Tell the user the line the script prints. The change applies at once, to every session on this machine.

## Status lines

A status line names the action and its target in a few words. One status line covers every call in the same message. Subagent calls pass without a check.

## Layout

| File | Role |
|---|---|
| `SKILL.md` | This flow: run the toggle, add status lines while the gate is on |
| `scripts/toggle_step_notes.py` | The on, off, flip, and status CLI for the flag file |
| `scripts/test_toggle_step_notes.py` | Behavior tests for each action |
| `scripts/step_notes_constants/toggle_step_notes_constants.py` | Flag path, action names, report lines |
