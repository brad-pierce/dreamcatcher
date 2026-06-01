#!/usr/bin/env python3
"""dream-export.py - bundle ~/.claude/global-memory/ for transfer to the laptop.

Usage:
  dream-export.py                  # bundle current memory as a .tgz, print path
  dream-export.py --dry-run        # report what would be bundled; touch nothing
  dream-export.py --out <path>     # override output location (default: $export_dir)

Output: <export_dir>/dream-export-YYYY-MM-DD-HHMM.tgz
The bundle includes the .git/ directory so the laptop can keep full history
and the import-side safety check has commits to compare against.

The repo must be clean. We refuse to export a dirty tree, because the bundle
is meant to be the new authoritative state on the laptop -- shipping
uncommitted scratch would silently overwrite the laptop's own scratch.
"""

import argparse
import subprocess
import sys
import tarfile
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
    print(f"dream-export: {msg}", file=sys.stderr)
    sys.exit(code)


def tree_clean(memory: Path) -> bool:
    a = subprocess.run(["git", "diff", "--quiet"], cwd=memory, check=False)
    b = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=memory, check=False)
    return a.returncode == 0 and b.returncode == 0


def head_sha(memory: Path) -> str:
    r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=memory,
                       capture_output=True, text=True, check=False)
    return (r.stdout or "").strip() if r.returncode == 0 else ""


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Bundle global-memory for transfer to the laptop.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--dry-run", action="store_true",
                   help="Report what would be bundled; touch nothing.")
    p.add_argument("--out", metavar="PATH",
                   help="Override output path. Default: <export_dir>/dream-export-<ts>.tgz")
    return p.parse_args()


def default_out(export_dir: Path) -> Path:
    ts = datetime.now().strftime("%Y-%m-%d-%H%M")
    return export_dir / f"dream-export-{ts}.tgz"


def main() -> int:
    args = parse_args()

    memory = dc.memory_root()
    if not memory.is_dir():
        die(f"global memory root not found: {memory}")
    if not (memory / ".git").is_dir():
        die(f"{memory} is not a git repo")

    if not tree_clean(memory):
        die(f"uncommitted changes in {memory} -- commit or stash before exporting")

    sha = head_sha(memory)
    export_dir = dc.export_dir()
    if args.out:
        out_path = Path(args.out).expanduser()
    else:
        out_path = default_out(export_dir)

    if args.dry_run:
        print(f"Would bundle: {memory}")
        print(f"  head: {sha[:12] if sha else '(none)'}")
        print(f"  to:   {out_path}")
        return 0

    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Tarball anchored at the memory root: top-level entries become files like
    # MEMORY.md, decisions/, scratch/, .git/. We do NOT exclude the candidate
    # folder -- if there's pending review on the desktop, it travels too.
    try:
        with tarfile.open(out_path, "w:gz") as tar:
            tar.add(memory, arcname=".", recursive=True)
    except OSError as e:
        die(f"failed to write {out_path}: {e}")

    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"Bundled: {out_path}")
    print(f"  head:  {sha[:12] if sha else '(none)'}")
    print(f"  size:  {size_mb:.1f} MB")
    print()
    print("Transfer this file to the laptop (USB, file share, email, etc.),")
    print(f"then on the laptop run:  /dream-import {out_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
