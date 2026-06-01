#!/usr/bin/env python3
"""promote.py - review and promote a candidate dream into ~/.claude/global-memory/.

Usage:
  promote.py                    # promote the newest candidate folder
  promote.py <candidate-name>   # promote a specific candidate folder
  promote.py --list             # list available candidates and exit
  promote.py --dry-run [name]   # show what would change, don't write

Lifecycle:
  1. /dream-global (or /dream-bootstrap) writes to .candidate/<name>/.
  2. promote.py diffs candidate against live, opens BOOTSTRAP-NOTES first if
     present, then walks files one at a time.
  3. On approval, applies the candidate, commits, and pushes if a remote is
     configured (the new manual-sync default tolerates no-remote installs).
  4. Archives any scratch files the dream report flagged for archival.
"""

import argparse
import difflib
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Locate _dream_common.py whether we're running from the repo (development)
# or from ~/.claude/dream-hooks/ after setup.py deploys us alongside it.
_here = Path(__file__).resolve().parent
for _cand in (_here, _here / "hooks"):
    if (_cand / "_dream_common.py").is_file():
        sys.path.insert(0, str(_cand))
        break
import _dream_common as dc  # noqa: E402

dc.setup_utf8_io()

SKIP_FILES = {"BOOTSTRAP-NOTES.md", "NOTES.md", "archive-list.txt"}


def die(msg: str, code: int = 1) -> None:
    print(f"promote.py: {msg}", file=sys.stderr)
    sys.exit(code)


def list_candidates(candidate_root: Path) -> "list[str]":
    if not candidate_root.is_dir():
        return []
    return sorted(d.name for d in candidate_root.iterdir() if d.is_dir())


def confirm(prompt: str, default_yes: bool = False) -> bool:
    suffix = " [Y/n] " if default_yes else " [y/N] "
    try:
        ans = input(prompt + suffix).strip().lower()
    except EOFError:
        return False
    if not ans:
        return default_yes
    return ans in ("y", "yes")


def editor_command() -> "list[str]":
    env = os.environ.get("EDITOR")
    if env:
        return env.split()
    return ["notepad"] if os.name == "nt" else ["vi"]


def open_in_editor(path: Path) -> None:
    subprocess.run(editor_command() + [str(path)], check=False)


def show_diff(live: Path, candidate: Path, rel: str) -> None:
    print(f"----- {rel} -----")
    if not live.is_file():
        print("(new file)")
        text = candidate.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        for line in lines[:40]:
            print(line)
        if len(lines) > 40:
            print("... (truncated; open in editor for full)")
        print()
        return
    live_lines = live.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    cand_lines = candidate.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    diff = difflib.unified_diff(
        live_lines, cand_lines, fromfile=str(live), tofile=str(candidate),
    )
    sys.stdout.writelines(diff)
    print()


def has_remote(memory: Path) -> bool:
    r = subprocess.run(["git", "remote"], cwd=memory,
                       capture_output=True, text=True, check=False)
    return bool(r.stdout.strip())


def git(args: "list[str]", cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, check=check)


def git_has_staged_changes(cwd: Path) -> bool:
    r = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=cwd, check=False)
    return r.returncode != 0


def push_if_remote(memory: Path) -> None:
    if not has_remote(memory):
        print("(no git remote configured; commit is local. Use /dream-export to share.)")
        return
    r = subprocess.run(["git", "push"], cwd=memory, check=False)
    if r.returncode != 0:
        print("WARN: git push failed; commit is local. Push manually if needed.")


def walk_candidate_files(candidate_dir: Path) -> "list[tuple[Path, str]]":
    """Walk a candidate folder for promotion. Rejects symlinks and paths that
    resolve outside the candidate root (defense in depth against a candidate
    folder planted with `customer-context.md -> /etc/passwd` symlinks).
    """
    pairs: "list[tuple[Path, str]]" = []
    root_resolved = candidate_dir.resolve()
    for f in sorted(candidate_dir.rglob("*")):
        if f.is_symlink():
            continue
        if not f.is_file():
            continue
        rel = f.relative_to(candidate_dir).as_posix()
        if rel in SKIP_FILES:
            continue
        try:
            if not f.resolve().is_relative_to(root_resolved):
                continue
        except OSError:
            continue
        pairs.append((f, rel))
    return pairs


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Promote a candidate dream into global memory.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--list", action="store_true",
                   help="List available candidates and exit.")
    p.add_argument("--dry-run", action="store_true",
                   help="Show what would change; touch nothing.")
    p.add_argument("candidate_name", nargs="?",
                   help="Candidate folder name. Default: newest.")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    memory = dc.memory_root()
    if not memory.is_dir():
        die(f"global memory root not found: {memory}")
    if not (memory / ".git").is_dir():
        die(f"{memory} is not a git repo")

    candidate_root = memory / ".candidate"
    if args.list:
        for name in list_candidates(candidate_root):
            print(name)
        return 0

    # v1.2: pre-pull before touching the live store. If the other machine pushed,
    # we want to rebase our local candidate against its work before applying.
    # `--list` skipped this above because it doesn't mutate anything.
    if not args.dry_run:
        pull = dc.prepull_memory()
        if pull["status"] == "not-fast-forward":
            die(pull["message"], code=2)
        if pull["status"] == "error":
            die(pull["message"])
        if pull["status"] == "ok" and pull["message"] != "memory already up to date":
            print(f"(prepull: {pull['message']})")

    if not candidate_root.is_dir():
        die(f"no candidate folder: {candidate_root}")

    candidate_name = args.candidate_name
    if not candidate_name:
        existing = list_candidates(candidate_root)
        if not existing:
            die(f"no candidates in {candidate_root}")
        candidate_name = existing[-1]

    candidate_dir = candidate_root / candidate_name
    if not candidate_dir.is_dir():
        die(f"candidate not found: {candidate_dir}")

    is_bootstrap = candidate_name.startswith("bootstrap-")

    print(f"Promoting candidate: {candidate_name}")
    print(f"  source:      {candidate_dir}")
    print(f"  destination: {memory}")
    if is_bootstrap:
        print("  bootstrap:   yes (heavier review expected)")
    if args.dry_run:
        print("  mode:        dry run")
    print()

    notes_file = candidate_dir / "BOOTSTRAP-NOTES.md"
    if notes_file.is_file():
        print("BOOTSTRAP-NOTES.md found -- opening for review first.")
        open_in_editor(notes_file)
        if not confirm("Continue with promotion?"):
            die("aborted at notes review")

    pairs = walk_candidate_files(candidate_dir)
    for cand, rel in pairs:
        show_diff(memory / rel, cand, rel)

    if args.dry_run:
        print("Dry run complete. No changes applied.")
        return 0

    if not confirm("Apply candidate to live store?"):
        die("aborted at apply prompt")

    # The dream prompt is explicit that files unchanged this run do NOT appear
    # in the candidate folder, so an overlay copy is correct (not a mirror).
    for cand, rel in pairs:
        live = memory / rel
        live.parent.mkdir(parents=True, exist_ok=True)
        # follow_symlinks=False: the walker already rejects symlinks, but
        # this is defense in depth against any path that slipped through.
        shutil.copyfile(cand, live, follow_symlinks=False)

    if (candidate_dir / "SUMMARY.txt").is_file():
        commit_msg = (candidate_dir / "SUMMARY.txt").read_text(
            encoding="utf-8").splitlines()[0]
    elif is_bootstrap:
        commit_msg = "bootstrap: initial global-memory seed"
    else:
        commit_msg = f"dream: {candidate_name}"

    git(["add", "-A"], memory)
    if git_has_staged_changes(memory):
        git(["commit", "-m", commit_msg], memory)
        push_if_remote(memory)
    else:
        print("No changes to commit. Skipping commit and push.")

    archive_list = candidate_dir / "archive-list.txt"
    if archive_list.is_file():
        scratch_root = memory / "scratch"
        scratch_archive = scratch_root / ".archived"
        scratch_archive.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        archived_any = False
        # archive-list.txt entries are paths relative to scratch_root. A
        # malicious or buggy candidate could write something like
        # "../../../.ssh/id_ed25519" and have it shutil.move'd into the
        # memory repo (then committed and pushed). Containment: reject any
        # line that traverses outside scratch_root, or contains a drive
        # letter, or starts with a separator.
        scratch_root_resolved = scratch_root.resolve()
        for raw_line in archive_list.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            # Cheap pre-filter: reject obvious traversal markers and any
            # absolute-path prefix before touching the filesystem.
            if (".." in line.split("/")
                    or ".." in line.split("\\")
                    or line.startswith(("/", "\\"))
                    or (len(line) >= 2 and line[1] == ":")):
                print(f"Skipped suspicious archive-list entry: {line}",
                      file=sys.stderr)
                continue
            src = scratch_root / line
            # Resolved containment check: src must live under scratch_root.
            try:
                src_resolved = src.resolve()
            except OSError:
                continue
            try:
                src_resolved.relative_to(scratch_root_resolved)
            except ValueError:
                print(f"Skipped archive-list entry escaping scratch/: {line}",
                      file=sys.stderr)
                continue
            if not src.is_file():
                continue
            if src.is_symlink():
                print(f"Skipped symlink in archive-list entry: {line}",
                      file=sys.stderr)
                continue
            dst = scratch_archive / f"{today}-{Path(line).name}"
            shutil.move(str(src), str(dst))
            print(f"Archived: {line} -> .archived/{dst.name}")
            archived_any = True
        if archived_any:
            scratch_dirty = subprocess.run(
                ["git", "diff", "--quiet", "--", "scratch/"],
                cwd=memory, check=False,
            )
            if scratch_dirty.returncode != 0:
                git(["add", "-A", "scratch/"], memory)
                git(["commit", "-m", f"scratch: archive after {candidate_name}"], memory)
                push_if_remote(memory)

    shutil.rmtree(candidate_dir)

    print("Promotion complete.")
    if is_bootstrap:
        print("Bootstrap: seed reverie.json before the first nightly dream "
              "(see the /dream-bootstrap flow).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
