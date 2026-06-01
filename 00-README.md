# Dreamcatcher — Project Handoff

> **Current version: v1.4.** Cross-project memory consolidation for Claude Code. Both desktop and laptop are dream-writers sharing memory through a private git remote. The nightly cycle is autonomous on the happy path; SessionStart injects the always-applicable memory into every session. This file is the working summary; `README.md` is the GitHub front door and `Dreamcatcher - Architecture.docx` is the full as-built design reference.

## What this is

Dreamcatcher (originally codenamed "The Dreaming") is a memory layer that sits above Claude Code's per-project Auto Dream. It captures patterns, preferences, customer context, practice context, tooling environment, in-flight deliverables, and dated decisions that span every project the user works on. The store at `~/Dreamcatcher/memory/` is loaded automatically into every Claude Code session at session start, so the user stops re-explaining themselves.

## How it works (one paragraph)

A scheduled task fires the nightly consolidation by feeding the staged prompt content to `claude -p` (slash commands are interactive-only, so the scheduler does not invoke `/dream-global` directly; the same prompt is available interactively as `/dream-global`). The run pulls the latest live store from a private git remote, reads each project's transcripts newer than the per-project reverie marker, writes a candidate to `.candidate/<run-timestamp>/` mirroring the live store's layout, validates the candidate against sanity floors (delta-percentage, structural validity), applies on pass, writes a structured JSON audit log to `memory/.dream-log/<run-id>.json`, makes a parseable structured commit, and pushes. An hourly `dreamcatcher-pull.py` cron on each machine keeps both clones current between runs. `SessionStart` hooks inject `MEMORY.md` and `working-style.md` into the session context at every new session; `~/CLAUDE.md` tells Claude where the other topic files live and when to read each on demand.

## Component inventory

```
setup.py                         cross-platform installer (idempotent)
scripts/                         all runtime Python (setup.py deploys to ~/Dreamcatcher/hooks/)
  _dream_common.py               shared helpers (path resolution, prepull, priming)
  snapshot_transcript.py         PreCompact handler
  queue_session.py               SessionEnd handler
  desktop_status.py              SessionStart handler, desktop (status + memory inject)
  laptop_status.py               SessionStart handler, laptop (status + memory inject)
  dream_promote.py               auto-promote pipeline (called from /dream-global Phase 5)
  dreamcatcher-pull.py           hourly git pull --ff-only cron wrapper
  dreamcatcher-log.py            browse memory/.dream-log/<run-id>.json
  promote.py                     manual escape hatch when a sanity floor trips
  dream-rollback.py              git revert + reverie restore (one op; --run flag)
  dream-export.py                bundle live memory as a tarball (fallback)
  dream-import.py                apply a bundle to local memory (with safety checks)
commands/                        slash command prompts (deployed to ~/.claude/commands/)
  dream-global.md, dream-bootstrap.md, dream-audit.md   the three core prompts
  dream-export.md, dream-import.md, dream-prime.md, dream-rollback.md   utilities
templates/CLAUDE-memory-section.md   appended by setup.py to ~/CLAUDE.md
templates/bootstrap-scope-template.md, templates/seed-from-claude-ai-template.md   bootstrap hand-authoring guides
tools/gen_architecture_docx.py       regenerates "Dreamcatcher - Architecture.docx"
tools/gen_product_overview_docx.py   regenerates "Dreamcatcher - Product Overview.docx"
docs/laptop-setup.md             runbook for joining a desktop from a second machine
```

## Reading order

If you are a fresh Claude session picking up this project, read in this order. Stop when you have enough context for the task at hand:

1. **This file** (00-README.md) — the working summary.
2. **README.md** — the architecture overview and threat model, pitched for a first-time reader.
3. **`Dreamcatcher - Architecture.docx`** — the full as-built design: sanity-floor definitions, JSON log schema, rollback semantics, redaction rules, the four-test filter.
4. **`commands/dream-global.md`** — the live `/dream-global` consolidation prompt (deployed to `~/.claude/commands/` by `setup.py`).
5. **`commands/dream-bootstrap.md`** — the one-time bootstrap prompt, plus the templates under `templates/` it relies on.
6. **`commands/dream-audit.md`** — the monthly reads-only audit prompt.
7. **`CLAUDE.md`** — repo conventions and the hard rules the code must preserve.

## Live state on this clone

- **Source repo:** the repo you cloned this from. Latest tag: `v1.3.1`.
- **Memory remote:** a private git repo you set up at install time, configured as `origin` on `~/Dreamcatcher/memory/`. Both desktop and laptop push and pull this.
- **Hooks deployed:** `~/Dreamcatcher/hooks/` on each machine; `~/.claude/commands/` has the slash command wrappers.
- **Scheduled tasks:**
  - Desktop nightly `/dream-global` at 02:00 PDT (Task Scheduler).
  - Laptop nightly `/dream-global` at 03:00 PDT (crontab or launchd).
  - Hourly `Dreamcatcher-Pull` on each machine.
- **CLAUDE.md wiring:** user-level `~/CLAUDE.md` contains the marker-wrapped "Cross-project memory (Dreamcatcher)" section pasted by `setup.py` step 9.

## How to continue with a fresh Claude

Suggested opening prompt:

> I'm continuing work on Dreamcatcher, a cross-project memory consolidation system for Claude Code. The current version is v1.3 (operational). Please read **00-README.md (this file), then README.md**, and skim `Dreamcatcher - Architecture.docx` plus the prompts under `commands/` if you need the as-built design. The next concrete pieces of work are (a) regenerating the architecture DOCX after any prompt or hook change, (b) macOS hardening of the laptop install if any rough edges surface, or (c) the Dream Team v2 design (`dream-team/00-foundation.md` plus the decision file in the live memory store).

If you are not in a Claude Code session but reading the repo on GitHub, start from `README.md` (the front-door doc) instead. It has the same architectural overview pitched for someone who has not seen the project before.

## Known soft spots

- The first auto-promote against a real production candidate happened 2026-05-21 on the desktop. Subsequent runs have been clean, but the sanity-floor calibration (delta-percentage threshold at 50%) has not been stress-tested over months of operation. Adjust by editing `DELTA_PCT_FLOOR` in `hooks/dream_promote.py` if it proves too lax or too tight.
- macOS launchd plist generation for the nightly is documented (in `docs/laptop-setup.md`) but `setup.py` does not auto-write it; the user runs the crontab line manually for now.
- `dream-rollback.py` interactive picker has not been exercised against a real bad commit since v1.3. First contact will almost certainly surface a quirk.
- The reverie-backups directory accumulates over time. A housekeeping task to cull backups older than 30 days is documented but not yet implemented.

## Out of scope (for now)

- Dream Team v2 (cross-developer consolidation, promotion service, redaction at submission). Designed but not built. See `dream-team/00-foundation.md` and `decisions/2026-05-17-dream-team-v2-concept-captured.md`.
- A web UI for browsing memory or audit logs. Today the surface is `~/Dreamcatcher/memory/` (a normal git repo) plus `dreamcatcher-log.py` for the JSON audit logs.
- Anything that requires third-party dependencies. The runtime is stdlib-only on purpose.
