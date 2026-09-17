---
name: review-loop
description: Run independent whole-repository reviews with verified fixes, checks, and authorized local commits. Use only when explicitly invoked to run this review loop.
---

# Review Loop

Coordinate independent whole-repository reviews, validate findings, fix verified issues, run checks, and commit fixes locally. Success requires two consecutive clean reviews of the same unchanged commit within 10 attempted passes.

## Launch requirements

Require explicit authorization for ordinary commits, for example: "I authorize ordinary commits to the current branch." Invoking the skill alone is insufficient. If authorization is absent or ambiguous, request it and wait before starting. This covers all ordinary commits in the run without reconfirmation; required platform approvals still apply.

Use the host's built-in subagents. Verify a documented mechanism for launching each reviewer with no inherited coordinator or previous-reviewer conversation, such as `collaboration.spawn_agent` with `fork_turns: "none"` when supported. A separate filesystem is unnecessary; a separate task or an instruction to "ignore previous context" does not establish isolation. Stop if isolation cannot be verified. Do not install or invoke a separate Codex or Claude Code CLI.

## Run boundaries

- Work only with the existing local repository. Do not access GitHub or other remote services, query or modify remotes, or fetch, pull, or push. The human handles all remote synchronization. This boundary also applies to reviewers, checks, and hooks; stop if a required operation needs remote access.
- Do not rewrite history, create or switch branches, discard work, include unrelated work, or weaken tests/checks.
- Keep coordinator findings, fix explanations, and review logs out of the committed codebase.
- A stop condition ends the run as **blocked**. Follow **Completion and limits** for cleanup and reporting; do not start another pass to bypass a stop.

## Preparation

### Starting-state requirements

- Follow AGENTS.md, CLAUDE.md, and the repository's instructions.
- Require an existing local Git working tree with a valid HEAD commit on a checked-out branch. Stop if the repository or commit is missing, HEAD is detached, or there are staged changes, unstaged changes, or non-ignored untracked files.
- Record the checked-out branch as the **starting branch** and its current commit as the **expected local HEAD**. Any branch, including main, is supported; no remote or upstream is required.
- Identify required test, lint, type-check, and build commands. If none are specified, select relevant available checks and state their scope. A required or selected check that cannot run is a blocker.
- If no checks are required and no relevant runnable checks exist, record the **no-checks exception**, which waives check execution only.
- Initialize the review-pass and consecutive-clean counters to zero.

### Invariants during the run

- Before each review, before editing or committing, and at completion, verify that the starting branch is checked out and HEAD matches the expected local HEAD. Only **Verify commit** may advance the expected local HEAD.
- On any mismatch or unrelated working-tree change, stop. Do not merge, rebase, reset, or adopt outside changes to continue.

## Reviewer prompt

Give each reviewer only the prompt below with its placeholders filled in. Make user requirements self-contained; use "None specified" if there are none. Do not attach prior findings, fix explanations, this skill, or the coordinator's conversation.

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
earlier review artifacts, modify files, switch or create branches, change
commits.

Report concrete, actionable findings with file/line references, triggering
scenarios, and impact. Do not request cosmetic changes or speculative
refactoring. If you find no actionable issues, say so explicitly.

State what you reviewed. For each excluded or unavailable category or path,
give the reason and any residual coverage gap with its potential impact.
A material coverage gap is an unreviewed component or behavior that could
materially affect correctness or security.
```

## Check execution rules

A **full suite** runs all checks identified during preparation. A **check run** is either a full suite or a single targeted check used to diagnose or verify a fix. Targeted checks do not satisfy the full-suite requirement in **Check and stage content**.

For every check command, compare repository status and content before and after, regardless of exit status. Inspect every tracked-file change and new non-ignored file. Accept only changes justified by the intended fix; stop on unrelated or unexplained changes.

Two independent limits apply to pre-commit checks. Reset their counters only at the start of each pass:

- **Failure repairs: at most two attempts.** After a failed check run, repair a verified repository issue or stop. One attempt consists of evidence-backed repair edits followed directly by a full-suite run. The initial failed run consumes no attempt. Stop if checks fail with no attempts remaining.
- **Changes made by checks: one stabilization rerun.** After the first check run that makes justified content changes, the next run must be a full suite against the resulting content. Multiple commands may change content within that initial run. Stop if any command in the stabilization rerun or a later run changes content again.

If a run both fails and changes files, the next full suite serves as both repair verification and stabilization. Both limits still apply; a stabilization rerun without failure-repair edits consumes no repair attempt. Post-commit checks follow **Verify commit** instead of these retry limits.

## For each review pass

A pass becomes permanently **non-clean** if its review is not accepted, any finding is verified, or reviewed content changes (even if later reverted). Reset the consecutive-clean count to zero as soon as any of these occurs. Rejected findings alone do not affect the count.

### Launch reviewer

Increment the pass count, record the current commit, and mark the pass provisionally clean. Launch a new reviewer using the verified isolation mechanism and **Reviewer prompt**. Failed launches and incomplete reviews still consume a pass.

### Assess review

Wait for the reviewer to finish before editing. Accept only a completed review with no unresolved execution errors or material coverage gaps, as defined in **Reviewer prompt**.

If launch or review acceptance fails, do not edit, run checks, or commit in that pass. If available capabilities can address the problem, skip to **Retire reviewer**; otherwise stop.

### Validate and fix findings

Validate each finding against the reviewed commit. Record the reason for each rejection. Fix verified findings and add regression tests where appropriate.

Resolve all verified findings before proceeding. Use user instructions and repository guidance for routine decisions; stop and identify any missing requirements, authorization, or consequential choice that cannot be inferred. Fixing review findings has no separate attempt limit; repairs prompted by failing checks follow **Check execution rules**. Stop if no evidence-backed next step remains, attempts repeat without progress, or a finding cannot be resolved within scope.

### Check and stage content

Unless the no-checks exception applies, require a passing full suite that made no content changes, even on passes with no fixes. Reuse a result only from the current pass and only while content remains unchanged; otherwise rerun the full suite.

If fixes exist, stage only those fixes. Verify that the staged files match the checked content, with no unstaged tracked changes or unexplained non-ignored files. Record the staged Git tree ID using `git write-tree` and associate it with the check results or exception. Keep this content unchanged until committing; handle hook changes in **Verify commit**.

### Commit fixes

Apply the run invariants. If fixes exist, verify that the staged tree still matches the recorded tree ID, then commit to the starting branch. Otherwise, proceed to **Retire reviewer** without creating an empty commit.

If the commit command fails, including hook rejection, stop. Inspect and report HEAD, the index, and working tree so the user knows whether a commit was created and what remains uncommitted. Do not repair, retry the commit, or bypass hooks.

### Verify commit

Require a clean working tree and a new commit whose sole parent is the expected local HEAD and whose changes are all intended. Compare its tree ID (`git rev-parse 'HEAD^{tree}'`) with the recorded staged tree ID:

- If they match, the recorded check results apply.
- If they differ, verify that hooks caused the differences and that they remain within the intended fix, then run a full suite against the new commit unless the no-checks exception applies.

Stop if any requirement cannot be verified, or if post-commit checks fail or change content. Do not repair or retry failed verification. Advance the expected local HEAD only after verification succeeds.

### Retire reviewer

Stop the reviewer if it is still running, then close it using the supported lifecycle mechanism. If no close operation exists, consider the reviewer retired and never reuse or resume it for another pass.

### Count clean passes

Increment the consecutive-clean count if the pass remains clean and has satisfied **Check and stage content**. Then apply **Completion and limits**.

## Completion and limits

- When the consecutive-clean count reaches two, apply the run invariants. Verify that both passes reviewed the same unchanged commit and the working tree is clean. If verification succeeds, finish as **completed**; otherwise stop.
- If success has not been achieved by the end of pass 10, stop. Otherwise start the next pass.

On every exit, retire any remaining reviewer, preserve local commits and uncommitted changes, and produce the **Final report**.

A blocked run cannot resume. The user must resolve the blocker and restore a clean local working tree before launching a new run under **Launch requirements** and **Preparation**.

## Final report

- Outcome: completed or blocked. If blocked, explain the blocker and what must be resolved before a new run.
- Starting branch and final commit. Mark unavailable or unverified Git values explicitly and explain why.
- Fixes, checks and their results (or the no-checks exception), review coverage, and remaining limitations.
- Total review passes and consecutive clean passes.
- Local commits created during the run, any uncommitted changes, and whether all operations stayed local.

Do not claim that the repository is guaranteed bug-free.
