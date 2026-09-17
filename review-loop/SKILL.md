---
name: review-loop
description: Run repeated independent whole-repository reviews with verified fixes, required checks, and explicitly authorized local commits to the starting branch, leaving pushes to the human. Use only when explicitly invoked to run this review loop.
---

# Review Loop

Run repeated whole-repository code reviews, fix verified issues, run checks, and commit fixes locally to the branch checked out at launch. Aim for two consecutive independent clean reviews within 10 passes. The sections below define clean passes, completion conditions, and stopping rules.

You are the coordinator and fixer. Use the app's built-in subagents for independent reviews. This skill is explicit-invocation-only.

## Launch authorization

Before starting the loop, verify that the user has explicitly authorized this run to make ordinary commits to the branch checked out at launch. Invoking this skill alone is not authorization, and these stored instructions do not grant authorization. Authorization may be supplied in the launch prompt or a follow-up for this run. If commit authorization is absent or ambiguous, request it before starting the loop; resume only after it is supplied.

An acceptable authorization in the user's launch prompt is: "I authorize ordinary commits to the current branch." Once provided for this run, do not request redundant confirmation for each authorized commit. Respect required platform approvals.

Throughout the run, do not push, rewrite history, bypass branch protection, modify remote configuration or remote branches, include unrelated work, or weaken tests/checks. Fetching to refresh remote-tracking references is permitted.

## First, check capabilities

- Verify that you can launch a NEW reviewer subagent for each pass without inheriting the coordinator's conversation or any previous reviewer conversations.
- Use an actual fresh-context mechanism supported and documented by the available tools. For example, use `collaboration.spawn_agent` with `fork_turns: "none"` only when the current tool documentation verifies that this omits surrounding conversation history. In other hosts, use the equivalent fresh-context mechanism only if the available tool documentation establishes its isolation. Do not assume a tool name, subagent type, or default spawning behavior provides isolation.
- Telling an existing agent to "ignore previous context" does not count. A separate task or thread does not necessarily have cleared context.
- If genuinely fresh reviewer context cannot be provided or verified, stop before editing and explain the limitation. Never substitute an unverified reviewer or claim independence without evidence.
- Do not install or invoke a separate Codex or Claude Code CLI for this workflow.

## Preparation

### Starting-state requirements

- Follow AGENTS.md, CLAUDE.md, and the repository's instructions.
- Record the currently checked-out branch as the starting branch and record its configured GitHub upstream (remote, remote URL, and destination branch). Any branch, including main, is supported.
- Stop if HEAD is detached, the working tree is not clean, or the branch has no configured upstream. Both GitHub.com and GitHub Enterprise are supported. Establish that the configured remote identifies a GitHub repository: use its resolved URL for GitHub.com, or existing project documentation or authenticated host metadata for an Enterprise host. Resolve SSH aliases or URL rewrites when present; a suggestive hostname alone is insufficient evidence for Enterprise. Stop if the host or repository identity cannot be established.
- Verify that the configured destination branch exists on that remote using a live remote query or fetch. Refresh its remote-tracking reference using the existing configuration, confirm that it matches the live destination branch, and verify that the starting branch resolves to exactly the same commit. Stop if the branch is missing, remote access fails, or the commits differ; a cached remote-tracking reference alone is insufficient. For later upstream refreshes, repeat the live remote and remote-tracking verification, but compare the upstream with the fixed expected upstream commit under **Invariants during the run**; local HEAD may then be ahead because of this loop’s verified fix commits.
- Record the starting commit as both the expected local HEAD and the expected upstream commit.
- The user manages branches: never create or switch branches, discard work, or change upstream configuration to make the preconditions pass.
- Identify the required test, lint, type-check, and build commands from applicable project requirements. If none are specified, select relevant available checks and state their scope; do not invent mandatory commands. Run the selected checks under the same pass/fail rules as required checks. If no checks are required and no relevant runnable checks exist, record that fact; the loop may succeed based on reviews alone, with this limitation disclosed in the final report. A required check that cannot run is a blocker, not an absence of checks.
- Track the number of review passes, the consecutive clean-review count, and the commit reviewed in each pass. Start both counters at zero. Keep coordinator findings, fix explanations, and review logs out of reviewer prompts and out of the committed codebase.

### Invariants during the run

- Keep the starting branch and recorded upstream fixed for the entire run. Before each review, before editing or committing, and at completion, verify that the same branch is still checked out and its upstream configuration is unchanged. If either changes, stop as blocked without switching back or continuing on the newly checked-out branch.
- Before each review, before editing or committing, and at completion, verify local HEAD against the expected local HEAD. Advance that expectation only after this loop creates and verifies a commit.
- On remote refreshes, compare the upstream against the expected upstream commit, which remains fixed at the starting commit throughout the run. Local fix commits are expected to put the branch ahead of that upstream.
- Stop on unexpected commits or unrelated working-tree changes; do not merge, rebase, reset, or adopt outside changes to continue.

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

Increment the pass count and record the current commit. Launch a NEW, read-only reviewer with verified fresh conversation context using only the completed Reviewer prompt above. Do not pass the entire skill or its coordinator, editing, or commit instructions to the reviewer. Do not provide prior findings, fix explanations, review logs, or conversation history.

### Assess review

Wait for the reviewer to finish before editing. Inspect its output for errors, completeness, and coverage, and assess the potential impact of any reported gaps.

If the review has an error, missing output, is incomplete, or has a material coverage gap, mark the pass non-clean and reset the consecutive-clean count. Follow **Retire reviewer**. If a fresh review can address the problem with available capabilities and the pass limit allows another review, return to **Launch reviewer** without editing or committing in this pass. Otherwise, stop as blocked and explain the problem. For a complete review with no material coverage gaps, continue to **Validate and fix findings**.

### Validate and fix findings

Validate each finding against the reviewed commit. Record why any finding is rejected; a rejected finding alone does not prevent a clean pass. Fix genuine issues and add regression tests where appropriate. Any required or selected checks run during this phase must follow **Run and inspect checks**, including both per-pass limits.

Make routine implementation decisions using the user's instructions and repository guidance. If a fix requires missing requirements, additional authorization, or a consequential choice that cannot be inferred from that guidance, stop as blocked and identify the input needed before making the decision. Review-finding fixes have no separate numeric attempt limit: use judgment while an evidence-backed fix is making progress. Stop as blocked if no evidence-backed next step remains, attempts repeat without progress, or a verified finding cannot be resolved within the authorized scope. Do not continue with unresolved verified findings. This discretion does not override the check limits below.

### Run and inspect checks

Run all required or selected checks, including on passes with no fixes. If preparation established the no-checks exception, continue with that recorded limitation. A required or selected check that cannot run is a blocker.

For every check run, compare repository status and content before and after execution, regardless of exit status. Inspect every change to tracked files and every new non-ignored file; retain it only when justified by the intended fix. Stop as blocked on unrelated or unexplained changes and preserve them for the user.

Two independent limits apply across the entire pass, including checks run during **Validate and fix findings**:

- **Failure repairs: at most two attempts.** If checks fail because of a verified repository issue, a repair attempt consists of changes addressing an identified failure cause followed by a rerun of all required or selected checks. The initial failed run does not itself consume an attempt. Stop if no evidence-backed repair is available or checks still fail after the second attempt.
- **Changes made by checks: one stabilization rerun.** The first run that makes justified content changes marks the pass non-clean and requires a rerun of all required or selected checks against the resulting content. If that rerun or any later check run in this pass changes content again, stop as blocked. Repairs or transitions between phases do not reset this allowance.

If a run both fails and changes files, apply both rules: inspect its changes, make an evidence-backed repair if an attempt remains, then run the full check suite. That rerun counts as both the repair attempt's verification and the stabilization rerun. A stabilization rerun without a failure repair consumes no repair attempt. Stop as soon as either limit requires it, even if the other has capacity left. Do not start another review pass to reset either limit. Post-commit checks follow **Verify commit**, which permits no repairs.

### Record checked content

Once checks pass without further content changes, or the no-checks exception applies, stage only intended fixes. Verify that the staged files match the working-tree content used by the checks, with no unstaged tracked changes or unexplained non-ignored files. Record the staged Git tree ID using `git write-tree` and associate it with the check results or no-checks exception. Do not modify the checked content after recording it.

### Commit fixes

Recheck the branch, upstream configuration, and expected local HEAD; refresh and recheck the upstream, stopping on unexpected remote changes. If fixes exist, verify that the staged tree still matches the recorded tree ID, then commit to the starting branch under the launch authorization. Do not create empty commits. If there are no fixes, skip **Verify commit** and continue to **Retire reviewer**.

### Verify commit

Verify that the new commit has the expected previous HEAD as its sole parent and contains only intended changes. Compare its tree ID (`git rev-parse 'HEAD^{tree}'`) with the recorded staged tree ID. If they match and the working tree is clean, the recorded check results apply.

If commit hooks changed the committed content, inspect the differences for intended scope and rerun all required or selected checks against the resulting commit, subject to the recorded no-checks exception. Stop as blocked if differences cannot be attributed to hooks, hooks leave uncommitted changes, verification checks fail or change repository content, or the resulting commit or checks cannot be verified. Do not repair or retry a failed post-commit verification. Update the expected local HEAD only after all applicable verification succeeds.

### Retire reviewer

Close the finished reviewer using the supported lifecycle mechanism. If no close operation exists, retire the completed reviewer and never reuse or resume it for another pass. When **Assess review** directed retirement, follow that phase's retry-or-stop decision; otherwise continue to **Count clean passes**.

### Count clean passes

Increment the consecutive-clean count only if the review is complete, validation leaves no genuine findings, there are no material coverage gaps, all required or selected checks pass (or the recorded no-checks exception applies), and the reviewed commit and its content remain unchanged. Otherwise reset it to zero. A pass that produces fixes is never clean; its resulting commit needs a new review. Any change during or between passes to reviewed content, including tests, configuration, or scripts, resets the count.

Apply **Completion and limits** to decide whether to finish or return to **Launch reviewer**.

## Completion and limits

- Every attempted review counts toward the 10-pass limit, including errors, missing output, and incomplete reviews.
- When the consecutive-clean count reaches two, verify that both passes reviewed the same unchanged commit, the working tree is clean, local HEAD matches the expected local HEAD, and the refreshed GitHub upstream still matches the recorded starting commit. Stop successfully only if all conditions hold; otherwise stop as blocked. Local fix commits awaiting a human push are compatible with successful completion.
- If success has not been achieved by the end of pass 10, stop as blocked. Otherwise start the next pass, unless an earlier phase or invariant requires stopping. Do not continue retrying after a stopping rule applies.

## After a blocked run

A blocked run ends the loop; it does not resume with its old counters or recorded Git state. Preserve and report any local commits and uncommitted fixes. To try again, the user must resolve the blocker, handle any remaining changes, and synchronize the branch with its GitHub upstream before explicitly launching a new run with commit authorization. The new run repeats preparation and starts both counters at zero. Never push or discard changes to prepare that new run yourself.

## Final report

Report the starting branch and its recorded upstream, final commit, fixes, checks and their results, review coverage, pass count and consecutive clean passes, remaining limitations, and whether the goal completed or was blocked. Report Git values only when established; mark unavailable or unverified values explicitly and explain why, including when preparation stopped early. State that the loop did not push and list any known local commits awaiting a human push. When local HEAD and a refreshed upstream are both verified, report whether HEAD matches, is ahead, is behind, or has diverged from that upstream. If blocked, explain the blocker and any known local or unpushed changes. Do not claim that the repository is guaranteed bug-free.
