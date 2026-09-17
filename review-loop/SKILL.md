---
name: review-loop
description: Run repeated independent whole-repository reviews with verified fixes, required checks, and explicitly authorized local commits to the starting branch, leaving pushes to the human. Use only when explicitly invoked to run this review loop.
---

# Review Loop

Coordinate independent whole-repository reviews, fix verified issues, run checks, and commit fixes locally to the branch checked out at launch. Finish after two consecutive clean reviews of the same unchanged commit, within 10 attempted passes. Use the host's built-in subagents as reviewers.

## Launch authorization

Before starting, require explicit authorization for this run to make ordinary commits to the branch checked out at launch, for example: "I authorize ordinary commits to the current branch." Invoking the skill alone does not grant authorization. If authorization is absent or ambiguous, request it and wait before starting. Authorization supplied in the launch prompt or a follow-up applies to all ordinary commits in this run; do not reconfirm each commit. Respect required platform approvals.

Throughout the run, do not push, rewrite history, bypass branch protection, modify remote configuration or remote branches, include unrelated work, or weaken tests/checks. Fetching to refresh remote-tracking references is permitted.

## First, check capabilities

- Verify that the available tools support a new reviewer for each pass with no inherited coordinator or previous reviewer conversation. Use a documented isolation mechanism, such as `collaboration.spawn_agent` with `fork_turns: "none"` when its current documentation confirms this behavior.
- A tool name, default spawning behavior, separate task, or instruction to "ignore previous context" does not establish isolation. If fresh context cannot be verified, stop as blocked before editing and explain the limitation.
- Do not install or invoke a separate Codex or Claude Code CLI for this workflow.

## Preparation

### Starting-state requirements

- Follow AGENTS.md, CLAUDE.md, and the repository's instructions.
- Record the currently checked-out branch as the starting branch and record its configured GitHub upstream (remote, remote URL, and destination branch). Any branch, including main, is supported.
- Stop if HEAD is detached, the working tree is not clean, or the branch has no configured upstream.
- Establish that the configured remote identifies a GitHub repository. Both GitHub.com and GitHub Enterprise are supported. Use the resolved URL for GitHub.com, or existing project documentation or authenticated host metadata for an Enterprise host. Resolve SSH aliases or URL rewrites when present; a suggestive hostname alone is insufficient evidence for Enterprise. Stop if the host or repository identity cannot be established.
- Verify that the configured destination branch exists on that remote using a live remote query or fetch. Refresh its remote-tracking reference using the existing configuration and confirm that it matches the live destination branch. A cached remote-tracking reference alone is insufficient.
- Verify that the starting branch resolves to exactly the same commit as the live destination branch. Stop if the branch is missing, remote access fails, or the commits differ.
- Record the starting commit as both the expected local HEAD and the expected upstream commit.
- The user manages branches: never create or switch branches, discard work, or change upstream configuration to make the preconditions pass.
- Identify required test, lint, type-check, and build commands from project requirements. If none are specified, select relevant available checks and state their scope. Below, **checks** means all required or selected checks; both follow the same rules.
- If no checks are required and no relevant runnable checks exist, record the **no-checks exception**. The loop may succeed based on reviews alone, with this limitation disclosed in the final report. A required or selected check that cannot run is a blocker, not an absence of checks.
- Track the number of review passes, the consecutive clean-review count, and the commit reviewed in each pass. Start both counters at zero.
- Keep coordinator findings, fix explanations, and review logs out of the committed codebase. Use only the **Reviewer prompt** below to brief reviewers.

### Invariants during the run

- Before each review, before editing or committing, and at completion, verify the starting branch is still checked out, its upstream configuration is unchanged, and HEAD matches the expected local HEAD. Stop as blocked on any mismatch; do not switch back or adopt the new state. Advance the expected local HEAD only after this loop creates and verifies a commit.
- At every upstream refresh, repeat preparation's live remote and remote-tracking verification. The upstream must still match the expected upstream commit, fixed at the starting commit throughout the run. Local fix commits may put HEAD ahead of it.
- Stop on unexpected commits or unrelated working-tree changes; do not merge, rebase, reset, or adopt outside changes to continue.
- Before any early exit, follow **Retire reviewer** for any launched reviewer that has not yet been retired.

## Reviewer prompt

Use the following prompt for each reviewer, filling in the repository location, exact commit, applicable project requirements, and relevant user requirements or constraints. Summarize user requirements without including prior findings, fix explanations, or conversation history. Use "None specified" when there are no additional user requirements.

```text
Repository: <repository location>
Commit to review: <exact commit SHA>
Applicable project requirements: <requirements or their locations>
Applicable user requirements and constraints: <self-contained summary or None specified>

Perform a read-only review of the WHOLE codebase at this exact commit,
including committed source, tests, configuration, and scripts. Inspect
committed files, not an uncommitted working-tree snapshot. Do not limit
the review to a Git diff or recent changes. Follow applicable project
instructions.

Inventory generated files, vendored dependencies, binaries, and submodules.
Review their integration and relevant correctness or security risks; inspect
submodules at their recorded commits when available. You may omit detailed
inspection of generated or vendored content when reviewing its maintained
inputs or integration is sufficient. List each excluded category or path,
the reason, and any residual coverage gap. Unavailable content is a coverage
gap to assess, not an automatic exclusion from scope.

Use static inspection only. Do not execute tests, builds, or repository
scripts; the coordinator runs checks after the review. You may use read-only
inspection commands to examine committed content.

Do not consult earlier review artifacts, modify files, switch or create
branches, change commits, or alter remote state.

Report concrete, actionable findings with file/line references, triggering
scenarios, and impact. Do not request cosmetic changes or speculative
refactoring. If you find no actionable issues, say so explicitly.

State what you reviewed and anything you could not inspect. A material
coverage gap is an unreviewed component or behavior that could materially
affect correctness or security. Explain the potential impact of each gap
so the coordinator can assess whether it prevents a clean pass.
```

## For each review pass

Follow these phases in order unless a phase explicitly directs otherwise.

### Launch reviewer

Increment the pass count, record the current commit, and initialize this pass's non-clean flag to false. Marking a pass non-clean immediately resets the consecutive-clean count to zero and keeps the flag true for the rest of the pass. Any change to reviewed content marks the pass non-clean, even if the original content is later restored. Launch a new reviewer using the verified fresh-context mechanism and only the completed **Reviewer prompt**. Do not pass the entire skill or coordinator instructions.

### Assess review

Wait for the reviewer to finish before editing. Inspect its output for errors, completeness, and coverage, and assess the potential impact of any reported gaps.

If the review has an error, missing output, is incomplete, or has a material coverage gap, mark the pass non-clean. Follow **Retire reviewer**. If a fresh review can address the problem with available capabilities and the pass limit allows another review, return to **Launch reviewer** without editing or committing in this pass. Otherwise, stop as blocked and explain the problem. For a complete review with no material coverage gaps, continue to **Validate and fix findings**.

### Validate and fix findings

Validate each finding against the reviewed commit. Record why any finding is rejected; a rejected finding alone does not prevent a clean pass. Mark the pass non-clean if any finding is verified, fix it, and add regression tests where appropriate. Checks run during this phase must follow **Run and inspect checks**, including both per-pass limits.

Make routine implementation decisions using the user's instructions and repository guidance. If a fix requires missing requirements, additional authorization, or a consequential choice that cannot be inferred from that guidance, stop as blocked and identify the input needed before making the decision. Review-finding fixes have no separate numeric attempt limit: use judgment while an evidence-backed fix is making progress. Stop as blocked if no evidence-backed next step remains, attempts repeat without progress, or a verified finding cannot be resolved within the authorized scope. Do not continue with unresolved verified findings. This discretion does not override the check limits below.

### Run and inspect checks

Run all checks, including on passes with no fixes, unless the recorded no-checks exception applies.

A **check execution** is one check command. A **suite run** is either a full run of all checks against the current content or a partial run consisting of one targeted check. Both are subject to the limits below; only a full run can establish that all checks pass.

For every check execution, compare repository status and content before and after execution, regardless of exit status. Inspect every change to tracked files and every new non-ignored file; retain it only when justified by the intended fix. Stop as blocked on unrelated or unexplained changes and preserve them for the user.

Two independent limits apply across the entire pass, including checks run during **Validate and fix findings**:

- **Failure repairs: at most two attempts.** If a full or partial run fails because of a verified repository issue, count one repair attempt when changes addressing an identified failure cause begin. The next check execution after the repair must begin a new full suite run. The initial failed run does not itself consume an attempt. Stop if no evidence-backed repair is available or checks still fail after the second attempt.
- **Changes made by checks: one stabilization rerun.** The first suite run that makes justified content changes requires the next run to be a full stabilization rerun against the resulting content. Multiple check commands may make justified changes within that initial suite run; they collectively use one allowance. If any check execution in the stabilization rerun or any later suite run in this pass changes content again, stop as blocked. Repairs or transitions between phases do not reset this allowance.

If a suite run both fails and changes files, apply both rules: inspect its changes, make an evidence-backed repair if an attempt remains, then run the full check suite. That rerun counts as both the repair attempt's verification and the stabilization rerun. A stabilization rerun without a failure repair consumes no repair attempt. Stop as soon as either limit requires it, even if the other has capacity left. Do not start another review pass to reset either limit. Post-commit checks follow **Verify commit**, which permits no repairs.

### Record checked content

Once checks pass without further content changes, or the no-checks exception applies, stage only intended fixes. Verify that the staged files match the working-tree content used by the checks, with no unstaged tracked changes or unexplained non-ignored files. Record the staged Git tree ID using `git write-tree` and associate it with the check results or no-checks exception. Do not modify the checked content after recording it.

### Commit fixes

Recheck the branch, upstream configuration, and expected local HEAD; refresh and recheck the upstream, stopping on unexpected remote changes. If fixes exist, verify that the staged tree still matches the recorded tree ID, then commit to the starting branch under the launch authorization. Do not create empty commits. If there are no fixes, skip **Verify commit** and continue to **Retire reviewer**.

If the commit command fails, including rejection by a commit hook before HEAD changes, stop as blocked. Inspect and report HEAD, the index, and working-tree changes so the user knows whether a commit was created and what remains uncommitted. Preserve that state; do not repair, retry the commit, or bypass hooks in this run.

### Verify commit

Verify that the new commit has the expected previous HEAD as its sole parent and contains only intended changes. Compare its tree ID (`git rev-parse 'HEAD^{tree}'`) with the recorded staged tree ID. If they match and the working tree is clean, the recorded check results apply.

If commit hooks changed the committed content, inspect the differences for intended scope and rerun all required or selected checks against the resulting commit, subject to the recorded no-checks exception. Stop as blocked if differences cannot be attributed to hooks, hooks leave uncommitted changes, verification checks fail or change repository content, or the resulting commit or checks cannot be verified. Do not repair or retry a failed post-commit verification. Update the expected local HEAD only after all applicable verification succeeds.

### Retire reviewer

Stop the reviewer if it is still running, then close it using the supported lifecycle mechanism. If no close operation exists, consider the reviewer retired and never reuse or resume it for another pass. On an early exit, proceed directly to **Final report** after cleanup. Otherwise, when **Assess review** directed retirement, follow that phase's retry-or-stop decision; for a completed pass, continue to **Count clean passes**.

### Count clean passes

Increment the consecutive-clean count only if the pass's non-clean flag is false, the review is complete with no material coverage gaps, validation found no verified issues, checks pass (or the recorded no-checks exception applies), and the reviewed commit and content remain unchanged. Otherwise mark the pass non-clean. A fix commit needs a new review. Changes between passes also reset the count, even if later reverted; unexpected changes trigger the run invariants.

Apply **Completion and limits** to decide whether to finish or return to **Launch reviewer**.

## Completion and limits

- Every attempted review counts toward the 10-pass limit, including errors, missing output, and incomplete reviews.
- When the consecutive-clean count reaches two, verify that both passes reviewed the same unchanged commit, the working tree is clean, local HEAD matches the expected local HEAD, and the refreshed GitHub upstream still matches the recorded starting commit. Stop successfully only if all conditions hold; otherwise stop as blocked. Local fix commits awaiting a human push are compatible with successful completion.
- If success has not been achieved by the end of pass 10, stop as blocked. Otherwise start the next pass, unless an earlier phase or invariant requires stopping. Do not continue retrying after a stopping rule applies.

## After a blocked run

A blocked run ends the loop; it does not resume with its old counters or recorded Git state. Preserve and report any local commits and uncommitted fixes. To try again, the user must resolve the blocker, handle any remaining changes, and synchronize the branch with its GitHub upstream before explicitly launching a new run with commit authorization. The new run repeats preparation and starts both counters at zero. Never push or discard changes to prepare that new run yourself.

## Final report

Include:

- Outcome: completed or blocked, with the blocker if applicable.
- Starting branch, recorded upstream, and final commit. Report Git values only when established; mark unavailable or unverified values explicitly and explain why, including when preparation stopped early.
- Fixes, checks and their results, review coverage, and remaining limitations.
- Total review passes and consecutive clean passes.
- Confirmation that the loop did not push, known local commits awaiting a human push, and any uncommitted changes.
- Whether HEAD matches, is ahead, is behind, or has diverged from the upstream, when local HEAD and a refreshed upstream are both verified.

Do not claim that the repository is guaranteed bug-free.
