#!/usr/bin/env python3
"""Generate "Dreamcatcher - Architecture.docx" — v1.4 as-built.

Uses python-docx. Honors Brad's editorial standards for narrative-style
deliverables: no em dashes (uses commas / parens / hyphens instead),
prose-first where the structure can be prose, bullets only where structure
is the point (lifecycle phases, redaction rules, files-at-a-glance).

This generator describes the system as it stands at v1.4.
"""

from datetime import date
from pathlib import Path

from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH


# ---------- styling helpers ----------

def _set_default_font(doc):
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)


def _h1(doc, text):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(20)
    run.font.color.rgb = RGBColor(0x00, 0x33, 0x66)
    p.paragraph_format.space_before = Pt(18)
    p.paragraph_format.space_after = Pt(8)


def _h2(doc, text):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(14)
    run.font.color.rgb = RGBColor(0x00, 0x33, 0x66)
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(4)


def _h3(doc, text):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(12)
    run.font.color.rgb = RGBColor(0x00, 0x1F, 0x40)
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(2)


def _p(doc, text):
    p = doc.add_paragraph(text)
    p.paragraph_format.space_after = Pt(8)
    return p


def _bullet(doc, text):
    p = doc.add_paragraph(text, style="List Bullet")
    p.paragraph_format.space_after = Pt(2)
    return p


def _code(doc, text):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.name = "Consolas"
    run.font.size = Pt(9)
    p.paragraph_format.left_indent = Inches(0.25)
    p.paragraph_format.space_after = Pt(8)
    return p


# ---------- content ----------

def build_doc(out_path: Path) -> None:
    doc = Document()
    _set_default_font(doc)

    # ===== Title block =====
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = title.add_run("Dreamcatcher")
    r.bold = True
    r.font.size = Pt(32)
    r.font.color.rgb = RGBColor(0x00, 0x33, 0x66)

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = sub.add_run("As-Built Architecture, v1.4")
    r.font.size = Pt(16)
    r.font.color.rgb = RGBColor(0x00, 0x1F, 0x40)
    sub.paragraph_format.space_after = Pt(6)

    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = meta.add_run(f"Author: Brad Pierce  |  {date.today().isoformat()}  |  "
                     f"github.com/brad-pierce/dreamcatcher")
    r.font.size = Pt(10)
    r.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
    meta.paragraph_format.space_after = Pt(24)

    doc.add_page_break()

    # ===== Executive summary =====
    _h1(doc, "Executive summary")
    _p(doc, (
        "Dreamcatcher is a cross-project memory consolidation system for Claude Code. It sits as a tier above per-project "
        "Auto Dream and captures facts, patterns, and preferences that span many projects into a single git-versioned "
        "store at ~/Dreamcatcher/memory/. Per-project Auto Dream distills each project's transcripts into a per-project "
        "MEMORY.md; Dreamcatcher runs a level higher, consolidating those project memories (plus narrowly sampled raw "
        "transcripts) into cross-project topic files that every future Claude Code session reads at session start."
    ))
    _p(doc, (
        "The system is autonomous on the happy path. A scheduled task fires each night, pulls the latest live store from "
        "a private git remote, reads each project's transcripts newer than the per-project reverie marker, writes a "
        "candidate, validates the candidate against sanity floors, applies on pass, writes a structured JSON audit log, "
        "makes a parseable structured commit, and pushes. An hourly background pull on each participating machine keeps "
        "both clones current between runs. The SessionStart hook injects the consolidated memory into every Claude Code "
        "session at session start, so the user stops re-explaining themselves."
    ))
    _p(doc, (
        "The implementation is Python with stdlib only (no pip dependencies at runtime), cross-platform for Windows and "
        "macOS, idempotent on re-install, and shipped as a small set of scripts plus markdown slash-command wrappers."
    ))

    # ===== Problem and gap =====
    _h1(doc, "Problem and gap")
    _p(doc, (
        "Claude Code's built-in Auto Dream is project-scoped. It does a good job distilling per-project signal but cannot, "
        "by design, spot cross-project patterns. A preference that shows up across thirty projects (always DOCX over "
        "Markdown, customer-facing voice unless told otherwise, manual validation loop on write-back automations, "
        "defensive defaults that prefer correctness over completeness) lives in every per-project memory in fragmented "
        "form but is never lifted up to a place agents will read before starting work in a new project."
    ))
    _p(doc, (
        "Anthropic's Managed Agents Dreams API and Claude.ai's userMemories block both attack the same gap from different "
        "directions, but neither is plumbed into the Claude Code CLI workflow that a daily user actually has. Dreamcatcher "
        "closes the loop: it reads what Claude Code has already written to disk, consolidates a layer above it, and feeds "
        "the consolidation back into the session that needs it."
    ))

    # ===== Architecture =====
    _h1(doc, "Architecture")

    _h2(doc, "Two-store pattern")
    _p(doc, (
        "Each nightly run writes to ~/Dreamcatcher/memory/.candidate/<run-timestamp>/ first and never touches the live "
        "store directly. The candidate-to-live step is owned by the dream agent itself via dream_promote.py: the agent "
        "writes a structured manifest describing what changed and why, dream_promote.py validates the candidate against "
        "sanity floors, and on pass copies the candidate files into the live store, writes a JSON audit log, makes a "
        "structured commit, and pushes. The candidate folder is removed after successful promote."
    ))
    _p(doc, (
        "The two-store pattern is borrowed from the Managed Agents Dreams API and remains the load-bearing safety "
        "property of the system. Auto-promote does not bypass the two-store separation; it just removes the human from "
        "the apply step on the happy path. promote.py survives in the codebase as the escape hatch when a sanity floor "
        "trips (catastrophic delta, structural-validity failure, push-rebase conflict) or when a human wants to hand-edit "
        "before applying. The system deliberately preserves the manual path because the autonomous path is constrained by "
        "exactly the floors documented below and nothing else."
    ))

    _h2(doc, "Auto-promote pipeline")
    _p(doc, (
        "dream_promote.py is the entry point that runs once the /dream-global agent has finished consolidation. It reads "
        "dream-manifest.json from the candidate folder (a structured description of changes, sources, reasons, and "
        "considered-but-skipped signal), validates the candidate against sanity floors, applies on pass, writes the JSON "
        "audit log, makes a structured commit message that is parseable for filtering, and pushes. If the initial push is "
        "rejected as non-fast-forward (another machine pushed during the dream cycle), dream_promote.py does one git pull "
        "--rebase and re-pushes; a real rebase conflict is treated as a safe stop with REQUIRES_REVIEW for the human."
    ))
    _p(doc, "Sanity floors that block auto-promote (the candidate is left in place with REQUIRES_REVIEW.txt instead):")
    _bullet(doc, "delta_pct - if the candidate would add or remove more than 50 percent of the live store's total line volume, abort. Catastrophic-rewrite guard for hallucinated wholesale changes.")
    _bullet(doc, "structural_invalid - each candidate topic file must have a top-level heading and at least one _source: provenance line (MEMORY.md and decisions/ exempt). Catches malformed dream output.")
    _bullet(doc, "empty_run - if no entries changed, skip the commit entirely. No no-op commits in the log.")
    _p(doc, "")
    _p(doc, (
        "Sanity floors are deliberately conservative. They catch obviously-wrong cases (truncation, hallucination, no-op "
        "runs) without trying to second-guess the dream's reasoning on close calls. Real semantic mistakes are caught at "
        "rollback time via dream-rollback.py --run <run-id>, not at promotion."
    ))

    _h2(doc, "Audit substrate")
    _p(doc, "Two layers, both in-repo so they travel to every machine on git pull:")
    _bullet(doc, "Structured commit message - the always-on audit. Every auto-promote commit's body carries parseable run-id, machine, sources, files-changed, add/update/remove counts, and reverie-advance lines. git log is the lowest-friction filter; dream-rollback.py --run uses this format to resolve a run-id to a SHA.")
    _bullet(doc, "Detailed JSON log at memory/.dream-log/<run-id>.json - the deep-dive. Manifest augmented with git_head_before/after, completed_at, and the sanity_check result. Records considered-but-skipped signal (the only place the audit captures why the dream did NOT remember something). dreamcatcher-log.py is the read tool over these files.")
    _p(doc, "")
    _p(doc, (
        "The JSON log is committed inside the same commit as the topic-file changes (amend-in-one-commit so audit and "
        "data travel atomically). On another machine's next pull, the audit arrives with the data; nothing extra to sync."
    ))

    _h2(doc, "Topic taxonomy")
    _p(doc, "Six stable topic files at the root of the live store, plus a dated decisions directory:")
    _bullet(doc, "working-style.md - collaboration norms, deliverable defaults, editorial standards. Stable preferences, not time-bounded.")
    _bullet(doc, "customer-context.md - engagement-level patterns. Customer names are not promoted by policy; engagement shapes survive.")
    _bullet(doc, "practice-context.md - practice context: domain, recurring partners, standards, and tools.")
    _bullet(doc, "tooling-environment.md - dev environment, MCP servers in flight, shared infrastructure patterns, scheduling rules, hardware.")
    _bullet(doc, "active-deliverables.md - in-flight projects and documents. All entries carry _active-as-of: so audit can surface stale ones.")
    _bullet(doc, "personal-context.md - location, hobbies, prior background, family.")
    _bullet(doc, "decisions/YYYY-MM-DD-<slug>.md - dated, append-only architecture or strategy decisions worth remembering.")
    _p(doc, "")
    _p(doc, (
        "MEMORY.md is a one-page index, capped at 200 lines, that points at the topic files. The index is never content; "
        "if a fact would land in MEMORY.md, it belongs in a topic file with a one-line pointer here."
    ))

    _h2(doc, "Provenance and active-as-of")
    _p(doc, (
        "Every entry carries a structured _source: <project-slug> @ YYYY-MM-DD_ line. The format is exact and parseable, "
        "because the monthly audit greps it. Multi-source consolidations emit two or three _source: lines, one per source, "
        "rather than flattening to a comma-joined line."
    ))
    _p(doc, (
        "Engagement-style entries (anything in customer-context, active-deliverables, or any tooling-environment entry "
        "describing a current state) also carry _active-as-of: YYYY-MM-DD_. The audit surfaces entries whose "
        "active-as-of is older than 90 days, which is how stale-but-not-contradicted facts get caught. Stable "
        "preferences (working-style entries, practice-context entries, decisions) do not carry active-as-of because "
        "they are not time-bounded."
    ))

    _h2(doc, "Per-machine state")
    _p(doc, (
        "Per-machine state lives outside the git repo at ~/Dreamcatcher/state/. The reverie file (reverie.json) records "
        "the last-processed transcript timestamp per project; the next dream reads transcripts newer than each "
        "per-project reverie value. The reverie-backups directory holds nightly snapshots taken before each dream "
        "updates the reverie, so dream-rollback can restore them as one operation with the git revert."
    ))
    _p(doc, (
        "Per-machine state is deliberately out of git. Each machine's reverie advances independently because each "
        "machine processes its own transcripts; the two will diverge in normal operation, and that is correct."
    ))

    _h2(doc, "Two-machine topology")
    _p(doc, (
        "Both desktop and laptop are dream-writers. The two machines share the live memory through a private git remote "
        "(the user's own GitHub-private repo or equivalent) and an hourly background pull job. Each machine runs "
        "dreamcatcher-pull.py on a once-an-hour schedule (Windows Task Scheduler, macOS launchd or cron); the job does "
        "nothing more than git pull --ff-only on the memory repo and exits. Every /dream-global cycle and every "
        "promote.py invocation also calls dc.prepull_memory() as its first step (Phase 0), so the dream is always "
        "reasoning against the latest state."
    ))
    _p(doc, (
        "Schedule offset serializes the two cycles: desktop runs /dream-global at 02:00 Pacific, laptop at 03:00 "
        "Pacific. A one-hour gap is generous given the hourly pull keeps both machines within fifteen minutes. The same "
        "schedule discipline keeps Anthropic-API automations outside the 0500-1200 PDT congestion window."
    ))
    _p(doc, (
        "/dream-export and /dream-import survive as the fallback for first-time machine seeding (no git remote yet) and "
        "air-gapped operation. They are not the cross-machine default. The bundle path is invoked once per machine at "
        "first install; afterwards the git remote handles everything."
    ))

    _h2(doc, "SessionStart memory injection")
    _p(doc, (
        "The SessionStart hook (desktop_status.py / laptop_status.py) emits a brief status block (pending review count, "
        "last dream commit recency, reverie freshness) and then calls dc.emit_memory_priming() to inject the "
        "consolidated memory itself into the session as context. Claude Code reads SessionStart stdout as session "
        "context, so the memory becomes available to the very first message of every session without the user having to "
        "do anything."
    ))
    _p(doc, (
        "Always-injected (small, stable, always-applicable):"
    ))
    _bullet(doc, "MEMORY.md - the topic-file index (~30 lines).")
    _bullet(doc, "working-style.md - stable preferences and editorial standards (~200 lines).")
    _p(doc, (
        "Total always-on overhead is roughly 17 KB. The split was drawn to keep short sessions cheap: heavier topic "
        "files (practice-context.md, tooling-environment.md, active-deliverables.md, customer-context.md, "
        "personal-context.md) and the decisions directory stay on-demand, read via the Read tool against absolute paths "
        "when the question intersects with the topic."
    ))
    _p(doc, (
        "The user-level ~/CLAUDE.md is the discoverable pointer for the on-demand half. setup.py step 9 detects "
        "whether the user's ~/CLAUDE.md contains the Dreamcatcher memory section (marker-wrapped for idempotency) and "
        "appends it from templates/CLAUDE-memory-section.md if absent. The section tells Claude where each on-demand "
        "topic file lives and gives heuristics for when to read each (practice or domain questions reach for "
        "practice-context.md; deployment or MCP work reaches for tooling-environment.md; in-flight project name "
        "reaches for active-deliverables.md; past architectural choice reaches for decisions/)."
    ))
    _p(doc, (
        "For existing sessions that started before SessionStart was wired, the static slash command /dream-prime "
        "(deployed by setup.py step 7 from commands/dream-prime.md) loads the same MEMORY.md + working-style.md "
        "content on demand. The command also serves as a forced-refresh path after a manual edit to the live store."
    ))

    # ===== Operational lifecycle =====
    _h1(doc, "Operational lifecycle")

    _h2(doc, "Install")
    _p(doc, (
        "setup.py prompts for discovery_roots (the directories the bootstrap and nightly find passes are allowed to "
        "walk), writes a config.json at ~/Dreamcatcher/state/, deploys all runtime Python from scripts/ into "
        "~/Dreamcatcher/hooks/, stages the nightly and bootstrap prompt bodies into ~/Dreamcatcher/prompts/ for "
        "the scheduled headless runs, copies the slash command wrappers into ~/.claude/commands/, merges hook "
        "entries into ~/.claude/settings.json, and pastes the Dreamcatcher memory section into ~/CLAUDE.md (or prints paste "
        "instructions if --yes was not passed). The settings.json edit is backed up with a timestamped .bak file. "
        "setup.py is idempotent: re-running cleans up old dream-hooks entries and redeploys fresh copies; the "
        "~/CLAUDE.md section is detected by marker and skipped if already present."
    ))
    _p(doc, (
        "After install, two one-time manual steps remain: setting up the private git remote on ~/Dreamcatcher/memory/ "
        "and registering the hourly pull cron via the platform-specific command setup.py prints in its summary "
        "output."
    ))

    _h2(doc, "Bootstrap (one-time per machine)")
    _p(doc, (
        "The bootstrap is structurally different from the nightly dream and gets its own slash command "
        "(/dream-bootstrap) and prompt. Five stages, all driven by the user, with the prompt itself being just "
        "Stage 4:"
    ))
    _bullet(doc, "Stage 1 - Discovery and scope. Walk discovery_roots, classify projects into active+curated, active+uncurated, dormant, and noise. Hand-author bootstrap-scope.md as the source of truth for what is in scope.")
    _bullet(doc, "Stage 2 - Pre-distillation. Run /init (or let Auto Dream catch up) on each active+uncurated project so the bootstrap can read pre-distilled MEMORY.md files rather than mining raw transcripts.")
    _bullet(doc, "Stage 3 - Seed assembly. Paste the claude.ai userMemories block into scratch/seed-claude-ai-memory-YYYY-MM-DD.md using the file-11 template. This is treated as the highest-confidence input by the bootstrap.")
    _bullet(doc, "Stage 4 - The bootstrap prompt itself. Fresh Claude Code session in ~/Dreamcatcher/memory/, run /dream-bootstrap. Output lands in .candidate/bootstrap-<timestamp>/.")
    _bullet(doc, "Stage 5 - Heavy review, promote, reverie seed. Read every candidate file end to end. Expect 20 to 30 percent deletion. Run promote.py. Seed reverie.json with per-project current timestamps so the first nightly knows where to resume.")

    _h2(doc, "Nightly cycle")
    _p(doc, (
        "/dream-global runs in five phases. Phase 0 is the pre-pull: dreamcatcher-pull.py fast-forwards the memory repo "
        "from the remote so the dream reasons against the latest state. Phases 1 through 4 are the consolidation loop "
        "(orient, gather signal narrowly from in-scope projects newer than each per-project reverie value, consolidate "
        "with merge-before-duplicate discipline, prune and index). Phase 5 is the auto-promote: the agent writes "
        "dream-manifest.json describing what changed and why, invokes dream_promote.py, and exits based on the outcome "
        "(PROMOTED, REQUIRES_REVIEW, or error)."
    ))
    _p(doc, (
        "The hooks installed at install time keep the system self-announcing: PreCompact snapshots the in-flight "
        "transcript to ~/Dreamcatcher/inputs/precompact/ so the dream reads the un-degraded source; SessionEnd queues "
        "each session into a pointer file so the dream does not have to scan all of ~/.claude/projects/; SessionStart "
        "prints a status line plus the memory priming into session context."
    ))

    _h2(doc, "Monthly audit")
    _p(doc, (
        "/dream-audit walks the live store and emits a review document but never writes. Three categories surface: "
        "entries older than 90 days with no source-refresh, entries whose source project has had zero new sessions in "
        "60 days, and entries that contradict more recent entries in the same file but were not fixed at the source. "
        "The user reads the document, decides what to prune, and prunes manually with a commit message like "
        "audit-prune: stale entries from Q4. The audit also drops a monthly snapshot tag (snapshot/YYYY-MM) as the "
        "rollback anchor for slow-drift questions."
    ))

    _h2(doc, "Rollback")
    _p(doc, (
        "dream-rollback.py wraps git revert plus reverie restore as a single operation. Reverting the bad commit "
        "without rolling back the reverie leaves the next nightly skipping the very transcripts that produced the bad "
        "consolidation. The reverie piece is non-optional."
    ))
    _p(doc, (
        "The --run <run-id> flag resolves the auto-promote commit by grepping for the run-id: line in commit-message "
        "bodies; the rest of the flow is unchanged from the interactive picker version (revert the commit, restore the "
        "reverie from the timestamped backup taken before the dream advanced it, push the revert). The other machine's "
        "hourly pull cron catches up automatically; no second human action required. For taxonomy mistakes that span "
        "many commits, the right tool is a manual restructure commit, not rollback."
    ))

    _h2(doc, "Export and import (fallback)")
    _p(doc, (
        "The bundle workflow is the fallback path, not the default. It remains useful for two scenarios: first-time "
        "seeding of a new machine (no git remote configured yet), and air-gapped operation when the machines are not "
        "on a network together. /dream-export bundles the live store (including .git/) as <export_dir>/dream-export-"
        "YYYY-MM-DD-HHMM.tgz; the export refuses to operate on a dirty tree. The user transfers the file however they "
        "prefer (USB, AirDrop, file share, email). /dream-import on the other machine validates the bundle (rejects "
        "absolute-path entries, parent-traversal, links, and bundles missing a .git/ root), compares commit histories, "
        "and refuses to apply if the receiving machine has commits the bundle does not include. --force overrides the "
        "safety check; either way the current memory is moved aside to a timestamped backup directory so a forced "
        "overwrite is recoverable."
    ))

    _h2(doc, "In-session memory loading")
    _p(doc, (
        "/dream-prime is the in-session manual switch. Useful for sessions opened before the SessionStart hook was "
        "wired on this machine, for forced refreshes after a manual memory edit, or for any case where the user wants "
        "to verify the memory has loaded. The command instructs Claude to read MEMORY.md and working-style.md, then "
        "report a tight summary of what is now loaded (number of topic files indexed, most load-bearing working-style "
        "rules, reminder that the other topic files are available on demand)."
    ))

    # ===== Implementation notes =====
    _h1(doc, "Implementation notes")

    _h2(doc, "Language and platform")
    _p(doc, (
        "Python 3.8 or later, stdlib only for the runtime scripts. setup.py, promote.py, dream-rollback.py, "
        "dream-export.py, dream-import.py, and the hook handlers (snapshot_transcript.py, queue_session.py, "
        "desktop_status.py, laptop_status.py, dream_promote.py, dreamcatcher-pull.py, dreamcatcher-log.py) plus the "
        "shared _dream_common.py helper module live under hooks/ in the source tree and are deployed to "
        "~/Dreamcatcher/hooks/ by setup.py. Cross-platform conventions are enforced throughout: pathlib.Path rather "
        "than $HOME in command strings, os.path.expanduser for home-relative paths, no shell expansion, no POSIX-only "
        "assumptions. python-docx is used only by tools/gen_*.py to regenerate the as-built docs and is never on the "
        "runtime path."
    ))
    _p(doc, (
        "Windows-specific gotchas are handled at the helper level: setup_utf8_io() in _dream_common reconfigures stdout "
        "and stderr to UTF-8 with errors='replace' so that file content containing em dashes, BOMs, or non-ASCII "
        "characters does not crash the script under Windows cp1252. PowerShell 5.1 incompatibilities (no &&, no ||, "
        "stderr-redirection quirks on native executables, UTF-16 BOM by default on Out-File) are documented in the "
        "live store's tooling-environment.md."
    ))

    _h2(doc, "Hook design")
    _p(doc, (
        "Hooks are wired via ~/.claude/settings.json with absolute paths and the platform-appropriate Python "
        "interpreter name (python on Windows, python3 on macOS). setup.py merges new hook entries idempotently: "
        "re-running drops any existing entries that reference dream-hooks and reinstalls fresh copies. All hook "
        "handlers exit 0 on any non-fatal condition. PreCompact exit 2 is explicitly never used because it is a "
        "Claude Code hang vector. Errors are logged to ~/Dreamcatcher/state/logs/hook-<name>-<date>.log and the "
        "user-visible behavior remains 'event proceeds normally'."
    ))

    _h2(doc, "Sanity floors and the JSON log schema")
    _p(doc, (
        "The auto-promote pipeline is gated by three sanity floors that block silent application of obviously-wrong "
        "consolidations. delta_pct counts the unified-diff +/- line volume across all candidate files, divided by the "
        "live store's total topic-file line count, and aborts if the result exceeds 50 percent. structural_invalid "
        "walks each candidate file checking that it has a top-level heading and (unless it is MEMORY.md or under "
        "decisions/) at least one _source: line. empty_run skips the commit entirely when no entries changed. When "
        "any floor trips, REQUIRES_REVIEW.txt is written into the candidate folder with the reason, the JSON log "
        "records outcome=requires_review with the floor's detail, and the run exits 0 (safe stop, not an error)."
    ))
    _p(doc, "JSON log schema at memory/.dream-log/<run-id>.json:")
    _code(doc, (
        "{\n"
        "  \"run_id\": \"2026-05-21T142425Z\",\n"
        "  \"machine\": \"desktop\",\n"
        "  \"started_at\": \"2026-05-21T14:24:25Z\",\n"
        "  \"completed_at\": \"2026-05-21T14:51:12Z\",\n"
        "  \"summary\": \"<one-line, becomes commit subject>\",\n"
        "  \"git_head_before\": \"<sha>\",\n"
        "  \"git_head_after\":  \"<sha>\",\n"
        "  \"reverie_advance\": {\"from\": \"<UTC>\", \"to\": \"<UTC>\"},\n"
        "  \"sources_considered\": [\n"
        "    {\"project\": \"<slug>\", \"transcripts\": N, \"grep_hits\": N}\n"
        "  ],\n"
        "  \"entries\": [\n"
        "    {\"action\": \"added|updated|removed\",\n"
        "     \"file\": \"<topic-file>\",\n"
        "     \"anchor\": \"<section>\",\n"
        "     \"reason\": \"<why>\",\n"
        "     \"sources\": [{\"project\": \"<slug>\", \"date\": \"YYYY-MM-DD\"}]}\n"
        "  ],\n"
        "  \"considered_but_skipped\": [\n"
        "    {\"signal\": \"<thing>\", \"reason\": \"<why dropped>\"}\n"
        "  ],\n"
        "  \"sanity_check\": {\n"
        "    \"delta_pct\": 9.1,\n"
        "    \"delta_lines\": 412,\n"
        "    \"live_lines\": 4527,\n"
        "    \"structural_valid\": true,\n"
        "    \"outcome\": \"auto-promote\",\n"
        "    \"floors_tripped\": []\n"
        "  }\n"
        "}\n"
    ))
    _p(doc, (
        "considered_but_skipped is the load-bearing field for future-session forensics: it is the only place in the "
        "audit where the dream records why it did NOT remember something. A future session asking why X is not in "
        "memory reads this field; the answer is in the log, not buried in transcript history."
    ))

    _h2(doc, "Security considerations")
    _p(doc, "Four threat surfaces, each with a deliberate mitigation:")
    _bullet(doc, "Tar-slip in dream-import.py - the bundle validator iterates every member (not just the first 200) and rejects absolute paths, parent-traversal, drive-letter paths, and link or device entries. tarfile.extractall passes filter='data' on Python 3.12 and later, with a manual-validation fallback for older versions.")
    _bullet(doc, "Redaction rules baked into the dream and bootstrap prompts as non-negotiable instructions: account numbers, contract values, ARR, API keys, tokens, customer-contact email addresses, and specific endpoint or seat counts above round numbers are never captured. Customer names are excluded by policy.")
    _bullet(doc, "Auto-promote sanity floors catch catastrophic rewrites: a candidate that would change more than half of memory line volume is rejected, as is any candidate with structural-validity problems. Real semantic mistakes are caught at rollback time, not at promotion.")
    _bullet(doc, "Repo location is user-choice. The default cross-machine transport is a private git host (private GitHub, Gitea, encrypted volume, NAS bare repo). The system has no telemetry and never reaches a third party.")

    # ===== File inventory =====
    _h1(doc, "File inventory")
    _h2(doc, "Source tree (github.com/brad-pierce/dreamcatcher)")
    _code(doc, (
        "setup.py                         cross-platform installer (idempotent)\n"
        "scripts/                         all runtime Python (deployed to ~/Dreamcatcher/hooks/)\n"
        "  _dream_common.py, snapshot_transcript.py, queue_session.py,\n"
        "  desktop_status.py, laptop_status.py, dream_promote.py,\n"
        "  dreamcatcher-pull.py, dreamcatcher-log.py, promote.py,\n"
        "  dream-rollback.py, dream-export.py, dream-import.py\n"
        "commands/                        slash command prompts (deployed to ~/.claude/commands/)\n"
        "  dream-global.md, dream-bootstrap.md, dream-audit.md (core prompts),\n"
        "  dream-export.md, dream-import.md, dream-prime.md, dream-rollback.md\n"
        "templates/CLAUDE-memory-section.md   pasted by setup.py into ~/CLAUDE.md\n"
        "templates/bootstrap-scope-template.md, seed-from-claude-ai-template.md   bootstrap guides\n"
        "tools/gen_architecture_docx.py   regenerates this document\n"
        "tools/gen_product_overview_docx.py  regenerates the layperson product overview\n"
        "docs/laptop-setup.md             runbook for joining a desktop from a second machine\n"
        "00-README.md                     project handoff doc for fresh Claude sessions\n"
        "README.md                        GitHub front-door\n"
        "Dreamcatcher - Architecture.docx     this document\n"
        "Dreamcatcher - Product Overview.docx layperson-facing companion\n"
    ))

    _h2(doc, "Deployed locations")
    _code(doc, (
        "~/Dreamcatcher/memory/         live store, git repo, shared via private remote\n"
        "  MEMORY.md, six topic files, decisions/, scratch/\n"
        "  .candidate/<ts>/              per-run candidate output (gitignored)\n"
        "  .dream-log/<run-id>.json      structured JSON audit log per run\n"
        "~/Dreamcatcher/state/          per-machine state, outside git\n"
        "  config.json                   install-time config (discovery_roots, paths)\n"
        "  reverie.json                  per-project last-processed timestamps\n"
        "  reverie-backups/              snapshots before each reverie update\n"
        "  logs/                         per-day hook, dream, pull, rollback logs\n"
        "~/Dreamcatcher/hooks/          deployed Python scripts (hook handlers + utilities)\n"
        "~/Dreamcatcher/inputs/         PreCompact transcript snapshots\n"
        "~/.claude/commands/             slash command wrappers (for /dream-* invocations)\n"
        "~/.claude/settings.json         hook entries merged in by setup.py (backup taken)\n"
        "~/CLAUDE.md                     user-level Claude Code instructions; setup.py\n"
        "                                pastes the marker-wrapped memory section here\n"
    ))

    # ===== Known soft spots =====
    _h1(doc, "Known soft spots")
    _bullet(doc, "Sanity floors are conservatively tuned. The 50 percent delta floor has not been calibrated against months of long-running operation; it may prove too lax or too tight in practice. Adjustment is a point release.")
    _bullet(doc, "macOS setup.py prints the crontab line for the nightly and the hourly pull but does not auto-write a launchd plist. Users on macOS who prefer launchd write the plist manually following the path documented in docs/laptop-setup.md.")
    _bullet(doc, "The reverie-backups directory accumulates over time. A housekeeping task to cull backups older than 30 days is documented but not yet implemented.")
    _bullet(doc, "dream-rollback.py interactive picker has not been exercised against many real bad commits yet. First-contact friction is likely.")

    # ===== Out of scope =====
    _h1(doc, "Out of scope (today)")
    _p(doc, (
        "The natural next layer is teams: multiple developers sharing a cross-team memory above their own personal "
        "memory, with promotion gated by review, redaction enforced before anything leaves a developer's control, and "
        "clean off-boarding when someone leaves the team. That layer is designed in detail (Dream Team v2) and not yet "
        "built. The design lives in this repo at dream-team/00-foundation.md, with the lock-in decision recorded in "
        "the live store at decisions/2026-05-17-dream-team-v2-concept-captured.md."
    ))
    _p(doc, (
        "Also deliberately out of scope: a web UI for browsing the memory or audit logs (the surface today is the git "
        "repo plus dreamcatcher-log.py), any dependency on third-party Python packages at runtime (stdlib only is the "
        "cross-platform contract), and any inference about content that would require an LLM call outside the /dream-"
        "global cycle (the dream is the only place reasoning happens; everything else is deterministic plumbing)."
    ))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    here = Path(__file__).resolve().parent.parent
    build_doc(here / "Dreamcatcher - Architecture.docx")
