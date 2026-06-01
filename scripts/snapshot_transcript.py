#!/usr/bin/env python3
"""snapshot_transcript.py - desktop PreCompact hook handler.

Runs (async) before Claude Code compacts a session transcript. Copies the
transcript JSONL aside so the dream-global pass can read the un-degraded
source rather than the post-compaction version. Without this, long sessions
are systematically degraded as dream sources.

Exits 0 on any non-fatal condition. We never block compaction -- exit 2 on
PreCompact is a Claude Code hang vector. Errors go to the log; the user-
visible UX is "compaction proceeds normally."
"""

import shutil
import sys
import time
from pathlib import Path

import _dream_common as dc

log = dc.logger("snapshot")

_MIN_FREE_BYTES = 500 * 1024 * 1024  # 500 MB; matches bash version


def main() -> int:
    event = dc.read_event()
    transcript = event.get("transcript_path") or ""
    session = event.get("session_id") or ""

    if not transcript or not session:
        log(f"ERROR missing transcript_path or session_id; got: {str(event)[:200]}")
        return 0

    src = Path(transcript)
    if not src.is_file():
        log(f"ERROR transcript file not found: {src}")
        return 0

    snapshot_root = dc.inputs_root() / "precompact"
    try:
        snapshot_root.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        log(f"ERROR cannot create {snapshot_root}: {e}")
        return 0

    # Better to lose a snapshot than to fill the disk during a compaction
    # that's already under pressure.
    try:
        free = shutil.disk_usage(snapshot_root).free
        if free < _MIN_FREE_BYTES:
            log(f"WARN low disk space ({free // 1024} KB free); skipping snapshot for {session}")
            return 0
    except OSError:
        pass

    dest = snapshot_root / f"{session}-{int(time.time())}.jsonl"
    try:
        shutil.copyfile(src, dest)
    except OSError as e:
        log(f"ERROR copy failed: {src} -> {dest}: {e}")
        return 0

    try:
        size = dest.stat().st_size
    except OSError:
        size = -1
    log(f"OK snapshot saved: {dest} ({size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
