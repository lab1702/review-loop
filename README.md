# review-loop

Review the whole repository, fix verified issues, and run checks until two consecutive independent reviews of the same commit are clean, with at most 10 review passes.

The install scripts copy the skill to both `~/.agents/skills/` (Codex) and `~/.claude/skills/` (Claude Code).

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

Start in an existing local Git repository and check out the branch you want reviewed. The branch must have a commit and a clean working tree: no staged changes, unstaged changes, or non-ignored untracked files. The loop works on that branch (including `main`) and never creates or switches branches. If the checked-out branch changes or HEAD changes outside the loop's verified commits, the loop stops. Verified fixes are committed locally after checks pass.

The loop operates only on the local repository and does not access GitHub or other remote services. No remote or upstream is required. You handle all fetching, pulling, and pushing. Reviewers, checks, and hooks must also operate locally; a required operation that needs remote access blocks the run.

If a run is blocked, its local commits and uncommitted fixes are preserved. Resolve the blocker and restore a clean local working tree before launching a new run with commit authorization. A new run starts its review counters at zero.

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
