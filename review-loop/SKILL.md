---
name: review-loop
description: Run independent whole-repository reviews with verified fixes, checks, and authorized local commits. Use only when explicitly invoked to run this review loop.
---

# Review Loop

Review the whole repository and fix verified issues until two consecutive passes are clean on the same unchanged commit, within 10 attempted passes.

In this skill, **stop** means end the run as **blocked**; do not resume it.

## Launch requirements

Require explicit authorization to create local commits on the current branch, for example: "I authorize ordinary commits to the current branch." Invocation alone is insufficient. If authorization is missing or unclear, request it and wait. Authorization covers the entire run.

Use the host's built-in subagents with verified support for starting without coordinator or prior reviewer conversations (for example, documented `collaboration.spawn_agent` support for `fork_turns: "none"`). Stop if this context isolation cannot be verified; a separate task or an instruction to "ignore previous context" is insufficient. Filesystem isolation is unnecessary. Do not install or invoke a separate Codex or Claude Code CLI.

## Run boundaries

- Work only with the existing local repository. Do not access remote services, query or modify remotes, or fetch, pull, or push. This boundary applies to reviewers, checks, and hooks; stop if a required operation needs remote access.
- Do not amend commits, rewrite history, create or switch branches, discard work, include unrelated work, or weaken tests/checks.
- Keep review artifacts (transcripts, finding inventories, and run logs) in the conversation, outside the working tree, or in an already-ignored location. Never commit them.

## Preparation

- Follow applicable user and repository instructions, including AGENTS.md and CLAUDE.md.
- Require an existing local Git working tree with a valid HEAD on a checked-out branch and a **clean working tree**: no staged changes, unstaged changes, or non-ignored untracked files. Stop if any requirement is unmet.
- Record the checked-out branch as the **starting branch** and its commit as the **expected local HEAD**. Any branch, including main, is supported; no remote or upstream is required.
- Identify required test, lint, type-check, and build commands. If none are specified, select relevant available checks and state their scope.
- Stop if a required or selected check needs an unavailable environment prerequisite, such as a runtime or local service. Handle repository-caused failures under [Check execution rules](#check-execution-rules).
- Record the **no-checks exception** only if no checks are required and no relevant checks exist. It waives check execution only.
- Initialize the attempted-pass and consecutive-clean counters to zero.

## Run invariants

**Content changes** are changes to tracked or non-ignored untracked files, including additions and deletions.

Before each review, before editing or committing, and at completion, verify that the starting branch is checked out and HEAD matches the expected local HEAD. Advance the expected value only after [Verify commit](#verify-commit) succeeds. Stop on any mismatch or any working-tree change that is unexplained or made outside this run.

## Reviewer prompt

Give each reviewer only the prompt below with its placeholders filled in. Make user requirements self-contained; use "None specified" if there are none. Do not attach prior findings, fix explanations, or this skill.

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

A **full suite** runs all checks identified during preparation. A **check run** is a full suite or a single targeted check. Targeted checks may diagnose or verify fixes unless a recovery rule below requires static diagnosis or a full suite next.

Each pass with an accepted review requires a passing full suite that makes no content changes, even if no fixes were needed, unless the no-checks exception applies. Reuse results only within that pass while content remains unchanged.

For every check command, compare repository status and content before and after, regardless of exit status. Stop immediately on any content change not justified by the intended fix. Once the stabilization rerun starts, stop on any further check-induced content change in that pass.

Apply the following recovery rules before running further checks. They apply only before committing; post-commit checks follow [Verify commit](#verify-commit).

- **Failed check run:** Allow at most two **failure-repair attempts** per pass; stop if none remain. Diagnose using existing output and static inspection only, then repair a verified repository issue or stop. Each attempt consists of one repair followed immediately by a full suite, regardless of the suite's result.
- **First justified check-induced change:** Run a full suite next as the **stabilization rerun**. If the check run also failed, repair it under the failure rule first; the following suite consumes one repair attempt and serves as the stabilization rerun.

## For each review pass

A pass becomes permanently **non-clean** if reviewer launch or acceptance fails, any finding is verified (including during checks), or any content changes, even if later reverted. Immediately reset the consecutive-clean count to zero. Otherwise, the pass is **clean** once [Check and stage content](#check-and-stage-content) succeeds; rejected findings alone do not disqualify it.

### Launch reviewer

Increment the attempted-pass count and record the current commit, even if launch or review later fails. Initialize this pass's failure-repair count to zero and stabilization rerun to unused; do not reset either during the pass. Launch a new reviewer using the verified isolation mechanism and [Reviewer prompt](#reviewer-prompt).

### Assess review

Wait for the reviewer to finish before editing. Accept only a completed review with no unresolved execution errors or material coverage gaps, as defined in [Reviewer prompt](#reviewer-prompt).

If launch or review acceptance fails, skip to [Retire reviewer](#retire-reviewer) without editing, running checks, or committing. Retry in a later pass only if available capabilities can address the problem; otherwise stop.

### Validate and fix findings

Validate each finding against the reviewed commit. Record the reason for each rejection. Fix verified findings and add regression tests where appropriate.

Resolve all verified findings before proceeding. The check-failure repair limit does not apply to reviewer-finding repairs. Stop if:

- Required information or a consequential choice cannot be inferred, or required authorization is missing.
- A finding cannot be resolved within scope.
- No evidence-backed next step remains, or attempts repeat without progress.

### Check and stage content

Satisfy [Check execution rules](#check-execution-rules) before proceeding.

If no content changes remain relative to the reviewed commit, skip to [Retire reviewer](#retire-reviewer).

Otherwise, stage only verified fixes. Require no unstaged tracked changes or unexplained non-ignored files. Verify that staged content matches what passed checks (or qualifies for the no-checks exception). Record the staged tree ID (`git write-tree`) alongside those results or the exception. Keep this content unchanged until committing.

### Commit fixes

Verify that the staged tree still matches the recorded tree ID, then commit to the starting branch.

If the commit command fails, including hook rejection, inspect HEAD, the index, and working tree for the final report, then stop. Do not repair, retry the commit, or bypass hooks.

### Verify commit

Require a clean working tree and a new commit whose sole parent is the expected local HEAD and whose changes are all intended. Compare its tree ID (`git rev-parse 'HEAD^{tree}'`) with the recorded staged tree ID:

- If they match, the recorded check results apply.
- If they differ, verify that hooks caused the differences and that they remain within the intended fix, then run a full suite against the new commit unless the no-checks exception applies.

Stop without repair or retry if verification fails, including any post-commit check failure or content change. On success, advance the expected local HEAD to the new commit.

### Retire reviewer

Interrupt any still-running reviewer and close it if supported. Never reuse or resume a retired reviewer. Retiring a reviewer does not itself end the run.

## Completion and limits

At the end of each pass, increment the consecutive-clean count if the pass is clean, then evaluate these conditions in order:

- When the consecutive-clean count reaches two, verify that both passes reviewed the same unchanged commit and the working tree is clean. If verification succeeds, finish as **completed**; otherwise stop.
- If success has not been achieved by the end of pass 10, stop with the reason **review-pass limit reached**. Otherwise start the next pass.

On every exit, follow [Retire reviewer](#retire-reviewer) for any remaining reviewer, preserve local commits and uncommitted changes, and produce the [Final report](#final-report).

Each new run begins at [Launch requirements](#launch-requirements) with fresh counters. The user must first resolve any underlying blocker and ensure the working tree is clean. Reaching only the ten-pass limit requires no repository changes.

## Final report

- Outcome: completed or blocked. If blocked, explain the stop reason and any prerequisites for a new run.
- Starting branch and final commit. Mark unavailable or unverified Git values explicitly and explain why.
- Fixes, checks and their results (or the no-checks exception), review coverage, and remaining limitations.
- Attempted review passes and consecutive clean passes.
- Local commits created during the run, any uncommitted changes, and whether all operations stayed local.

Do not claim that the repository is guaranteed bug-free.
