# RELEASING.md — Pre-flight checklist before flipping this repo public

This doc is for future-you. It assumes you have already decided to publish the working repo (or one of its sibling release artifacts) and are about to change its visibility from private to public.

**Do not skip this checklist. The whole reason it exists is that the failure mode is not malice — it's sequencing.**

## How this checklist works

The procedural structure (what to check, in what order, with what guards) lives in this file and is safe to publish. The **specific patterns** to grep for (the exact strings that were redacted out of the working repo) live in a separate file that is **gitignored and never published**:

```
.release-patterns.private
```

Publishing the pattern list itself would be a treasure map of what was hidden, so it stays local-only. If `.release-patterns.private` does not exist on your machine, generate it from your last scrub's grep history before continuing — the gate cannot run without it.

## Repo-state map (don't conflate these)

A typical Dreamcatcher install ships three repos with distinct visibility intent. Adapt to your own repo names; the categories are what matters.

| Repo role | Visibility intent | Notes |
|---|---|---|
| Working source | Private today; may flip public | The repo subject to this checklist before any flip. |
| Frozen archive | Private forever | Unredacted snapshot of the working repo from before the scrub. Never push to it from the working repo, never flip its visibility. |
| Live memory store | Private forever | The git-backed cross-project memory used at runtime. Contains real customer-engagement shapes and personal context. Never flips. |

If you are about to run a visibility-change command against any repo other than the working source, stop and read this file again.

## Pre-flight scrub

Run from the working repo root.

### 1. Verify the archive is intact and current

Confirm the frozen archive still exists, is private, and is reachable. If missing or empty, re-create it from the current working repo before any further work. A fresh archive snapshot is the only recovery path if a future scrub turns out to have removed something you wanted to keep.

### 2. Grep for Tier 1 + Tier 2 personal/business references

Read the patterns from `.release-patterns.private` and grep them against every tracked text file in the repo. Expect **zero matches**. Any hit is a regression that needs surgical redaction before the flip.

A minimal driver (run this whenever you scrub; the exact form will depend on your shell and your pattern file syntax):

```bash
# Build a single extended-regex alternation from the active lines in
# the private patterns file, then grep for it across all tracked
# *.md and *.py files, excluding archive directories and the .git tree.
PATTERNS=$(grep -vE '^(\s*#|\s*$)' .release-patterns.private | paste -sd '|' -)
grep -rnE "$PATTERNS" --include='*.md' --include='*.py' \
  --exclude-dir=archive --exclude-dir=.git .
```

If the driver returns nothing, the pattern set is satisfied. If anything matches, redact (replace with a generic placeholder), move into a narrative-framed section, or remove the line entirely. Re-run the driver after each fix.

### 3. Grep for any single-user name in the three shipping prompts

The prompts at `commands/dream-global.md`, `commands/dream-bootstrap.md`, and `commands/dream-audit.md` deploy to every user's `~/.claude/commands/` on install. They must never name a specific user. The convention is `the user` or `you` (in the audit prompt). Re-grep these three files for any name you used during your own build.

### 4. Verify no devlog or design-history files have crept back in

Earlier versions of this repo shipped numbered design files (`01-*.md` through `18-*.md`) that mixed first-person narrative voice with internal working examples not meant for publication. They were removed: the operational prompts now live in `commands/`, the bootstrap templates in `templates/`, and the as-built design in the DOCX artifacts. Confirm no numbered narrative file has been re-added to the working tree. If one reappears, scrub it or keep it private before the flip — and remember (step 8) that removing it from the tree does **not** remove it from git history.

### 5. Regenerate the DOCX artifacts and commit

If the source prompts or hook code have changed since the last DOCX regen, the binaries on disk are stale. Regenerate both with the scripts under `tools/` before the flip:

```bash
python tools/gen_architecture_docx.py
python tools/gen_product_overview_docx.py
git status   # if anything is M on the two .docx files, commit them
```

If either file is locked by Word, close Word first.

After regeneration, re-run the step-2 driver against the regenerated DOCX content (open them with `python-docx` and walk paragraphs). The DOCX binaries can drift differently from the source files if a generator was updated but not re-run.

### 6. Confirm the `~/CLAUDE.md` template is generic

The marker-wrapped template at `templates/CLAUDE-memory-section.md` is what `setup.py` step 9 deploys to a new user's `~/CLAUDE.md`. It must not contain any specific user's name, employer, or in-flight project names. Re-grep using the step-2 driver scoped to that file alone.

### 7. Sanity-check your own local `~/CLAUDE.md`

Your local `~/CLAUDE.md` is **not** in this repo, but it does contain your own specific memory section (the version with your employer name, named in-flight projects, etc.). It does not get pushed by anything in this workflow, but worth confirming you have not accidentally moved it into a tracked location.

### 8. Scrub git history of any prior leaks

This is the step most likely to surprise you. **Even if the working tree is clean today, the patterns may still be visible in `git log -p`.** When the repo flips public, `git log` becomes public too.

Two cases:

- **The leaked content was only in your most recent commit and is not yet on a remote you cannot rewrite.** Amend or interactively rebase to remove it.
- **The leaked content is older or already pushed.** Use `git filter-repo` (or `git filter-branch` as the older equivalent) with a replacement pattern derived from `.release-patterns.private` to scrub the affected blobs out of history, then force-push to your private remote. Do this **before** the visibility flip, not after.

If you discover you need this step but are not confident running `git filter-repo`, stop and do not flip. The clean recovery from a botched history rewrite is much cheaper than the recovery from a published leak.

## The flip itself

After every step above returns clean:

1. Update the repo description if it currently says anything internal-sounding.
2. Run the visibility-change command for your git host (for GitHub, `gh repo edit <owner>/<repo> --visibility public`).
3. The host will ask you to type the repo name to confirm. **That is the last guard between you and a public repo. Don't muscle-memory through it.**

## Immediate post-flip verification

```bash
# Confirm the working repo flipped
gh repo view <owner>/<repo> --json visibility,defaultBranchRef
# expect: visibility = PUBLIC

# Confirm the OTHER repos are STILL private (the most important check)
gh repo view <owner>/<archive-repo> --json visibility,isPrivate
gh repo view <owner>/<memory-repo> --json visibility,isPrivate
# expect both: isPrivate = true, visibility = PRIVATE
```

If either of the other two flipped, **revert immediately**:

```bash
gh repo edit <owner>/<archive-repo> --visibility private
gh repo edit <owner>/<memory-repo> --visibility private
```

Recently-public repos are cached for a short window by search engines and `archive.org`; the faster you revert the smaller the exposure.

## If you realise mid-flip that content shouldn't have been published

Same recovery: change visibility back to private. Then assume the content has been seen (search engines, crawlers, archive.org all index quickly). Rewrite the offending content in a new commit, but understand that the original commit is on the public-history record for anyone who cloned during the public window.

The defensive move at that point is a fresh repo from a scrubbed snapshot, not a force-push of the existing one.

## Known architectural limits to disclose alongside any release

Independent of the per-release scrub, certain properties of the v1.3 design are worth flagging to any downstream user. Make sure these end up in the project's public README (or equivalent) before flipping a release public.

- **The private git remote is the trust root.** `prepull_memory()` verifies fast-forwardability but does not check commit signatures or restrict author identities. A compromised push credential → memory injection → both machines + every future session. Mitigation lives outside the v1.3 code: signed commits on the remote, restricted push access, periodic `git log --show-signature` review. A verified-signature gate is a v1.4 candidate; today's release should not claim otherwise.
- **Sanity floors catch catastrophic rewrites, not semantic attacks.** The 50% delta floor and the structural-validity floor block obviously-wrong consolidations. They do not validate semantic content. Small well-formed adversarial entries pass. Semantic protection lives in the prompts (transcript-as-data discipline) and in monthly `/dream-audit`.
- **Transcripts are untrusted byte streams.** The dream reads them looking for signal; adversarial content in any transcript can attempt to inject memory content. Prompts contain anti-injection language; this is a defense, not a sandbox.
- **SessionStart-injected memory is loaded as session context.** A successful write to the live memory store propagates to every Claude Code session on every participating machine on next session start. The audit cadence is the human review checkpoint; treat it as load-bearing.

The README in the working repo should carry these disclosures verbatim. Step 7 of the pre-flight scrub (the template/CLAUDE.md sanity check) implicitly assumes the README's "Threat model and known limits" section is current.

## What this checklist deliberately does not do

- It does not script the scrub. The greps are read-only; remediation is manual because each hit needs judgment about whether to redact, genericize, or move into a narrative-framed section.
- It does not audit AI-tooling access to your local clone. That belongs in a separate operational review.
- It does not verify the live memory store — that store is private by design and never enters the public-release path.

## Updating this checklist

If a future scrub adds a new pattern category, add the pattern to `.release-patterns.private` in the same commit that lands the redaction. **Do not add specific strings to this file.** The whole point of the split is that `.release-patterns.private` carries the specifics and is never published, while this file carries the structure and is safe to publish.

If a process change makes the gate more durable (a new check, a clarified step, a different ordering), update this file. Procedural improvements are exactly what should be public; pattern specifics are exactly what should not be.
