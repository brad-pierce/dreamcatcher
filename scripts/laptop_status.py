#!/usr/bin/env python3
"""laptop_status.py - laptop SessionStart hook handler.

Inspects local memory state and any dream-export bundles waiting to import.
Emits a short status line to stdout -- Claude Code injects SessionStart
stdout into the session as context.

This replaces the bash `laptop-sync.sh`. The laptop hook deliberately does
not run `git pull`. Sync is manual:
    desktop: /dream-export  ->  transfer bundle  ->  laptop: /dream-import <path>
This hook just inspects what's there and tells the user whether anything is
pending. The user's eyes are the authority on whether to import.

Runs synchronously. Target: <1s. Settings.json gives it 30s of headroom for
the rare case the git status is slow on a cold disk.
"""

import subprocess
import sys
from pathlib import Path

import _dream_common as dc

dc.setup_utf8_io()

log = dc.logger("status")


def memory_state(memory_root: Path) -> "tuple[str, str]":
    """Return (last_commit_desc, state) where state is 'clean' or 'dirty'."""
    if not (memory_root / ".git").is_dir():
        return "", ""

    last_commit = ""
    try:
        r = subprocess.run(
            ["git", "log", "-1", "--format=%cr - %s"],
            cwd=memory_root, capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0:
            last_commit = r.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass

    state = ""
    try:
        r = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=memory_root, capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0:
            state = "dirty" if r.stdout.strip() else "clean"
    except (OSError, subprocess.TimeoutExpired):
        pass

    return last_commit, state


def pending_imports(export_dir: Path) -> "list[Path]":
    """List dream-export-*.tgz bundles in the export directory, newest first."""
    if not export_dir.is_dir():
        return []
    try:
        bundles = sorted(
            export_dir.glob("dream-export-*.tgz"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    except OSError:
        return []
    return bundles


def last_import_marker() -> str:
    """Filename of the most recently imported bundle, if /dream-import has
    written a marker. Empty string if none.
    """
    marker = dc.state_root() / "last-import.txt"
    if not marker.is_file():
        return ""
    try:
        return marker.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def main() -> int:
    memory = dc.memory_root()
    if not memory.is_dir():
        print("Global memory not initialized on this machine.")
        print("Run setup.py, then import the first /dream-export bundle from the desktop.")
        log("INFO no memory store")
        return 0

    last_commit, state = memory_state(memory)
    bundles = pending_imports(dc.export_dir())
    last_imported = last_import_marker()

    print("Dream status (laptop):")
    if last_commit:
        print(f"  Last consolidation: {last_commit}")
    if state == "dirty":
        print("  Local memory has uncommitted changes (scratch present).")
        print("  /dream-import will refuse silent overwrite -- commit or stash first.")
    if bundles:
        newest = bundles[0]
        already = (newest.name == last_imported)
        if already:
            print(f"  Newest export bundle already imported: {newest.name}")
        elif len(bundles) == 1:
            print(f"  Export bundle waiting to import: {newest.name}")
            print(f"  Run: /dream-import {newest}")
        else:
            print(f"  {len(bundles)} export bundles present; newest: {newest.name}")
            print(f"  Run: /dream-import {newest}")

    log(f"OK status emitted (commit={last_commit!r}, state={state}, "
        f"bundles={len(bundles)}, last_imported={last_imported!r})")

    # v1.3 (2026-05-22): inject the cross-project memory itself so Claude
    # has the user's preferences and the topic-file index from the first message
    # of every session. Same shape as desktop_status.py; both machines get
    # the same priming since both can be the primary working machine.
    dc.emit_memory_priming()
    return 0


if __name__ == "__main__":
    sys.exit(main())
