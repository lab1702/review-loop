---
name: review-loop
description: Run repeated independent whole-repository reviews with verified fixes, required checks, and explicitly authorized commits to the starting branch and upstream pushes. Use only when explicitly invoked to run this review loop.
disable-model-invocation: true
---

# Review Loop

Run repeated whole-repository code reviews, fix verified issues, run checks, commit to the branch checked out at launch, and push to its existing GitHub upstream. Finish after TWO consecutive independent reviews of the same unchanged commit find no actionable issues or material coverage gaps and all required checks pass.

You are the coordinator and fixer. Use the app's built-in subagents for independent reviews. This skill is explicit-invocation-only.

## Launch authorization

Before starting the loop, verify that the user has explicitly authorized this run to make ordinary commits to the branch checked out at launch and push to its existing GitHub upstream. Invoking this skill alone is not authorization, and these stored instructions do not grant authorization. Authorization may be supplied in the launch prompt or a follow-up for this run. If either authorization is absent or ambiguous, request it before starting the loop; resume only after it is supplied.

An acceptable authorization in the user's launch prompt is: "I authorize ordinary commits to the current branch and pushes to its existing upstream." Once provided for this run, do not request redundant confirmation for each authorized commit or push. Respect required platform approvals.

Do not force-push, rewrite history, bypass branch protection, change remotes, or include unrelated work.

## First, check capabilities

- Verify that you can launch a NEW reviewer subagent for each pass without inheriting the coordinator's conversation or any previous reviewer conversations.
- Use an actual fresh-context mechanism supported and documented by the available tools. For example, use `collaboration.spawn_agent` with `fork_turns: "none"` only when the current tool documentation verifies that this omits surrounding conversation history. In other hosts, use the equivalent fresh-context mechanism only if the available tool documentation establishes its isolation. Do not assume a tool name, subagent type, or default spawning behavior provides isolation.
- Telling an existing agent to "ignore previous context" does not count. A separate task or thread does not necessarily have cleared context.
- If genuinely fresh reviewer context cannot be provided or verified, stop before editing and explain the limitation. Never substitute an unverified reviewer or claim independence without evidence.
- Do not install or invoke a separate Codex or Claude Code CLI for this workflow.

## Preparation

- Follow AGENTS.md, CLAUDE.md, and the repository's instructions.
- Record the currently checked-out branch as the starting branch and record its configured GitHub upstream (remote, remote URL, and destination branch). Any branch, including main, is supported. Stop if HEAD is detached, the working tree is not clean, or the branch has no verifiable existing GitHub upstream. Refresh the remote state using the existing configuration and verify that the starting branch and upstream resolve to exactly the same commit; do not rely on a stale remote-tracking reference. Stop on a mismatch. The user manages branches: never create or switch branches, discard work, or change upstream configuration to make the preconditions pass.
- Keep the starting branch and recorded upstream fixed for the entire run. Before each review, before editing, committing, or pushing, and at completion, verify that the same branch is still checked out and its upstream configuration is unchanged. If either changes, stop as blocked without switching back or continuing on the newly checked-out branch.
- Record the starting commit as the expected local HEAD and the expected upstream commit. Before each review, before editing, committing, or pushing, and at completion, verify local HEAD against the expected local HEAD. Advance that expectation only after this loop creates a commit. On remote refreshes before a push, compare the upstream against the expected upstream commit. The post-push refresh must instead match the exact commit just pushed; only then advance the expected upstream commit. Stop on unexpected commits or unrelated working-tree changes; do not merge, rebase, reset, or adopt outside changes to continue.
- Identify the required test, lint, type-check, and build commands from applicable project requirements. If none are specified, select relevant available checks and state their scope; do not invent mandatory commands. If no runnable checks exist, disclose that limitation rather than claim tests passed.
- Track the number of review passes, the consecutive clean-review count, and the commit reviewed in each pass. Start both counters at zero. Keep coordinator findings, fix explanations, and review logs out of reviewer prompts and out of the committed codebase.

## For each review pass

1. Increment the pass count and record the current commit. Launch a NEW, read-only reviewer with verified fresh conversation context. Provide only the repository location, current commit, review instructions, and applicable project requirements. Do not provide prior findings, fix explanations, review logs, or conversation history. Instruct the reviewer to inspect committed files at that exact commit, not an uncommitted working-tree snapshot. The reviewer must not consult earlier review artifacts, modify files, switch or create branches, change commits, or alter remote state.
2. Ask the reviewer to audit the WHOLE current codebase at that commit, including committed source, tests, configuration, and scripts. Do not limit the review to a Git diff or recent changes.
3. Require concrete, actionable findings with file/line references, triggering scenarios, and impact. Require a statement of coverage and anything the reviewer could not inspect. Do not request cosmetic changes or speculative refactoring.
4. Wait for the reviewer to finish before editing. Validate each finding against the reviewed commit. Record why any finding is rejected; a rejected finding alone does not prevent a clean pass. Fix genuine issues and add regression tests where appropriate. Do not weaken tests or checks. Stop as blocked on unresolved findings or decisions requiring the user's input.
5. Run all required checks, including on passes with no fixes. When fixes pass, verify that only intended changes are included, commit them to the starting branch, and push normally to its recorded GitHub upstream under the launch authorization. Verify that the effective push URL matches the recorded GitHub repository. Explicitly target only the recorded remote and destination branch when pushing; do not rely on push defaults that could update another branch. Refresh and recheck the upstream before committing or pushing and stop on unexpected remote changes. Do not create empty commits for clean passes. After pushing, refresh the upstream and verify that it equals the commit this loop pushed, then update the expected upstream commit. A failed or unverifiable push is blocked; preserve and report any local unpushed commit.
6. Close the finished reviewer using the supported lifecycle mechanism. If no close operation exists, retire the completed reviewer and never reuse or resume it for another pass. Start a NEW reviewer with verified fresh conversation context for every subsequent pass; do not include earlier review results.

## Completion and limits

- Reset the clean-review counter after any code change, including changes to tests, configuration, or scripts. A change to the reviewed commit also invalidates the consecutive-clean sequence.
- Count a clean pass only when an independent review completes with no actionable findings remaining after validation, no material coverage gaps, and all required checks passing for the same unchanged commit. Increment the consecutive-clean counter by one for each such pass. A pass that produces fixes is not clean; the resulting commit must be reviewed again.
- Errors, missing output, incomplete reviews, and failing or unavailable required checks are not clean passes. Reset the consecutive-clean count on a non-clean pass. For a reviewer error or material coverage gap, a fresh reviewer may retry within the 10-pass limit; every attempted review counts as a pass. If the gap cannot be addressed with available capabilities, stop as blocked. Fix check failures caused by a verified repository issue and rerun the checks; stop if required checks remain failing or unavailable.
- Stop successfully after two consecutive clean passes on the same unchanged commit, with a clean working tree and local HEAD matching the refreshed GitHub upstream.
- Run at most 10 review passes. If success has not been achieved by the end of pass 10, stop as blocked. Stop earlier on unresolved findings, unavailable permissions, unexpected remote changes, or decisions requiring the user's input. Do not continue retrying beyond these limits.
- Preserve the safety guardrails throughout the loop: no force-push, history rewriting, branch-protection bypass, remote changes, unrelated work, or weakened tests/checks.

## Final report

Report the starting branch and its recorded upstream, final commit, fixes, checks and their results, review coverage, pass count and consecutive clean passes, remaining limitations, and whether the goal completed or was blocked. State whether local HEAD matches the verified GitHub upstream; if blocked, explain the blocker and any local or unpushed changes. Do not claim that the repository is guaranteed bug-free.
