# bootstrap-scope.md — Template

> **Purpose:** the hand-authored map of which projects are in scope for the bootstrap, what each one *is*, and how to treat it. Produced during Stage 1 of bootstrap setup (discovery), consumed by the orient phase of the `/dream-bootstrap` prompt.
>
> **Where it lives:** `~/Dreamcatcher/memory/scratch/bootstrap-scope.md` on the desktop, before the bootstrap prompt runs. Once the bootstrap promotes, the promote script moves it to `scratch/.archived/` along with the seed scratch files.
>
> **Length:** as long as it needs to be. For a user with ~30 projects this is probably 100–200 lines. Optimise for the bootstrap prompt being able to pick up *what each project means* without having to guess from transcripts.
>
> **Authoring posture:** this is the one place where the user's judgement is non-substitutable. The bootstrap prompt cannot infer "<project-codename> was a Q4 migration engagement, mostly concluded, occasional follow-up tickets" from transcripts alone. Write what only you know.

---

Copy the block below and fill it in. Delete this preamble before saving. Keep the section headers as-is; the bootstrap prompt expects them.

---

# Bootstrap Scope

_authored: YYYY-MM-DD_
_machine: desktop_

## Triage rule (record for the next time)

Anything I can't articulate a reason for in one sentence is noise. If I have to think about whether a project mattered, it didn't.

## Active and curated

Projects with recent sessions AND an existing `~/.claude/projects/<project>/memory/MEMORY.md`. The bootstrap reads the per-project MEMORY.md and skips raw transcripts.

- **project-slug-1** — One-line description of what this project is.
  - Notes: _Optional — anything the bootstrap should NOT consolidate from this project. E.g. "early prototyping noise from 2024-08 to 2024-10; only signal from 2024-11 onward."_
- **project-slug-2** — One-line description.
- ...

## Active but uncurated

Projects with recent sessions but no `MEMORY.md` yet. **These need `/init` (or a wait for Auto Dream) before the bootstrap runs** — bootstrap Stage 2. If a project ends up listed here at bootstrap time without distillation, the bootstrap falls through to narrow transcript grep, which is more expensive and lossier.

- **project-slug-3** — One-line description.
  - Distillation status: _e.g. "ran `/init` 2026-05-09, MEMORY.md exists" / "Auto Dream eligible, last triggered 2026-05-07"_
- ...

## Dormant but valuable

Projects with no recent sessions but the work mattered. These should ideally have a `MEMORY.md` from their active period; if not, run `/init` on them before the bootstrap as a one-off. Do NOT mine cold transcripts from dormant projects inline during the bootstrap.

- **project-slug-4** — One-line description, plus why it matters now.
  - Status: _e.g. "concluded 2025-09; resurrected briefly 2026-03 for a one-off question"_
- ...

## Noise (explicitly excluded)

Listed for the record so the next bootstrap (if there ever is one) and the user's future self both know these are intentional exclusions, not oversights. The bootstrap will not read these even if they show up under `~/.claude/projects/`.

- **project-slug-5** — One-line description of why this is noise.
- ...

## Project name reconciliation

If any project goes by multiple names (a directory name that doesn't match how the user refers to it in conversation, or two related projects that get conflated), list the mapping here. The bootstrap prompt uses the directory name as the `<project-slug>` in `_source:` lines; if the human-readable name differs, that's worth surfacing.

- `directory-name-1` ↔ "the way the user refers to it in conversation"
- ...

## Cross-project relationships worth flagging

Anything the bootstrap should know about how projects relate. E.g. "project-A and project-B are two halves of the same customer engagement"; "project-C is a continuation of project-D after the engagement was reorganised". The bootstrap will otherwise treat them as independent.

- ...

## Things the bootstrap should ask about (not infer)

Open questions where the bootstrap should flag in `BOOTSTRAP-NOTES.md` rather than guess. E.g. "If you find conflicting endpoint counts for Customer X across projects, flag — don't pick one." Anywhere you want a human-in-the-loop call on an ambiguous fact.

- ...

---

## Filling-in checklist (delete before saving)

- [ ] Ran the discovery commands from bootstrap Stage 1
- [ ] Every directory under `~/.claude/projects/` is accounted for (bucketed or in Noise)
- [ ] Every CLAUDE.md found by `find` is accounted for
- [ ] Stage 2 pre-distillation is complete OR the active+uncurated section explicitly notes which projects still need it
- [ ] Triage rule applied — anything I couldn't articulate in one sentence went to Noise
- [ ] Project name reconciliation done — no surprises waiting for the bootstrap
