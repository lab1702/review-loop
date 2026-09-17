---
name: review-loop
description: Run repeated independent whole-repository reviews with verified fixes, required checks, and explicitly authorized local commits to the starting branch, leaving pushes to the human. Use only when explicitly invoked to run this review loop.
---

# Review Loop

Run repeated whole-repository code reviews, fix verified issues, run checks, commit fixes to the branch checked out at launch, and leave all pushes to the human. Never push as part of this loop. Finish after two consecutive independent reviews of the same unchanged commit leave no validated actionable findings or material coverage gaps, and all required or selected checks pass, subject to the documented no-checks exception. A pass that changes the reviewed content is never clean.

You are the coordinator and fixer. Use the app's built-in subagents for independent reviews. This skill is explicit-invocation-only.

## Launch authorization

Before starting the loop, verify that the user has explicitly authorized this run to make ordinary commits to the branch checked out at launch. Invoking this skill alone is not authorization, and these stored instructions do not grant authorization. Authorization may be supplied in the launch prompt or a follow-up for this run. If commit authorization is absent or ambiguous, request it before starting the loop; resume only after it is supplied.

An acceptable authorization in the user's launch prompt is: "I authorize ordinary commits to the current branch." Once provided for this run, do not request redundant confirmation for each authorized commit. Respect required platform approvals.

Do not push, rewrite history, bypass branch protection, modify remote configuration or remote branches, or include unrelated work. Fetching to refresh remote-tracking references is permitted.

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
- Stop if HEAD is detached, the working tree is not clean, or the branch has no verifiable existing GitHub upstream. Refresh the remote state using the existing configuration and verify that the starting branch and upstream resolve to exactly the same commit; do not rely on a stale remote-tracking reference. Stop on a mismatch.
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

1. Increment the pass count and record the current commit. Launch a NEW, read-only reviewer with verified fresh conversation context using only the completed Reviewer prompt above. Do not pass the entire skill or its coordinator, editing, or commit instructions to the reviewer. Do not provide prior findings, fix explanations, review logs, or conversation history.
2. Wait for the reviewer to finish before editing. Inspect its output for errors, completeness, and coverage, and assess the potential impact of any reported gaps.
3. If the review has an error, missing output, is incomplete, or has a material coverage gap, mark the pass non-clean and reset the consecutive-clean count. Close or retire the reviewer as described in step 6. If a fresh review can address the problem with available capabilities and fewer than 10 passes have been attempted, start the next pass at step 1 without editing or committing in this pass. Otherwise, stop as blocked and explain the problem. For a complete review with no material coverage gaps, proceed to step 4.
4. Validate each finding against the reviewed commit. Record why any finding is rejected; a rejected finding alone does not prevent a clean pass. Fix genuine issues and add regression tests where appropriate. Any required or selected checks run during this step are subject to the same per-pass repair limit defined in step 5. Do not weaken tests or checks. Make routine implementation decisions using the user's instructions and repository guidance. If a fix requires missing requirements, additional authorization, or a consequential choice that cannot be inferred from that guidance, stop as blocked and identify the input needed before making the decision. Review-finding fixes have no separate numeric attempt limit: use judgment while an evidence-backed fix is making progress. Stop as blocked if no evidence-backed next step remains, attempts repeat without progress, or a verified finding cannot be resolved within the authorized scope. Do not proceed to step 5 with unresolved verified findings. This discretion does not override the check-repair limit in step 5.
5. Check the resulting state, commit any fixes, and verify the commit in this order:

   1. **Run checks.** Run all required or selected checks, including on passes with no fixes. If preparation established the no-checks exception, proceed with that recorded limitation. A required or selected check that cannot run is a blocker.

   2. **Handle check failures.** If checks fail because of a verified repository issue, allow at most two repair attempts in total across this pass, including checks run during step 4. A repair attempt is a set of changes addressing an identified cause of a check failure, followed by a rerun of all required or selected checks. Count from the first such failure; entering a new step does not reset the count. Stop as blocked if checks still fail after the second attempt or no evidence-backed repair is available. Do not start another review pass to reset this limit. Post-commit verification permits no additional repairs.

   3. **Inspect changes made by checks.** Compare repository status and content before and after checks, including checks run during step 4. A successful exit alone does not validate files changed by a formatter, build, or other check. Inspect every change to tracked files and every new non-ignored file; retain it only when it is justified by the intended fix. Stop as blocked on unrelated or unexplained changes and preserve them for the user. If justified changes occur, mark the pass non-clean and rerun all required or selected checks against the resulting content. If that rerun changes repository content again, stop as blocked rather than repeatedly chasing generated changes. Any check failure remains subject to the shared two-attempt repair limit.

   4. **Record the checked content.** Once checks pass without further content changes, or the no-checks exception applies, stage only intended fixes. Verify that the staged files match the working-tree content used by the checks, with no unstaged tracked changes or unexplained non-ignored files. Record the staged Git tree ID using `git write-tree` and associate it with the check results or no-checks exception. Do not modify the checked content after recording it.

   5. **Commit fixes.** Recheck the branch, upstream configuration, and expected local HEAD; refresh and recheck the upstream, stopping on unexpected remote changes. If fixes exist, verify that the staged tree still matches the recorded tree ID, then commit to the starting branch under the launch authorization. Do not create empty commits. If there are no fixes, proceed to step 6 of the review pass.

   6. **Verify the commit.** Verify that the new commit has the expected previous HEAD as its sole parent and contains only intended changes. Compare its tree ID (`git rev-parse 'HEAD^{tree}'`) with the recorded staged tree ID. If they match and the working tree is clean, the recorded check results apply. If commit hooks changed the committed content, inspect the differences for intended scope and rerun all required or selected checks against the resulting commit, subject to the recorded no-checks exception. Stop as blocked if differences cannot be attributed to hooks, hooks leave uncommitted changes, verification checks fail or change repository content, or the resulting commit or checks cannot be verified. Do not repair or retry a failed post-commit verification. Update the expected local HEAD only after all applicable verification succeeds. Keep all fix commits local for the human to push; unpushed fix commits do not block the loop.

6. Close the finished reviewer using the supported lifecycle mechanism. If no close operation exists, retire the completed reviewer and never reuse or resume it for another pass. Start a NEW reviewer with verified fresh conversation context for every subsequent pass; do not include earlier review results.
7. Update the consecutive-clean count. Increment it only if the review is complete, validation leaves no genuine findings, there are no material coverage gaps, all required or selected checks pass (or the recorded no-checks exception applies), and the reviewed commit and its content remain unchanged. Otherwise reset it to zero. A pass that produces fixes is never clean; its resulting commit needs a new review. Any change during or between passes to reviewed content, including tests, configuration, or scripts, resets the count.
8. If the count reaches two, verify the completion conditions below and stop successfully only if they all hold; otherwise stop as blocked. If fewer than two clean passes have accumulated and this was pass 10, stop as blocked. Otherwise begin the next pass at step 1.

## Completion and limits

- Every attempted review counts toward the 10-pass limit, including errors, missing output, and incomplete reviews. Handle these and material coverage gaps through step 3; handle failing or unavailable checks through step 5. An unavailable required or selected check never qualifies for the no-checks exception.
- Stop successfully after two consecutive clean passes on the same unchanged commit, with a clean working tree, local HEAD matching the expected local HEAD, and the refreshed GitHub upstream still matching the recorded starting commit. Local fix commits awaiting a human push are compatible with successful completion.
- Run at most 10 review passes. If success has not been achieved by the end of pass 10, stop as blocked. Stop earlier on verified findings that remain unresolved after step 4, unavailable permissions, unexpected remote changes, or missing user input as defined in step 4. Do not continue retrying beyond these limits.
- Preserve the safety guardrails throughout the loop: no pushes, history rewriting, branch-protection bypass, modifications to remote configuration or remote branches, unrelated work, or weakened tests/checks. Fetching to refresh remote-tracking references is permitted.

## After a blocked run

A blocked run ends the loop; it does not resume with its old counters or recorded Git state. Preserve and report any local commits and uncommitted fixes. To try again, the user must resolve the blocker, handle any remaining changes, and synchronize the branch with its GitHub upstream before explicitly launching a new run with commit authorization. The new run repeats preparation and starts both counters at zero. Never push or discard changes to prepare that new run yourself.

## Final report

Report the starting branch and its recorded upstream, final commit, fixes, checks and their results, review coverage, pass count and consecutive clean passes, remaining limitations, and whether the goal completed or was blocked. Report Git values only when established; mark unavailable or unverified values explicitly and explain why, including when preparation stopped early. State that the loop did not push and list any known local commits awaiting a human push. When local HEAD and a refreshed upstream are both verified, report whether HEAD matches, is ahead, is behind, or has diverged from that upstream. If blocked, explain the blocker and any known local or unpushed changes. Do not claim that the repository is guaranteed bug-free.
