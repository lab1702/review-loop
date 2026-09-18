# review-loop

Review the whole repository, fix verified issues, and run checks until two consecutive independent reviews of the same commit are clean, with at most 10 review passes.

The install scripts copy the skill to both `~/.agents/skills/` (Codex) and `~/.claude/skills/` (Claude Code).

Install from a checkout outside those destination folders. The installers reject overlapping paths, prepare both replacements before updating either installation, and restore previous installations if replacement fails.

Both installers use exclusive `.review-loop-install.lock` files in the destination `skills` directories. Concurrent runs fail before preparing replacements. Locks are released after cleanup or rollback. If a forcibly terminated run leaves a lock behind, confirm that no installer is running before removing that lock and retrying; inspect any reported recovery files first.

Both installations require explicit invocation. Codex uses `policy.allow_implicit_invocation: false` in `agents/openai.yaml`; the installers add `disable-model-invocation: true` to the Claude Code copy's frontmatter. Use the installer for Claude Code so this flag is included.

## Installation

### Linux and macOS

```bash
./install_review-loop.sh
```

### Windows

```powershell
.\install_review-loop.ps1
```

## Usage

Start in an existing local Git repository and check out the branch you want reviewed. The branch must have a commit and a clean working tree: no staged changes, unstaged changes, or non-ignored untracked files. No merge, rebase, cherry-pick, revert, or other sequencer operation may be in progress. The loop works on that branch (including `main`) and never creates or switches branches. If the checked-out branch changes or HEAD changes outside the loop's verified commits, the loop stops. Verified fixes are committed locally after checks pass. Check requirements are refreshed when repairs change the available or required checks.

Network access is allowed for review, repairs, and checks, including documentation lookups, GitHub queries, dependency downloads, and fetching missing Git objects. No remote or upstream is required. Fetches, including automatic fetches in partial clones, must preserve the checked-out branch, HEAD, index, and working-tree content. You handle all pushes to GitHub or other remotes; the loop, reviewers, checks, and hooks must never push.

Temporary files, directories, and inspection helpers are allowed outside the working tree or in an ignored location. Scratch files and review artifacts are never committed, and disposable files created by the run are cleaned up when no longer needed. Reviewers inspect committed content without editing repository content; the coordinator runs tests and builds and can obtain routine prerequisites using network access and temporary environments.

If a run is blocked, its local commits and uncommitted fixes are preserved. Resolve any underlying blocker and ensure the local working tree is clean before launching a new run with commit authorization. If the run stopped solely at the ten-pass limit, no repository changes are required; you may launch a new run immediately. A new run starts its review counters at zero.

In the Codex chat window:

```
$review-loop
I authorize ordinary commits to the current branch.
```

In Claude Code:

```
/review-loop
I authorize ordinary commits to the current branch.
```

## Installer checks

Run `python3 -B -m unittest discover -s tests -v`. The tests use temporary destinations and exercise each available shell. Set `REVIEW_LOOP_PWSH` to select a PowerShell executable. Tests for unavailable shells are skipped.
