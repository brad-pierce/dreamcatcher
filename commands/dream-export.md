---
description: Bundle global memory into a transferable tarball for the laptop
---

The dream-export script tars `~/Dreamcatcher/memory/` (including `.git/`) into a single `.tgz` you can move to the laptop however you like — USB stick, AirDrop, email, file share. On the laptop, `/dream-import` applies it.

The script is non-interactive and short. Output is the path of the bundle.

To run it, open a terminal and execute:

```
python ~/Dreamcatcher/hooks/dream-export.py $ARGUMENTS
```

Arguments:
- *(no args)* — bundle the current memory to `<export_dir>/dream-export-YYYY-MM-DD-HHMM.tgz` (export_dir defaults to `~/Downloads/`; configurable in `~/Dreamcatcher/state/config.json`)
- `--dry-run` — report what would be bundled; touch nothing
- `--out <path>` — override the output location

What it does NOT do:
- It does not push anywhere. The bundle is a local file; transferring it is your call (manual sync is a deliberate design decision).
- It does not export a dirty tree. Commit or stash uncommitted scratch before running, otherwise the export refuses.
- It does not delete or rotate old bundles. The export directory accumulates; trim manually when you want to.
