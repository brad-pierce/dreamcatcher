"""Shared helpers for dream-hooks. Stdlib only.

This file lives in hooks/ alongside the hook scripts and is deployed to
~/.claude/dream-hooks/ by setup.py. The hook scripts import it as
`import _dream_common as dc`; Python adds the script's directory to sys.path
automatically when a script is invoked, so the import works without a package.

Path resolution precedence (highest first):
    1. environment variable override (DREAM_STATE_ROOT, GLOBAL_MEMORY_ROOT, etc.)
    2. config.json written by setup.py
    3. ~/.claude/<default subdir>
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def home() -> Path:
    return Path(os.path.expanduser("~"))


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


_CONFIG_CACHE: "dict | None" = None


def _default_state_root() -> Path:
    # v1.1 (2026-05-18): Dreamcatcher's writable footprint moved out from
    # under ~/.claude/ because Claude Code's auto-mode classifier flags writes
    # under that directory as sensitive and refuses them in headless `claude -p`
    # subprocesses (which is how the nightly schedule fires). New home:
    # ~/Dreamcatcher/{memory,state,inputs,hooks}/. Pre-v1.1 installs are
    # detected and migrated by `setup.py --migrate`.
    return home() / "Dreamcatcher" / "state"


def _config_path() -> Path:
    env = os.environ.get("DREAM_STATE_ROOT")
    base = Path(env) if env else _default_state_root()
    return base / "config.json"


def load_config() -> dict:
    """Read ~/.claude/dream-state/config.json (or env-overridden location).

    Returns {} on missing or unparseable config; hooks should always tolerate
    a missing config so they remain useful before setup.py has run.
    """
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE
    path = _config_path()
    if not path.is_file():
        _CONFIG_CACHE = {}
        return _CONFIG_CACHE
    try:
        _CONFIG_CACHE = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        _CONFIG_CACHE = {}
    return _CONFIG_CACHE


def _resolved_path(env_var: str, config_key: str, default_subpath: str) -> Path:
    env = os.environ.get(env_var)
    if env:
        return Path(env)
    cfg = load_config()
    if cfg.get(config_key):
        return Path(cfg[config_key])
    return home() / ".claude" / default_subpath


def _resolved_v11(env_var: str, config_key: str, sub: str) -> Path:
    """v1.1 resolver: defaults under ~/Dreamcatcher/<sub>/ instead of ~/.claude/<sub>/.

    env var still wins; config.json value still wins over default. Existing
    installs that have config.json pointing at ~/.claude/* keep working until
    migrated.
    """
    env = os.environ.get(env_var)
    if env:
        return Path(env)
    cfg = load_config()
    if cfg.get(config_key):
        return Path(cfg[config_key])
    return home() / "Dreamcatcher" / sub


def state_root() -> Path:
    return _resolved_v11("DREAM_STATE_ROOT", "dream_state", "state")


def memory_root() -> Path:
    return _resolved_v11("GLOBAL_MEMORY_ROOT", "memory_root", "memory")


def inputs_root() -> Path:
    return _resolved_v11("DREAM_INPUTS_ROOT", "dream_inputs", "inputs")


def hooks_root() -> Path:
    return _resolved_v11("DREAM_HOOKS_ROOT", "dream_hooks", "hooks")


def log_dir() -> Path:
    return state_root() / "logs"


def export_dir() -> Path:
    """Where /dream-export drops bundles and /dream-import reads them from.

    Default is ~/Downloads, which exists on both Windows and macOS. Override
    via DREAM_EXPORT_DIR env or `export_dir` key in config.json.
    """
    env = os.environ.get("DREAM_EXPORT_DIR")
    if env:
        return Path(env)
    cfg = load_config()
    if cfg.get("export_dir"):
        return Path(cfg["export_dir"])
    return home() / "Downloads"


def logger(name: str):
    """Return a log function writing to logs/hook-<name>-YYYY-MM-DD.log.

    Logging failures are swallowed -- the hook must never fail because the
    log file couldn't be written.
    """
    def _log(msg: str) -> None:
        try:
            d = log_dir()
            d.mkdir(parents=True, exist_ok=True)
            day = datetime.now().strftime("%Y-%m-%d")
            path = d / f"hook-{name}-{day}.log"
            with path.open("a", encoding="utf-8") as f:
                f.write(f"[{utc_now()}] {name}: {msg}\n")
        except Exception:
            pass
    return _log


def emit_memory_priming(stream=None) -> None:
    """Print the always-applicable global memory content for SessionStart hooks.

    v1.3 (2026-05-22): SessionStart hooks emit not just status info but the
    cross-project memory itself, so Claude has the user's preferences and the
    memory index in context from the first message of every session.

    Pre-v1.3, hooks only emitted a 3-line status block; the actual memory
    content sat in `~/Dreamcatcher/memory/` and was never wired to consumption.

    Always-injected (small, stable, always-applicable):
        - MEMORY.md            (~30-line index)
        - working-style.md     (~200 lines of stable preferences)

    Read-on-demand (pointer in the output, content NOT injected):
        - customer-context.md
        - practice-context.md
        - tooling-environment.md
        - active-deliverables.md
        - personal-context.md
        - decisions/*.md

    Total always-on overhead is ~6-8 KB. Heavier topic files stay opt-in so
    short sessions don't pay for context they won't use. The CLAUDE.md
    pointer at the user level tells Claude when to read the other files.

    Silently no-ops on any missing file. Pre-bootstrap installs (no topic
    files yet) emit nothing memory-side, which is correct.
    """
    if stream is None:
        stream = sys.stdout

    memory = memory_root()
    if not memory.is_dir():
        return

    always_inject = [
        ("MEMORY.md", "Cross-project memory index (the topic-file table of contents)"),
        ("working-style.md", "Working style (always-applicable preferences and editorial standards)"),
    ]
    for name, label in always_inject:
        path = memory / name
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        print(file=stream)
        print(f"=== {label} (~/Dreamcatcher/memory/{name}) ===", file=stream)
        print(content.rstrip(), file=stream)

    # Pointer to on-demand files so Claude knows what's available without
    # the cost of loading their content into every session.
    on_demand = [
        ("customer-context.md", "engagement patterns (no customer names by policy)"),
        ("practice-context.md", "your professional practice context: the domain you work in, recurring partners, standards, and tools"),
        ("tooling-environment.md", "dev environment, MCP servers, cloud and deployment conventions, scheduling rules"),
        ("active-deliverables.md", "in-flight projects, deployed tools, recurring deliverables"),
        ("personal-context.md", "location, hobbies, prior background, family"),
        ("decisions/", "dated architecture and strategy decisions worth remembering"),
    ]
    print(file=stream)
    print("=== Other topic files (read from ~/Dreamcatcher/memory/ on demand) ===", file=stream)
    for name, blurb in on_demand:
        path = memory / name
        present = path.is_file() or path.is_dir()
        marker = "" if present else "  (not present yet)"
        print(f"  - {name}{marker} - {blurb}", file=stream)


def prepull_memory(verbose: bool = True) -> dict:
    """Run `git pull --ff-only` on the memory repo before a dream/promote cycle.

    v1.2 (2026-05-19): entry point for bidirectional sync between the user's
    two machines. Both `/dream-global` (via the skill prompt's Phase 0) and
    `promote.py` call this first to ensure they're acting on the latest live
    memory. The hourly `dreamcatcher-pull.py` cron also calls it.

    Returns a dict:
        status: one of 'ok', 'no-repo', 'no-remote', 'not-fast-forward', 'error'
        message: human-readable detail (always populated)
        output: combined stdout+stderr from git (may be empty)

    Caller contract:
        ok / no-repo / no-remote  -> continue (single-machine and pre-bootstrap
            installs hit no-remote/no-repo respectively; both are benign)
        not-fast-forward          -> exit clean with the message; the other
            machine pushed first, and forcing through could lose work. The
            next cycle will pick up the pulled state.
        error                     -> exit non-zero; genuine git/network issue.
    """
    import subprocess

    memory = memory_root()
    if not (memory / ".git").is_dir():
        return {
            "status": "no-repo",
            "message": f"no git repo at {memory} (run setup.py or /dream-bootstrap first)",
            "output": "",
        }

    remote_check = subprocess.run(
        ["git", "remote"],
        cwd=memory, capture_output=True, text=True, check=False,
    )
    if remote_check.returncode != 0 or not remote_check.stdout.strip():
        return {
            "status": "no-remote",
            "message": "memory repo has no remote configured (local-only mode; "
                       "use /dream-export to share with another machine)",
            "output": "",
        }

    pull = subprocess.run(
        ["git", "pull", "--ff-only"],
        cwd=memory, capture_output=True, text=True, check=False,
    )
    combined = (pull.stdout + pull.stderr).strip()

    if pull.returncode == 0:
        lower = combined.lower()
        if "already up to date" in lower or "already up-to-date" in lower:
            return {"status": "ok", "message": "memory already up to date", "output": combined}
        return {"status": "ok", "message": "memory fast-forwarded from remote", "output": combined}

    lower = combined.lower()
    if any(t in lower for t in (
        "not possible to fast-forward",
        "non-fast-forward",
        "diverg",
        "refusing to merge",
        "rejected",
    )):
        return {
            "status": "not-fast-forward",
            "message": "memory has diverged from remote; another machine pushed work "
                       "this side doesn't have. Resolve by running "
                       "`git -C ~/Dreamcatcher/memory pull --rebase` interactively, "
                       "or wait for the next cycle if you trust the other side's edits.",
            "output": combined,
        }

    return {
        "status": "error",
        "message": f"git pull failed: {combined[:400]}",
        "output": combined,
    }


_READ_EVENT_CAP = 10 * 1024 * 1024  # 10 MB; realistic hook events are tiny


def read_event() -> dict:
    """Read Claude Code's hook event JSON from stdin. Returns {} on any failure.

    Bounded to _READ_EVENT_CAP bytes. A runaway upstream (buggy Claude Code
    release, OS-level pipe redirection, malicious upstream) could otherwise
    feed unbounded bytes into a hook, exhausting memory before the hook's
    settings.json timeout fires.
    """
    try:
        raw = sys.stdin.read(_READ_EVENT_CAP + 1)
    except Exception:
        return {}
    if len(raw) > _READ_EVENT_CAP:
        # Successful read at-or-over the cap is suspicious; refuse rather
        # than try to parse a possibly-truncated JSON object.
        return {}
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def setup_utf8_io() -> None:
    """Reconfigure stdout/stderr to UTF-8 with errors='replace'.

    On Windows, default stdout encoding is cp1252, which crashes on unicode
    content (BOMs, em-dashes, etc.) common in memory files. Claude Code reads
    hook stdout as session context; emitting cp1252-mojibake there is worse
    than emitting valid UTF-8. Safe to call multiple times.
    """
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, OSError):
                pass
