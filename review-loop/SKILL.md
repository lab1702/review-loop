---
name: review-loop
description: Run independent whole-repository reviews, fix verified issues, run checks, and make authorized local commits. Use only when explicitly invoked.
---

# Review Loop

Review the whole repository and fix verified issues until two consecutive passes are clean on the same unchanged commit. Attempt at most 10 passes.

**Stop** means end the entire run as **blocked** and follow [Exit and restart](#exit-and-restart).

## Launch requirements

Require explicit authorization for local commits on the current branch, for example: "I authorize ordinary commits to the current branch." Authorization covers the entire run; invocation alone is insufficient. If it is missing or unclear, request it and wait.

Require host-provided subagents with documented support for starting without coordinator or prior reviewer conversations (for example, `collaboration.spawn_agent` with `fork_turns: "none"`). Otherwise stop. A separate task or an instruction to "ignore previous context" does not establish isolation; sharing the repository filesystem is allowed. Do not install or invoke a separate Codex or Claude Code CLI.

## Run boundaries

- Use only the existing local repository. Do not access remote services, query or modify remotes, or fetch, pull, or push. This applies to reviewers, checks, and hooks; stop if a required operation needs remote access.
- Set `GIT_NO_LAZY_FETCH=1` in the environment of every Git command and of checks and hooks that may invoke Git. Set it explicitly in each execution environment, including reviewers; do not assume shell or subagent environment changes persist. This prevents static reads in partial clones from fetching missing objects. Verify Git support locally with `git --no-lazy-fetch --version`; if unsupported or a required object is missing locally, stop and report the coverage gap without fetching.
- Do not amend commits, rewrite history, create or switch branches, discard work from outside this run, include unrelated work, or weaken tests/checks. You may revise or revert your own uncommitted fix attempts during the run.
- Keep review artifacts (transcripts, finding inventories, and run logs) in the conversation, outside the working tree, or in an already-ignored location. Never commit them.

**Content changes** are edits, additions, or deletions of tracked or non-ignored untracked files. A **clean working tree** has no staged changes, unstaged changes, or non-ignored untracked files.

Before each review, edit, or commit, and at completion, verify that the starting branch is checked out and HEAD matches the expected local HEAD. Stop on a mismatch, or if any working-tree change is unexplained or comes from outside this run.

Require no merge, rebase, cherry-pick, revert, or other sequencer operation in progress during preparation and before every commit. Check Git's operation state using `git rev-parse --git-path` (including `MERGE_HEAD`, `CHERRY_PICK_HEAD`, `REVERT_HEAD`, `rebase-merge`, `rebase-apply`, and `sequencer`); a clean working tree alone is insufficient. Stop without completing or aborting an existing operation.

## Preparation

- Follow applicable user and repository instructions, including AGENTS.md and CLAUDE.md.
- Require a clean local Git working tree with a valid HEAD on a checked-out branch; otherwise stop.
- Record the **starting branch** and its commit as the **expected local HEAD**. Any branch, including `main`, is supported; no remote or upstream is required.
- Identify required check commands (tests, lint, type checking, and builds). If none are specified, select relevant available checks and state their scope.
- If no checks are required and no relevant checks exist, record a **no-checks exception**. It waives check execution only.
- Initialize the attempted-pass and consecutive-clean counters to zero.

## Reviewer prompt

Give each reviewer only the prompt below with its placeholders filled in. Summarize user requirements without relying on prior conversation; use "None specified" if there are none. Do not attach prior findings, fix explanations, or this skill.

```text
Repository: <repository location>
Commit to review: <exact commit SHA>
Applicable project requirements: <requirements or their locations>
Applicable user requirements and constraints: <self-contained summary or None specified>

Review the whole codebase at this exact commit, including source, tests,
configuration, and scripts. Inspect committed files, not the working-tree
snapshot or only a diff. Follow applicable project instructions.

Inventory generated files, vendored dependencies, binaries, and submodules.
Review their integration and relevant correctness or security risks; inspect
submodules at their recorded commits when available locally. You may omit detailed
inspection of generated or vendored content when reviewing its maintained
inputs or integration is sufficient.

Use only locally available files and Git objects. Do not access GitHub or
other remote services, query or modify remotes, or fetch, pull, or push.
Set GIT_NO_LAZY_FETCH=1 for every Git command, including in fresh shells,
to prevent implicit fetches in partial clones. Verify Git support locally
with git --no-lazy-fetch --version. If unsupported or required objects are missing, report
the affected paths and coverage gap without fetching.
Use only static, read-only inspection commands. Do not execute tests,
builds, or repository scripts; the coordinator runs checks. Do not consult
earlier review artifacts, modify files, switch or create branches, or create
or alter commits.

Report concrete, actionable findings with file/line references, triggering
scenarios, and impact. Do not request cosmetic changes or speculative
refactoring. If you find no actionable issues, say so explicitly.

State what you reviewed. For each excluded or unavailable category or path,
give the reason and any residual coverage gap with its potential impact.
A material coverage gap prevents a supported conclusion about the correctness
or security of an in-scope component or behavior.
```

## Check execution rules

A **full suite** runs all currently required or selected relevant checks, initially identified during preparation. A **check run** is a full suite or a targeted check. Stop if a check requires an unavailable runtime, local service, or other prerequisite.

Reassess the check commands and any no-checks exception at the start of each pass and after changes to tests, check configuration, dependencies, or project instructions, including changes made by checks or hooks. Include newly available or required checks, and revoke the exception when checks now exist or are required. If the suite changes, invalidate earlier results and require the updated full suite before staging or completing the pass; for hook changes, apply [Verify commit](#verify-commit). This does not reset repair or stabilization limits.

Before staging or completing a pass with an accepted review, require a passing full suite that leaves content unchanged, unless the no-checks exception applies. Results apply only to unchanged content within that pass.

Compare repository status and content before and after every check command, regardless of exit status. Stop if any check-induced change falls outside the verified fixes.

The following recovery rules apply only before committing. Post-commit checks follow [Verify commit](#verify-commit).

A **failure-repair attempt** diagnoses a check failure using only existing output and static inspection, then repairs a verified repository issue. Allow at most two per pass; stop if a failure has no verified repair or would require a third attempt. Count only repairs prompted by check failures, including issues also reported by the reviewer.

A **stabilization rerun** is the first full suite after a check run changes content. Once it starts, any further check-induced content change in that pass stops the run.

Apply the table after all commands in the check run finish, unless a stop condition requires immediate exit:

| Check-run result | Required next action |
| --- | --- |
| Success without content changes | Full suite: proceed. Targeted check: run the full suite before staging or completing the pass. |
| Failure without content changes | Perform one failure-repair attempt, then immediately run the full suite. |
| Success with content changes | Run the stabilization rerun next. |
| Failure with content changes | Perform one failure-repair attempt, then immediately run the full suite as the stabilization rerun. |

## For each review pass

Mark the pass permanently **non-clean** and reset the consecutive-clean count to zero as soon as any of these events occurs:

- Reviewer launch or acceptance fails.
- A finding is verified, including during checks.
- Content changes, even if later reverted.

Otherwise, the pass is **clean** once [Check and stage content](#check-and-stage-content) succeeds. Rejected findings alone do not disqualify it.

### Launch reviewer

At the start of each pass, reset failure-repair attempts to zero and stabilization status to not started. Increment the attempted-pass count before attempting to launch a fresh, isolated reviewer of the expected local HEAD with the [Reviewer prompt](#reviewer-prompt).

### Assess review

Wait for the reviewer to finish before editing. Accept only a completed review with no unresolved execution errors or material coverage gaps, as defined in [Reviewer prompt](#reviewer-prompt).

If launch or acceptance fails, [retire the reviewer](#retire-reviewer). Continue at [Completion and limits](#completion-and-limits) only if available capabilities can address the problem in another pass; otherwise stop.

### Validate and fix findings

Validate each finding against the reviewed commit and record reasons for rejections. Resolve all verified findings, adding regression tests where appropriate.

Stop if:

- Required information or a consequential choice cannot be inferred, or required authorization is missing.
- A verified finding cannot be resolved within scope.
- No evidence-backed next step remains, or attempts repeat without progress.

### Check and stage content

Satisfy [Check execution rules](#check-execution-rules) before proceeding.

If no content changes remain relative to the reviewed commit, skip staging and committing and go to [Retire reviewer](#retire-reviewer).

Otherwise, stage only verified fixes and leave no unstaged tracked changes or non-ignored untracked files. Verify that staged content matches what passed checks, unless the no-checks exception applies. Record the staged tree ID (`git write-tree`) with the check results or exception. Keep content unchanged until committing.

### Commit fixes

Verify that the staged tree still matches the recorded tree ID, then commit to the starting branch.

If the commit command fails, including hook rejection, inspect HEAD, the index, and working tree for the final report, then stop without repair, retry, or bypassing hooks.

### Verify commit

Require the starting branch to remain checked out, a clean working tree, and a new commit whose sole parent is the expected local HEAD and whose changes are all intended. Compare its tree ID (`git rev-parse 'HEAD^{tree}'`) with the recorded staged tree ID:

- If they match, the recorded check results or no-checks exception apply.
- If they differ, verify that hooks caused the differences and that they remain within the intended fix, then run a full suite against the new commit unless the no-checks exception applies.

Stop without repair or retry if verification fails, including any post-commit check failure or content change. On success, advance the expected local HEAD to the new commit.

### Retire reviewer

Interrupt the reviewer if still running and close it if supported. Never reuse or resume it.

## Completion and limits

At the end of each pass, increment the consecutive-clean count if clean, then evaluate in order:

- If two consecutive passes are clean, verify that both reviewed the same unchanged commit and the working tree is clean. Finish as **completed** if verified; otherwise stop.
- If 10 passes have been attempted, stop with the reason **review-pass limit reached**. Otherwise start the next pass.

## Exit and restart

On every exit, retire any remaining reviewer, preserve local commits and uncommitted changes, and produce the [Final report](#final-report).

A new invocation restarts at [Launch requirements](#launch-requirements) with fresh counters. The user must first resolve blockers and ensure a clean working tree; reaching only the pass limit requires no repository changes.

## Final report

- Outcome: completed or blocked. If blocked, explain the stop reason and any prerequisites for a new run.
- Starting branch and final commit. Mark unavailable or unverified Git values explicitly and explain why.
- Fixes, checks and their results (or the no-checks exception), review coverage, and remaining limitations.
- Attempted review passes and consecutive clean passes.
- Local commits created during the run, any uncommitted changes, and whether all operations stayed local.
