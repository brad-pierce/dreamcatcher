#!/usr/bin/env python3
"""dream_promote.py - the v1.2 auto-promote pipeline.

Called from /dream-global Phase 5 once the agent has written a candidate folder
plus dream-manifest.json describing what changed and why. Runs sanity floors,
applies the candidate on pass, writes a JSON audit log, makes a structured
commit, and pushes. Floor failure or push-with-rebase conflict leaves the
candidate in place and exits 0 with REQUIRES_REVIEW set — the manual
`promote.py` is the escape hatch.

Usage:
    python dream_promote.py <run-id>
    python dream_promote.py <run-id> --dry-run

The candidate folder is expected at <memory>/.candidate/<run-id>/. The manifest
file is <candidate>/dream-manifest.json with the schema:

    {
      "run_id": "<run-id>",
      "machine": "<desktop|laptop|...>",
      "started_at": "<UTC>",
      "summary": "<one-line <=72 chars>",
      "sources_considered": [{"project": "<slug>", "transcripts": N, "grep_hits": N}, ...],
      "entries": [
        {"action": "added|updated|removed",
         "file": "<topic-file>",
         "anchor": "<section heading or anchor>",
         "reason": "<why>",
         "sources": [{"project": "<slug>", "date": "YYYY-MM-DD"}, ...]},
        ...
      ],
      "considered_but_skipped": [{"signal": "...", "reason": "..."}, ...],
      "reverie_advance": {"from": "<UTC>", "to": "<UTC>"}
    }

The final JSON log written to memory/.dream-log/<run-id>.json is the manifest
augmented with git_head_before/after, sanity_check outcome, and completed_at.

Exit codes:
    0   success (promoted, or REQUIRES_REVIEW left for human)
    1   error worth an operator's attention (manifest unreadable, git failure
        not handled by rebase, etc.)
"""

import argparse
import difflib
import json
import shutil
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


# Sanity floors -------------------------------------------------------------

DELTA_PCT_FLOOR = 50.0  # candidate changing >50% of memory line-volume aborts

# Files that don't count toward "topic-file line volume" for delta computation.
NON_TOPIC_FILES = {
    "BOOTSTRAP-NOTES.md",
    "NOTES.md",
    "SUMMARY.txt",
    "archive-list.txt",
    "dream-manifest.json",
    "REQUIRES_REVIEW.txt",
}


def die(msg: str, code: int = 1) -> None:
    print(f"dream_promote: {msg}", file=sys.stderr)
    sys.exit(code)


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def walk_topic_files(root: Path) -> "list[tuple[Path, str]]":
    """Walk a folder and return (abs_path, relative_path) for each candidate
    topic file. Excludes manifest, notes, archive lists. Mirrors promote.py's
    walk_candidate_files.

    Containment: rejects symlinks, and rejects paths that resolve outside
    the candidate root. A malicious candidate folder could otherwise plant
    `customer-context.md -> /etc/passwd` or `working-style.md -> ~/.ssh/id_rsa`
    and have the file's contents copied into the live memory store and
    committed (then pushed) by the apply step below.
    """
    out: "list[tuple[Path, str]]" = []
    root_resolved = root.resolve()
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            # Symlinks in candidate folders are never legitimate; the dream
            # agent writes plain markdown files. Reject without following.
            continue
        if not path.is_file():
            continue
        if path.name in NON_TOPIC_FILES:
            continue
        rel_parts = path.relative_to(root).parts
        if rel_parts and rel_parts[0].startswith("."):
            continue
        # Resolved-containment check: defense in depth against any path
        # construct that escaped the walker's notion of `root`.
        try:
            if not path.resolve().is_relative_to(root_resolved):
                continue
        except OSError:
            continue
        rel = "/".join(rel_parts)
        out.append((path, rel))
    return out


def count_lines(path: Path) -> int:
    if not path.is_file():
        return 0
    try:
        return len(path.read_text(encoding="utf-8", errors="replace").splitlines())
    except OSError:
        return 0


def total_live_lines(memory: Path) -> int:
    """Sum line counts of all topic files in the live store (top-level *.md
    plus decisions/*.md). Used as the denominator for delta_pct."""
    total = 0
    for f in memory.glob("*.md"):
        if f.name not in NON_TOPIC_FILES:
            total += count_lines(f)
    decisions = memory / "decisions"
    if decisions.is_dir():
        for f in decisions.glob("*.md"):
            total += count_lines(f)
    return total


def compute_delta_lines(memory: Path, candidate_files: "list[tuple[Path, str]]") -> int:
    """Sum of added + removed lines across all candidate-vs-live diffs."""
    total = 0
    for cand_path, rel in candidate_files:
        live_path = memory / rel
        cand_lines = cand_path.read_text(encoding="utf-8", errors="replace").splitlines()
        if not live_path.is_file():
            total += len(cand_lines)
            continue
        live_lines = live_path.read_text(encoding="utf-8", errors="replace").splitlines()
        diff = list(difflib.unified_diff(live_lines, cand_lines, lineterm=""))
        # unified_diff produces +/- prefixed lines plus @@ hunk headers and
        # file headers. Count only the actual +/- content lines.
        for line in diff:
            if line.startswith(("+++", "---")):
                continue
            if line.startswith(("+", "-")):
                total += 1
    return total


def check_structural_validity(candidate_files: "list[tuple[Path, str]]") -> "list[str]":
    """Return a list of problems found. Each topic file must:
      - have at least one line starting with '# ' (a top-level heading)
      - contain at least one `_source:` line OR be MEMORY.md
    MEMORY.md is index-only and exempt from the _source: rule.
    """
    problems: "list[str]" = []
    for path, rel in candidate_files:
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        if not any(line.startswith("# ") for line in lines):
            problems.append(f"{rel}: missing top-level heading")
        if rel != "MEMORY.md" and not rel.startswith("decisions/"):
            if "_source:" not in text:
                problems.append(f"{rel}: no _source: provenance line found")
    return problems


# Manifest ------------------------------------------------------------------

# Manifest field caps. The dream agent writes these; an adversarial dream
# (prompt-injection-poisoned or buggy) could write enormous values that
# bloat the audit log committed to the memory repo. Caps are conservative
# upper bounds on what a real consolidation produces.
_MANIFEST_MAX_SUMMARY = 200
_MANIFEST_MAX_REASON = 2000
_MANIFEST_MAX_ENTRIES = 500
_MANIFEST_MAX_SOURCES = 200
_MANIFEST_MAX_SKIPPED = 200
_MANIFEST_VALID_ACTIONS = {"added", "updated", "removed", "carried-forward"}
_MANIFEST_NEWLINE_FIELDS = {"summary"}  # fields that must not contain newlines


def _validate_manifest(manifest: dict) -> "list[str]":
    """Return a list of structural problems with the manifest. Empty list
    means the manifest is well-formed enough to use.

    Validates:
      - Required top-level fields exist with reasonable types
      - String fields are within length caps
      - Lists are within count caps
      - 'summary' and other commit-message-bound fields contain no newlines
        (otherwise they fragment the structured commit body into apparent
        new fields)
      - entries[].action is one of the recognized verbs
    """
    problems: "list[str]" = []
    if not isinstance(manifest, dict):
        return ["manifest is not a JSON object"]

    for field in ("run_id", "machine", "summary"):
        v = manifest.get(field)
        if not isinstance(v, str):
            problems.append(f"manifest.{field} missing or not a string")
            continue
        if "\n" in v or "\r" in v:
            problems.append(f"manifest.{field} contains newlines")
        if field == "summary" and len(v) > _MANIFEST_MAX_SUMMARY:
            problems.append(
                f"manifest.summary too long ({len(v)} > {_MANIFEST_MAX_SUMMARY})"
            )

    entries = manifest.get("entries")
    if entries is None:
        entries = []
    if not isinstance(entries, list):
        problems.append("manifest.entries is not a list")
        entries = []
    if len(entries) > _MANIFEST_MAX_ENTRIES:
        problems.append(
            f"manifest.entries too long ({len(entries)} > {_MANIFEST_MAX_ENTRIES})"
        )

    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            problems.append(f"manifest.entries[{i}] is not an object")
            continue
        action = e.get("action")
        if action not in _MANIFEST_VALID_ACTIONS:
            problems.append(
                f"manifest.entries[{i}].action invalid: {action!r}"
            )
        for f in ("file", "anchor", "reason"):
            v = e.get(f)
            if v is not None and not isinstance(v, str):
                problems.append(f"manifest.entries[{i}].{f} not a string")
            elif isinstance(v, str) and len(v) > _MANIFEST_MAX_REASON:
                problems.append(
                    f"manifest.entries[{i}].{f} too long ({len(v)})"
                )
        sources = e.get("sources") or []
        if not isinstance(sources, list):
            problems.append(f"manifest.entries[{i}].sources is not a list")
        elif len(sources) > _MANIFEST_MAX_SOURCES:
            problems.append(
                f"manifest.entries[{i}].sources too long ({len(sources)})"
            )

    skipped = manifest.get("considered_but_skipped") or []
    if not isinstance(skipped, list):
        problems.append("manifest.considered_but_skipped is not a list")
    elif len(skipped) > _MANIFEST_MAX_SKIPPED:
        problems.append(
            f"manifest.considered_but_skipped too long ({len(skipped)})"
        )

    sources_considered = manifest.get("sources_considered") or []
    if not isinstance(sources_considered, list):
        problems.append("manifest.sources_considered is not a list")

    # sources_considered[].project sometimes interpolates into the structured
    # commit message; reject newlines.
    for i, s in enumerate(sources_considered if isinstance(sources_considered, list) else []):
        if not isinstance(s, dict):
            continue
        proj = s.get("project")
        if isinstance(proj, str) and ("\n" in proj or "\r" in proj):
            problems.append(
                f"manifest.sources_considered[{i}].project contains newlines"
            )

    return problems


def read_manifest(candidate_dir: Path) -> "dict | None":
    path = candidate_dir / "dream-manifest.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        die(f"dream-manifest.json invalid JSON: {e}")
    return None


def _truncate_summary(s: str, limit: int = 72) -> str:
    """Truncate a commit-subject summary at <=limit chars, word-boundary aware."""
    s = s.strip()
    if len(s) <= limit:
        return s
    cut = s.rfind(" ", 0, limit + 1)
    if cut <= 0:
        cut = limit
    return s[:cut].rstrip(" ,;:-")


def build_commit_message(manifest: dict) -> str:
    summary = manifest.get("summary", "consolidate cross-project memory")
    summary = _truncate_summary(summary, 72)

    entries = manifest.get("entries", [])
    added = sum(1 for e in entries if e.get("action") == "added")
    updated = sum(1 for e in entries if e.get("action") == "updated")
    removed = [e for e in entries if e.get("action") == "removed"]

    sources = manifest.get("sources_considered", [])
    source_str = ", ".join(
        f"{s.get('project', '?')}({s.get('grep_hits', s.get('transcripts', 0))})"
        for s in sources
    ) or "(none)"

    files_changed = sorted({e.get("file", "?") for e in entries})

    lines = [
        f"dream: {summary}",
        "",
        f"run-id: {manifest.get('run_id', '?')}",
        f"machine: {manifest.get('machine', '?')}",
        f"sources: {source_str}",
        f"files-changed: {', '.join(files_changed)}" if files_changed else "files-changed: (none)",
        f"added: {added} entries",
        f"updated: {updated} entries",
        f"removed: {len(removed)} entries"
        + (f"  ({'; '.join(r.get('anchor', '?') for r in removed)})" if removed else ""),
    ]
    advance = manifest.get("reverie_advance") or {}
    if advance:
        lines.append(f"reverie-advance: {advance.get('from', '?')} -> {advance.get('to', '?')}")

    lines.append("")
    lines.append("Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>")
    return "\n".join(lines)


# Git ---------------------------------------------------------------------

def git(args: "list[str]", cwd: Path, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=False,
        capture_output=capture, text=capture,
    )


def git_head(memory: Path) -> str:
    r = git(["rev-parse", "HEAD"], memory, capture=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def has_remote(memory: Path) -> bool:
    r = git(["remote"], memory, capture=True)
    return bool(r.stdout.strip())


def push_with_rebase(memory: Path, log) -> str:
    """Push the auto-promote commit. If rejected, pull --rebase and retry.
    If rebase fails (real conflict), abort the rebase and return 'conflict'.
    Returns one of 'pushed', 'no-remote', 'rebased', 'conflict', 'error'."""
    if not has_remote(memory):
        return "no-remote"

    r = git(["push"], memory, capture=True)
    if r.returncode == 0:
        return "pushed"

    out = (r.stdout + r.stderr).lower()
    log(f"initial push failed: {(r.stdout + r.stderr)[:300]}")
    if "rejected" not in out and "non-fast-forward" not in out:
        return "error"

    log("rebase-on-collision: pulling --rebase")
    rb = git(["pull", "--rebase"], memory, capture=True)
    if rb.returncode != 0:
        log(f"rebase failed; aborting: {(rb.stdout + rb.stderr)[:300]}")
        git(["rebase", "--abort"], memory)
        return "conflict"

    rp = git(["push"], memory, capture=True)
    if rp.returncode == 0:
        return "rebased"
    log(f"re-push after rebase still failed: {(rp.stdout + rp.stderr)[:300]}")
    return "error"


# REQUIRES_REVIEW ----------------------------------------------------------

def write_requires_review(candidate_dir: Path, reason: str, detail: str) -> None:
    path = candidate_dir / "REQUIRES_REVIEW.txt"
    body = (
        f"REQUIRES_REVIEW\n"
        f"reason: {reason}\n"
        f"written-at: {utcnow()}\n"
        f"\n"
        f"detail:\n{detail}\n"
        f"\n"
        f"To apply manually after addressing the issue, run:\n"
        f"  python promote.py {candidate_dir.name}\n"
    )
    path.write_text(body, encoding="utf-8")


def write_log(memory: Path, run_id: str, log_payload: dict) -> Path:
    log_root = memory / ".dream-log"
    log_root.mkdir(exist_ok=True)
    path = log_root / f"{run_id}.json"
    path.write_text(json.dumps(log_payload, indent=2) + "\n", encoding="utf-8")
    return path


# Main pipeline ------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Auto-promote a dream candidate (v1.2).")
    p.add_argument("run_id", help="Candidate folder name under <memory>/.candidate/")
    p.add_argument("--dry-run", action="store_true",
                   help="Run sanity floors and report; do not apply or commit.")
    return p.parse_args()


def main() -> int:
    dc.setup_utf8_io()
    args = parse_args()
    log_fn = dc.logger("dream-promote")

    memory = dc.memory_root()
    if not (memory / ".git").is_dir():
        die(f"no git repo at {memory}")

    candidate_dir = memory / ".candidate" / args.run_id
    if not candidate_dir.is_dir():
        die(f"candidate not found: {candidate_dir}")

    manifest = read_manifest(candidate_dir)
    if manifest is None:
        die("dream-manifest.json missing in candidate folder. "
            "v1.2 auto-promote requires a manifest. Use `python promote.py "
            f"{args.run_id}` for manual review of pre-v1.2 candidates.")

    # Schema-validate the manifest before letting any of its values flow into
    # the commit message, audit log, or git commands. A prompt-injection-
    # poisoned dream could otherwise write huge or newline-laced fields that
    # corrupt the audit substrate or fragment the structured commit body.
    manifest_problems = _validate_manifest(manifest)
    if manifest_problems:
        write_requires_review(
            candidate_dir,
            reason="manifest-invalid",
            detail="\n".join(manifest_problems),
        )
        print(f"REQUIRES_REVIEW: dream-manifest.json failed schema validation:")
        for p in manifest_problems[:10]:
            print(f"  - {p}")
        log_fn(f"manifest invalid: {manifest_problems}")
        return 0

    log_fn(f"start auto-promote run_id={args.run_id} dry_run={args.dry_run}")

    # Pre-pull: another machine may have pushed since the dream cycle started.
    pull = dc.prepull_memory(verbose=False)
    log_fn(f"prepull: status={pull['status']}")
    if pull["status"] == "not-fast-forward":
        write_requires_review(
            candidate_dir,
            reason="prepull-diverged",
            detail=pull["message"],
        )
        print(f"REQUIRES_REVIEW: {pull['message']}")
        return 0
    if pull["status"] == "error":
        die(pull["message"])

    candidate_files = walk_topic_files(candidate_dir)
    if not candidate_files:
        log_fn("empty candidate; skipping commit")
        print("empty candidate folder; nothing to promote")
        return 0

    # Sanity floors -----------------------------------------------------
    structural_problems = check_structural_validity(candidate_files)
    delta_lines = compute_delta_lines(memory, candidate_files)
    live_lines = max(total_live_lines(memory), 1)
    delta_pct = 100.0 * delta_lines / live_lines

    floors_tripped: "list[str]" = []
    if structural_problems:
        floors_tripped.append(
            "structural-invalid: " + "; ".join(structural_problems[:5])
        )
    if delta_pct > DELTA_PCT_FLOOR:
        floors_tripped.append(
            f"delta-pct: {delta_pct:.1f}% > {DELTA_PCT_FLOOR}% threshold "
            f"({delta_lines} changed of {live_lines} total)"
        )

    sanity = {
        "delta_pct": round(delta_pct, 2),
        "delta_lines": delta_lines,
        "live_lines": live_lines,
        "structural_valid": not structural_problems,
        "outcome": "requires_review" if floors_tripped else "auto-promote",
        "floors_tripped": floors_tripped,
    }
    log_fn(f"sanity: {sanity}")

    if floors_tripped:
        write_requires_review(
            candidate_dir,
            reason="sanity-floor-tripped",
            detail="\n".join(floors_tripped),
        )
        # Still write a log entry so the audit captures the trip.
        payload = dict(manifest)
        payload.update({
            "git_head_before": git_head(memory),
            "git_head_after": git_head(memory),
            "completed_at": utcnow(),
            "sanity_check": sanity,
        })
        log_path = write_log(memory, args.run_id, payload)
        print(f"REQUIRES_REVIEW: sanity floor(s) tripped:")
        for trip in floors_tripped:
            print(f"  - {trip}")
        print(f"  candidate preserved at: {candidate_dir}")
        print(f"  log at: {log_path}")
        print(f"  run `python promote.py {args.run_id}` to review and apply manually.")
        return 0

    if args.dry_run:
        print(f"sanity floors pass (delta {delta_pct:.1f}%, {len(candidate_files)} files).")
        print(f"would commit and push if not --dry-run.")
        return 0

    # Apply -----------------------------------------------------------
    head_before = git_head(memory)

    for cand, rel in candidate_files:
        live = memory / rel
        live.parent.mkdir(parents=True, exist_ok=True)
        # follow_symlinks=False: refuse to read through a symlink in the
        # candidate. The walker already rejects symlinks, but this is
        # defense in depth against any path that slips through.
        shutil.copyfile(cand, live, follow_symlinks=False)

    # Stage the topic file changes, plus the log we're about to write.
    git(["add", "-A"], memory)

    commit_msg = build_commit_message(manifest)
    cr = subprocess.run(
        ["git", "commit", "-m", commit_msg],
        cwd=memory, capture_output=True, text=True, check=False,
    )
    if cr.returncode != 0:
        out = (cr.stdout + cr.stderr).strip()
        if "nothing to commit" in out.lower():
            log_fn("no-op commit; live store already matches candidate")
            print("nothing to commit; candidate already matches live store")
            return 0
        die(f"git commit failed: {out[:300]}")

    head_after = git_head(memory)
    payload = dict(manifest)
    payload.update({
        "git_head_before": head_before,
        "git_head_after": head_after,
        "completed_at": utcnow(),
        "sanity_check": sanity,
    })
    log_path = write_log(memory, args.run_id, payload)

    # Amend the just-made commit to include the log (so log and topic-file
    # changes ship in one commit, traveling together to other machines).
    git(["add", str(log_path)], memory)
    subprocess.run(
        ["git", "commit", "--amend", "--no-edit"],
        cwd=memory, capture_output=True, text=True, check=False,
    )
    head_after = git_head(memory)
    payload["git_head_after"] = head_after
    log_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    subprocess.run(
        ["git", "commit", "--amend", "--no-edit"],
        cwd=memory, capture_output=True, text=True, check=False,
    )

    push_outcome = push_with_rebase(memory, log_fn)
    log_fn(f"push outcome: {push_outcome}")

    if push_outcome == "conflict":
        # Local commit landed but couldn't push cleanly. Surface for review;
        # the next dream cycle's prepull will refuse until human resolves.
        write_requires_review(
            candidate_dir,
            reason="push-rebase-conflict",
            detail=("Local commit succeeded but rebase against remote produced "
                    "conflicts. Resolve manually in ~/Dreamcatcher/memory/."),
        )
        print("WARN: commit local; push-with-rebase hit a real conflict.")
        print(f"  candidate preserved at: {candidate_dir}")
        return 0
    if push_outcome == "error":
        print("WARN: commit local; push failed for a non-rebase reason. Investigate.")
        return 0

    # Success: candidate folder served its purpose. Remove it so .candidate/
    # stays a working area, not a graveyard. The git history + .dream-log
    # carry the audit forward.
    shutil.rmtree(candidate_dir, ignore_errors=True)

    print(f"PROMOTED run_id={args.run_id}")
    print(f"  commit: {head_after[:12]}")
    print(f"  push:   {push_outcome}")
    print(f"  log:    {log_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
