# Codex and Claude Code
$skillsDirs = @(
    (Join-Path $HOME '.agents\skills'),
    (Join-Path $HOME '.claude\skills')
)

foreach ($skillsDir in $skillsDirs) {
    $targetDir = Join-Path $skillsDir 'review-loop'

    if (Test-Path -LiteralPath $targetDir) {
        Remove-Item -LiteralPath $targetDir -Recurse -Force -ErrorAction Stop
    }

    New-Item -ItemType Directory -Path $skillsDir -Force -ErrorAction Stop | Out-Null
    Copy-Item -LiteralPath '.\review-loop' -Destination $skillsDir -Recurse -Force -ErrorAction Stop
}

# Claude Code uses a frontmatter flag; Codex uses agents/openai.yaml.
$claudeSkillPath = Join-Path $HOME '.claude\skills\review-loop\SKILL.md'
$skillContent = Get-Content -LiteralPath '.\review-loop\SKILL.md' -Raw -Encoding UTF8 -ErrorAction Stop
$claudeSkillContent = $skillContent -replace '\A---\r?\n', "---`ndisable-model-invocation: true`n"
[System.IO.File]::WriteAllText($claudeSkillPath, $claudeSkillContent, [System.Text.UTF8Encoding]::new($false))
