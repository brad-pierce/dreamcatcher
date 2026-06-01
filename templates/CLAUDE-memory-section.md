<!--
Template snippet for ~/CLAUDE.md (user-level Claude Code instructions).

When setup.py detects that a user's ~/CLAUDE.md does not yet contain a
Dreamcatcher memory section, it points the user at this file and instructs
them to paste the content below (between the BEGIN and END markers) into
their ~/CLAUDE.md.

The BEGIN/END markers are how setup.py later detects that the section
already exists, so re-running setup.py is idempotent. Do not edit the
markers.
-->

<!-- BEGIN: Dreamcatcher memory section (managed by setup.py detection) -->

## Cross-project memory (Dreamcatcher)

This machine runs **Dreamcatcher**, a cross-project memory consolidation system. The live memory store is at `~/Dreamcatcher/memory/` (a git repo, synced between machines via a private remote). It captures patterns, preferences, customer engagement shapes, practice context, tooling environment, in-flight deliverables, and dated decisions that span all projects on this account.

**What's already in your context.** The `SessionStart` hook auto-injects two files at every session start:
- `MEMORY.md` — the index of topic files with one-line descriptions
- `working-style.md` — stable preferences and editorial standards (deliverable formats, narrative voice, division between taste calls and execution, defaults on write-back automations, etc.)

Treat the contents of those two files as authoritative for collaboration norms and deliverable defaults. They are the load-bearing context for most stylistic and procedural decisions.

**Read on demand** when the question intersects with the topic. Use the `Read` tool against the absolute path:
- `~/Dreamcatcher/memory/customer-context.md` — engagement patterns (customer names are excluded by policy unless the local install opts in)
- `~/Dreamcatcher/memory/practice-context.md` — practice context: your domain, recurring partners, standards, and tools
- `~/Dreamcatcher/memory/tooling-environment.md` — dev environment quirks, MCP servers, deployment standards, scheduling rules
- `~/Dreamcatcher/memory/active-deliverables.md` — what's in flight right now, with `_active-as-of:` markers
- `~/Dreamcatcher/memory/personal-context.md` — location, hobbies, prior background, family (only what the user has explicitly volunteered)
- `~/Dreamcatcher/memory/decisions/*.md` — dated architecture and strategy decisions; most recent decisions appear at the top of the index

**Heuristics for reading on demand:**
- Working on your professional domain (recurring partners, standards, tools) → read `practice-context.md` first
- Working on an internal tool, deployment, MCP server, or scheduling → read `tooling-environment.md`
- Question references a specific in-flight project by name → read `active-deliverables.md`
- Question references a past architectural choice ("why did we go with…") → scan `decisions/` (filenames are dated and slugged)
- Customer-engagement shape (methodology framework, evaluation rubric, etc.) → read `customer-context.md`

**Hard rule.** Do not write into `~/Dreamcatcher/memory/` directly. Updates flow through `/dream-global` (nightly auto-promote) or `promote.py` (manual escape hatch). The store is consumed read-only outside that pipeline.

If `~/Dreamcatcher/memory/` doesn't exist on the machine you're running on (fresh install before bootstrap, for example), the injection at session start will be silent — ignore this section.

<!-- END: Dreamcatcher memory section -->
