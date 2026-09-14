# review-loop

Loop review-fix-test until review comes clean or 10 reviews are done

This is tested with **Codex** inside the **ChatGPT Desktop** app, and also installs for **Claude Code**.

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

In the Codex chat window:

```
$review-loop
```

In Claude Code:

```
/review-loop
```
