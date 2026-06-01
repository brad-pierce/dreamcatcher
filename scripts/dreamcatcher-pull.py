#!/usr/bin/env python3
"""dreamcatcher-pull.py - fast-forward ~/Dreamcatcher/memory/ from its git remote.

Intended for hourly cron / Task Scheduler / launchd. Idempotent and safe to run
in single-machine setups: when no remote is configured, this is a no-op.

Exit codes:
    0  - benign outcome (ok, already up to date, no remote, no repo, or
         not-fast-forward — the next /dream-global will deal with divergence).
    1  - genuine git/network error worth an operator's attention.

All outcomes log to ~/Dreamcatcher/state/logs/hook-dreamcatcher-pull-<date>.log
via _dream_common.logger(), so cron output redirection isn't required to keep
an audit trail.
"""

import sys
from pathlib import Path

# Locate _dream_common.py whether running from the repo or from ~/Dreamcatcher/hooks/.
_here = Path(__file__).resolve().parent
for _cand in (_here, _here / "hooks"):
    if (_cand / "_dream_common.py").is_file():
        sys.path.insert(0, str(_cand))
        break
import _dream_common as dc  # noqa: E402


def main() -> int:
    dc.setup_utf8_io()
    log = dc.logger("dreamcatcher-pull")

    result = dc.prepull_memory(verbose=False)
    log(f"status={result['status']}: {result['message']}")
    if result["output"]:
        log(f"git-output: {result['output']}")

    status = result["status"]

    if status in ("ok", "no-remote", "no-repo"):
        print(result["message"])
        return 0

    if status == "not-fast-forward":
        # benign from this script's POV; /dream-global is the right place to
        # surface a real conflict resolution prompt.
        print(result["message"])
        return 0

    print(f"ERROR: {result['message']}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
