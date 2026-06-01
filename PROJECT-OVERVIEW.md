# Introducing Dreamcatcher

I built a memory layer for Claude Code, and I'm publishing it as open source today.

Here is the problem I started from. Claude Code is excellent inside a single project. Across projects, it is amnesiac. Every time I open a new session, in every other repo I work in, the AI starts from zero. My preferences, the engagement I am running, the architectural calls I made last week in a different codebase, the deliverable format my customers expect, all of it gets re-explained, every session, in every conversation. The cost of that re-explanation is small per session and ruinous in aggregate.

Claude Code ships with project-scoped memory called Auto Dream. It is a real feature and it works well, but only within one repo. Anything that recurs across projects (your working style, your customer context, your deployment standards, your dated decisions) has no home in the stock setup. It lives in fragmented form inside individual projects and never gets lifted to a place the next session will read.

Dreamcatcher is the layer above. A small Python tool that wakes up overnight, reads what Claude Code has already written to disk across every project, distills the patterns and preferences that span them, and writes those into a single cross-project memory store. The store gets loaded into every new Claude Code session automatically at session start. You stop re-explaining yourself.

The mechanics are deliberately boring. The memory store is a normal git repository on your machine. Consolidation runs as a scheduled nightly job. Two machines (desktop and laptop) share the store through a private git remote with an hourly background pull, so whichever machine you sit down at already has what the other one taught Claude the night before. Every consolidation produces a structured audit log committed alongside the topic-file changes, so the system explains itself when you want to know what it remembered and why. A single command rolls back any consolidation you do not like, alongside the bookkeeping that decided which transcripts had been processed.

What it captures is your working style, your customer engagement shapes, your tooling environment, your in-flight deliverables, and your dated decisions. What it deliberately excludes is customer names, credentials, specific financial figures, and personal information beyond what you explicitly volunteer. The redaction rules are baked into the consolidation prompt as non-negotiable instructions.

The pitch in one sentence: the system collects what matters across every project and makes it available everywhere, without you having to remember to do anything.

Today's release is v1.3, operational on my own two machines for the past week. Cross-platform for Windows and macOS, Python 3.8+ stdlib only at runtime, no telemetry, no third party in the loop. The repository is at github.com/brad-pierce/dreamcatcher.

A natural next layer is teams. Multiple developers sharing a cross-team memory above their own personal memory, with promotion gated by review and redaction enforced before anything leaves a developer's control. That design is captured in the repo as Dream Team v2 and is not yet built. If you would be interested in being one of the first teams to use it, find me here.
