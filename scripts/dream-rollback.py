#!/usr/bin/env python3
"""dream-rollback.py - revert a dream commit AND roll back the reverie as one op.

Why both: the reverie lives outside git on purpose (per-machine state).
Reverting the bad commit without rolling back the reverie leaves the next
nightly dream skipping the very transcripts that produced the bad
consolidation -- and you've lost the chance to redo them with a tweaked
prompt. The reverie piece is non-optional.

Usage:
  dream-rollback.py                       # interactive: pick a recent dream
  dream-rollback.py <sha>                 # revert this specific commit
  dream-rollback.py --run <run-id>        # v1.2: revert the auto-promote commit
                                          # for this dream run; matches against
                                          # the parseable `run-id:` line in
                                          # structured commit messages.
  dream-rollback.py --list                # list recent dream commits, exit
  dream-rollback.py --keep-reverie [sha]
                                          # revert but DON'T roll back the
                                          # reverie (rare; the consolidation
                                          # was wrong but the source
                                          # transcripts are no longer worth
                                          # re-mining)
"""

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_here = Path(__file__).resolve().parent
for _cand in (_here, _here / "hooks"):
    if (_cand / "_dream_common.py").is_file():
        sys.path.insert(0, str(_cand))
        break
import _dream_common as dc  # noqa: E402

dc.setup_utf8_io()

_DREAM_SUBJECT = re.compile(r"^(dream:|bootstrap:)")


def die(msg: str, code: int = 1) -> None:
    print(f"dream-rollback: {msg}", file=sys.stderr)
    sys.exit(code)


def log_to_file(memory_state: Path, msg: str) -> None:
    try:
        log_dir = memory_state / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        day = datetime.now().strftime("%Y-%m-%d")
        path = log_dir / f"rollback-{day}.log"
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with path.open("a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except OSError:
        pass


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


def has_remote(memory: Path) -> bool:
    r = subprocess.run(["git", "remote"], cwd=memory,
                       capture_output=True, text=True, check=False)
    return bool(r.stdout.strip())


def git_run(args: "list[str]", cwd: Path,
            capture: bool = False, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, check=check,
                          capture_output=capture, text=capture)


def tree_clean(memory: Path) -> bool:
    a = subprocess.run(["git", "diff", "--quiet"], cwd=memory, check=False)
    b = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=memory, check=False)
    return a.returncode == 0 and b.returncode == 0


def list_dream_commits(memory: Path, limit: int = 20) -> "list[tuple[str, str, str]]":
    r = git_run(
        ["log", f"-n{limit}", "--format=%h\t%ai\t%s",
         "--grep=^dream:", "--grep=^bootstrap:"],
        memory, capture=True,
    )
    out: "list[tuple[str, str, str]]" = []
    for line in (r.stdout or "").splitlines():
        parts = line.split("\t", 2)
        if len(parts) == 3:
            out.append((parts[0], parts[1], parts[2]))
    return out


def commit_subject(memory: Path, sha: str) -> str:
    r = git_run(["log", "-1", "--format=%s", sha], memory, capture=True)
    return (r.stdout or "").strip()


def commit_date(memory: Path, sha: str) -> str:
    r = git_run(["log", "-1", "--format=%ai", sha], memory, capture=True)
    return (r.stdout or "").strip()


def commit_date_iso_short(memory: Path, sha: str) -> str:
    r = git_run(["log", "-1", "--format=%ad", "--date=format:%Y-%m-%d", sha],
                memory, capture=True)
    return (r.stdout or "").strip()


def resolve_run_id(memory: Path, run_id: str) -> str:
    """Find the commit SHA that auto-promoted the given run-id.

    v1.2 auto-promote commits include `run-id: <run-id>` in the structured
    commit message body. We grep for that exact line. Returns the SHA or ''
    if no matching commit is found.
    """
    r = git_run(
        ["log", "-n50", "--all", "--format=%H",
         f"--grep=^run-id: {re.escape(run_id)}$",
         "--extended-regexp"],
        memory, capture=True,
    )
    out = (r.stdout or "").strip().splitlines()
    return out[0] if out else ""


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Revert a dream commit and roll back the reverie.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--keep-reverie", action="store_true",
                   help="Revert the commit, but leave the reverie alone.")
    p.add_argument("--list", action="store_true",
                   help="List recent dream/bootstrap commits and exit.")
    p.add_argument("--run", dest="run_id", default=None,
                   help="v1.2: revert the auto-promote commit for this run-id "
                        "(structured commit messages carry a parseable "
                        "`run-id: <run-id>` line).")
    p.add_argument("sha", nargs="?",
                   help="Specific commit SHA to revert (or pick interactively).")
    return p.parse_args()


def restore_reverie_or_prompt(
    state_root: Path, sha: str, dream_date: str,
) -> None:
    backup_dir = state_root / "reverie-backups"
    reverie_file = state_root / "reverie.json"

    candidates = [backup_dir / f"reverie-{dream_date}.json"]
    if backup_dir.is_dir():
        candidates.extend(sorted(backup_dir.glob(f"reverie-{dream_date}T*.json")))

    restore_from = next((c for c in candidates if c.is_file()), None)

    if restore_from:
        print()
        print("Found reverie backup from before the dream:")
        print(f"  {restore_from}")
        if confirm("Restore reverie.json from this backup?", default_yes=True):
            if reverie_file.is_file():
                stash_ts = datetime.now().strftime("%Y-%m-%dT%H%M%S")
                stash = backup_dir / f"reverie-pre-rollback-{stash_ts}.json"
                backup_dir.mkdir(parents=True, exist_ok=True)
                stash.write_bytes(reverie_file.read_bytes())
                log_to_file(state_root, f"Stashed current reverie to {stash}")
            reverie_file.parent.mkdir(parents=True, exist_ok=True)
            reverie_file.write_bytes(restore_from.read_bytes())
            log_to_file(state_root, f"Restored reverie from {restore_from}")
            print("Reverie restored.")
        else:
            log_to_file(state_root, f"User declined reverie restore from {restore_from}")
            print("Reverie unchanged. The next nightly dream will skip the transcripts")
            print(f"that produced {sha} -- you may want to manually edit {reverie_file}.")
        return

    log_to_file(state_root, f"No reverie backup found for {dream_date}")
    print()
    print(f"No reverie backup found at {backup_dir}/reverie-{dream_date}*.json.")
    print("Manual rollback required.")
    print()
    print("Current reverie.json:")
    if reverie_file.is_file():
        print(reverie_file.read_text(encoding="utf-8", errors="replace"))
    else:
        print("  (reverie.json does not exist)")
    print()
    print("Edit it now to reflect the state from before the dream, or skip with")
    print("Ctrl+C and re-run with --keep-reverie.")
    if confirm("Open reverie.json in $EDITOR?", default_yes=True):
        subprocess.run(editor_command() + [str(reverie_file)], check=False)
        log_to_file(state_root, "User manually edited reverie.json")


def main() -> int:
    args = parse_args()

    memory = dc.memory_root()
    state_root = dc.state_root()

    if not memory.is_dir():
        die(f"global memory root not found: {memory}")
    if not (memory / ".git").is_dir():
        die(f"{memory} is not a git repo")

    if args.list:
        for sha, date, subject in list_dream_commits(memory):
            print(f"{sha}  {date}  {subject}")
        return 0

    if not tree_clean(memory):
        die(f"uncommitted changes in {memory} -- clean up before rolling back")

    sha = args.sha
    if args.run_id:
        if sha:
            die("pass either --run <run-id> or a sha, not both")
        sha = resolve_run_id(memory, args.run_id)
        if not sha:
            die(f"no commit found for run-id: {args.run_id}")
        print(f"Resolved --run {args.run_id} to commit {sha[:12]}")
    if not sha:
        commits = list_dream_commits(memory)
        if not commits:
            die("no dream commits found in last 20 -- pass a sha explicitly if you know it")
        print("Recent dream/bootstrap commits:")
        print()
        for i, (s, d, subj) in enumerate(commits):
            print(f"  [{i:>2}] {s}  {d}  {subj}")
        print()
        try:
            idx_raw = input("Select index to roll back (or empty to cancel): ").strip()
        except EOFError:
            idx_raw = ""
        if not idx_raw:
            die("cancelled")
        if not idx_raw.isdigit():
            die(f"invalid index: {idx_raw}")
        idx = int(idx_raw)
        if idx >= len(commits):
            die(f"index out of range: {idx}")
        sha = commits[idx][0]

    rev = git_run(["rev-parse", "--verify", sha], memory, capture=True)
    if rev.returncode != 0:
        die(f"not a valid commit: {sha}")
    anc = git_run(["merge-base", "--is-ancestor", sha, "HEAD"], memory)
    if anc.returncode != 0:
        die(f"{sha} is not in current branch history")

    subject = commit_subject(memory, sha)
    cdate = commit_date(memory, sha)

    if not _DREAM_SUBJECT.match(subject):
        print(f"Warning: {sha} does not look like a dream commit:")
        print(f"  {subject}")
        if not confirm("Proceed anyway?"):
            die("cancelled")

    print()
    print("About to roll back:")
    print(f"  commit:  {sha}")
    print(f"  subject: {subject}")
    print(f"  date:    {cdate}")
    print()
    print("Effects:")
    print(f"  1. git revert {sha} (forward-moving correction)")
    if not args.keep_reverie:
        print("  2. roll reverie.json BACK to its state before the dream that produced")
        print(f"     {sha} so the next nightly dream re-reads those transcripts with")
        print("     the (presumably tweaked) prompt")
    else:
        print("  2. reverie.json NOT rolled back (--keep-reverie passed)")
    print()
    print("We do NOT force-push or rewrite history. With manual sync, the laptop")
    print("imports forward-moving changes via /dream-import; a revert is what makes")
    print("the correction safe across the topology.")
    print()
    if not confirm("Proceed?"):
        die("cancelled")

    log_to_file(state_root, f"Starting rollback of {sha}: {subject}")

    revert = subprocess.run(["git", "revert", "--no-edit", sha], cwd=memory, check=False)
    if revert.returncode != 0:
        log_to_file(state_root, "git revert produced conflicts; left in conflicted state")
        print(file=sys.stderr)
        print("git revert produced conflicts. The repo is now in a conflicted state.",
              file=sys.stderr)
        print(f"This usually means a later dream commit touched the same lines as {sha}.",
              file=sys.stderr)
        print("Resolve conflicts manually, then:", file=sys.stderr)
        print("", file=sys.stderr)
        print("  git revert --continue", file=sys.stderr)
        print("  # then re-run dream-rollback.py with --keep-reverie and the new sha",
              file=sys.stderr)
        print("  # OR manually roll back reverie.json if you do want to re-mine",
              file=sys.stderr)
        print("", file=sys.stderr)
        print("If you'd rather start over:", file=sys.stderr)
        print("", file=sys.stderr)
        print("  git revert --abort", file=sys.stderr)
        return 1

    head = git_run(["rev-parse", "HEAD"], memory, capture=True)
    revert_sha = (head.stdout or "").strip()
    log_to_file(state_root, f"Created revert commit {revert_sha}")

    if args.keep_reverie:
        log_to_file(state_root, "Skipped reverie rollback (--keep-reverie)")
        print()
        print("Revert complete. Reverie unchanged.")
        if has_remote(memory):
            print("Pushing to origin...")
            subprocess.run(["git", "push"], cwd=memory, check=False)
            log_to_file(state_root, f"Pushed {revert_sha} to origin")
        else:
            print("(no git remote configured; revert is local. Use /dream-export to share.)")
        print("Done.")
        return 0

    dream_date = commit_date_iso_short(memory, sha)
    restore_reverie_or_prompt(state_root, sha, dream_date)

    print()
    if has_remote(memory):
        print("Pushing revert to origin...")
        subprocess.run(["git", "push"], cwd=memory, check=False)
        log_to_file(state_root, f"Pushed {revert_sha} to origin")
    else:
        print("(no git remote configured; revert is local. Use /dream-export to share.)")

    print()
    print("Rollback complete.")
    print(f"  Reverted: {sha}")
    print(f"  New head: {revert_sha}")
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"  Log:      {state_root / 'logs' / f'rollback-{today}.log'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
