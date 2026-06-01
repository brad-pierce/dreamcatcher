# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## What this repo is

This is the **design and reference implementation** for **Dreamcatcher** (originally codenamed "The Dreaming") — a cross-project memory consolidation system for Claude Code. The current version is **v1.4**. The artifacts here are *not* the running system; they are what `setup.py` deploys to `~/Dreamcatcher/` and `~/.claude/`.

**Reading order for non-trivial work:** `00-README.md` (project handoff) → `README.md` (architecture overview) → the deployed prompts in `commands/` (`dream-global.md`, `dream-bootstrap.md`, `dream-audit.md`) → `Dreamcatcher - Architecture.docx` for the full as-built design (sanity-floor definitions, JSON log schema, threat model, rollback semantics).

## Architecture in one paragraph

Per-project Auto Dream (built into Claude Code) is the lower tier; this system adds a global tier at `~/Dreamcatcher/memory/` (a git repo with `MEMORY.md` index + topic files) that consolidates across projects. The two-store pattern (candidate → live) is preserved structurally, but the candidate-to-live step is owned by the dream agent itself via `dream_promote.py` running sanity floors and committing on pass; `promote.py` survives as the escape hatch when a floor trips. Both desktop and laptop are dream-writers sharing memory through a private git remote with an hourly `dreamcatcher-pull.py` cron on each machine and a pre-pull at the top of every `/dream-global` cycle. The `SessionStart` hook injects `MEMORY.md` + `working-style.md` into every session at session start; `~/CLAUDE.md` tells Claude where the other topic files live and when to read each on demand. Per-machine state (`reverie.json`, backups, logs) lives under `~/Dreamcatcher/state/` and deliberately stays out of git.

## Repo layout (what to know that isn't obvious)

- **`commands/*.md`** are the slash command prompts `setup.py` copies verbatim to `~/.claude/commands/`. `dream-global.md`, `dream-bootstrap.md`, and `dream-audit.md` are the three core prompts (nightly consolidation, one-time bootstrap, monthly audit); `dream-export.md`, `dream-import.md`, `dream-prime.md`, and `dream-rollback.md` are the utility wrappers. Editing a prompt here changes the deployed command on the next `setup.py` run — treat them as production text.
- **`scripts/_dream_common.py`** is the shared helper imported by every hook and CLI script. All Python lives in `scripts/` in the repo; `setup.py` deploys it to `~/Dreamcatcher/hooks/` at install time. Path resolution precedence is `env var > config.json > default ~/Dreamcatcher/...`. When adding a new well-known path, extend `_resolved_v11` rather than hard-coding.
- **`templates/bootstrap-scope-template.md`** and **`templates/seed-from-claude-ai-template.md`** are the hand-authoring guides the `/dream-bootstrap` flow points the user at during first-time setup; `setup.py` references them from its post-install instructions.
- **`templates/CLAUDE-memory-section.md`** is the marker-wrapped snippet `setup.py` step 9 pastes into `~/CLAUDE.md` so new-user installs get the on-demand-read pointer wired automatically.
- **`tools/gen_*.py`** are DOCX generators (`Dreamcatcher - Architecture.docx`, `Dreamcatcher - Product Overview.docx`). Regenerate after any prompt or hook change that the as-built docs claim is part of the current system.
- **`docs/laptop-setup.md`** is the operational runbook for joining a desktop running v1.3.
- **`archive/`** holds the original bash predecessors. Reference material only — do not edit them and do not let them drift back into use.
- **No automated test suite.** Verification is smoke tests run manually (install dry-run, synthetic hook events, standalone hook execution, end-to-end probe questions in a fresh Claude Code session).

## Hard conventions

- **Python 3.8+, stdlib only.** No `pip install`, no third-party deps at runtime. `python-docx` is the one exception, used only by `tools/gen_*.py` for DOCX generation — not by anything in the runtime path.
- **Cross-platform: Windows and macOS, no WSL.** Use `pathlib.Path`, `os.path.expanduser`, `shutil`. Never `$HOME` in command strings, never POSIX-only shell expansion. `setup.py` writes platform-appropriate interpreter names (`python` on Windows, `python3` on macOS) into `settings.json`.
- **`reverie.json`, never `cursor.json`.** Same for `reverie-backups/`, `reverie-YYYY-MM-DDTHHMMSS.json`, and `--keep-reverie`. The rename is settled; any `cursor` in a non-archive file is a bug.
- **Discovery is bounded.** Stage 1 bootstrap and nightly find passes only walk paths listed in `~/Dreamcatcher/state/config.json` → `discovery_roots`. Do not introduce unbounded `find ~/` style walks.
- **Hooks never block on errors.** `PreCompact` exiting 2 hangs Claude Code. Hook handlers exit 0 on any non-fatal condition and log failures to `~/Dreamcatcher/state/logs/`. Logging itself must swallow exceptions.
- **UTF-8 stdout/stderr** in every script that prints — call `dc.setup_utf8_io()` early. Windows default `cp1252` corrupts memory file content (em-dashes, BOMs).
- **Manual sync ≠ backup.** File-level backup tools protect against loss but do not move consolidations between machines. The cross-machine transport is the git remote, not Time Machine or Backblaze.
- **Prepull before mutating live memory.** `/dream-global` (Phase 0) and `promote.py` and `dream_promote.py` all call `dc.prepull_memory()` at the top. It returns a structured status; single-machine installs hit the benign no-remote branch.
- **Auto-promote is gated by sanity floors.** `dream_promote.py` aborts to `REQUIRES_REVIEW` if a candidate would change more than `DELTA_PCT_FLOOR` (50%) of memory line-volume or has structural validity problems. Real semantic mistakes are caught by `dream-rollback --run <run-id>`, not by floors at promotion time.
- **Do not write to `~/Dreamcatcher/memory/` directly.** Updates flow through `/dream-global` (auto-promote) or `promote.py` (escape hatch). Read-only outside that pipeline.

## Common operations

```bash
# Verify install plan without touching anything
python setup.py --dry-run --yes

# Install (idempotent; --laptop variant for the secondary machine)
python setup.py --yes
python setup.py --yes --laptop

# Dream cycle, interactive (manual, in a live session):
#   /dream-global
# Dream cycle, scheduled/headless (what the nightly runner does): slash commands
# are interactive-only, so feed the staged prompt CONTENT to claude -p:
claude -p "$(cat ~/Dreamcatcher/prompts/dream-global.md)" --allowedTools "Bash,Read,Write,Edit"

# Browse the audit log
python ~/Dreamcatcher/hooks/dreamcatcher-log.py list
python ~/Dreamcatcher/hooks/dreamcatcher-log.py show <run-id>
python ~/Dreamcatcher/hooks/dreamcatcher-log.py grep <pattern>

# Sync (also hourly via cron)
python ~/Dreamcatcher/hooks/dreamcatcher-pull.py

# Load memory into an existing session (manual switch for sessions opened before SessionStart wired)
# In a Claude Code session:
/dream-prime

# Rollback a bad dream
python dream-rollback.py --run <run-id>     # by structured run-id from JSON log
python dream-rollback.py --list             # interactive picker over recent dream commits

# Cross-machine fallback (first-time seed or air-gap; not the default)
python dream-export.py                      # writes ~/Downloads/dream-export-<ts>.tgz
python dream-import.py <bundle.tgz>         # refuses if local has commits the bundle doesn't

# Manual promote (escape hatch when a sanity floor tripped or for hand-edits)
python promote.py --list
python promote.py --dry-run [<candidate-name>]
python promote.py [<candidate-name>]

# Regenerate the as-built docs after a prompt or hook change
python tools/gen_architecture_docx.py
python tools/gen_product_overview_docx.py
```

In the repo, all Python lives in `scripts/`. After install, deployed scripts live at `~/Dreamcatcher/hooks/` and are invoked from there by the slash command wrappers and the scheduled jobs. Every script resolves `_dream_common.py` alongside itself, so the import works whether it runs from the repo's `scripts/` dir or the deployed `~/Dreamcatcher/hooks/`. Preserve that lookup when reorganizing.

## Editing the prompts and docs

If you change behavior, change the affected prompt or doc *and* the code in the same commit. The prompts in `commands/` (`dream-global.md`, `dream-bootstrap.md`, `dream-audit.md`) ship to users on next install — treat them as production text. The DOCX generators in `tools/` are also production text; regenerate the DOCX files when their content claims become stale.

## Live state on this clone

- Source repo origin: whichever repo you cloned this from. Latest tag: `v1.3.1`.
- Memory remote: a private git repo configured as `origin` on `~/Dreamcatcher/memory/`, shared between desktop and laptop.
- Scheduled tasks: desktop nightly at 02:00 PDT, laptop nightly at 03:00 PDT, hourly `Dreamcatcher-Pull` on each machine.
