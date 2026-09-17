---
name: review-loop
description: Run independent whole-repository reviews with verified fixes, checks, and authorized local commits. Use only when explicitly invoked to run this review loop.
---

# Review Loop

Success requires two consecutive clean review passes on the same unchanged commit within 10 attempted passes.

## Launch requirements

Require explicit authorization for **ordinary commits**: new local commits on the starting branch. For example: "I authorize ordinary commits to the current branch." Skill invocation alone is insufficient. If authorization is absent or ambiguous, request it and wait; once given, it covers the entire run.

Use the host's built-in subagents and verify that reviewers can start without coordinator or prior reviewer conversation, such as documented `collaboration.spawn_agent` support for `fork_turns: "none"`. Stop if this isolation cannot be verified. A separate task or an instruction to "ignore previous context" is insufficient; a separate filesystem is unnecessary. Do not install or invoke a separate Codex or Claude Code CLI.

## Run boundaries

- Work only with the existing local repository. Do not access remote services, query or modify remotes, or fetch, pull, or push. This boundary applies to reviewers, checks, and hooks; stop if a required operation needs remote access.
- Do not amend commits, rewrite history, create or switch branches, discard work, include unrelated work, or weaken tests/checks.
- Keep review transcripts, finding inventories, and run logs in the conversation, outside the working tree, or in an already-ignored location. Never commit them.
- On any stop, follow [Completion and limits](#completion-and-limits).

## Preparation

### Starting-state requirements

- Follow applicable user and repository instructions, including AGENTS.md and CLAUDE.md.
- Require an existing local Git working tree with a valid HEAD on a checked-out branch and a **clean working tree**: no staged changes, unstaged changes, or non-ignored untracked files. Stop if any requirement is unmet.
- Record the checked-out branch as the **starting branch** and its current commit as the **expected local HEAD**. Any branch, including main, is supported; no remote or upstream is required.
- Identify required test, lint, type-check, and build commands. If none are specified, select relevant available checks and state their scope. Record the **no-checks exception** only when no checks are required and no relevant checks exist; it waives check execution only. Stop if a required or selected check cannot run.
- Initialize the review-pass and consecutive-clean counters to zero.

### Invariants during the run

**Content changes** are changes to tracked or non-ignored untracked files, including additions and deletions.

Before each review, before editing or committing, and at completion, verify that the starting branch is checked out and HEAD matches the expected local HEAD. Advance the expected value only after [Verify commit](#verify-commit) succeeds. Stop on any mismatch or unrelated working-tree change; do not adopt outside changes to continue.

## Reviewer prompt

Give each reviewer only the prompt below with its placeholders filled in. Make the user requirements self-contained; use "None specified" if there are none. Do not attach prior findings, fix explanations, or this skill.

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
Use only static, read-only inspection commands. Do not execute tests,
builds, or repository scripts; the coordinator runs checks. Do not consult
earlier review artifacts, modify files, switch or create branches, or create
or alter commits.

Report concrete, actionable findings with file/line references, triggering
scenarios, and impact. Do not request cosmetic changes or speculative
refactoring. If you find no actionable issues, say so explicitly.

State what you reviewed. For each excluded or unavailable category or path,
give the reason and any residual coverage gap with its potential impact.
A material coverage gap is an unreviewed component or behavior that could
materially affect correctness or security.
```

## Check execution rules

A **full suite** runs all checks identified during preparation. A **check run** is either a full suite or a single targeted check. Use targeted checks to diagnose or verify a fix only when a full suite is not required next.

For every check command, compare repository status and content before and after, regardless of exit status. Stop on any content change not justified by the intended fix.

The rules below apply before committing. Each pass allows at most **two failure-repair attempts** and **one stabilization rerun**. Post-commit checks follow [Verify commit](#verify-commit) instead.

### Failed checks

After any failed check run:

1. Stop if no repair attempts remain.
2. Diagnose using only existing output and static inspection.
3. Repair a verified repository issue, or stop.
4. Run a full suite next. The repair and this suite together consume one attempt, whether the suite passes or fails.

### Changes made by checks

After the first check run that makes justified content changes:

1. Run a full suite next; this is the stabilization rerun.
2. Stop if any check command changes content during the stabilization rerun or any later run.

If the first content-changing check run also fails, follow [Failed checks](#failed-checks) before the stabilization rerun. The next full suite serves both purposes, consuming one repair attempt and the stabilization rerun. A stabilization rerun without a preceding failure consumes no repair attempt.

## For each review pass

A pass becomes permanently **non-clean** if reviewer launch or acceptance fails, any finding is verified (including during checks), or content changes (even if later reverted). Reset the consecutive-clean count to zero immediately. Otherwise, the pass is **clean** once [Check and stage content](#check-and-stage-content) succeeds. Rejected findings alone do not disqualify it.

### Launch reviewer

Increment the pass count and record the current commit, even if launch or review later fails. Reset the failure-repair and stabilization-rerun counters to zero only here. Launch a new reviewer using the verified isolation mechanism and [Reviewer prompt](#reviewer-prompt).

### Assess review

Wait for the reviewer to finish before editing. Accept only a completed review with no unresolved execution errors or material coverage gaps, as defined in [Reviewer prompt](#reviewer-prompt).

If launch or review acceptance fails, do not edit, run checks, or commit in that pass. Skip to [Retire reviewer](#retire-reviewer) if available capabilities can address the problem in a later pass; otherwise stop.

### Validate and fix findings

Validate each finding against the reviewed commit. Record the reason for each rejection. Fix verified findings and add regression tests where appropriate.

Resolve all verified findings before proceeding. Finding repairs have no separate attempt limit, but stop if:

- Required information or a consequential choice cannot be inferred, or required authorization is missing.
- A finding cannot be resolved within scope.
- No evidence-backed next step remains, or attempts repeat without progress.

Check failures follow [Check execution rules](#check-execution-rules).

### Check and stage content

Unless the no-checks exception applies, require a passing full suite that made no content changes, even on passes with no fixes. Reuse results only within the current pass while content remains unchanged.

If no content changes remain relative to the reviewed commit, skip to [Retire reviewer](#retire-reviewer) without creating an empty commit.

Otherwise, stage only verified fixes. Verify that staged content matches the content that passed checks (or qualifies for the no-checks exception), with no unstaged tracked changes or unexplained non-ignored files. Record the staged Git tree ID using `git write-tree` and associate it with the check results or exception. Keep this content unchanged until committing.

### Commit fixes

Verify that the staged tree still matches the recorded tree ID, then commit to the starting branch.

If the commit command fails, including hook rejection, inspect HEAD, the index, and working tree for the final report, then stop. Do not repair, retry the commit, or bypass hooks.

### Verify commit

Require a clean working tree and a new commit whose sole parent is the expected local HEAD and whose changes are all intended. Compare its tree ID (`git rev-parse 'HEAD^{tree}'`) with the recorded staged tree ID:

- If they match, the recorded check results apply.
- If they differ, verify that hooks caused the differences and that they remain within the intended fix, then run a full suite against the new commit unless the no-checks exception applies.

Stop if any requirement cannot be verified, or if post-commit checks fail or change content. Do not repair or retry failed verification. On success, advance the expected local HEAD to the new commit.

### Retire reviewer

Stop any still-running reviewer and close it if supported. Never reuse or resume a retired reviewer.

## Completion and limits

At the end of each pass, increment the consecutive-clean count if the pass is clean, then evaluate these conditions in order:

- When the consecutive-clean count reaches two, verify that both passes reviewed the same unchanged commit and the working tree is clean. If verification succeeds, finish as **completed**; otherwise stop.
- If success has not been achieved by the end of pass 10, stop. Otherwise start the next pass.

On every exit, follow [Retire reviewer](#retire-reviewer) for any remaining reviewer, preserve local commits and uncommitted changes, and produce the [Final report](#final-report).

Any stop ends the run as **blocked**, with no further passes or resumption. The user must resolve the blocker and restore a clean working tree before starting a new run from [Launch requirements](#launch-requirements).

## Final report

- Outcome: completed or blocked. If blocked, explain the blocker and what must be resolved before a new run.
- Starting branch and final commit. Mark unavailable or unverified Git values explicitly and explain why.
- Fixes, checks and their results (or the no-checks exception), review coverage, and remaining limitations.
- Total review passes and consecutive clean passes.
- Local commits created during the run, any uncommitted changes, and whether all operations stayed local.

Do not claim that the repository is guaranteed bug-free.
