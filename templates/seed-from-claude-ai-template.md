# seed-from-claude-ai.md — Template

> **Purpose:** the format for the user's `claude.ai` memory dump as it lands in `~/Dreamcatcher/memory/scratch/` ahead of the bootstrap. Stage 3 of bootstrap setup (seed assembly), consumed by the `/dream-bootstrap` prompt as **highest-confidence input**.
>
> **Where it lives:** `~/Dreamcatcher/memory/scratch/seed-claude-ai-memory-YYYY-MM-DD.md`. The date is the date you copied the memory out of `claude.ai`, not the date you're running the bootstrap.
>
> **Lifecycle:** seed-only, not ongoing. The bootstrap consumes this once; the promote script moves it to `scratch/.archived/` after a successful bootstrap promotion. Do not try to keep this updated as `claude.ai` memory evolves — that's the trap bootstrap Stage 3 explicitly chose to avoid. If `claude.ai` memory has materially shifted six months from now and you want it incorporated, drop a *new* seed file with a fresh date and run an audit pass.
>
> **Authoring posture:** the user's only real job here is **categorisation** and **redaction**. The content is already filtered for signal by `claude.ai`'s own consolidation. Don't rewrite it; just slot each fact under the topic file it's likely destined for, mark confidence where it's not obvious, and strip anything that shouldn't be in a Git repo.

---

Copy the block below into `scratch/seed-claude-ai-memory-YYYY-MM-DD.md` and fill it in. Delete this preamble before saving. Keep the section headers — the bootstrap prompt looks for them by name.

---

# Seed: claude.ai memory dump

_dumped: YYYY-MM-DD_
_source: claude.ai userMemories block, conversation interface_
_confidence: high (already filtered by claude.ai consolidation)_
_seed-only: true — not refreshed by nightly dream_

## How to read this file

Each section corresponds to one topic file in the bootstrap output. Facts under each section are candidates for that topic file. The bootstrap may move them — its categorisation overrides this one — but starting from this categorisation saves it from having to infer.

Confidence markers per entry:
- `[H]` — high confidence, copy verbatim if it earns a place in memory
- `[M]` — medium confidence, bootstrap should re-examine against project sources
- `[?]` — flagged for review, bootstrap should write to BOOTSTRAP-NOTES.md rather than memory

Default confidence is `[H]` unless marked otherwise.

## Redactions applied to this file

Before the bootstrap touches this, scrub:
- Account numbers, contract values, ARR figures
- API keys, tokens, passwords, connection strings, non-public internal URLs
- Customer contact email addresses (preserve role/title)
- Specific endpoint or seat counts above round numbers
- Personal information about family beyond what's already in other scratch files

Note any redactions made when authoring:
- _e.g. "Redacted Customer X endpoint count from specific figure to round figure"_

The bootstrap then applies its own redaction pass on top, but the more is done here, the less the bootstrap has to guess.

---

## working-style.md candidates

Collaboration norms, formatting preferences, deliverable defaults, communication patterns. Things that apply across every project and shouldn't expire on a date.

- [H] _e.g. "Prefers DOCX deliverables to Markdown for customer-facing work."_
- [H] ...
- [M] _e.g. "Tends to ask for round-number figures rather than exact counts in assessments."_ — _M because this came up in only one claude.ai conversation; bootstrap should verify against project signal_
- ...

## customer-context.md candidates

Active engagements, named customers, engagement type, what each customer cares about. **Apply `_active-as-of:` in the bootstrap** — these are time-bounded.

- [H] _e.g. "<CUSTOMER_CODENAME> — <segment> customer, <product> migration engagement <quarter> <year>, ~N endpoints, primary contact is the <role> who cares about <concern>."_
- ...

## practice-context.md candidates

Professional practice context: the domain you work in, the partners, standards, and tools that recur, and how your field's engagements are typically structured. Stable practice-level facts, not engagement-specific.

- [H] _e.g. "<EMPLOYER> works mainly in <domain>; <a recurring standard or process> applies to most engagements."_
- ...

## tooling-environment.md candidates

The user's dev environment, MCP servers in flight, hardware. Some of these are time-bounded ("<hardware> currently set up for <use case>") — those get `_active-as-of:` in the bootstrap.

- [H] _e.g. "Windows desktop with WSL2 Ubuntu for dev; PowerShell for native Windows tasks."_
- [H] _e.g. "<hardware item>, primary workflow is for <use case>."_  — _engagement-style, will get _active-as-of:_
- ...

## active-deliverables.md candidates

Documents being authored, code being built, articles in review. These will mostly age out within months; **all get `_active-as-of:`**. If anything here has actually concluded by the time you're authoring this seed, move it to "Historical context for decisions" below instead.

- [H] _e.g. "Drafting a <SYSTEM_A> → <SYSTEM_B> data bridge as an MCP server, mid-implementation as of YYYY-MM-DD."_
- ...

## decisions/ candidates

Dated, append-only architecture/strategy decisions worth remembering. Each becomes one file: `decisions/YYYY-MM-DD-<slug>.md`. The date is the date the decision was made, *not* the date you're authoring this seed.

- [H] **YYYY-MM-DD — chose <vendor-A> over <vendor-B> for <project>**: _one-sentence reason_
- [H] **YYYY-MM-DD — DOCX over Markdown as default customer deliverable format**: _one-sentence reason_
- ...

## Historical context (no fixed home)

Facts that were once active but no longer are, and that the bootstrap should consider for `decisions/` files or simply discard. The user's call on which.

- _e.g. "Concluded the (named customer) compliance audit engagement YYYY-MM; no follow-up expected."_
- ...

## Cross-cutting flags for the bootstrap

Anything that doesn't fit a topic file but the bootstrap should know about:
- _e.g. "If you find references to '<CODENAME>' in any project, it's the codename for the same customer across all of them — do not split into separate entries."_
- _e.g. "When in doubt about a customer fact, defer to customer-context.md authored by the bootstrap, not to this seed."_
- ...

## Open questions for the user to resolve before the bootstrap consumes this

Things the seed contains but the user hasn't decided how to handle. The bootstrap should treat any entry here as `[?]` and surface in `BOOTSTRAP-NOTES.md`.

- _e.g. "Two contradictory notes on whether (customer) is still an active engagement — resolve before running."_
- ...

---

## Filling-in checklist (delete before saving)

- [ ] Copied raw userMemories block out of claude.ai
- [ ] Slotted every fact under a section (used "Historical context" for orphans)
- [ ] Applied redactions per the rules above; noted what was redacted
- [ ] Confidence markers applied where not default-high
- [ ] Open questions section is empty OR explicitly accepted that the bootstrap will flag them
- [ ] File is in `~/Dreamcatcher/memory/scratch/` with the dump date in the filename
