# Laptop setup — joining a desktop running Dreamcatcher v1.2

One-page primer. Run this on the secondary machine (typically a laptop) to bring it onto v1.2-or-later bidirectional sync with the desktop's private memory repo.

Use case this is written for: a laptop coming online to join an existing desktop install that's already on v1.2 or later, where the laptop was last seeded via the manual export/import bundle path.

---

## 0. Prereqs (check, don't reinstall)

```bash
python3 --version              # need 3.8+
git --version                  # any modern git
which gh && gh auth status     # for the private repo; optional if HTTPS PAT works
```

If you've been working on this laptop for a while, all three are likely already present. If not, install Homebrew first, then `brew install python3 git`.

---

## 1. Update the source repo to v1.2

```bash
cd ~/dreamcatcher        # or wherever the Mac's clone lives
git fetch
git pull --ff-only origin main
git log --oneline -5
# top should include "v1.2 docs..." and "v1.2 step 4..." commits
git tag -l v1.2          # should print: v1.2
```

If the Mac doesn't have the source repo yet:

```bash
cd ~
git clone https://github.com/<YOUR_USER>/dreamcatcher.git
cd dreamcatcher
```

(Repo is public; no auth needed.)

---

## 2. Redeploy hooks at v1.2

```bash
cd ~/dreamcatcher
python3 setup.py --laptop --yes
```

Re-running is idempotent. It:
- Refreshes `~/.claude/commands/dream-global.md` from the v1.2 `/dream-global` prompt (adds Phase 0 prepull and Phase 5 auto-promote).
- Deploys the three new v1.2 utilities to `~/Dreamcatcher/hooks/`: `dream_promote.py`, `dreamcatcher-pull.py`, `dreamcatcher-log.py`.
- Prints the macOS-shaped schedule-registration commands at the end.

---

## 3. Add the GitHub remote and pull the live memory

```bash
cd ~/Dreamcatcher/memory
git remote -v                  # should be empty (laptop was seeded via bundle)
git remote add origin https://github.com/<YOUR_USER>/dreamcatcher-memory.git
git fetch origin
git pull --ff-only origin main
git log --oneline -5
# top should match the desktop's most recent dream commit
```

Auth: if `git pull` prompts for credentials, use `gh auth login` first (it'll patch git's credential helper) **or** generate a fine-grained PAT scoped to `dreamcatcher-memory` and paste it as the HTTPS password.

**If `git pull --ff-only` is rejected as non-fast-forward** — the Mac's memory repo has commits the desktop doesn't (unlikely given the laptop has been read-mostly, but possible). Two options:

```bash
# Option A — keep the Mac's local commits, rebase onto remote
git pull --rebase origin main
# resolve any conflicts in topic files, then:
git push

# Option B — discard local commits and adopt the desktop's state wholesale
cd ~
mv Dreamcatcher/memory Dreamcatcher/memory.preremote-$(date +%Y%m%d)
git clone https://github.com/<YOUR_USER>/dreamcatcher-memory.git Dreamcatcher/memory
```

Option B is what to do if the Mac's local commits look like a partial promote that wasn't worth keeping.

---

## 4. Register the hourly pull cron

The simplest macOS option is crontab. From `setup.py`'s output:

```bash
(crontab -l 2>/dev/null; echo "0 * * * * /usr/bin/python3 $HOME/Dreamcatcher/hooks/dreamcatcher-pull.py >> $HOME/Dreamcatcher/state/logs/cron-pull.log 2>&1") | crontab -
crontab -l                     # verify the line landed
```

To remove later: `crontab -e` and delete the line.

**launchd alternative** (more native on macOS, survives reboots cleaner): write `~/Library/LaunchAgents/local.dreamcatcher.pull.plist` with `StartInterval=3600` pointing at `dreamcatcher-pull.py`, then `launchctl load <plist>`. Skip unless the crontab approach proves flaky.

---

## 5. Schedule the nightly /dream-global for 03:00 PDT

Desktop fires at 02:00; laptop at 03:00 keeps the one-hour offset that serializes the two writers.

Write a small wrapper (analog of the desktop's `nightly-runner.ps1`) and a launchd plist (or crontab line):

```bash
cat > ~/Dreamcatcher/state/nightly-runner.sh <<'EOF'
#!/usr/bin/env bash
set -u
LOG=~/Dreamcatcher/state/logs/nightly-dream-$(date +%Y-%m-%d).log
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] starting nightly consolidation (laptop)" >> "$LOG"
cd ~/Dreamcatcher/memory
# Slash commands are interactive-only; feed the staged prompt content to claude -p.
claude -p "$(cat ~/Dreamcatcher/prompts/dream-global.md)" --allowedTools "Bash,Read,Write,Edit" >> "$LOG" 2>&1
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] nightly consolidation exited with code $?" >> "$LOG"
EOF
chmod +x ~/Dreamcatcher/state/nightly-runner.sh

# crontab line (03:00 local; Pacific because the Mac's timezone is set that way)
(crontab -l 2>/dev/null; echo "0 3 * * * $HOME/Dreamcatcher/state/nightly-runner.sh") | crontab -
crontab -l
```

The same Anthropic-API congestion rule applies: keep this **outside 0500–1200 PDT**.

---

## 6. Smoke tests

```bash
# Pull-only sanity check (should print "memory fast-forwarded from remote" or "already up to date")
python3 ~/Dreamcatcher/hooks/dreamcatcher-pull.py

# Confirm v1.2 utilities are deployed
ls ~/Dreamcatcher/hooks/dream_promote.py ~/Dreamcatcher/hooks/dreamcatcher-pull.py ~/Dreamcatcher/hooks/dreamcatcher-log.py

# Confirm the deployed prompt is v1.2 (should print 7+)
grep -c "Phase 5\|Phase 0\|dream_promote\|dreamcatcher-pull" ~/.claude/commands/dream-global.md

# Confirm the remote is set on memory
git -C ~/Dreamcatcher/memory remote -v

# Confirm latest commit matches the desktop
git -C ~/Dreamcatcher/memory log --oneline -3

# Browse a recent dream-run audit log (e.g., the desktop's most recent auto-promote)
python3 ~/Dreamcatcher/hooks/dreamcatcher-log.py list
python3 ~/Dreamcatcher/hooks/dreamcatcher-log.py show <run-id-from-list>
```

---

## 7. What to expect tomorrow morning

- **02:00 PDT** — desktop's nightly fires, auto-promotes, pushes to remote.
- **02:05–02:59 PDT** — laptop's hourly pull at the next top-of-hour catches the desktop's commit.
- **03:00 PDT** — laptop's nightly fires, runs `/dream-global` against now-current memory, auto-promotes its own consolidations, pushes back. Desktop's next hourly pull catches up.

If either nightly hits `REQUIRES_REVIEW`, the candidate folder is left in place under `~/Dreamcatcher/memory/.candidate/<run-id>/` with a `REQUIRES_REVIEW.txt`. Promote manually with `python3 ~/Dreamcatcher/hooks/promote.py <run-id>` after addressing the flagged issue.

---

## Rollback if something goes wrong

The v1.2 code is purely additive on top of v1.1.1. Worst case:

```bash
# Stop the schedules
crontab -e                                     # remove the two cron lines
# OR: launchctl unload <plist> if you used launchd

# Revert the source repo
cd ~/dreamcatcher
git reset --hard v1.1.1
python3 setup.py --laptop --yes              # redeploys v1.1.1 hooks/prompts

# Memory repo can stay where it is — v1.2 commits are forward-moving;
# rolling the source code back doesn't require touching the memory store.
```

The remote (`<YOUR_USER>/dreamcatcher-memory`) stays put either way — it's the durable record of consolidated memory regardless of which code version produced it.

---

## Notes for future re-runs of this doc

- AirDrop / bundle workflow (`/dream-export` + `/dream-import`) is now the **fallback**, not the primary. Use it only for first-time seed when there's no shared git remote yet, or for air-gapped operation.
- The 1-hour offset between desktop (02:00) and laptop (03:00) is the load-bearing serialization for two writers. If both machines fire close together, the second one's pre-pull may fail non-fast-forward; that's a safe stop, not damage.
- `Dreamcatcher - Architecture.docx` in the source repo is the canonical design reference for the bidirectional-sync and auto-promote behavior. Read it if anything here doesn't match what the system is doing.
