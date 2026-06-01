#!/usr/bin/env python3
"""queue_session.py - desktop SessionEnd hook handler.

Appends a pointer to the session into ~/.claude/dream-state/queue.jsonl so
the next nightly dream knows which sessions to look at without scanning all
of ~/.claude/projects/. Each line is a JSON object. Phase 2 of the dream
reads the queue; the reverie update for the project implicitly clears the
queue entry (the next run won't reach back past the marker).

Exits 0 on any non-fatal condition. SessionEnd exit codes don't block
anything user-visible, but spamming non-zero exits clutters the transcript
notice area.

Concurrency note: SessionEnd doesn't fire frequently enough to need a real
lock, and on POSIX appending a short JSON line (<PIPE_BUF) is atomic. On
Windows, append mode is serialized by the OS for short writes. So no flock.
"""

import json
import sys

import _dream_common as dc

log = dc.logger("queue")


def main() -> int:
    event = dc.read_event()
    session = event.get("session_id") or ""
    cwd = event.get("cwd") or ""
    transcript = event.get("transcript_path") or ""

    if not session:
        log("ERROR missing session_id in event")
        return 0

    queue_dir = dc.state_root()
    try:
        queue_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        log(f"ERROR cannot create {queue_dir}: {e}")
        return 0

    entry = {
        "session": session,
        "cwd": cwd,
        "transcript": transcript,
        "ts": dc.utc_now(),
    }
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    queue_file = queue_dir / "queue.jsonl"

    try:
        with queue_file.open("a", encoding="utf-8") as f:
            f.write(line)
    except OSError as e:
        log(f"ERROR append to {queue_file} failed: {e}")
        return 0

    log(f"OK queued {session} (cwd={cwd})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
