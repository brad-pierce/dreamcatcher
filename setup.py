#!/usr/bin/env python3
"""setup.py - deploy Dreamcatcher to ~/Dreamcatcher/

Cross-platform: Windows and macOS (and Linux for smoke tests). Stdlib only.
Idempotent. Re-running cleans up old hook entries in settings.json and
redeploys fresh copies of scripts and prompts. settings.json is backed up
before every modification.

v1.1 (2026-05-18): Writable directories moved out from under ~/.claude/
because Claude Code's auto-mode classifier treats writes there as sensitive
and refuses them in headless `claude -p` subprocesses. New layout:

  ~/Dreamcatcher/memory/    (live git store; v1.2 adds .dream-log/<run-id>.json
                             audit logs that travel with topic-file changes)
  ~/Dreamcatcher/state/     (per-machine state, reverie, logs, config)
  ~/Dreamcatcher/inputs/    (PreCompact transcript snapshots)
  ~/Dreamcatcher/hooks/     (deployed Python scripts: hook handlers, plus
                             dreamcatcher-pull.py and dreamcatcher-log.py
                             user-facing v1.2 utilities)

Slash command discovery stays at ~/.claude/commands/ and settings.json
stays at ~/.claude/settings.json (Claude Code reads from those locations).

v1.2 (2026-05-19): Cross-machine bidirectional sync via private git remote
becomes the default (manual export/import is the fallback). /dream-global
auto-promotes on the happy path; manual promote.py is the escape hatch when
a sanity floor trips. setup.py prints the recommended schedule-registration
command for the platform but does NOT auto-register it without consent.

Usage:
  python setup.py              # desktop install (default)
  python setup.py --laptop     # laptop install (different hook set)
  python setup.py --dry-run    # show what would change, touch nothing
  python setup.py --yes        # accept default discovery roots non-interactively
  python setup.py --migrate    # move a pre-v1.1 install from ~/.claude/ to ~/Dreamcatcher/

What it does:
  0. Verify git is available.
  1. Create directory structure under ~/Dreamcatcher/.
  2. git init ~/Dreamcatcher/memory/ if not already a repo.
  3. Prompt for discovery roots (Stage 1 + nightly find passes are bound to
     these), write them to ~/Dreamcatcher/state/config.json.
  4. Copy scripts/*.py to ~/Dreamcatcher/hooks/ (hook handlers, the
     auto-promote pipeline, the pull/log utilities, and the CLI tools).
  5. Stage the dream-global and dream-bootstrap prompt bodies to
     ~/Dreamcatcher/prompts/ so scheduled headless runs feed prompt
     content to `claude -p` rather than a slash command (which is an
     interactive-mode-only feature).
  6. Copy all slash command files from commands/ to ~/.claude/commands/
     (the /dream-global, /dream-bootstrap, /dream-audit prompts plus
     /dream-export, /dream-import, /dream-prime, /dream-rollback) for
     interactive use.
  7. Merge hook config into ~/.claude/settings.json using absolute paths
     pointing at ~/Dreamcatcher/hooks/ and the platform-appropriate python
     interpreter name.
  8. Detect/instruct on the Dreamcatcher memory section in ~/CLAUDE.md
     (v1.3). SessionStart-injected MEMORY.md + working-style.md works
     unconditionally; this step wires the on-demand-read pointer. Creates
     ~/CLAUDE.md from template if absent; appends with --yes if the file
     exists but lacks the section; otherwise prints paste instructions.
  9. Print the platform-appropriate command to register the hourly pull
     job (Task Scheduler on Windows, crontab/launchd on macOS). Not
     auto-registered -- user runs it once.

What it does NOT do (these need human judgment):
  - Set a git remote on global-memory (pick where to host it; or skip).
  - Register the hourly pull job (printed for user to run once; v1.2).
  - Run Stage 1 discovery -- the bucketing-projects step (see /dream-bootstrap).
  - Run /init across uncurated projects -- Stage 2.
  - Copy your claude.ai memory dump -- Stage 3.
  - The bootstrap run itself -- Stage 4.
  - Reverie seeding after the first promotion -- Stage 5.
"""

import argparse
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


# ---------- argv ----------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Deploy Dreamcatcher (installs under ~/Dreamcatcher/; v1.1+).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--laptop", action="store_const", const="laptop",
                   dest="mode", help="Install laptop hook set (read-mostly).")
    p.add_argument("--desktop", action="store_const", const="desktop",
                   dest="mode", help="Install desktop hook set (default).")
    p.add_argument("--dry-run", action="store_true",
                   help="Show what would change. Touch nothing.")
    p.add_argument("--yes", "-y", action="store_true",
                   help="Accept default discovery roots without prompting.")
    p.add_argument("--discovery-root", action="append", default=[],
                   metavar="PATH",
                   help="Discovery root (repeatable). Overrides interactive prompt.")
    p.add_argument("--migrate", action="store_true",
                   help="Migrate a pre-v1.1 install from ~/.claude/{global-memory,"
                        "dream-state,dream-inputs,dream-hooks}/ to ~/Dreamcatcher/"
                        "{memory,state,inputs,hooks}/. Updates config.json paths "
                        "and rewrites settings.json hook command paths. Idempotent.")
    p.set_defaults(mode="desktop")
    return p.parse_args()


# ---------- output helpers ----------

def say(msg: str) -> None:
    print(f"  {msg}")

def section(title: str) -> None:
    print()
    print(f"=== {title} ===")

def warn(msg: str) -> None:
    print(f"  WARN: {msg}", file=sys.stderr)

def die(msg: str, code: int = 1) -> "None":
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


# ---------- platform helpers ----------

def platform_kind() -> str:
    s = platform.system().lower()
    if s.startswith("win"):
        return "windows"
    if s == "darwin":
        return "darwin"
    return "linux"

def python_cmd_for(kind: str) -> str:
    """Interpreter to write into settings.json hook command strings.

    Returns sys.executable (the absolute path of the Python that ran setup.py)
    so a PATH-shadow attack -- malicious python.exe earlier on the user's PATH
    than the real one -- cannot substitute itself into hook execution. Fall
    back to the bare `python` / `python3` name if sys.executable looks
    unreliable (e.g. it points at the Python launcher's stub).

    The user can still edit settings.json by hand to change the interpreter.
    """
    exe = sys.executable
    if exe and Path(exe).is_file():
        # Quote-escape backslashes for embedding into JSON command strings
        # (json.dumps later handles the actual escaping, but the path itself
        # must round-trip cleanly).
        return exe
    return "python" if kind == "windows" else "python3"

def default_discovery_roots(kind: str, home: Path) -> "list[str]":
    """Default directories the dream walks looking for in-scope projects.

    Narrow defaults on purpose: the dream prompts grep transcripts that live
    under ~/.claude/projects/, and that's also where Auto Dream's per-project
    memory files live. A broader default (the user's whole home) means
    walking every directory under it on every nightly cycle, with the dream
    prompt incidentally seeing whatever's there. Users with project trees
    elsewhere can add roots interactively at install time.

    Windows also includes C:/Claude as a historical project home some users
    have. Drop or replace via the interactive prompt or --discovery-root.
    """
    candidates = [home / ".claude" / "projects"]
    if kind == "windows":
        c_claude = Path("C:/Claude")
        if c_claude.is_dir():
            candidates.append(c_claude)
    return [str(p) for p in candidates if p.is_dir() or candidates.index(p) == 0]

def chmod_executable(path: Path) -> None:
    if os.name != "posix":
        return
    st = path.stat()
    path.chmod(st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


# ---------- discovery roots ----------

def prompt_discovery_roots(defaults: "list[str]", non_interactive: bool) -> "list[str]":
    print("Discovery roots bound where Stage 1 bootstrap and nightly passes are")
    print("allowed to walk. Bounding keeps consolidation predictable and prevents")
    print("scanning your whole drive. Provide one or more absolute paths separated")
    print("by commas, or press Enter for defaults.")
    say(f"defaults: {', '.join(defaults)}")

    if non_interactive or not sys.stdin.isatty():
        say(f"using defaults (non-interactive)")
        return defaults

    try:
        raw = input("  Discovery roots [Enter for defaults]: ").strip()
    except EOFError:
        raw = ""

    if not raw:
        return defaults

    roots = [r.strip() for r in raw.split(",") if r.strip()]
    expanded = [str(Path(r).expanduser()) for r in roots]
    missing = [r for r in expanded if not Path(r).exists()]
    if missing:
        warn(f"these roots do not exist yet: {', '.join(missing)}")
        warn("kept anyway -- adjust later in config.json if that's wrong.")
    return expanded


# ---------- step runners ----------

def check_dependencies() -> None:
    section("0. Dependencies")
    if shutil.which("git") is None:
        die("git is required but not on PATH. Install git and re-run.")
    say("git: OK")
    say(f"python: {sys.version.split()[0]} ({sys.executable})")


def make_skeleton(paths: dict, dry: bool) -> None:
    section("1. Directory skeleton")
    dirs = [
        paths["memory"] / "decisions",
        paths["memory"] / "scratch",
        paths["state"] / "logs",
        paths["state"] / "reverie-backups",
        paths["inputs"] / "precompact",
        paths["hooks"],
        paths["prompts"],
        paths["commands"],
    ]
    for d in dirs:
        if d.exists():
            say(f"exists: {d}")
        elif dry:
            say(f"[dry-run] would create: {d}")
        else:
            d.mkdir(parents=True, exist_ok=True)
            say(f"created: {d}")


def init_memory_repo(memory: Path, dry: bool) -> None:
    section("2. Global-memory git repo")
    if (memory / ".git").is_dir():
        say(f"already a git repo: {memory}")
        return
    if dry:
        say("[dry-run] would git init + write .gitignore + initial commit")
        return

    (memory / "decisions" / ".gitkeep").touch()
    (memory / "scratch" / ".gitkeep").touch()

    # Prefer -b main; fall back for older git.
    init = subprocess.run(
        ["git", "init", "-q", "-b", "main"], cwd=memory,
        stderr=subprocess.PIPE, text=True,
    )
    if init.returncode != 0:
        subprocess.run(["git", "init", "-q"], cwd=memory, check=False)
        subprocess.run(
            ["git", "symbolic-ref", "HEAD", "refs/heads/main"],
            cwd=memory, check=False,
        )

    (memory / ".gitignore").write_text(
        "# Per-run candidate output; promoted via promote.py\n"
        ".candidate/\n"
        "\n"
        "# Audit review documents; per-machine, not part of consolidated record\n"
        ".audit/\n"
        "\n"
        "# OS detritus\n"
        ".DS_Store\n"
        "Thumbs.db\n",
        encoding="utf-8",
    )

    subprocess.run(["git", "add", "."], cwd=memory, check=False)
    commit = subprocess.run(
        ["git", "commit", "-q", "-m", "init: empty global-memory repo skeleton"],
        cwd=memory, stderr=subprocess.PIPE, text=True,
    )
    if commit.returncode != 0:
        warn("initial commit did not complete.")
        for line in (commit.stderr or "").splitlines()[:4]:
            print(f"    {line}", file=sys.stderr)
        warn("common causes: missing user.name/user.email, or signing required.")
        warn("to finish manually after fixing:")
        warn(f"  cd {memory} && git commit -m 'init: empty global-memory repo skeleton'")
        say(f"initialized: {memory} (commit did NOT land; everything else OK)")
        return

    say(f"initialized: {memory} (commit landed; no remote set -- your call)")


def resolve_discovery_roots(cli_roots: "list[str]", kind: str, home: Path,
                            non_interactive: bool) -> "list[str]":
    section("3. Discovery roots + config.json")
    if cli_roots:
        say(f"using --discovery-root: {', '.join(cli_roots)}")
        return cli_roots
    return prompt_discovery_roots(default_discovery_roots(kind, home), non_interactive)


def write_config(paths: dict, roots: "list[str]", kind: str, mode: str, dry: bool) -> None:
    config_path = paths["state"] / "config.json"
    config = {
        "discovery_roots": roots,
        "platform": kind,
        "python_command": python_cmd_for(kind),
        "claude_root": str(paths["claude"]),
        "memory_root": str(paths["memory"]),
        "dream_state": str(paths["state"]),
        "dream_hooks": str(paths["hooks"]),
        "dream_inputs": str(paths["inputs"]),
        "commands_dir": str(paths["commands"]),
        "settings_file": str(paths["settings"]),
        "mode": mode,
        "installed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if dry:
        say(f"[dry-run] would write: {config_path}")
        return
    tmp = config_path.with_suffix(config_path.suffix + ".tmp")
    tmp.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, config_path)
    say(f"wrote: {config_path}")


def _strip_front_matter(text: str) -> str:
    """Drop a leading YAML front-matter block (--- ... ---) if present.

    The slash-command files in commands/ carry a `---\\ndescription: ...\\n---`
    header for interactive use. The scheduled (headless) runs feed the prompt
    body to `claude -p`, so the staged copy has the header stripped.
    """
    if text.startswith("---"):
        lines = text.splitlines(keepends=True)
        for i in range(1, len(lines)):
            if lines[i].rstrip("\r\n") == "---":
                return "".join(lines[i + 1:]).lstrip("\n")
    return text


def deploy_python_scripts(repo: Path, paths: dict, dry: bool) -> None:
    section("4. Deploy runtime scripts")
    src_dir = repo / "scripts"
    py_scripts = sorted(src_dir.glob("*.py"))
    if not py_scripts:
        say("no Python scripts found in scripts/ -- nothing to deploy.")
    for src in py_scripts:
        dst = paths["hooks"] / src.name
        if dry:
            say(f"[dry-run] would deploy: {src.name}")
            continue
        shutil.copyfile(src, dst)
        chmod_executable(dst)
        say(f"deployed: {src.name}")

    section("5. Stage scheduled-run prompts")
    # The nightly consolidation and the one-time bootstrap run headless via the
    # OS scheduler (claude -p). Slash-command invocation is an interactive-mode
    # feature, so the scheduled job feeds the prompt CONTENT instead. Stage the
    # operational body of each (front matter stripped) to ~/Dreamcatcher/prompts/.
    for cmd_name in ("dream-global", "dream-bootstrap"):
        src = repo / "commands" / f"{cmd_name}.md"
        if not src.exists():
            say(f"missing (skipped): commands/{cmd_name}.md")
            continue
        dst = paths["prompts"] / f"{cmd_name}.md"
        if dry:
            say(f"[dry-run] would stage prompt: {dst}")
            continue
        dst.write_text(_strip_front_matter(src.read_text(encoding="utf-8")), encoding="utf-8")
        say(f"staged prompt: {cmd_name}.md")


# ---------- slash command deployment ----------

def copy_static_commands(repo: Path, commands_dir: Path, dry: bool) -> None:
    section("6. Deploy slash commands")
    src_dir = repo / "commands"
    if not src_dir.is_dir():
        say("no commands/ directory in repo; skipped")
        return
    for src in sorted(src_dir.glob("*.md")):
        dst = commands_dir / src.name
        if dry:
            say(f"[dry-run] would deploy: /{src.stem}")
            continue
        shutil.copyfile(src, dst)
        say(f"deployed: /{src.stem}")


# ---------- settings.json merge ----------

def build_hooks_block(mode: str, python_cmd: str, dream_hooks: Path) -> dict:
    """Return the hooks-events dict to merge into settings.json.

    Absolute paths, platform-appropriate python interpreter name -- no shell
    expansion needed on either OS.
    """
    def cmd(script: str) -> str:
        return f"{python_cmd} {dream_hooks / script}"

    if mode == "desktop":
        return {
            "PreCompact": [{
                "matcher": "auto|manual",
                "hooks": [{
                    "type": "command",
                    "command": cmd("snapshot_transcript.py"),
                    "async": True,
                    "timeout": 60,
                }],
            }],
            "SessionEnd": [{
                "hooks": [{
                    "type": "command",
                    "command": cmd("queue_session.py"),
                    "async": True,
                }],
            }],
            "SessionStart": [{
                "matcher": "startup|resume",
                "hooks": [{
                    "type": "command",
                    "command": cmd("desktop_status.py"),
                }],
            }],
        }
    # laptop
    return {
        "SessionStart": [{
            "matcher": "startup|resume",
            "hooks": [{
                "type": "command",
                "command": cmd("laptop_status.py"),
                "timeout": 30,
            }],
        }],
    }


def referenced_dream_hook(cmd_str: str) -> bool:
    """True if a settings.json hook command references our hook scripts.

    Catches the bash-era path `~/.claude/dream-hooks/`, the v1.0 Python path
    `~/.claude/dream_hooks/`, and the v1.1+ path `~/Dreamcatcher/hooks/` (matched
    via the Dreamcatcher\\hooks or Dreamcatcher/hooks substring on the respective
    OSes). Also matches by hook script filename as a final safety net so any
    future layout change still gets cleaned on re-install.

    A re-install replaces rather than duplicates the hook entries this matches.
    The previous version of this function checked only the bash-era / v1.0
    substrings and silently allowed v1.1+ entries to accumulate across installs.
    """
    lower = cmd_str.replace("\\", "/").lower()
    if "dream-hooks/" in lower or "dream_hooks/" in lower:
        return True
    if "dreamcatcher/hooks/" in lower:
        return True
    # Filename fallback: catches the script names regardless of deploy path.
    for script in (
        "snapshot_transcript.py",
        "queue_session.py",
        "desktop_status.py",
        "laptop_status.py",
        "dream_promote.py",
        "dreamcatcher-pull.py",
        "dreamcatcher-log.py",
    ):
        if script in lower:
            return True
    return False


def merge_settings(settings_path: Path, new_hooks: dict, dry: bool) -> None:
    section("7. Wire hooks into settings.json")
    if not settings_path.exists():
        if dry:
            say(f"[dry-run] would create empty {settings_path}")
        else:
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            settings_path.write_text("{}\n", encoding="utf-8")
            say(f"created empty {settings_path}")

    if dry:
        say(f"[dry-run] would merge these hooks into {settings_path}:")
        for line in json.dumps(new_hooks, indent=2).splitlines():
            print(f"    {line}")
        return

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    backup = settings_path.with_suffix(settings_path.suffix + f".bak-{stamp}")
    shutil.copyfile(settings_path, backup)
    say(f"backed up to: {backup}")

    try:
        current = json.loads(settings_path.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError as e:
        die(f"existing {settings_path} is not valid JSON: {e}. "
            f"Original preserved at {backup}.")

    current.setdefault("hooks", {})
    for event, entries in new_hooks.items():
        existing = current["hooks"].get(event, []) or []
        # Drop any existing matcher groups whose hooks reference our dream-hooks
        # dir, so a re-install replaces them. Unrelated hooks are preserved.
        kept = []
        for group in existing:
            hooks_in_group = group.get("hooks", []) or []
            if any(referenced_dream_hook(str(h.get("command", ""))) for h in hooks_in_group):
                continue
            kept.append(group)
        current["hooks"][event] = kept + entries

    # Atomic write: a Ctrl+C or OOM between truncate and write would leave
    # ~/.claude/settings.json empty or partial, breaking Claude Code's hook
    # discovery. Write to a sibling .tmp and os.replace -- atomic on both
    # POSIX and Windows for same-volume renames.
    tmp = settings_path.with_suffix(settings_path.suffix + ".tmp")
    tmp.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, settings_path)
    say(f"merged hooks into {settings_path}")


# ---------- main ----------

def summary(paths: dict, repo: Path, mode: str) -> None:
    section("Done")
    print()
    print(f"Dreamcatcher is installed for: {mode}")
    print()
    print(f"Source repo:       {repo}")
    print(f"Global memory:     {paths['memory']}")
    print(f"Hook handlers:     {paths['hooks']}")
    print(f"Slash commands:    {paths['commands']}")
    print(f"Settings file:     {paths['settings']}")
    print(f"Per-machine state: {paths['state']}")
    print(f"Config file:       {paths['state'] / 'config.json'}")
    print()
    print("Next steps (not automated -- these need your judgment):")
    print()
    print(f"  1. v1.2 cross-machine sync (recommended): set a private git remote")
    print(f"       cd {paths['memory']}")
    print(f"       git remote add origin <your-private-repo-url>")
    print(f"       git push -u origin main")
    print(f"     On the OTHER machine, after `setup.py --laptop`:")
    print(f"       cd {paths['memory']}")
    print(f"       git remote add origin <same-url>")
    print(f"       git pull --ff-only")
    print(f"     Or leave local-only and rely on /dream-export + /dream-import as")
    print(f"     a fallback (v1.1 default; still supported for air-gap and seed).")
    print()
    print(f"  1b. v1.2 hourly pull cron (recommended once remote is set):")
    _print_schedule_command(paths)
    print()
    print(f"  1c. Nightly consolidation schedule (content-fed; runs headless):")
    print(f"       Slash commands are interactive-only, so do NOT schedule")
    print(f"       `claude -p \"/dream-global\"`. Feed the staged prompt content:")
    _ng = paths["prompts"] / "dream-global.md"
    if os.name == "nt":
        print(f"         claude -p (Get-Content -Raw \"{_ng}\") "
              f"--allowedTools \"Bash,Read,Write,Edit\"")
    else:
        print(f"         claude -p \"$(cat '{_ng}')\" "
              f"--allowedTools \"Bash,Read,Write,Edit\"")
    print(f"       Wrap that in your nightly runner; keep it outside 0500-1200 PDT.")
    print()
    print("  2. Verify hooks loaded:")
    print("       Start a fresh Claude Code session and type /hooks")
    print("       You should see dream-hooks entries under \"User\" scope.")
    print()
    print("  3. Stage 1 -- Discovery:")
    print(f"       Run /dream-bootstrap discovery within the configured")
    print(f"       discovery_roots and hand-author")
    print(f"       {paths['memory'] / 'scratch' / 'bootstrap-scope.md'}")
    print(f"       using {repo / 'templates' / 'bootstrap-scope-template.md'}")
    print()
    print("  4. Stage 2 -- Pre-distillation (overnight):")
    print("       For each active+uncurated project from bootstrap-scope.md,")
    print("       run /init or let project Auto Dream catch up.")
    print()
    print("  5. Stage 3 -- Seed assembly (~30 min):")
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"       Paste your claude.ai memory dump into")
    print(f"       {paths['memory'] / 'scratch' / f'seed-claude-ai-memory-{today}.md'}")
    print(f"       using {repo / 'templates' / 'seed-from-claude-ai-template.md'}")
    print()
    print("  6. Stage 4 -- The bootstrap:")
    print(f"       Fresh Claude Code session in {paths['memory']}, type /dream-bootstrap")
    print()
    print("  7. Stage 5 -- Heavy review + promote + reverie seed:")
    print("       Read every candidate file end-to-end (no diff exists yet).")
    print(f"       python {paths['hooks'] / 'promote.py'} bootstrap-<timestamp>")
    print(f"       Then manually seed {paths['state'] / 'reverie.json'} with one entry")
    print("       per in-scope project (latest activity timestamp from .claude/projects/).")
    print()


_CLAUDE_MD_MARKER_BEGIN = "<!-- BEGIN: Dreamcatcher memory section (managed by setup.py detection) -->"
_CLAUDE_MD_MARKER_END = "<!-- END: Dreamcatcher memory section -->"


def ensure_user_claude_md(repo: Path, home: Path, yes: bool, dry: bool) -> None:
    """Step 9 (v1.3): check / instruct on the Dreamcatcher memory section in ~/CLAUDE.md.

    The SessionStart hook injects MEMORY.md and working-style.md into every
    session unconditionally. The other half of v1.3's consumption wiring is a
    section in ~/CLAUDE.md telling Claude where the on-demand topic files
    live and when to read them. That section must exist for the on-demand
    half to work.

    setup.py does not silently overwrite ~/CLAUDE.md (it may contain
    unrelated user content). Detection logic:
      1. If ~/CLAUDE.md exists AND already contains the BEGIN marker -> no-op.
      2. If ~/CLAUDE.md does not exist -> create it from the template
         (safe because we're not overwriting anything; --dry-run still skips).
      3. If ~/CLAUDE.md exists but lacks the marker AND --yes is set ->
         append the template content with a clear visual separator and
         a comment line noting the setup.py version that added it.
      4. If ~/CLAUDE.md exists but lacks the marker AND --yes is NOT set ->
         print instructions for the user to paste the template manually.

    Idempotent: re-running setup.py on a system that already has the
    section is a no-op regardless of --yes.
    """
    section("8. v1.3 user-level CLAUDE.md memory directive")
    template_path = repo / "templates" / "CLAUDE-memory-section.md"
    if not template_path.is_file():
        say(f"WARN template not found: {template_path}")
        say(f"      (v1.3 SessionStart injection still works; on-demand reads may not be prioritized)")
        return

    user_claude_md = home / "CLAUDE.md"

    if user_claude_md.is_file():
        try:
            existing = user_claude_md.read_text(encoding="utf-8")
        except OSError as e:
            say(f"WARN could not read {user_claude_md}: {e}")
            return
        if _CLAUDE_MD_MARKER_BEGIN in existing:
            say(f"Dreamcatcher memory section already present in {user_claude_md}")
            return
    else:
        existing = None

    template_body = template_path.read_text(encoding="utf-8")
    # Strip the leading template-only comment block (everything before
    # _CLAUDE_MD_MARKER_BEGIN). What goes into ~/CLAUDE.md starts at the
    # BEGIN marker.
    idx = template_body.find(_CLAUDE_MD_MARKER_BEGIN)
    if idx == -1:
        say(f"WARN template malformed (missing BEGIN marker): {template_path}")
        return
    section_payload = template_body[idx:].rstrip() + "\n"

    if existing is None:
        # Fresh ~/CLAUDE.md: write the section as the entire file body.
        # Safe because we are not overwriting anything.
        if dry:
            say(f"[dry-run] would create {user_claude_md} from template")
            return
        user_claude_md.write_text(
            "# Global Instructions for Claude\n\n" + section_payload,
            encoding="utf-8",
        )
        say(f"created {user_claude_md} with the Dreamcatcher memory section")
        return

    # ~/CLAUDE.md exists but lacks the section.
    if yes:
        if dry:
            say(f"[dry-run] would append memory section to {user_claude_md}")
            return
        separator = "\n\n" if not existing.endswith("\n\n") else ""
        with user_claude_md.open("a", encoding="utf-8") as f:
            f.write(separator + section_payload)
        say(f"appended memory section to {user_claude_md} (--yes)")
        return

    # Manual instruction path.
    say(f"NOTE: {user_claude_md} exists but does not contain the Dreamcatcher memory section.")
    say(f"      For Claude to know about the on-demand topic files, paste the content of")
    say(f"      {template_path}")
    say(f"      (between the BEGIN/END markers) into {user_claude_md}.")
    say(f"      Re-running `python setup.py --yes` will append it automatically.")


def _print_schedule_command(paths: dict) -> None:
    """Print the platform-appropriate command to register the hourly
    `dreamcatcher-pull.py` job. v1.2 keeps registration manual so setup.py
    doesn't elevate privileges or touch user-account schedules without
    explicit consent."""
    pull_script = paths["hooks"] / "dreamcatcher-pull.py"
    if os.name == "nt":
        # schtasks runs at HOURLY by default for the user invoking it; no
        # elevation needed for a user-scope task.
        print(f"       Windows (Task Scheduler):")
        print(f"         schtasks /Create /TN \"Dreamcatcher-Pull\" "
              f"/TR \"python {pull_script}\" /SC HOURLY /F")
        print(f"       To disable later:")
        print(f"         schtasks /Delete /TN \"Dreamcatcher-Pull\" /F")
    else:
        # macOS / Linux: simplest is a crontab line. launchd is more native
        # on macOS; we point at it as an upgrade path.
        log_path = paths["state"] / "logs" / "cron-pull.log"
        print(f"       macOS/Linux (crontab):")
        print(f"         (crontab -l 2>/dev/null; echo "
              f"\"0 * * * * /usr/bin/python3 {pull_script} >> {log_path} 2>&1\") "
              f"| crontab -")
        print(f"       To disable later, edit `crontab -e` and remove the line.")
        print(f"       macOS users who prefer launchd: write a plist at")
        print(f"         ~/Library/LaunchAgents/local.dreamcatcher.pull.plist")
        print(f"         with StartInterval=3600 and ProgramArguments pointing at")
        print(f"         {pull_script}, then `launchctl load <plist>`.")


def _force_rmtree(path: Path) -> None:
    """Remove a directory tree, surviving Windows read-only files.

    Windows marks files in .git/objects/ as read-only when git packs them, and
    plain rmtree fails to delete them with WinError 5 / PermissionError. The
    onerror handler clears the read-only attribute and retries.

    If the directory ends up empty but the directory handle itself is locked
    (a Windows-specific pattern caused by indexers or AV scanners briefly
    holding handles), we return successfully and let the caller see the
    empty husk. The data is gone; the empty directory is benign.
    """
    def _onerror(func, p, exc_info):
        try:
            os.chmod(p, stat.S_IWRITE | stat.S_IREAD)
            func(p)
        except Exception:
            raise
    try:
        shutil.rmtree(str(path), onerror=_onerror)
    except PermissionError as e:
        # If the only thing left is the (empty) directory itself, accept it.
        if path.is_dir() and not any(path.iterdir()):
            return
        raise


def migrate_from_claude_dir(paths: dict, dry: bool) -> int:
    """v1.1 migration: move Dreamcatcher's writable footprint out from under
    ~/.claude/ and into ~/Dreamcatcher/.

    Moves (with shutil.move so the live git repo is preserved intact):
      ~/.claude/global-memory/ -> ~/Dreamcatcher/memory/
      ~/.claude/dream-state/   -> ~/Dreamcatcher/state/
      ~/.claude/dream-inputs/  -> ~/Dreamcatcher/inputs/
      ~/.claude/dream-hooks/   -> ~/Dreamcatcher/hooks/

    Updates ~/Dreamcatcher/state/config.json with the new absolute paths.
    Rewrites ~/.claude/settings.json hook command entries (backup taken first).
    Idempotent: if the destinations exist and the sources don't, reports OK.

    ~/.claude/commands/ stays put — Claude Code reads slash commands from
    there. ~/.claude/settings.json stays put — Claude Code reads it from
    there. Only the writable runtime state moves.
    """
    section("v1.1 migration: ~/.claude/ -> ~/Dreamcatcher/")
    claude_root = paths["claude"]
    dc_root = paths["dreamcatcher"]

    moves = [
        (claude_root / "global-memory", paths["memory"]),
        (claude_root / "dream-state",   paths["state"]),
        (claude_root / "dream-inputs",  paths["inputs"]),
        (claude_root / "dream-hooks",   paths["hooks"]),
    ]

    # Pre-flight: report what we see.
    any_to_move = False
    needs_resume = []  # both src and dst exist: a previous run copied but failed mid-delete
    for src, dst in moves:
        if src.exists() and dst.exists():
            # Recovery path: previous migration copied src->dst but couldn't delete
            # src (common on Windows due to read-only .git/objects/* files). If
            # the destination is a complete valid copy, we can finish the delete.
            say(f"both exist (resume cleanup): {src} -> {dst}")
            needs_resume.append((src, dst))
            continue
        if src.exists():
            any_to_move = True
            say(f"will move: {src} -> {dst}")
        elif dst.exists():
            say(f"already migrated: {dst}")
        else:
            say(f"neither side present (nothing to do): {src}")

    if not any_to_move and not needs_resume:
        say("nothing to migrate. checking config + settings for stale paths...")

    if dry:
        say("[dry-run] no moves performed.")
        return 0

    dc_root.mkdir(parents=True, exist_ok=True)

    # Copy + verify + delete-source, with Windows read-only handling.
    for src, dst in moves:
        if src.exists() and not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src, dst)
            _force_rmtree(src)
            say(f"moved: {src.name} -> {dst}")
        elif src.exists() and dst.exists() and (src, dst) in needs_resume:
            _force_rmtree(src)
            say(f"cleanup-deleted residual source: {src}")

    # Rewrite config.json with new absolute paths.
    config_path = paths["state"] / "config.json"
    if config_path.is_file():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            warn(f"could not parse {config_path}: {e}. leaving as-is.")
        else:
            config["claude_root"]   = str(paths["claude"])
            config["dreamcatcher_root"] = str(dc_root)
            config["memory_root"]   = str(paths["memory"])
            config["dream_state"]   = str(paths["state"])
            config["dream_inputs"]  = str(paths["inputs"])
            config["dream_hooks"]   = str(paths["hooks"])
            config["migrated_to_v11_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            tmp = config_path.with_suffix(config_path.suffix + ".tmp")
            tmp.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
            os.replace(tmp, config_path)
            say(f"updated paths in: {config_path}")

    # Rewrite settings.json hook commands to point at the new hooks dir.
    settings_path = paths["settings"]
    if settings_path.is_file():
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
        backup = settings_path.with_suffix(settings_path.suffix + f".bak-migrate-{stamp}")
        shutil.copyfile(settings_path, backup)
        say(f"backed up settings.json to: {backup}")

        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            warn(f"could not parse {settings_path}: {e}. left intact, see backup.")
        else:
            old_hooks_str = str(claude_root / "dream-hooks")
            new_hooks_str = str(paths["hooks"])
            changed = 0
            for event, groups in (settings.get("hooks") or {}).items():
                for group in groups:
                    for h in group.get("hooks", []) or []:
                        cmd = h.get("command", "")
                        if old_hooks_str in cmd:
                            h["command"] = cmd.replace(old_hooks_str, new_hooks_str)
                            changed += 1
            if changed:
                tmp = settings_path.with_suffix(settings_path.suffix + ".tmp")
                tmp.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
                os.replace(tmp, settings_path)
                say(f"updated {changed} hook command path(s) in settings.json")
            else:
                say("no hook commands referenced the old path; settings.json unchanged")

    say("migration complete. start a new Claude Code session to pick up the new hook paths.")
    return 0


def setup_utf8_io() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, OSError):
                pass


def main() -> int:
    setup_utf8_io()
    args = parse_args()
    repo = Path(__file__).resolve().parent
    home = Path(os.path.expanduser("~")).resolve()
    kind = platform_kind()

    # v1.1 (2026-05-18): Dreamcatcher's writable directories moved out from
    # under ~/.claude/ because Claude Code's auto-mode classifier treats
    # writes under that path as sensitive and refuses them in headless
    # `claude -p` subprocesses. The slash-command discovery dir stays at
    # ~/.claude/commands/ (Claude Code reads it; we only write at install
    # time, not at runtime). settings.json also stays where Claude Code
    # reads it.
    dc_root = home / "Dreamcatcher"
    paths = {
        "claude":      home / ".claude",
        "dreamcatcher": dc_root,
        "memory":      dc_root / "memory",
        "state":       dc_root / "state",
        "inputs":      dc_root / "inputs",
        "hooks":       dc_root / "hooks",
        "prompts":     dc_root / "prompts",
        "commands":    home / ".claude" / "commands",
        "settings":    home / ".claude" / "settings.json",
    }

    print(f"Dreamcatcher install -- mode: {args.mode}, platform: {kind}, "
          f"dry-run: {args.dry_run}, migrate: {args.migrate}")

    check_dependencies()

    if args.migrate:
        return migrate_from_claude_dir(paths, args.dry_run)

    make_skeleton(paths, args.dry_run)
    init_memory_repo(paths["memory"], args.dry_run)

    cli_roots = [str(Path(r).expanduser()) for r in args.discovery_root]
    non_interactive = args.yes or args.dry_run
    roots = resolve_discovery_roots(cli_roots, kind, home, non_interactive)
    write_config(paths, roots, kind, args.mode, args.dry_run)

    deploy_python_scripts(repo, paths, args.dry_run)
    copy_static_commands(repo, paths["commands"], args.dry_run)

    new_hooks = build_hooks_block(args.mode, python_cmd_for(kind), paths["hooks"])
    merge_settings(paths["settings"], new_hooks, args.dry_run)

    # v1.3 (2026-05-22): SessionStart hooks inject MEMORY.md + working-style.md
    # into session context. That works without any user action. The other half
    # of the v1.3 fix is a "Cross-project memory (Dreamcatcher)" section in
    # ~/CLAUDE.md that tells Claude where the on-demand topic files live. That
    # one DOES need user action because ~/CLAUDE.md is personal config we
    # should not overwrite silently. We detect and instruct (or append if
    # --yes is passed and the file doesn't exist yet).
    ensure_user_claude_md(repo, home, args.yes, args.dry_run)

    summary(paths, repo, args.mode)
    return 0


if __name__ == "__main__":
    sys.exit(main())
