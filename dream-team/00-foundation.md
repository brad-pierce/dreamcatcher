# Dream Team — v2 Design Foundation

The architecture and decisions we've settled for v2 (Dream Team), captured before context evaporates. This is the foundation; subsequent design notes in this directory will expand individual pieces as we dig in.

Authored: 2026-05-15. Status: design foundation, no code yet.

## What v2 is

A layer adjacent to Dreamcatcher (not strictly above), capturing team-level patterns when multiple developers work in different, somewhat personal ways across many machines and distances. Per-project opt-in. Privacy-respecting. Security as a first-class concept rather than a hardening pass.

Where v1 (Dreamcatcher) consolidates a single developer's signal across many projects, v2 (Dream Team) consolidates many developers' signals within a single project, with an explicit-consent path for cross-project team patterns. The two systems are siblings that share infrastructure, not a stacked tier.

## What's settled

### 1. Architecture shape: push-with-corroboration

Each developer's personal Dream stays unchanged at `~/Dreamcatcher/memory/`. When the developer has opted-in to a project's Dream Team, the same nightly run also produces a sanitized **team-candidate** scoped to that project. Team-candidates from N developers aggregate into the project's `.dream-team/team-memory.md`, but only facts that appear in two or more independent team-candidates become team-memory entries.

Multi-source corroboration is the load-bearing security property: a single compromised machine cannot write team memory alone. A poisoned fact that slips through one developer's transcripts must independently appear in at least one other developer's transcripts to land.

### 2. In-repo team-memory, per-developer opt-in

Team-memory lives in the project's own repo at `.dream-team/team-memory.md`. The leading dot keeps it out of the way visually but the file is committed and visible to anyone with repo access. The project's `CLAUDE.md` carries a single reference line ("Read `.dream-team/team-memory.md` before starting work") so every Claude Code session in the repo reads it automatically. Reading is automatic on clone; contribution requires explicit opt-in.

Opt-in is per-developer-per-project, not per-project alone. Two developers on the same repo can have different comfort levels with contributing personal dream data, and that asymmetry is a first-class concept rather than a workaround.

### 3. The `/dream-team` slash command

Three actions on first run in a project:

1. **Initialize if absent.** Create `.dream-team/`, write a starter `team-memory.md` (empty topic shape), create `.dream-team/contributors.json` with the inviting dev as the first contributor, add the CLAUDE.md reference line. First-clone-to-run scaffolds the repo.
2. **Enroll the current developer.** Append the dev's identity to `.dream-team/contributors.json`, set a local config marker so the user's nightly `/dream-global` knows to emit a team-candidate for this project next run.
3. **Surface current state.** Dump `team-memory.md` into the session context so the new dev sees the team's accumulated patterns immediately. Print summary ("Enrolled. Team-memory at v3, last updated 2026-05-10. 47 facts across 4 topic files.")

Re-running `/dream-team` later does step 3 only (status surface, no scaffolding, no re-enrollment).

### 4. Sanitization is deterministic

Sanitization runs before any team-candidate is staged for aggregation. It is deterministic, never LLM-driven (LLM-driven sanitization is itself an injection surface). The rules live in a versioned file at `.dream-team/sanitization.yaml` per project so teams can tune without code changes.

Default strip rules (v0 sketch, will harden in a follow-up design pass):

- Customer names matching the project's denylist
- Email addresses
- Phone numbers
- Account numbers, contract values, ARR figures, specific endpoint or seat counts
- Absolute paths containing home directory prefixes (`/Users/<name>/`, `C:\Users\<name>\`, `/home/<name>/`)
- Personal-context.md entries entirely (do not export)
- Customer-context.md entries entirely (do not export)
- Anything matching instruction-shaped patterns ("Always do X" or "When you see Y, do Z") without explicit provenance — these are **refused submission, not silently stripped**. The developer is told and must add provenance or remove before submitting.

### 5. Aggregation: start manual, build for automation

For a small team, manual aggregation is the right floor. Aggregation workflow shape is consistent across team sizes; the only thing that changes is who runs it.

Starting model (3-5 dev team):

1. Each developer's nightly run writes the team-candidate to `~/.claude/dream-state/team-candidates/<project>/<ts>/` locally.
2. Developer reviews candidate, runs `/dream-team-push` which commits to a branch `dream-team/<dev>-<date>` and opens a PR (or pushes a marker that an aggregation step picks up).
3. A `/dream-team-aggregate` command (run by anyone, or by a team lead on rotation) reads all open `dream-team/*` branches, runs corroboration (N≥2 required), and proposes a rollup PR.
4. Human reviews and merges. The aggregator never auto-merges.

This composes cleanly into automation as the team grows. Step 2 can move to auto-push, step 3 can move to a scheduled CI job. The shape of the per-developer candidate file and the corroboration rules stay the same.

### 6. Topic taxonomy mapped onto v1 stores

Which of the developer's personal Dream files export and which never do:

| Personal Dream file | Team-Dream export |
|---|---|
| working-style.md | Yes by default, post-sanitization |
| practice-context.md | Yes by default (practice-level facts) |
| customer-context.md | Never |
| personal-context.md | Never |
| tooling-environment.md | Selective. Stack defaults yes; personal hardware no |
| active-deliverables.md | Selective. Project-architectural facts yes; personal projects no |

The selective files require either developer review at submit time or a finer-grained tagging convention within the entries themselves. Working out the tagging is a follow-up design pass.

### 7. Scale-up: small to large

The architecture works at N=3 today and should not paint itself into a corner that breaks at N=30. Three things change at scale, all configurable rather than rewritten:

- **Corroboration threshold becomes proportional.** Default expression in `.dreamteam.yaml`: `corroboration_required: max(2, ceil(N * 0.2))`. At 3 devs that's 2 (67% agreement). At 30 devs that's 6 (20% agreement). Easy to tune.
- **Identity privacy becomes first-class.** At 3 devs everyone knows who wrote what. At 30, per-entry `_corroborated-by:` lists hash-prefixes plus a count, not names. Contributors can prove their contribution to themselves; viewers see breadth without identity.
- **Aggregation moves from human-driven to automated.** PR-on-aggregate breaks down past ~10 devs because PRs queue up. Designate a CI job to run aggregation weekly and propose the rollup PR; the team-lead-on-rotation approves.
- **Topic taxonomy becomes configurable.** The default topic set reflects one user's shape, not a universal one. `.dreamteam.yaml` declares the topic file set, falling back to the personal Dream taxonomy if unset.

### 8. Cross-project team patterns: surfaced, not auto-promoted

The "team-org" tier (cross-project team memory across multiple repos with the same team) is **out of v2 scope**. Designed-in as a hook but not built.

The personal Dream's nightly run can notice when a fact already exists in a team-memory store (because the developer's opted-in projects' team-memory files are referenced from CLAUDE.md and thus part of the personal Dream's gather phase) AND surface a "candidate team-org promotion" entry in `BOOTSTRAP-NOTES.md` (or its nightly equivalent) when the same pattern appears across multiple team-memory stores. The developer manually decides whether to elevate. No automatic cross-project propagation.

### 9. Developer departures

N≥2 corroboration provides resilience by design. When a developer leaves, their previous contributions stay, and the remaining contributors carry the corroboration count for facts they jointly produced. No retroactive decrement.

A separate `/dream-team-audit` command (counterpart to v1's `/dream-audit`) can flag facts whose corroboration is stale (no re-attestation within a configurable window) and surface them for either re-validation by remaining contributors or pruning. Audit reads, does not write.

### 10. First use case

3-5 person engineering test group. This sizes the architecture: aggregation can be manual, corroboration threshold is 2 absolute, taxonomy can start from the personal Dream taxonomy with light edits, no proportional thresholds needed yet. The architecture should still degrade cleanly toward the larger-team shape when it's time.

## What v2 does not address

- **Federation across organizations.** A team-memory store is a single project's data, not a shared substrate across companies.
- **Real-time collaboration.** Async dream cycles only; no live shared editing.
- **Conflict resolution beyond N-corroboration.** If two factions of a team converge on contradictory patterns, the architecture surfaces the contradiction but does not arbitrate.
- **Privacy guarantees against motivated adversaries.** Sanitization is best-effort, not formal privacy. A determined contributor can leak personal context by phrasing entries carefully. The architecture mitigates accidental leakage; intentional leakage is a personnel question, not a technical one.

## Open design questions

To dig in as time allows. Subsequent design notes in this directory will pick these up.

1. **Sanitization rule format.** YAML schema, regex vs. structured patterns, how teams tune denylists, how the "instruction-shaped refusal" path surfaces feedback to the developer.
2. **Contributors.json schema and identity model.** Git email plus a salted hash, or something richer? How does a developer leave the team cleanly?
3. **Aggregation step concrete.** Where the per-developer candidates land (Option A/B/C), how corroboration is computed when the same fact has slightly different wording across developers (semantic matching is an LLM job, which is exactly what we wanted to avoid).
4. **Selective-export tagging.** How tooling-environment and active-deliverables get reviewed at submit time. Per-entry tag (`_team-share: yes_`), or per-file convention, or LLM-classified-with-human-confirm?
5. **`/dream-team-audit` specifics.** Cadence, what counts as "stale corroboration," how re-attestation works mechanically.
6. **Conflict between team-memory and personal-Dream patterns.** When a developer's personal Dream contradicts the team-memory they're opted into, who wins for the next session's context?
7. **Bootstrap of an existing team.** A team that already has runbooks, Confluence, wiki pages — how does Dream Team get seeded without starting from zero?
8. **Cross-project team-org tier.** Designed-in hook only for v2; full design deferred. What's the minimum hook surface to leave today?

## Suggested next concrete step

Pick one of the open questions and design it through. Two candidates that would unblock implementation thinking quickly:

- **Sanitization rule format (Q1).** Concrete enough to write tests against. Decides what the "team-candidate" file actually looks like coming out of personal Dream.
- **Aggregation step (Q3).** Decides where candidates land, how corroboration is computed, how the rollup PR shape works. The architecture-shaping question.

Either is a natural next file in this directory.

## Relationship to v1

Dream Team consumes outputs of Dreamcatcher but does not replace it. A developer with no team can run v1 alone. A developer with a team runs both. The personal Dream stays personal; the team-candidate is a separate, sanitized, project-scoped artifact.

When v2 ships, the README gets a section pointing at this directory, and the topic taxonomy in v1's working-style.md gets an entry capturing the team-shareable convention. Nothing else in v1 changes.
