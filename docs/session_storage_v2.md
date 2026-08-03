# Learning session storage v2

Learning sessions use schema `2.0`. Version `1.0` files are migrated in memory
when loaded and are written as `2.0` on the next save.

Version 2 adds:

- a user-editable `display_name`;
- per-session UI state for the result tab, completion tab, and Field display;
- clone support with a new session UUID; and
- the existing analysis, dialogue, token diagnostics, and learning state.

## Write and recovery behavior

`JsonSessionRepository` writes a temporary file, flushes it to disk, and
atomically replaces the primary JSON file. Before replacing an existing valid
primary file, it copies that file to `.json.bak`.

If the primary file cannot be decoded or validated, the repository loads the
last valid backup and restores the primary file. The GUI reports that recovery.
If neither copy is usable, session listing skips only that session and keeps
the remaining sessions available. Unrecoverable files are retained for manual
inspection rather than deleted automatically.

Deleting a session removes its primary, backup, and temporary files after the
existing GUI confirmation.

## UI persistence

The current result tab, completion tab, and Field quantity are saved whenever
they change. Rename and clone operations are available in the Case Study
session bar. Reset keeps the current session name and UI preferences while
clearing its learning content.

I-V, Field, and Case free-question panels expose a retry button after a provider
failure. A provider-recommended wait is shown as a countdown; an available
intent checkpoint is reused by the existing question pipeline.
