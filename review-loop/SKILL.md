---
name: review-loop
description: Run independent whole-repository reviews with verified fixes, checks, and authorized local commits. Use only when explicitly invoked to run this review loop.
---

# Review Loop

Use the host's built-in subagents with fresh conversation contexts to review the whole repository. The coordinator validates findings, fixes verified issues, runs checks, and commits fixes locally to the starting branch. Finish after two consecutive clean reviews of the same unchanged commit, within 10 attempted passes.

## Launch authorization

Require explicit authorization for ordinary commits, for example: "I authorize ordinary commits to the current branch." Invoking the skill alone is insufficient. If authorization is absent or ambiguous, request it and wait before starting. Authorization covers all ordinary commits in this run; do not reconfirm each commit. Respect required platform approvals.

Throughout the run, do not push, rewrite history, bypass branch protection, modify remote configuration or remote branches, include unrelated work, or weaken tests/checks. Fetching to refresh remote-tracking references is permitted.

## Capabilities

- Verify a documented mechanism for launching reviewers without inheriting the coordinator's or previous reviewers' conversations, such as `collaboration.spawn_agent` with `fork_turns: "none"` when supported. Isolation here means a fresh conversation context, not a separate filesystem. A separate task or an instruction to "ignore previous context" is insufficient evidence. Stop if context isolation cannot be verified.
- Do not install or invoke a separate Codex or Claude Code CLI for this workflow.

## Preparation

### Starting-state requirements

- Follow AGENTS.md, CLAUDE.md, and the repository's instructions.
- Stop if HEAD is detached, the working tree is not clean, or the branch has no configured upstream.
- Record the checked-out branch as the **starting branch** and its configured upstream (remote, remote URL, and destination branch). Any branch, including main, is supported.
- Establish that the remote identifies a GitHub.com or GitHub Enterprise repository, resolving SSH aliases and URL rewrites. For Enterprise, use project documentation or authenticated host metadata; a suggestive hostname alone is insufficient. Stop if the host or repository identity cannot be established.
- Perform an **upstream refresh**: verify the destination branch with a live remote query or fetch, refresh its remote-tracking reference using the existing configuration, and confirm both identify the same commit. Stop if the branch is missing, access fails, or the commits differ; a cached reference alone is insufficient.
- Require the starting branch to match the refreshed upstream commit. Record it as both the **expected local HEAD** and the **expected upstream commit**. The expected upstream commit stays fixed throughout the run; local fix commits may put HEAD ahead of it.
- The user manages branches: never create or switch branches, discard work, or change upstream configuration to make the preconditions pass.
- Identify required test, lint, type-check, and build commands. If none are specified, select relevant available checks and state their scope. **Checks** means this set of commands; a required or selected check that cannot run is a blocker.
- If no checks are required and no relevant runnable checks exist, record the **no-checks exception**: reviews alone may establish success.
- Initialize the review-pass and consecutive-clean counters to zero.
- Keep coordinator findings, fix explanations, and review logs out of the committed codebase.

### Invariants during the run

- Before each review, before editing or committing, and at completion, verify that the starting branch is checked out, its upstream configuration is unchanged, and HEAD matches the expected local HEAD. Only **Verify commit** may advance the expected local HEAD.
- After preparation, every **upstream refresh** must match the fixed expected upstream commit.
- On any mismatch or unrelated working-tree change, stop. Do not switch back, merge, rebase, reset, or adopt outside changes to continue.

## Reviewer prompt

Give each reviewer only the prompt below with its placeholders filled in. Summarize user requirements without relying on conversation history; use "None specified" if there are none. Exclude prior findings, fix explanations, this skill, and coordinator instructions.

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
submodules at their recorded commits when available. You may omit detailed
inspection of generated or vendored content when reviewing its maintained
inputs or integration is sufficient.

Use only static, read-only inspection commands. Do not execute tests,
builds, or repository scripts; the coordinator runs checks. Do not consult
earlier review artifacts, modify files, switch or create branches, change
commits, or alter remote state.

Report concrete, actionable findings with file/line references, triggering
scenarios, and impact. Do not request cosmetic changes or speculative
refactoring. If you find no actionable issues, say so explicitly.

State what you reviewed. For each excluded or unavailable category or path,
give the reason and any residual coverage gap with its potential impact.
A material coverage gap is an unreviewed component or behavior that could
materially affect correctness or security. The coordinator assesses these
gaps before accepting the review.
```

## Check execution rules

A **check run** is either the full suite defined during preparation or a single targeted check. A targeted check cannot replace the full suite.

For every check command, compare repository status and content before and after, regardless of exit status. Inspect every tracked-file change and new non-ignored file. Accept only changes justified by the intended fix; stop on unrelated or unexplained changes.

Two independent limits apply across all pre-commit checks in a pass, including targeted checks. Neither resets between phases or repairs:

- **Failure repairs: at most two attempts.** After a failed check run, repair a verified repository issue or stop. Each attempt consists of evidence-backed repair edits followed directly by a full-suite run. The initial failed run consumes no attempt. Stop if checks fail with no attempts remaining.
- **Changes made by checks: one stabilization rerun.** After the first check run that makes justified content changes, the next run must be a full suite against the resulting content. Multiple commands may change content within that initial run. Stop if any command in the stabilization rerun or a later run changes content again.

If a run both fails and changes files, inspect the changes and repair within the remaining allowance. The next full-suite run serves as both repair verification and stabilization; stabilization alone consumes no repair attempt. Post-commit checks follow **Verify commit**.

## For each review pass

Follow these phases in order unless a phase directs otherwise.

A **non-clean** pass resets the consecutive-clean count to zero and cannot become clean again. Any change to reviewed content, even if later reverted, makes the pass non-clean.

### Launch reviewer

Increment the pass count, record the current commit, and mark the pass provisionally clean. Launch a new reviewer using the verified isolation mechanism and **Reviewer prompt**. Failed launches and incomplete reviews still consume a pass.

### Assess review

Wait for the reviewer to finish before editing. Accept only complete output with no execution errors or material coverage gaps, as defined in the prompt.

Otherwise, mark the pass non-clean and follow **Retire reviewer** without editing or committing. If available capabilities can address the problem, apply **Completion and limits** to decide whether another pass is allowed; otherwise stop.

### Validate and fix findings

Validate each finding against the reviewed commit. Record why any finding is rejected; rejection alone does not prevent a clean pass. For verified findings, mark the pass non-clean, fix them, and add regression tests where appropriate. Targeted checks follow **Check execution rules**.

Resolve all verified findings before proceeding. Use user instructions and repository guidance for routine decisions. Stop and identify the input needed for missing requirements, additional authorization, or a consequential choice that cannot be inferred. Finding fixes have no separate attempt limit, but stop if no evidence-backed next step remains, attempts repeat without progress, or a finding cannot be resolved within scope.

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

Increment the consecutive-clean count if the pass remains clean and checks pass (or the no-checks exception applies). A non-clean pass leaves the count at zero.

Apply **Completion and limits** to decide whether to finish or return to **Launch reviewer**.

## Completion and limits

- When the consecutive-clean count reaches two, apply the run invariants and perform an **upstream refresh**. Verify that both passes reviewed the same unchanged commit and the working tree is clean. Finish successfully only if all conditions hold; otherwise stop. Local fix commits awaiting a human push are compatible with success.
- If success has not been achieved by the end of pass 10, stop. Otherwise start the next pass.

Any stop other than successful completion ends the run as **blocked**; do not start another pass to bypass it. On every exit, follow **Retire reviewer** for any reviewer not yet retired, preserve local commits and uncommitted changes, and produce the **Final report**.

A blocked run cannot resume. The user must resolve the blocker, handle remaining changes, and synchronize the branch with its GitHub upstream before explicitly launching a new authorized run. Repeat preparation with fresh counters and Git state.

## Final report

Include:

- Outcome: completed or blocked. If blocked, explain the blocker and what must be resolved before a new run.
- Starting branch, recorded upstream, and final commit. Mark unavailable or unverified Git values explicitly and explain why.
- Fixes, checks and their results (or the no-checks exception), review coverage, and remaining limitations.
- Total review passes and consecutive clean passes.
- Confirmation that the loop did not push, known local commits awaiting a human push, and any uncommitted changes.
- Whether HEAD matches, is ahead, is behind, or has diverged from the upstream, when local HEAD and a refreshed upstream are both verified.

Do not claim that the repository is guaranteed bug-free.
