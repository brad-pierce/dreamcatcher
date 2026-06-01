#!/usr/bin/env python3
"""desktop_status.py - desktop SessionStart hook handler.

Emits a short status line to stdout -- Claude Code injects SessionStart
stdout into the session as context. So the user doesn't have to
manually check whether a candidate is awaiting review, when the last dream
ran, whether the reverie is recent, or whether anything in the logs looked
weird.

Runs synchronously (no async). Keep it fast -- a slow SessionStart hook
delays every session start. Target: <1s. The only IO is a few stats, a
small file read, and one short git log.
"""

import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import _dream_common as dc

dc.setup_utf8_io()

_WARN_PATTERN = re.compile(r"^\[.*\] (ERROR|WARN) ")


def list_candidates(candidate_root: Path) -> "tuple[int, str]":
    if not candidate_root.is_dir():
        return 0, ""
    try:
        entries = sorted(d for d in candidate_root.iterdir() if d.is_dir())
    except OSError:
        return 0, ""
    if not entries:
        return 0, ""
    return len(entries), entries[-1].name


def last_dream_commit(memory_root: Path) -> str:
    if not (memory_root / ".git").is_dir():
        return ""
    try:
        result = subprocess.run(
            [
                "git", "log", "-1", "--format=%cr - %s",
                "--grep=^dream:", "--grep=^bootstrap:",
            ],
            cwd=memory_root,
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return ""


def count_recent_warnings(log_dir: Path) -> int:
    if not log_dir.is_dir():
        return 0
    today = datetime.now().date()
    days = [today, today - timedelta(days=1)]
    total = 0
    for day in days:
        ds = day.strftime("%Y-%m-%d")
        candidates = [log_dir / f"dream-{ds}.log", *log_dir.glob(f"hook-*-{ds}.log")]
        for f in candidates:
            if not f.is_file():
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for line in text.splitlines():
                if _WARN_PATTERN.match(line):
                    total += 1
    return total


def reverie_age(state_root: Path) -> str:
    f = state_root / "reverie.json"
    if not f.is_file():
        return ""
    try:
        mtime = f.stat().st_mtime
    except OSError:
        return ""
    hours = int((time.time() - mtime) // 3600)
    if hours < 36:
        return f"{hours}h ago"
    return f"{hours // 24}d ago"


def main() -> int:
    memory = dc.memory_root()
    if not memory.is_dir():
        # Bootstrap hasn't run. Stay silent rather than emit confusion every
        # session start. The bootstrap itself will produce its own status.
        return 0

    candidate_count, newest = list_candidates(memory / ".candidate")
    last_dream = last_dream_commit(memory)
    warnings = count_recent_warnings(dc.log_dir())
    reverie = reverie_age(dc.state_root())

    print("Dream status (desktop):")
    if candidate_count > 0:
        print(f"  Pending review: {candidate_count} candidate(s); newest: {newest}")
    else:
        print("  Pending review: none")
    if last_dream:
        print(f"  Last dream commit: {last_dream}")
    if reverie:
        print(f"  Reverie last updated: {reverie}")
    if warnings > 0:
        print(f"  WARN: {warnings} warning(s)/error(s) in dream or hook logs (last 2 days)")

    # v1.3 (2026-05-22): inject the cross-project memory itself so Claude
    # has the user's preferences and the topic-file index from the first message
    # of every session. Pre-v1.3 the hook only emitted the status block
    # above; the actual memory content was never wired to consumption.
    dc.emit_memory_priming()
    return 0


if __name__ == "__main__":
    sys.exit(main())
