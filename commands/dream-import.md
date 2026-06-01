---
description: Apply a dream-export bundle from the desktop to local global memory
---

The dream-import script validates a `dream-export-*.tgz` bundle produced by the desktop and applies it to local `~/Dreamcatcher/memory/`. It refuses to silently overwrite local-only commits — that's typically the laptop's own scratch.

To run it, open a terminal and execute:

```
python ~/Dreamcatcher/hooks/dream-import.py $ARGUMENTS
```

Arguments:
- `<path-or-filename>` — the bundle to apply. Bare filenames are looked up in the configured export directory (default `~/Downloads/`).
- `--dry-run` — validate, run the safety check, report; touch nothing.
- `--force` — bypass the divergence safety check. The local memory is still backed up to a timestamped sibling directory before the overwrite, so a forced import is recoverable.

Safety behavior:
- If the local repo has commits the bundle doesn't have (likely your laptop scratch), the script refuses with exit code 2 and tells you how to inspect. Either commit the scratch into a bundle of its own and have the desktop pull it in, or re-run with `--force` to discard.
- The current memory is moved to `memory.pre-import-<timestamp>` (a sibling under `~/Dreamcatcher/`) before the new bundle is laid down. Nothing is destroyed; if the import looks wrong, the backup is right next door.
- After import, `~/Dreamcatcher/state/last-import.txt` records the bundle filename. The laptop SessionStart hook reads this to tell you whether the newest bundle in your export directory is already applied.

After import, the new HEAD reflects the desktop's state plus a synthetic `import: ...` commit that traces back to the bundle.
