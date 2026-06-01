# Dreamcatcher

**v1.4** — Cross-project memory consolidation for Claude Code.

A single store of patterns, preferences, customer context, practice context, tooling environment, in-flight deliverables, and dated decisions that span every project a Claude Code user works on. The store gets consolidated automatically each night and gets loaded into every future Claude Code session automatically at session start. The user stops re-explaining themselves.

## How it works

Per-project Auto Dream (built into Claude Code) distills each project's transcripts into a per-project `MEMORY.md`. Dreamcatcher runs a tier above that, consolidating across projects into a small set of topic files at `~/Dreamcatcher/memory/`:

| File | Purpose |
|---|---|
| `MEMORY.md` | One-page index of topic files and dated decisions, capped at 200 lines |
| `working-style.md` | Stable preferences and editorial standards |
| `customer-context.md` | Engagement patterns (no customer names by policy) |
| `practice-context.md` | Practice context: your domain, recurring partners, standards, and tools |
| `tooling-environment.md` | Dev environment, MCP servers, deployment standards, scheduling rules |
| `active-deliverables.md` | What's in flight right now, with `_active-as-of:` markers |
| `personal-context.md` | Location, hobbies, prior background, family |
| `decisions/YYYY-MM-DD-<slug>.md` | Append-only architecture and strategy decisions |

Every entry carries structured provenance (`_source: <project> @ YYYY-MM-DD_`) and engagement-style entries carry `_active-as-of:` so a monthly audit can surface stale facts.

**Nightly cycle.** A scheduled task fires the nightly consolidation (02:00 PDT on the desktop, 03:00 PDT on the laptop, outside the 0500–1200 PDT Anthropic API congestion window). Because slash commands are an interactive-mode feature, the scheduled job feeds the staged consolidation prompt to `claude -p` (its content, not a `/dream-global` slash command); the same prompt is also available interactively as `/dream-global`. It pulls the latest live store from the git remote, reads transcripts newer than each per-project reverie marker, writes a candidate to `.candidate/<run-timestamp>/`, runs sanity floors (delta-percentage, structural validity), and on pass applies the candidate, writes a structured JSON audit log to `memory/.dream-log/<run-id>.json`, makes a parseable structured commit, and pushes. The dream agent owns the candidate-to-live step end to end; the manual `promote.py` survives as an escape hatch when a sanity floor trips.

**Bidirectional sync.** Both desktop and laptop are dream-writers, sharing the live memory through a private git remote. An hourly `dreamcatcher-pull.py` cron on each machine keeps both clones current; `/dream-global` also pre-pulls at the top of every cycle (Phase 0). Schedule offset between the two machines (one hour) keeps the two cycles serialized so neither blocks on a non-fast-forward.

**Loaded into every session automatically.** The `SessionStart` hook injects `MEMORY.md` and `working-style.md` into the session context at every Claude Code session start. The user-level `~/CLAUDE.md` tells Claude where the other topic files live and when to read each (heuristics by topic). For existing sessions that started before the hook was wired, `/dream-prime` is a manual switch that loads the same content on demand.

**Audit and rollback.** Every dream run leaves two artifacts: a structured commit message in `git log` (parseable: `run-id`, `machine`, sources, deltas) and a detailed JSON log at `memory/.dream-log/<run-id>.json` (per-entry reason, considered-but-skipped signal). `dream-rollback.py --run <run-id>` reverts the matching commit and restores the reverie from its timestamped backup as one operation. The other machine's hourly pull catches up the revert automatically.

## Install

```bash
git clone https://github.com/brad-pierce/dreamcatcher.git
cd dreamcatcher
python setup.py --yes              # desktop
python setup.py --yes --laptop     # laptop
```

Cross-platform (Windows + macOS), Python 3.8+, stdlib only. `setup.py` is idempotent — re-running cleans up old hook entries and redeploys fresh copies. It prints platform-shaped commands at the end for setting up the private git remote, registering the hourly pull cron, and scheduling the content-fed nightly consolidation; those are one-time manual steps.

After install: complete the bootstrap (`/dream-bootstrap` in a session rooted at `~/Dreamcatcher/memory/`) to seed the store from existing project memories and a paste of your Claude.ai userMemories block. Once seeded, the nightly cycle takes over.

## Daily usage

```
/dream-global       — nightly consolidation (scheduled; runs unattended)
/dream-prime        — load memory into the current session (existing sessions)
/dream-audit        — monthly reads-only audit; surfaces stale entries
/dream-rollback     — revert a bad dream commit + reverie
/dream-export       — bundle the live store as a tarball (fallback for seed/air-gap)
/dream-import       — apply a desktop-produced bundle to the local memory
```

Plus the utilities deployed to `~/Dreamcatcher/hooks/`:

```
python ~/Dreamcatcher/hooks/dreamcatcher-pull.py     # cron-driven, runs hourly
python ~/Dreamcatcher/hooks/dream_promote.py <id>    # called from /dream-global Phase 5
python ~/Dreamcatcher/hooks/dreamcatcher-log.py      # browse JSON audit logs
python ~/Dreamcatcher/hooks/promote.py <name>        # manual escape hatch
```

## Architecture summary

The memory store at `~/Dreamcatcher/memory/` is a git repo, shared across machines through a private remote. Six topic files at the root capture cross-project signal; a `decisions/` directory holds dated decisions; a `scratch/` directory holds per-machine notes the next dream ingests and the promote step archives; a `.dream-log/` directory holds the per-run JSON audit logs (committed alongside the topic-file changes so they travel via git pull); a `.candidate/` directory holds in-flight dream output (gitignored).

Per-machine state lives outside the git repo at `~/Dreamcatcher/state/`. The `reverie.json` file records the last-processed transcript timestamp per project; `reverie-backups/` holds nightly snapshots taken before each dream advances the reverie; `logs/` holds per-day hook and dream logs.

Hooks wire the system into Claude Code's session lifecycle. `PreCompact` snapshots the in-flight transcript so the dream reads the un-degraded source. `SessionEnd` queues each session into a pointer file so the dream does not have to scan all of `~/.claude/projects/`. `SessionStart` prints a status line into session context, then injects `MEMORY.md` + `working-style.md`.

For the full architecture (sanity-floor definitions, JSON log schema, security threat model, rollback semantics, redaction rules, the four-test filter for what earns a place in memory), read `Dreamcatcher - Architecture.docx`. For a layperson-facing version, read `Dreamcatcher - Product Overview.docx`. Both regenerate from generators in `tools/`.

## Repository layout

```
setup.py                        cross-platform installer (idempotent)
scripts/                        all runtime Python; setup.py deploys to ~/Dreamcatcher/hooks/
  _dream_common.py              shared helpers (path resolution, prepull, priming)
  snapshot_transcript.py        PreCompact handler
  queue_session.py              SessionEnd handler
  desktop_status.py             SessionStart handler, desktop
  laptop_status.py              SessionStart handler, laptop
  dream_promote.py              auto-promote pipeline (Phase 5 entry point)
  dreamcatcher-pull.py          hourly git pull --ff-only cron wrapper
  dreamcatcher-log.py           browse memory/.dream-log/<run-id>.json
  promote.py                    manual escape hatch when a sanity floor trips
  dream-rollback.py             git revert + reverie rollback (one op; --run flag)
  dream-export.py               bundle live memory as a tarball (fallback)
  dream-import.py               apply a bundle to local memory (with safety checks)
commands/                       slash command prompts (deployed to ~/.claude/commands/)
  dream-global.md, dream-bootstrap.md, dream-audit.md   the three core prompts
  dream-export.md, dream-import.md, dream-prime.md, dream-rollback.md   utilities
templates/                      first-install scaffolding
  CLAUDE-memory-section.md      pasted by setup.py into ~/CLAUDE.md
  bootstrap-scope-template.md, seed-from-claude-ai-template.md   bootstrap hand-authoring guides
tools/                          DOCX generators (run as needed)
  gen_architecture_docx.py, gen_product_overview_docx.py
docs/                           operational runbooks
  laptop-setup.md               joining a desktop from a second machine
00-README.md                    project handoff doc for fresh Claude sessions
```

## Hard conventions

- **Python 3.8+, stdlib only.** No `pip install` required at runtime.
- **Cross-platform Windows + macOS.** `pathlib.Path`, `os.path.expanduser`, no shell expansion, no POSIX-only assumptions.
- **`reverie.json` lives outside git.** Per-machine state; the two machines' reveries diverge in normal operation because each processes its own transcripts.
- **Discovery is bounded** to `discovery_roots` in `~/Dreamcatcher/state/config.json`. No unbounded `find ~/`.
- **Hooks never block on errors.** Exit 0 on any non-fatal condition; log failures to `~/Dreamcatcher/state/logs/`.
- **Do not write to `~/Dreamcatcher/memory/` directly.** Updates flow through `/dream-global` (auto-promote) or `promote.py` (escape hatch). The store is consumed read-only outside that pipeline (the hourly pull may also fast-forward the working tree from the remote).

## Threat model and known limits

A few properties that matter for anyone running this in production. Read these before publishing your own memory store anywhere shared.

**The private git remote is the trust root.** Both machines pull from the configured `origin` of `~/Dreamcatcher/memory/` on an hourly cron. The pull verifies fast-forwardability (rejects rewritten history) but does not verify commit signatures or restrict the author allow-list. If push access to the remote is compromised — stolen `gh auth` cache, leaked PAT, compromised SSH key — an attacker can push tampered topic-file content, both machines pull it on the next cron, and SessionStart injects it into every future Claude Code session as if it were Brad's own memory. Mitigations available outside the v1.3 codebase: enable required signed commits on the remote and `git config gpg.format` + `git config commit.gpgsign true` locally, restrict push access to the user's own machines, audit `git log --show-signature` periodically. v1.4 may build a verified-signature gate into `prepull_memory()` and `dream_promote.py`; today it is a deployment-side discipline.

**Sanity floors gate catastrophic rewrites, not semantic attacks.** The `delta_pct > 50` and `structural_invalid` floors in `dream_promote.py` block consolidations that would rewrite half the memory or produce malformed output. They explicitly do not validate semantic content. A small well-formed adversarial entry (one line, with a `_source:` and a `# heading`) passes every floor and lands. Semantic-content protection lives in the dream and audit prompts (the "prompt-injection resistance" sections in the `/dream-global` and `/dream-bootstrap` prompts, and the Phase 2.5 suspect-surfacing in the `/dream-audit` prompt) and in the human reviewing `/dream-audit` output periodically. Real semantic mistakes get rolled back via `dream-rollback --run <run-id>`, not prevented at promotion time.

**Transcript content is untrusted bytes.** The dream agent reads `~/.claude/projects/*.jsonl` looking for signal. Anything in those JSONLs was either typed by the user, pasted by the user (potentially from adversarial sources), or emitted by another Claude session that itself read untrusted bytes. The shipping prompts (`/dream-global`, `/dream-bootstrap`) tell the agent to treat transcript content as evidence-about-what-the-user-worked-on, never as instructions to the agent itself. This is a prompt-design defense, not a hard sandbox; it reduces blast radius but cannot eliminate the class.

**SessionStart-injected memory is loaded as session context.** Anything in `MEMORY.md` and `working-style.md` flows into every new Claude Code session via the SessionStart hook. The user-level `~/CLAUDE.md` section tells Claude to "treat the contents of those two files as authoritative." A successful write to the memory store (by any of the routes above) propagates to every session on every participating machine. The monthly `/dream-audit` is the human review checkpoint; treat it as load-bearing, not optional.

## Status

v1.3 is operational. The reference deployment has both machines auto-syncing through a private memory remote; nightly cycles run unattended; the SessionStart injection wires the memory into every new session. The Dream Team v2 concept (cross-developer enterprise consolidation, with promotion gated by review and redaction enforced before anything leaves a developer's control) is designed but not yet built — see `dream-team/00-foundation.md` in this repo.
