---
name: review-loop
description: Run repeated independent whole-repository reviews with verified fixes, required checks, and explicitly authorized commits to main and upstream pushes. Use only when explicitly invoked to run this review loop.
---

# Review Loop

Run repeated whole-repository code reviews, fix verified issues, run checks, commit to main, and push to GitHub. Finish after TWO consecutive independent reviews of the same unchanged commit find no actionable issues or material coverage gaps and all required checks pass.

You are the coordinator and fixer. Use the app's built-in subagents for independent reviews. This skill is explicit-invocation-only.

## Launch authorization

Before starting the loop, verify that the user's launch prompt explicitly authorizes ordinary commits to main and pushes to its existing GitHub upstream. Invoking this skill alone is not authorization, and these stored instructions do not grant authorization. If either authorization is absent or ambiguous, stop as blocked and request the missing authorization before editing, committing, or pushing.

An acceptable authorization in the user's launch prompt is: "I authorize ordinary commits to main and pushes to its existing upstream." Once provided for this run, do not request redundant confirmation for each authorized commit or push. Respect required platform approvals.

Do not force-push, rewrite history, bypass branch protection, change remotes, or include unrelated work.

## First, check capabilities

- Verify that you can launch a NEW reviewer subagent for each pass without inheriting the coordinator's conversation or any previous reviewer conversations.
- Use an actual fresh-context mechanism supported and documented by the available tools. For example, use `collaboration.spawn_agent` with `fork_turns: "none"` only when the current tool documentation verifies that this omits surrounding conversation history. Do not assume default spawning provides isolation.
- Telling an existing agent to "ignore previous context" does not count. A separate task or thread does not necessarily have cleared context.
- If genuinely fresh reviewer context cannot be provided or verified, stop before editing and explain the limitation. Never substitute an unverified reviewer or claim independence without evidence.
- Do not install or invoke a separate Codex CLI for this workflow.

## Preparation

- Follow AGENTS.md and the repository's instructions.
- Verify that the current branch is main, the working tree is clean, and main matches its configured GitHub upstream. Refresh the remote state using the existing configuration before comparing commits; do not rely on a stale remote-tracking reference. Stop on a mismatch or if the upstream cannot be verified. Do not switch branches, discard work, or change upstream configuration to make the preconditions pass.
- Identify the required test, lint, type-check, and build commands from applicable project requirements.
- Track the number of review passes, the consecutive clean-review count, and the commit reviewed in each pass. Start both counters at zero. Keep coordinator findings, fix explanations, and review logs out of reviewer prompts and out of the committed codebase.

## For each review pass

1. Increment the pass count and record the current commit. Launch a NEW, read-only reviewer with verified fresh conversation context. Provide only the repository location, current commit, review instructions, and applicable project requirements. Do not provide prior findings, fix explanations, review logs, or conversation history. Instruct the reviewer not to consult earlier review artifacts or modify files, commits, or remote state.
2. Ask the reviewer to audit the WHOLE current codebase at that commit, including committed source, tests, configuration, and scripts. Do not limit the review to a Git diff or recent changes.
3. Require concrete, actionable findings with file/line references, triggering scenarios, and impact. Require a statement of coverage and anything the reviewer could not inspect. Do not request cosmetic changes or speculative refactoring.
4. Wait for the reviewer to finish before editing. Validate each finding against the current code, fix genuine issues, and add regression tests where appropriate. Do not weaken tests or checks. Stop as blocked on unresolved findings or decisions requiring the user's input.
5. Run all required checks, including on passes with no fixes. When fixes pass, verify that only intended changes are included, commit them to main, and push normally to its existing GitHub upstream under the launch authorization. Recheck the upstream before committing or pushing and stop on unexpected remote changes. Do not create empty commits for clean passes. Verify a successful push by checking that local HEAD matches the refreshed upstream.
6. Close the finished reviewer using the supported lifecycle mechanism. If no close operation exists, retire the completed reviewer and never reuse or resume it for another pass. Start a NEW reviewer with verified fresh conversation context for every subsequent pass; do not include earlier review results.

## Completion and limits

- Reset the clean-review counter after any code change, including changes to tests, configuration, or scripts. A change to the reviewed commit also invalidates the consecutive-clean sequence.
- Count a clean pass only when an independent review completes with no actionable findings or material coverage gaps and all required checks pass for the same unchanged commit. A pass that produces fixes is not clean; the resulting commit must be reviewed again.
- Errors, missing output, incomplete reviews, and failing or unavailable required checks are not clean passes. Reset the consecutive-clean count on a non-clean pass.
- Stop successfully after two consecutive clean passes on the same unchanged commit, with a clean working tree and local HEAD matching the refreshed GitHub upstream.
- Run at most 10 review passes. If success has not been achieved by the end of pass 10, stop as blocked. Stop earlier on unresolved findings, unavailable permissions, unexpected remote changes, or decisions requiring the user's input. Do not continue retrying beyond these limits.
- Preserve the safety guardrails throughout the loop: no force-push, history rewriting, branch-protection bypass, remote changes, unrelated work, or weakened tests/checks.

## Final report

Report the final commit, fixes, checks and their results, review coverage, pass count and consecutive clean passes, remaining limitations, and whether the goal completed or was blocked. State whether local HEAD matches the verified GitHub upstream; if blocked, explain the blocker and any local or unpushed changes. Do not claim that the repository is guaranteed bug-free.
