# review-loop

Review the whole repository, fix verified issues, and run checks until two consecutive independent reviews of the same commit are clean, with at most 10 review passes.

The install scripts copy the skill to both `~/.agents/skills/` (Codex) and `~/.claude/skills/` (Claude Code).

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

Check out the branch you want reviewed before starting. The loop works on that branch (including `main`) and never creates or switches branches. It requires a clean working tree matching an existing GitHub upstream; configure and synchronize the upstream yourself before launching. If the checked-out branch or upstream configuration changes during the run, the loop stops. Verified fixes are committed locally after checks pass. The loop never pushes; successful completion can leave local fix commits for you to push manually.

If a run is blocked, its local commits and uncommitted fixes are preserved. Resolve the blocker, handle remaining changes, and synchronize the branch with its GitHub upstream before launching a new run with commit authorization. A new run starts its review counters at zero.

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
