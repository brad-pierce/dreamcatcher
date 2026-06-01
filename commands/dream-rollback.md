---
description: Revert a dream commit and roll back reverie.json as one operation
---

The dream-rollback script wraps `git revert` plus `reverie.json` rollback as a single operation. Without the reverie piece, rollback is half a remedy — the next nightly dream skips the very transcripts that produced the bad consolidation, and the chance to redo them with a tweaked prompt is lost.

The script is interactive (prompts before destructive operations), so it needs to run in a real terminal rather than through this Claude Code session.

To run it, open a terminal and execute:

```
python ~/Dreamcatcher/hooks/dream-rollback.py $ARGUMENTS
```

Arguments:
- *(no args)* — present a picker over recent dream/bootstrap commits
- `<sha>` — revert this specific commit
- `--list` — list recent dream commits and exit (no destructive action)
- `--keep-reverie [sha]` — revert but skip the reverie rollback step (rare; only when the transcripts that produced the bad commit are no longer worth re-mining)

After you've run it, I can read `~/Dreamcatcher/state/logs/rollback-$(date +%Y-%m-%d).log` and help interpret the outcome — useful especially if the revert hit conflicts or the reverie restore had to fall back to manual editing.

Sanity reminder, in case you got here in a hurry:
- This does **not** force-push or rewrite history. The laptop has likely already pulled the bad commit; a forward-moving revert is what makes the correction safe across the desktop/laptop topology.
- If the working tree is dirty (uncommitted scratch, for example), the script refuses to operate. Commit or stash first.
- For taxonomy mistakes — wrong topic shape, two files that should merge — this is the wrong tool. Use a manual restructure commit instead.
