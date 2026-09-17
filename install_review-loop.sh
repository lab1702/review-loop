#!/usr/bin/env bash

set -e

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
skill_source="$script_dir/review-loop"

for required_file in "$skill_source/SKILL.md" "$skill_source/agents/openai.yaml"; do
    if [[ ! -f "$required_file" || ! -r "$required_file" ]]; then
        printf 'Missing or unreadable skill file: %s\n' "$required_file" >&2
        exit 1
    fi
done

# Codex
rm -rf "$HOME/.agents/skills/review-loop"
mkdir -p "$HOME/.agents/skills"
cp -a -- "$skill_source" "$HOME/.agents/skills/"

# Claude Code
rm -rf "$HOME/.claude/skills/review-loop"
mkdir -p "$HOME/.claude/skills"
cp -a -- "$skill_source" "$HOME/.claude/skills/"

# Claude Code uses a frontmatter flag; Codex uses agents/openai.yaml.
{
    printf '%s\n' '---' 'disable-model-invocation: true'
    tail -n +2 "$skill_source/SKILL.md"
} > "$HOME/.claude/skills/review-loop/SKILL.md"
