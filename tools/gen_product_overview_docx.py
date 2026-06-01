#!/usr/bin/env python3
"""Generate "Dreamcatcher - Product Overview.docx", aimed at a layperson reader.

Different audience from the architecture doc: this one explains what
Dreamcatcher is, why it exists, and what it changes for someone using
Claude Code. No code, no git, no implementation details unless they
clarify a user-facing behavior. Same brand palette and editorial rules
as the architecture doc.

Editorial rules (from Brad's working-style memory):
  - No em dashes (use commas, parens, or hyphens).
  - Prose-first, bullets only where structure is genuinely the point.
  - Narrative momentum over jargon.
"""

from datetime import date
from pathlib import Path

from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH


# ---------- styling helpers (mirror gen_architecture_docx.py) ----------

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


def _quote(doc, text):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.italic = True
    run.font.color.rgb = RGBColor(0x00, 0x1F, 0x40)
    p.paragraph_format.left_indent = Inches(0.5)
    p.paragraph_format.right_indent = Inches(0.5)
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(10)
    return p


# ---------- content ----------

def build_doc(out_path: Path) -> None:
    doc = Document()
    _set_default_font(doc)

    # Title block
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = title.add_run("Dreamcatcher")
    r.bold = True
    r.font.size = Pt(32)
    r.font.color.rgb = RGBColor(0x00, 0x33, 0x66)

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = sub.add_run("Product Overview, v1.4")
    r.font.size = Pt(16)
    r.font.color.rgb = RGBColor(0x00, 0x1F, 0x40)
    sub.paragraph_format.space_after = Pt(6)

    tag = doc.add_paragraph()
    tag.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = tag.add_run("Cross-project memory for Claude Code, so your AI partner "
                    "remembers what matters across every session.")
    r.italic = True
    r.font.size = Pt(13)
    r.font.color.rgb = RGBColor(0x33, 0x33, 0x33)
    tag.paragraph_format.space_after = Pt(18)

    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = meta.add_run(f"Author: Brad Pierce  |  {date.today().isoformat()}  |  "
                     f"github.com/brad-pierce/dreamcatcher")
    r.font.size = Pt(10)
    r.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
    meta.paragraph_format.space_after = Pt(24)

    doc.add_page_break()

    # ----- 1. What is Dreamcatcher? -----
    _h1(doc, "What is Dreamcatcher?")
    _p(doc, (
        "Dreamcatcher is a memory system for Claude Code. It watches what you "
        "work on across every project, distills the patterns, preferences, and "
        "facts worth keeping, and makes them available to every future Claude "
        "Code session you start. The goal is simple: stop re-explaining yourself "
        "to your AI partner."
    ))
    _p(doc, (
        "If you have ever opened a new Claude Code session, told it about your "
        "deliverable preferences, the customer engagement you are in, the tools "
        "you have set up, the decisions you made last week, and then watched it "
        "make the same wrong assumption you corrected three days ago in a "
        "different project, you have felt the gap Dreamcatcher fills."
    ))

    _quote(doc, (
        "Without Dreamcatcher, every Claude Code session starts from zero. "
        "With Dreamcatcher, every session starts from what you already taught "
        "Claude, regardless of which project taught it."
    ))

    # ----- 2. The problem it solves -----
    _h1(doc, "The problem it solves")
    _p(doc, (
        "Claude Code, on its own, has two kinds of memory. Within a session, "
        "it remembers everything you say. Within a project, it can write notes "
        "to itself (called Auto Dream) that survive between sessions, but only "
        "for that one project. What it cannot do, by design, is connect the "
        "dots across projects."
    ))
    _p(doc, (
        "That gap matters because most knowledge workers do not live in one "
        "project. They move between a dozen engagements, a handful of internal "
        "tools, a side project or two, and an inbox full of analyses. The "
        "preference that shows up across thirty projects (always deliver "
        "DOCX rather than Markdown, write to the customer not the internal "
        "audience, use the smaller iteration style, watch for the same data-model "
        "gotcha in a tool you use daily) lives in every individual project's memory in fragmented "
        "form. It is never lifted to a place where the next session can read it "
        "before starting work."
    ))
    _p(doc, (
        "Dreamcatcher closes that loop. It reads what Claude Code has already "
        "written, finds the patterns that span projects, and puts them in one "
        "place every future session reads first."
    ))

    # ----- 3. How it works -----
    _h1(doc, "How it works, at a glance")
    _p(doc, (
        "Each night, Dreamcatcher runs a consolidation cycle. It reads any "
        "Claude Code activity since the last cycle, identifies what is worth "
        "keeping, and writes a small set of topic files to your local memory "
        "store. Those topic files cover your working style, your customer "
        "context, your tooling environment, the projects in flight, decisions "
        "worth remembering, and personal context like location and hobbies."
    ))
    _p(doc, (
        "When you start a new Claude Code session anywhere, Dreamcatcher "
        "automatically loads two things into Claude's context: the index of "
        "everything it knows about you, and the stable preferences you have "
        "set over time. The heavier topic files (in-flight projects, customer "
        "engagement shapes, practice context, tooling environment) "
        "are loaded on demand, the moment Claude needs them. You start the "
        "session at the point you would normally reach after twenty minutes "
        "of re-orienting it."
    ))
    _p(doc, (
        "The system is autonomous on the happy path. You install it once, set "
        "up a small private storage account so two computers can stay in sync, "
        "and Dreamcatcher runs in the background. The only time you need to "
        "step in is on the rare occasion the safety system flags a "
        "consolidation that needs human eyes."
    ))

    # ----- 4. What it remembers, and what it doesn't -----
    _h1(doc, "What it remembers, and what it deliberately does not")
    _h2(doc, "What gets captured")
    _p(doc, "Dreamcatcher captures the durable shape of how you work:")
    _bullet(doc, "Your working style and editorial preferences (format defaults, voice, deliverable shape).")
    _bullet(doc, "The engagements and projects in flight, with their state and shape (not the customers' names; see below).")
    _bullet(doc, "Your tooling environment (dev machines, MCP servers, hardware, the platform quirks that matter).")
    _bullet(doc, "Recurring patterns in your work (the eight-stage methodology you reuse, the fiscal-year-end campaign pattern, the schema gotchas).")
    _bullet(doc, "Decisions you have made, with dates and context, so future sessions know what is settled and what is open.")
    _bullet(doc, "Personal context that affects how you collaborate (your location, your hobbies, your prior background where relevant).")

    _h2(doc, "What is deliberately excluded")
    _p(doc, "Some categories are filtered out by policy and will never reach the memory store:")
    _bullet(doc, "Customer names. By design, customer names live in your CRM and project repos, not in the cross-project memory. The shape of the engagement survives; the customer's identity does not.")
    _bullet(doc, "Secrets and credentials. API keys, tokens, passwords, connection strings, and non-public internal URLs are never captured.")
    _bullet(doc, "Specific financial figures. Round-figure scale survives (\"a few thousand endpoints\"); the precise number does not.")
    _bullet(doc, "Personal information about family beyond what you have explicitly volunteered.")
    _p(doc, (
        "The redaction rules are baked into the consolidation prompt as "
        "non-negotiable instructions. When the system is uncertain, it redacts "
        "and leaves a marker so a later session knows the gap is intentional, "
        "not missing."
    ))

    # ----- 5. Privacy and trust -----
    _h1(doc, "Privacy and trust")
    _p(doc, (
        "Dreamcatcher is built on a single principle: your memory store is "
        "yours, never anyone else's. Three properties make that real."
    ))

    _h2(doc, "Local-first")
    _p(doc, (
        "The memory store lives on your own machines, in a folder you control. "
        "The optional private storage account that lets two computers share "
        "memory is a private repository you own (a private GitHub repository, "
        "for example). Nothing is sent to Anthropic, to Dreamcatcher itself, "
        "or to any third party. The system has no telemetry."
    ))

    _h2(doc, "Full audit trail")
    _p(doc, (
        "Every consolidation the system makes is logged in detail. The log "
        "records what sources were read, what changed in the memory store, "
        "the reason for each change, and what was considered but deliberately "
        "left out. The log travels alongside the memory itself, so a future "
        "version of you (or a colleague helping you set up your own copy) can "
        "see exactly what the system decided and why."
    ))

    _h2(doc, "One-command rollback")
    _p(doc, (
        "If a consolidation goes wrong, a single command undoes both the "
        "memory change and the bookkeeping that decided which transcripts had "
        "been processed. The next run will see those transcripts again and can "
        "redo the consolidation with a corrected prompt or a fresh review. "
        "Mistakes are recoverable, not permanent."
    ))

    _h2(doc, "Safety checks before applying")
    _p(doc, (
        "Before any consolidation lands in the memory store, the system runs "
        "a small set of sanity checks. The largest single one: if a "
        "consolidation would rewrite more than half of the memory in one pass, "
        "it refuses to apply automatically and asks for human review. "
        "Catastrophic mistakes (a confused AI deciding to delete everything) "
        "cannot land silently."
    ))

    # ----- 6. Two machines, one memory -----
    _h1(doc, "Two machines, one memory")
    _p(doc, (
        "Most knowledge workers use more than one computer. Dreamcatcher is "
        "designed for two: a primary machine where you do most of your work, "
        "and a secondary machine (typically a laptop) where you work when you "
        "travel."
    ))
    _p(doc, (
        "Both machines participate equally. Each one consolidates the work "
        "you did on it, and a small private synchronization channel keeps the "
        "two memories aligned. When you open the laptop on the road, it "
        "already has what you taught the desktop the night before. When you "
        "return to the desktop, it already has what you taught the laptop on "
        "the trip."
    ))
    _p(doc, (
        "The synchronization runs in the background, on a once-an-hour "
        "schedule. You do not have to remember to push, pull, export, or import. "
        "If you happen to be offline (on a plane, in a cabin) the system "
        "gracefully waits and catches up when you reconnect. If a "
        "synchronization would lose work, it refuses and surfaces the conflict; "
        "it will never silently overwrite something you cared about."
    ))

    # ----- 7. How is this different from project memory? -----
    _h1(doc, "How is this different from project memory?")
    _p(doc, (
        "Claude Code's built-in project memory (sometimes called Auto Dream) "
        "captures what is relevant to one project. That is genuinely useful "
        "and Dreamcatcher does not replace it. The two layers complement each "
        "other."
    ))
    _p(doc, (
        "Project memory is the layer for project-specific facts: this "
        "repository's coding conventions, the deployment quirks of this "
        "specific app, the architectural decisions for this codebase. When "
        "you open a session inside a project, that project's memory is what "
        "gets loaded."
    ))
    _p(doc, (
        "Dreamcatcher sits a tier above. It captures what is true about you, "
        "your work, and your environment across every project. When you open "
        "a session in a brand-new directory that has no project memory yet, "
        "Dreamcatcher's memory is already there. When you open a session in "
        "an existing project, you get both: the project's specifics, plus "
        "your cross-project context."
    ))

    # ----- 8. Who is it for? -----
    _h1(doc, "Who is Dreamcatcher for?")
    _p(doc, (
        "Anyone who uses Claude Code seriously across more than one or two "
        "projects, especially over weeks and months. The value compounds with "
        "scale: every additional project adds to the cross-project signal, "
        "and every additional week of use makes the memory more accurate at "
        "what you actually do and prefer."
    ))
    _p(doc, (
        "Concrete profiles where Dreamcatcher pays for its setup time:"
    ))
    _bullet(doc, "Practitioners with a dozen or more concurrent engagements who need each to feel like Claude already knows them.")
    _bullet(doc, "Builders working across multiple side projects who want their architectural decisions to carry forward.")
    _bullet(doc, "Researchers and analysts who develop a personal style over time and want their AI partner to learn it without re-teaching every session.")
    _bullet(doc, "Teams of one: a single human running across many projects, accountable to many stakeholders, where the cost of repeated re-orientation is the highest single recurring drag.")

    # ----- 9. Getting started -----
    _h1(doc, "Getting started")
    _p(doc, (
        "Installation is a single Python script that asks a few questions "
        "and writes the necessary configuration. The first time you run it, "
        "you choose where the memory store lives (the default is fine for "
        "most people), point at which directories the system is allowed to "
        "search for projects, and confirm. The script handles the rest, "
        "including telling you the one-time setup command for the optional "
        "two-machine synchronization."
    ))
    _p(doc, (
        "After install, you can either run the first consolidation yourself "
        "to test the loop, or let it run automatically on the nightly schedule. "
        "From that point forward Dreamcatcher operates in the background. "
        "Your next Claude Code session will already be reading what it has "
        "captured."
    ))
    _p(doc, (
        "Existing Claude Code users who already have project memories built "
        "up will find Dreamcatcher useful immediately: the first consolidation "
        "reads those project memories and builds a starting cross-project layer "
        "from them. You are not starting from a blank page; you are starting "
        "from everything Claude has already learned about your work, organized "
        "for the first time."
    ))

    # ----- 10. What is on the horizon? -----
    _h1(doc, "What is on the horizon?")
    _p(doc, (
        "Today Dreamcatcher serves one person, on up to two machines. The "
        "natural next layer is teams: multiple developers sharing a cross-team "
        "memory above their own personal memory, with promotion gated by "
        "review, redaction enforced before anything leaves a developer's "
        "control, and clean off-boarding when someone leaves the team."
    ))
    _p(doc, (
        "That layer is designed in detail and not yet built. It is named "
        "Dream Team and waits for the right team-of-three or team-of-five to "
        "be the first to use it. Until then, Dreamcatcher is a personal "
        "system that already pays for itself the first time you open a session "
        "and find your preferences and context are already there."
    ))

    # ----- Closing -----
    _h1(doc, "In one sentence")
    _quote(doc, (
        "Dreamcatcher is what lets your AI partner remember what matters "
        "across every project, on every machine, without you having to "
        "re-teach it every morning."
    ))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    here = Path(__file__).resolve().parent.parent
    build_doc(here / "Dreamcatcher - Product Overview.docx")
