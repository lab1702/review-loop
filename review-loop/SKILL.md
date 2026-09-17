---
name: review-loop
description: Run independent whole-repository reviews with verified fixes, checks, and authorized local commits. Use only when explicitly invoked to run this review loop.
---

# Review Loop

Use the host's built-in subagents to review the whole repository, fix verified issues, run checks, and commit fixes locally to the starting branch. Finish after two consecutive clean reviews of the same unchanged commit, within 10 attempted passes.

## Launch authorization

Require explicit authorization for ordinary commits in this run, for example: "I authorize ordinary commits to the current branch." Invoking the skill alone does not grant authorization. If authorization is absent or ambiguous, request it and wait before starting. Authorization in the launch prompt or a follow-up covers all ordinary commits in this run; do not reconfirm each commit. Respect required platform approvals.

Throughout the run, do not push, rewrite history, bypass branch protection, modify remote configuration or remote branches, include unrelated work, or weaken tests/checks. Fetching to refresh remote-tracking references is permitted.

## First, check capabilities

- Verify a documented mechanism for launching each reviewer without inheriting coordinator or previous reviewer conversation, such as `collaboration.spawn_agent` with `fork_turns: "none"` when supported by its current documentation. A separate task or an instruction to "ignore previous context" does not establish isolation. If isolation cannot be verified, stop before editing.
- Do not install or invoke a separate Codex or Claude Code CLI for this workflow.

## Preparation

### Starting-state requirements

- Follow AGENTS.md, CLAUDE.md, and the repository's instructions.
- Record the checked-out branch as the **starting branch** and its configured upstream (remote, remote URL, and destination branch). Any branch, including main, is supported.
- Stop if HEAD is detached, the working tree is not clean, or the branch has no configured upstream.
- Establish that the remote identifies a GitHub.com or GitHub Enterprise repository. Resolve SSH aliases and URL rewrites. For Enterprise, use project documentation or authenticated host metadata; a suggestive hostname alone is insufficient. Stop if the host or repository identity cannot be established.
- Perform an **upstream refresh**: verify the destination branch with a live remote query or fetch, refresh its remote-tracking reference using the existing configuration, and confirm both identify the same commit. Stop if the branch is missing, access fails, or the commits differ; a cached reference alone is insufficient.
- Require the starting branch to match that live upstream commit. Record it as both the **expected local HEAD** and the **expected upstream commit**. The expected upstream commit stays fixed throughout the run; local fix commits may put HEAD ahead of it.
- The user manages branches: never create or switch branches, discard work, or change upstream configuration to make the preconditions pass.
- Identify required test, lint, type-check, and build commands. If none are specified, select relevant available checks and state their scope. **Checks** means all required or selected checks.
- If no checks are required and no relevant runnable checks exist, record the **no-checks exception**: reviews alone may establish success, with this limitation disclosed in the final report. A required or selected check that cannot run is a blocker.
- Initialize the review-pass and consecutive-clean counters to zero.
- Keep coordinator findings, fix explanations, and review logs out of the committed codebase.

### Invariants during the run

- Before each review, before editing or committing, and at completion, verify that the starting branch is checked out, its upstream configuration is unchanged, and HEAD matches the expected local HEAD. Only **Verify commit** may advance the expected local HEAD.
- At every **upstream refresh**, require the live and remote-tracking commits to match the expected upstream commit.
- On any mismatch or unrelated working-tree change, stop. Do not switch back, merge, rebase, reset, or adopt outside changes to continue.
- Unless **Completion and limits** establishes success, any instruction to stop ends the run as blocked; do not start another pass to bypass it. On every exit, follow **Retire reviewer** for any reviewer not yet retired, preserve local commits and uncommitted changes, and produce the **Final report**.

## Reviewer prompt

Give each reviewer only the completed prompt below. Fill in the placeholders, summarizing relevant user requirements without relying on conversation history. Exclude prior findings, fix explanations, this skill, and coordinator instructions. Use "None specified" when there are no additional user requirements.

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

## Check execution rules

A **check execution** runs one check command. A **check run** is either the full suite of all checks against the current content or a single targeted check. Only a full suite can establish that all checks pass.

For every check execution, compare repository status and content before and after, regardless of exit status. Inspect every tracked-file change and new non-ignored file; retain only changes justified by the intended fix. Stop on unrelated or unexplained changes.

Before committing, two independent limits apply across the entire pass, including targeted checks:

- **Failure repairs: at most two attempts.** A failed check run requires an evidence-backed repair of a verified repository issue; otherwise stop. One attempt is a batch of repair edits followed by a full suite. Count it when edits begin; do not run targeted checks before that suite. The initial failed run consumes no attempt. Stop if checks still fail after the second attempt.
- **Changes made by checks: one stabilization rerun.** The first check run that makes justified content changes requires the next check run to be a full suite against the resulting content. Multiple check commands may change content within that initial run. If any check in the stabilization rerun or a later check run changes content again, stop.

If a check run both fails and changes files, inspect the changes, repair within the remaining allowance, then run the full suite. This counts as both repair verification and stabilization; stabilization alone consumes no repair attempt. Neither phase transitions nor repairs reset these limits, and either limit can stop the run independently. Post-commit checks follow **Verify commit**, which permits no repairs.

## For each review pass

Follow these phases in order unless a phase explicitly directs otherwise.

Marking a pass **non-clean** resets the consecutive-clean count to zero and is irreversible for that pass. Any change to reviewed content, including changes made by checks or later reverted, resets the count and marks an active pass non-clean. Unexpected changes trigger the run invariants.

### Launch reviewer

Increment the pass count, record the current commit, and initialize its non-clean flag to false. Launch a new reviewer using the verified isolation mechanism and the completed **Reviewer prompt**. Every launch attempt counts, including failed launches and incomplete reviews.

### Assess review

Wait for the reviewer to finish before editing. Require a complete review with no execution errors or material coverage gaps, as defined in the prompt.

If these criteria are not met or there is no output, mark the pass non-clean and follow **Retire reviewer** without editing or committing. Return to **Launch reviewer** only if available capabilities can address the problem and fewer than 10 passes have been attempted; otherwise stop. An acceptable review proceeds to **Validate and fix findings**.

### Validate and fix findings

Validate each finding against the reviewed commit. Record why any finding is rejected; rejection alone does not prevent a clean pass. For verified findings, mark the pass non-clean, fix them, and add regression tests where appropriate. Targeted checks follow **Check execution rules**.

Use user instructions and repository guidance for routine decisions. Stop if a fix needs missing requirements, additional authorization, or a consequential choice that cannot be inferred; identify the input needed. Resolve all verified findings before proceeding. Finding fixes have no separate numeric attempt limit, but stop if no evidence-backed next step remains, attempts repeat without progress, or a finding cannot be resolved within scope. The check limits still apply.

### Run full check suite

Run all checks under **Check execution rules**, including on passes with no fixes, unless the recorded no-checks exception applies.

### Record checked content

Once a full suite passes without content changes, or the no-checks exception applies, stage only intended fixes. Verify that the staged files match the checked content, with no unstaged tracked changes or unexplained non-ignored files. Record the staged Git tree ID using `git write-tree` and associate it with the results or exception. Do not modify this content before committing; hook changes are handled in **Verify commit**.

### Commit fixes

Apply the run invariants and perform an **upstream refresh**. If fixes exist, verify that the staged tree still matches the recorded tree ID, then commit to the starting branch under the launch authorization. Otherwise, proceed to **Retire reviewer** without creating an empty commit.

If the commit command fails, including hook rejection, stop. Inspect and report HEAD, the index, and working tree so the user knows whether a commit was created and what remains uncommitted. Do not repair, retry the commit, or bypass hooks.

### Verify commit

Require a clean working tree and a new commit whose sole parent is the expected local HEAD and whose changes are all intended. Compare its tree ID (`git rev-parse 'HEAD^{tree}'`) with the recorded staged tree ID:

- If they match, the recorded check results apply.
- If they differ, verify that hooks caused the differences and that they remain within the intended fix, then rerun all checks against the new commit unless the no-checks exception applies.

Stop if any requirement cannot be verified, or if post-commit checks fail or change content. Do not repair or retry failed verification. Advance the expected local HEAD only after verification succeeds.

### Retire reviewer

Stop the reviewer if it is still running, then close it using the supported lifecycle mechanism. If no close operation exists, consider the reviewer retired and never reuse or resume it for another pass.

### Count clean passes

Increment the consecutive-clean count only if the pass's non-clean flag is false and checks pass (or the recorded no-checks exception applies). Otherwise mark the pass non-clean.

Apply **Completion and limits** to decide whether to finish or return to **Launch reviewer**.

## Completion and limits

- When the consecutive-clean count reaches two, apply the run invariants and perform an **upstream refresh**. Also verify that both passes reviewed the same unchanged commit and the working tree is clean. Stop successfully only if all conditions hold; otherwise stop as blocked. Local fix commits awaiting a human push are compatible with success.
- If success has not been achieved by the end of pass 10, stop. Otherwise start the next pass.

## After a blocked run

A blocked run cannot resume. The user must resolve the blocker, handle remaining changes, and synchronize the branch with its GitHub upstream before explicitly launching a new authorized run. Repeat preparation with fresh counters and Git state; never push or discard changes to prepare a restart.

## Final report

Include:

- Outcome: completed or blocked, with the blocker if applicable.
- Starting branch, recorded upstream, and final commit. Report Git values only when established; mark unavailable or unverified values explicitly and explain why, including when preparation stopped early.
- Fixes, checks and their results, review coverage, and remaining limitations.
- Total review passes and consecutive clean passes.
- Confirmation that the loop did not push, known local commits awaiting a human push, and any uncommitted changes.
- Whether HEAD matches, is ahead, is behind, or has diverged from the upstream, when local HEAD and a refreshed upstream are both verified.

Do not claim that the repository is guaranteed bug-free.
