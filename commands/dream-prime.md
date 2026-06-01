---
description: Load the Dreamcatcher cross-project memory into the current session
---

Load the user's cross-project Dreamcatcher memory into this session. Useful for existing sessions started before v1.3's `SessionStart` injection was deployed, or for forced refreshes after a manual edit to the memory store.

Do this:

1. Read `~/Dreamcatcher/memory/MEMORY.md` — the topic-file index, plus the dated decisions list.
2. Read `~/Dreamcatcher/memory/working-style.md` — stable preferences and editorial standards (deliverable formats, narrative voice, taste-call division, write-back automation defaults, etc.).
3. Report back, in three or four lines, what is now loaded. Include:
   - The number of topic files indexed in MEMORY.md and the number of decisions listed.
   - The two or three most load-bearing rules from working-style.md (whichever are most likely to apply to this session's apparent work).
   - A reminder that the other topic files are available on demand via `Read` on the absolute paths listed in MEMORY.md (`~/Dreamcatcher/memory/customer-context.md`, `practice-context.md`, `tooling-environment.md`, `active-deliverables.md`, `personal-context.md`, `decisions/*.md`).

After this, treat the contents of those two files as authoritative for collaboration norms and deliverable defaults for the rest of this session.

If `~/Dreamcatcher/memory/MEMORY.md` does not exist, report that the memory store is not initialized on this machine and stop — do not invent content. The user should run `python setup.py` from the Dreamcatcher source repo and complete the bootstrap (`/dream-bootstrap`) before `/dream-prime` will have anything to load.
