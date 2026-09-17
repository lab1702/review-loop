#!/usr/bin/env bash

set -e

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
skill_source="$script_dir/review-loop"

# Resolve existing ancestors too, so symlinked destination parents cannot
# conceal a source/destination overlap. No directories are created here.
canonical_directory() {
    local path="$1" suffix=""
    while [[ ! -d "$path" ]]; do
        if [[ -e "$path" || -L "$path" ]]; then
            printf 'Not an accessible directory: %s\n' "$path" >&2
            return 1
        fi
        suffix="/$(basename -- "$path")$suffix"
        path="$(dirname -- "$path")"
    done
    (CDPATH= cd -- "$path" && printf '%s%s\n' "$(pwd -P)" "$suffix")
}

overlaps() {
    [[ "$1" == "$2" || "$1" == "${2%/}/"* || "$2" == "${1%/}/"* ]]
}

for required_file in "$skill_source/SKILL.md" "$skill_source/agents/openai.yaml"; do
    if [[ ! -f "$required_file" || ! -r "$required_file" ]]; then
        printf 'Missing or unreadable skill file: %s\n' "$required_file" >&2
        exit 1
    fi
done

skill_source="$(canonical_directory "$skill_source")"
targets=("$HOME/.agents/skills/review-loop" "$HOME/.claude/skills/review-loop")
resolved_targets=()
for target in "${targets[@]}"; do
    resolved="$(canonical_directory "$target")"
    if overlaps "$skill_source" "$resolved"; then
        printf 'Source and destination overlap: %s\n' "$target" >&2
        exit 1
    fi
    resolved_targets+=("$resolved")
done
if overlaps "${resolved_targets[0]}" "${resolved_targets[1]}"; then
    printf 'Installation destinations overlap.\n' >&2
    exit 1
fi

stages=()
locks=()
installing=0
cleanup() {
    local status=$? i stage target lock
    trap - EXIT
    for ((i=${#stages[@]}-1; i>=0; i--)); do
        stage="${stages[i]}"
        target="${targets[i]}"
        if [[ $status -ne 0 && $installing -eq 1 ]]; then
            # A missing staged directory means it was moved into place.
            if [[ ! -e "$stage/new" ]] && ! rm -rf -- "$target"; then
                printf 'Rollback failed; recovery files retained at %s\n' "$stage" >&2
                continue
            fi
            if [[ -e "$stage/previous" || -L "$stage/previous" ]]; then
                if ! mv -- "$stage/previous" "$target"; then
                    printf 'Rollback failed; previous installation retained at %s\n' "$stage/previous" >&2
                    continue
                fi
            fi
        fi
        rm -rf -- "$stage" || printf 'Could not remove temporary directory: %s\n' "$stage" >&2
    done
    for lock in "${locks[@]}"; do
        rm -f -- "$lock" || printf 'Could not remove installation lock: %s\n' "$lock" >&2
    done
    exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Exclusive file creation is shared with the PowerShell installer. Acquire both
# locks before preparing either copy, and retain them through cleanup/rollback.
for target in "${targets[@]}"; do
    skills_dir="$(dirname -- "$target")"
    mkdir -p -- "$skills_dir"
    lock="$skills_dir/.review-loop-install.lock"
    if ! (set -o noclobber; : > "$lock") 2>/dev/null; then
        printf 'Cannot acquire installation lock: %s. Another installer may be running.\n' "$lock" >&2
        exit 1
    fi
    locks+=("$lock")
done

# Prepare both complete copies on their destination filesystems before any swap.
for i in 0 1; do
    skills_dir="$(dirname -- "${targets[i]}")"
    mkdir -p -- "$skills_dir"
    stage="$(mktemp -d "$skills_dir/.review-loop-install.XXXXXX")"
    stages+=("$stage")
    cp -a -- "$skill_source" "$stage/new"
    if [[ $i -eq 1 ]]; then
        {
            printf '%s\n' '---' 'disable-model-invocation: true'
            tail -n +2 "$stage/new/SKILL.md"
        } > "$stage/claude-skill.md"
        mv -- "$stage/claude-skill.md" "$stage/new/SKILL.md"
    fi
    for required_file in "$stage/new/SKILL.md" "$stage/new/agents/openai.yaml"; do
        [[ -f "$required_file" && -r "$required_file" ]] || exit 1
    done
done

installing=1
for i in 0 1; do
    target="${targets[i]}"
    stage="${stages[i]}"
    if [[ -e "$target" || -L "$target" ]]; then
        mv -- "$target" "$stage/previous"
    fi
    mv -- "$stage/new" "$target"
done
