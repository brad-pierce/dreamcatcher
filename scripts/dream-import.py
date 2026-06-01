#!/usr/bin/env python3
"""dream-import.py - apply a dream-export bundle to ~/.claude/global-memory/.

Usage:
  dream-import.py <bundle.tgz>             # validate, safety-check, apply
  dream-import.py <bundle.tgz> --force     # bypass divergence safety check
  dream-import.py <bundle.tgz> --dry-run   # report what would change

Safety: refuses to apply if the local repo has commits the bundle doesn't.
That's the laptop's own scratch -- if you really want to discard it, pass
--force. The local memory is moved aside to a timestamped backup directory
either way, so even a forced overwrite is recoverable.
"""

import argparse
import hashlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path

_here = Path(__file__).resolve().parent
for _cand in (_here, _here / "hooks"):
    if (_cand / "_dream_common.py").is_file():
        sys.path.insert(0, str(_cand))
        break
import _dream_common as dc  # noqa: E402

dc.setup_utf8_io()


def die(msg: str, code: int = 1) -> None:
    print(f"dream-import: {msg}", file=sys.stderr)
    sys.exit(code)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Apply a dream-export bundle to global memory.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("bundle", help="Path to dream-export-*.tgz bundle.")
    p.add_argument("--force", action="store_true",
                   help="Bypass the divergence safety check (still keeps a backup).")
    p.add_argument("--dry-run", action="store_true",
                   help="Report what would change; touch nothing.")
    return p.parse_args()


def resolve_bundle(arg: str) -> Path:
    """Accept either an absolute path or a bare filename to be found in export_dir."""
    p = Path(arg).expanduser()
    if p.is_file():
        return p
    cand = dc.export_dir() / arg
    if cand.is_file():
        return cand
    die(f"bundle not found: {arg}")


def rev_list(repo: Path) -> "set[str]":
    r = subprocess.run(["git", "rev-list", "--all"], cwd=repo,
                       capture_output=True, text=True, check=False)
    if r.returncode != 0:
        return set()
    return {line for line in r.stdout.splitlines() if line}


def head_sha(repo: Path) -> str:
    r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                       capture_output=True, text=True, check=False)
    return (r.stdout or "").strip() if r.returncode == 0 else ""


def _unsafe_member_reason(member: tarfile.TarInfo) -> "str | None":
    """Return a reason string if this tar entry is unsafe, else None.

    Rejects absolute paths, parent-traversal, Windows drive letters, and any
    link or device member type. Validated against the same threat surface as
    Python's 3.12+ "data" tarfile filter.
    """
    if member.issym() or member.islnk():
        return "link entries are not allowed"
    if member.isdev() or member.isfifo():
        return "device/fifo entries are not allowed"
    name = member.name
    if not name:
        return "empty entry name"
    if name.startswith("/") or name.startswith("\\"):
        return "absolute path"
    if len(name) >= 2 and name[1] == ":":
        return "drive-letter path"
    # Catch both POSIX-style "a/../b" and Windows-style "a\\..\\b" -- replace
    # backslashes so Path on POSIX still notices ".." segments.
    for part in Path(name.replace("\\", "/")).parts:
        if part == "..":
            return "parent-traversal"
    return None


_MAX_BUNDLE_MEMBERS = 50_000
_MAX_BUNDLE_UNCOMPRESSED = 500 * 1024 * 1024  # 500 MB


def _bundle_sha256(tar_path: Path) -> str:
    """Hash the bundle bytes. Used to defend the validate->extract window
    against an attacker swapping the file between checks (TOCTOU)."""
    h = hashlib.sha256()
    with tar_path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def is_dream_export_bundle(tar_path: Path) -> "tuple[bool, str, str]":
    """Strict validation: iterate every member, reject unsafe entries, require
    at least one .git/ entry, cap total member count and total uncompressed
    size. Returns (ok, reason, sha256_at_validation_time).

    Caps added to defend against a "decompression bomb" bundle: a small
    gzipped file whose members declare huge uncompressed sizes. Caps:
        - member count <= 50,000
        - total uncompressed size <= 500 MB
    A real memory store is MB-scale and a few hundred entries; these caps
    are generous by orders of magnitude.

    sha256 is returned so the caller can re-hash before extraction and
    refuse if the bundle content changed between validate and extract.
    """
    saw_git = False
    member_count = 0
    total_size = 0
    try:
        sha = _bundle_sha256(tar_path)
        with tarfile.open(tar_path, "r:gz") as tar:
            for member in tar.getmembers():
                member_count += 1
                if member_count > _MAX_BUNDLE_MEMBERS:
                    return False, f"too many entries (>{_MAX_BUNDLE_MEMBERS})", ""
                total_size += max(member.size, 0)
                if total_size > _MAX_BUNDLE_UNCOMPRESSED:
                    return (False,
                            f"uncompressed size exceeds {_MAX_BUNDLE_UNCOMPRESSED} bytes",
                            "")
                reason = _unsafe_member_reason(member)
                if reason:
                    return False, f"unsafe entry {member.name!r}: {reason}", ""
                # dream-export.py writes entries with a "./" prefix (arcname=".").
                # Accept both that and the prefix-free form.
                norm = member.name.replace("\\", "/")
                if norm.startswith("./"):
                    norm = norm[2:]
                if norm == ".git" or norm.startswith(".git/"):
                    saw_git = True
        if not saw_git:
            return False, "no .git/ directory inside", ""
        return True, "", sha
    except (tarfile.TarError, OSError) as e:
        return False, f"tar read failed: {e}", ""


def main() -> int:
    args = parse_args()
    bundle = resolve_bundle(args.bundle).resolve()

    ok, reason, validated_sha = is_dream_export_bundle(bundle)
    if not ok:
        die(f"{bundle} is not a usable dream-export bundle: {reason}")

    memory = dc.memory_root()
    state = dc.state_root()

    print(f"Importing bundle: {bundle.name}")
    print(f"  size:  {bundle.stat().st_size / (1024 * 1024):.1f} MB")
    print(f"  to:    {memory}")
    print()

    with tempfile.TemporaryDirectory(prefix="dream-import-") as tmp:
        tmp_path = Path(tmp)
        # TOCTOU defense: re-hash the bundle before extraction and refuse if
        # its content has changed since validation. Without this, an attacker
        # with write access to the bundle path (the default is ~/Downloads/)
        # could swap the validated-clean bundle for a malicious one in the
        # narrow window between is_dream_export_bundle() and extractall().
        current_sha = _bundle_sha256(bundle)
        if current_sha != validated_sha:
            die("bundle content changed between validation and extraction "
                "(refusing to extract a possibly-tampered file)")
        try:
            with tarfile.open(bundle, "r:gz") as tar:
                # Defense in depth: is_dream_export_bundle already rejected
                # unsafe members above. On Python 3.12+ the "data" filter
                # additionally constrains the extractor itself; on 3.8-3.11 the
                # pre-validation is the load-bearing safety. Passing filter= on
                # older runtimes raises TypeError, which we tolerate.
                try:
                    tar.extractall(tmp_path, filter="data")
                except TypeError:
                    tar.extractall(tmp_path)
        except (tarfile.TarError, OSError) as e:
            die(f"failed to extract bundle: {e}")

        if not (tmp_path / ".git").is_dir():
            die("extracted bundle has no .git/ at top level; not a dream-export bundle")

        bundle_head = head_sha(tmp_path)
        print(f"  bundle head: {bundle_head[:12] if bundle_head else '(none)'}")

        local_only: "set[str]" = set()
        if memory.is_dir() and (memory / ".git").is_dir():
            local_commits = rev_list(memory)
            bundle_commits = rev_list(tmp_path)
            local_only = local_commits - bundle_commits
            print(f"  local head:  {head_sha(memory)[:12]}")
            print(f"  local-only commits: {len(local_only)}")
        else:
            print("  local memory absent or not a repo -- treating as fresh import")
        print()

        if local_only and not args.force:
            print(f"REFUSED: local memory has {len(local_only)} commit(s) the bundle doesn't.",
                  file=sys.stderr)
            print("That's likely your laptop scratch. To inspect:", file=sys.stderr)
            print(f"  cd {memory} && git log --oneline -20", file=sys.stderr)
            print("If you really want to discard local-only commits, re-run with --force.",
                  file=sys.stderr)
            print("(--force still moves the current memory aside to a timestamped backup",
                  file=sys.stderr)
            print(" before applying the bundle, so the discard is recoverable.)",
                  file=sys.stderr)
            return 2

        if args.dry_run:
            print("Dry run complete. No changes applied.")
            return 0

        ts = datetime.now().strftime("%Y-%m-%dT%H%M%S")
        if memory.exists():
            backup = memory.parent / f"{memory.name}.pre-import-{ts}"
            shutil.move(str(memory), str(backup))
            print(f"Backed up previous memory to: {backup}")
        memory.parent.mkdir(parents=True, exist_ok=True)
        # Copy extracted contents into place. shutil.copytree (Python >= 3.8)
        # with dirs_exist_ok handles the rare case where memory.parent already
        # has something at memory's name.
        shutil.copytree(tmp_path, memory, dirs_exist_ok=True)

    marker = state / "last-import.txt"
    state.mkdir(parents=True, exist_ok=True)
    marker.write_text(bundle.name + "\n", encoding="utf-8")

    # Tag-style commit so the import is traceable in the history. Allow-empty
    # because the bundle's content already matches the new HEAD; we're just
    # recording the import event on top.
    new_head = head_sha(memory)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m",
         f"import: {bundle.name} (was {new_head[:12]})"],
        cwd=memory, check=False,
    )

    print()
    print("Import complete.")
    print(f"  memory now at: {head_sha(memory)[:12]}")
    print(f"  bundle:        {bundle.name}")
    print(f"  marker:        {marker}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
