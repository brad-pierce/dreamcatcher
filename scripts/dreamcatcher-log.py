#!/usr/bin/env python3
"""dreamcatcher-log.py - browse the structured JSON audit log of dream runs.

v1.2 auto-promote writes one JSON log per run at:
    ~/Dreamcatcher/memory/.dream-log/<run-id>.json

The log is committed alongside the topic-file changes, so the audit travels
with the data on a `git pull`. This CLI is the read tool over those logs.

Usage:
    dreamcatcher-log.py                       # list recent runs
    dreamcatcher-log.py --list                # alias for the above
    dreamcatcher-log.py show <run-id>         # pretty-print a run summary
    dreamcatcher-log.py show <run-id> --json  # raw JSON for piping
    dreamcatcher-log.py grep <pattern>        # search across all run logs
    dreamcatcher-log.py grep <pattern> --field reason
                                              # restrict grep to a specific field
"""

import argparse
import json
import re
import sys
from pathlib import Path

_here = Path(__file__).resolve().parent
for _cand in (_here, _here / "hooks"):
    if (_cand / "_dream_common.py").is_file():
        sys.path.insert(0, str(_cand))
        break
import _dream_common as dc  # noqa: E402

dc.setup_utf8_io()


def die(msg: str, code: int = 1) -> None:
    print(f"dreamcatcher-log: {msg}", file=sys.stderr)
    sys.exit(code)


def log_root() -> Path:
    return dc.memory_root() / ".dream-log"


def list_runs(root: Path) -> "list[Path]":
    if not root.is_dir():
        return []
    return sorted(root.glob("*.json"))


def load(path: Path) -> "dict | None":
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"warn: could not read {path}: {e}", file=sys.stderr)
        return None


def cmd_list() -> int:
    root = log_root()
    runs = list_runs(root)
    if not runs:
        print(f"(no logs in {root})")
        return 0
    print(f"{'run-id':<22} {'machine':<10} {'sanity':<14} summary")
    print("-" * 80)
    for path in runs:
        data = load(path)
        if not data:
            continue
        run_id = data.get("run_id", path.stem)
        machine = data.get("machine", "?")
        sanity = (data.get("sanity_check") or {}).get("outcome", "?")
        summary = data.get("summary", "")[:46]
        print(f"{run_id:<22} {machine:<10} {sanity:<14} {summary}")
    return 0


def cmd_show(run_id: str, as_json: bool) -> int:
    path = log_root() / f"{run_id}.json"
    if not path.is_file():
        die(f"no log for run-id: {run_id}")
    data = load(path)
    if data is None:
        return 1

    if as_json:
        print(json.dumps(data, indent=2))
        return 0

    print(f"=== Dream Run: {data.get('run_id', '?')} ===")
    print(f"machine:      {data.get('machine', '?')}")
    print(f"started_at:   {data.get('started_at', '?')}")
    print(f"completed_at: {data.get('completed_at', '?')}")
    print(f"summary:      {data.get('summary', '?')}")
    print()

    sanity = data.get("sanity_check") or {}
    print(f"sanity: outcome={sanity.get('outcome', '?')}  "
          f"delta_pct={sanity.get('delta_pct', '?')}%  "
          f"structural_valid={sanity.get('structural_valid', '?')}")
    floors = sanity.get("floors_tripped") or []
    if floors:
        print(f"floors-tripped:")
        for f in floors:
            print(f"  - {f}")
    print()

    print(f"git: {data.get('git_head_before', '?')[:12]} -> "
          f"{data.get('git_head_after', '?')[:12]}")
    advance = data.get("reverie_advance") or {}
    if advance:
        print(f"reverie-advance: {advance.get('from', '?')} -> {advance.get('to', '?')}")
    print()

    sources = data.get("sources_considered") or []
    if sources:
        print(f"sources-considered ({len(sources)}):")
        for s in sources:
            transcripts = s.get("transcripts", "?")
            hits = s.get("grep_hits", "?")
            print(f"  - {s.get('project', '?')}: transcripts={transcripts}, grep_hits={hits}")
        print()

    entries = data.get("entries") or []
    if entries:
        print(f"entries ({len(entries)}):")
        for e in entries:
            action = e.get("action", "?").upper()
            file = e.get("file", "?")
            anchor = e.get("anchor", "?")
            print(f"  [{action:<7}] {file} :: {anchor}")
            reason = e.get("reason", "")
            if reason:
                for line in _wrap(reason, 72, indent=15):
                    print(line)
            for src in e.get("sources") or []:
                print(f"               _source: {src.get('project', '?')} @ {src.get('date', '?')}")
        print()

    skipped = data.get("considered_but_skipped") or []
    if skipped:
        print(f"considered-but-skipped ({len(skipped)}):")
        for s in skipped:
            print(f"  - {s.get('signal', '?')}")
            reason = s.get("reason", "")
            if reason:
                for line in _wrap(reason, 72, indent=4):
                    print(line)
        print()

    return 0


def _wrap(text: str, width: int, indent: int) -> "list[str]":
    out: "list[str]" = []
    line = ""
    for word in text.split():
        if len(line) + len(word) + 1 > width:
            out.append(" " * indent + line)
            line = word
        else:
            line = (line + " " + word).strip()
    if line:
        out.append(" " * indent + line)
    return out


def cmd_grep(pattern: str, field: str) -> int:
    rx = re.compile(pattern, re.IGNORECASE)
    root = log_root()
    runs = list_runs(root)
    if not runs:
        print(f"(no logs in {root})")
        return 0

    any_hit = False
    for path in runs:
        data = load(path)
        if not data:
            continue
        run_id = data.get("run_id", path.stem)
        hits: "list[str]" = []
        for entry in data.get("entries") or []:
            if field == "any":
                blob = " ".join(str(v) for v in entry.values())
            else:
                blob = str(entry.get(field, ""))
            if rx.search(blob):
                hits.append(f"  [{entry.get('action', '?')}] "
                            f"{entry.get('file', '?')} :: {entry.get('anchor', '?')} -- "
                            f"{entry.get('reason', '')[:80]}")
        for skipped in data.get("considered_but_skipped") or []:
            blob = f"{skipped.get('signal', '')} {skipped.get('reason', '')}"
            if rx.search(blob):
                hits.append(f"  [SKIPPED] {skipped.get('signal', '?')} -- "
                            f"{skipped.get('reason', '')[:80]}")
        if hits:
            any_hit = True
            print(f"=== {run_id} ===")
            for h in hits:
                print(h)
    if not any_hit:
        print(f"(no matches for /{pattern}/)")
    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Browse dream-run audit logs (v1.2).")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("list", help="List runs (default).")
    show = sub.add_parser("show", help="Show one run.")
    show.add_argument("run_id")
    show.add_argument("--json", action="store_true", help="Raw JSON output.")
    grep = sub.add_parser("grep", help="Search across all runs.")
    grep.add_argument("pattern")
    grep.add_argument("--field", default="any",
                      help="Restrict search to a specific field "
                           "(reason, file, anchor, signal). Default: any.")
    p.add_argument("--list", dest="top_list", action="store_true",
                   help="Equivalent to the `list` subcommand.")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    if args.top_list or args.cmd in (None, "list"):
        return cmd_list()
    if args.cmd == "show":
        return cmd_show(args.run_id, args.json)
    if args.cmd == "grep":
        return cmd_grep(args.pattern, args.field)
    die(f"unknown subcommand: {args.cmd}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
