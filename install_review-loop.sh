#!/usr/bin/env bash

set -e

# Codex
rm -rf "$HOME/.agents/skills/review-loop"
mkdir -p "$HOME/.agents/skills" && cp -a -- ./review-loop "$HOME/.agents/skills/"

# Claude Code
rm -rf "$HOME/.claude/skills/review-loop"
mkdir -p "$HOME/.claude/skills" && cp -a -- ./review-loop "$HOME/.claude/skills/"

# Claude Code uses a frontmatter flag; Codex uses agents/openai.yaml.
{
    printf '%s\n' '---' 'disable-model-invocation: true'
    tail -n +2 ./review-loop/SKILL.md
} > "$HOME/.claude/skills/review-loop/SKILL.md"
